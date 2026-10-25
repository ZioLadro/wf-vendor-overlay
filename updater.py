"""Self-update from the project's GitHub releases (Windows exe build).

Flow: ask GitHub for the latest release -> if newer, download WFVendorOverlay-windows.zip -> check its SHA-256
against the .sha256 file of the same release -> unpack to a staging folder -> a small batch file waits for this
program to exit, copies the files over the installation and starts the new version.
Your data (settings, prices, inventory) lives in %LOCALAPPDATA%\\WFVendorOverlay and is never touched.
Only the program itself is replaced, and only after the user agrees. Nothing is installed when running from source."""
import hashlib
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import requests

from config import APP_DIR
from version import __version__

REPO = "ZioLadro/wf-vendor-overlay"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
ASSET = "WFVendorOverlay-windows.zip"
RELEASES_PAGE = f"https://github.com/{REPO}/releases"
ALLOWED_HOSTS = ("api.github.com", "github.com", "objects.githubusercontent.com",
                 "release-assets.githubusercontent.com")
UA = f"WFVendorOverlay/{__version__}"


class UpdateError(Exception):
    pass


def parse_version(s: str) -> tuple:
    nums = [int(x) for x in re.findall(r"\d+", str(s).lstrip("vV").split("-")[0])[:3]]
    return tuple(nums + [0] * (3 - len(nums)))


def is_newer(remote: str, local: str = __version__) -> bool:
    return parse_version(remote) > parse_version(local)


def can_install() -> bool:
    """Only the packaged Windows build updates itself; from source use git pull."""
    return bool(getattr(sys, "frozen", False)) and sys.platform == "win32"


def install_dir() -> Path:
    return Path(sys.executable).parent


def _check_url(url: str):
    u = urlparse(url)
    if u.scheme != "https" or u.hostname not in ALLOWED_HOSTS:
        raise UpdateError(f"unexpected download address: {u.hostname}")


def check(timeout: float = 15.0) -> dict:
    """Latest release: {"version","tag","notes","page","zip_url","sha_url","newer"}. Raises UpdateError."""
    try:
        r = requests.get(API, headers={"Accept": "application/vnd.github+json", "User-Agent": UA}, timeout=timeout)
    except requests.RequestException as e:
        raise UpdateError(f"network error: {type(e).__name__}")
    if r.status_code == 404:
        raise UpdateError("no release published yet")
    if r.status_code != 200:
        raise UpdateError(f"HTTP {r.status_code}")
    d = r.json()
    tag = str(d.get("tag_name") or "")
    assets = {a.get("name"): a.get("browser_download_url") for a in d.get("assets") or [] if isinstance(a, dict)}
    return {"version": tag.lstrip("vV"), "tag": tag, "notes": str(d.get("body") or "")[:1500],
            "page": d.get("html_url") or RELEASES_PAGE, "zip_url": assets.get(ASSET),
            "sha_url": assets.get(ASSET + ".sha256"), "newer": bool(tag) and is_newer(tag),
            "installable": bool(assets.get(ASSET) and assets.get(ASSET + ".sha256"))}


def download(info: dict, progress=None, cancelled=lambda: False) -> Path:
    """Downloads, verifies and unpacks the release. Returns the staging folder. Raises UpdateError."""
    if not info.get("zip_url") or not info.get("sha_url"):
        raise UpdateError("the release has no installable package (zip + .sha256)")
    _check_url(info["zip_url"])
    _check_url(info["sha_url"])
    try:
        want = requests.get(info["sha_url"], headers={"User-Agent": UA}, timeout=20).text.split()[0].lower()
    except (requests.RequestException, IndexError) as e:
        raise UpdateError(f"cannot read the checksum: {type(e).__name__}")
    if not re.fullmatch(r"[0-9a-f]{64}", want):
        raise UpdateError("the checksum file is not valid")
    work = Path(tempfile.mkdtemp(prefix="wfupdate_", dir=str(APP_DIR)))
    zpath, h = work / ASSET, hashlib.sha256()
    try:
        with requests.get(info["zip_url"], headers={"User-Agent": UA}, stream=True, timeout=30) as r:
            if r.status_code != 200:
                raise UpdateError(f"HTTP {r.status_code}")
            _check_url(r.url)
            total = int(r.headers.get("Content-Length") or 0)
            done = 0
            with open(zpath, "wb") as f:
                for chunk in r.iter_content(1 << 16):
                    if cancelled():
                        raise UpdateError("cancelled")
                    f.write(chunk)
                    h.update(chunk)
                    done += len(chunk)
                    if progress:
                        progress(done, total)
    except requests.RequestException as e:
        raise UpdateError(f"download failed: {type(e).__name__}")
    if h.hexdigest() != want:
        raise UpdateError("the downloaded file does not match its checksum: not installed")
    staging = work / "files"
    root = staging.resolve()
    try:
        with zipfile.ZipFile(zpath) as z:
            for m in z.namelist():
                if not str((staging / m).resolve()).startswith(str(root)):
                    raise UpdateError("the package contains an unsafe path: not installed")
            z.extractall(staging)
    except zipfile.BadZipFile:
        raise UpdateError("the package is not a valid zip")
    exe = next(staging.rglob("WFVendorOverlay.exe"), None)
    if exe is None:
        raise UpdateError("the package does not contain WFVendorOverlay.exe")
    return exe.parent


LOG_FILE = APP_DIR / "update.log"


def installer_script(staging: Path, dest: Path, pid: int, log: Path = LOG_FILE) -> str:
    """Batch file: waits for this program to exit, copies the new files over the installation, starts the new
    version. Every step is written to update.log, to see what happened if it does not work."""
    return f"""@echo off
chcp 65001 >nul
set "LOG={log}"
echo [%date% %time%] update started, waiting for process {pid} >> "%LOG%"
set n=0
:wait
tasklist /FI "PID eq {pid}" 2>nul | find "{pid}" >nul
if errorlevel 1 goto gone
ping -n 2 127.0.0.1 >nul
set /a n+=1
if %n% LSS 60 goto wait
echo [%time%] the program did not exit in time, trying anyway >> "%LOG%"
:gone
ping -n 3 127.0.0.1 >nul
echo [%time%] copying {staging} to {dest} >> "%LOG%"
set n=0
:copy
xcopy "{staging}\\*" "{dest}\\" /E /Y /Q /R >> "%LOG%" 2>&1
if not errorlevel 1 goto done
echo [%time%] copy failed, errorlevel %errorlevel%, attempt %n% >> "%LOG%"
ping -n 3 127.0.0.1 >nul
set /a n+=1
if %n% LSS 20 goto copy
echo [%time%] giving up: the old version is started again >> "%LOG%"
start "" "{dest}\\WFVendorOverlay.exe"
exit /b 1
:done
echo [%time%] copied, starting the new version >> "%LOG%"
start "" "{dest}\\WFVendorOverlay.exe"
rmdir /S /Q "{staging.parent}"
"""


def launch_installer(staging: Path):
    """Starts the batch file that replaces the files once this program has exited. The caller must quit."""
    bat = staging.parent / "install_update.bat"
    bat.write_text(installer_script(staging, install_dir(), os.getpid()), encoding="utf-8")
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"launching {bat} (install dir {install_dir()}, staging {staging})\n")
    except OSError:
        pass
    # PyInstaller: the new program must not think it is a child of this one (same reason as the Settings restart)
    env = dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1")
    no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    breakaway = 0x01000000                      # not killed with this program's job, if it has one
    for flags in (no_window | breakaway, no_window):
        try:
            subprocess.Popen(["cmd", "/c", str(bat)], creationflags=flags, env=env, close_fds=True)
            return
        except OSError:
            continue
    raise OSError("could not start the installer")
