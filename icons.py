"""Optional icons from a folder of your own (Settings > assets folder): Archon Shard pictures in the Builds tab.

The folder is whatever you point to (for example the `assets` folder of an AlecaFrame installation, unpacked);
the program only reads from it and never copies or ships those files. Without the folder everything still works."""
import os
import re
import time
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap

from config import CFG

_cache = {}


MARKER = Path("archonShards")                      # a folder holding this (under img) is an icons folder
_auto = {"path": None, "when": 0.0}


def _valid(root) -> bool:
    try:
        return any((root / base / MARKER).is_dir() for base in ("img", "assets/img", ""))
    except OSError:
        return False


def _version_key(p: Path):
    """Sort key for Overwolf's version folders (1.2.10 after 1.2.9), newest last; the folder's date breaks ties."""
    nums = tuple(int(x) for x in re.findall(r"\d+", p.name)[:6])
    try:
        return (nums, p.stat().st_mtime)
    except OSError:
        return (nums, 0)


def find_assets() -> str:
    """Looks for an AlecaFrame icons folder by itself. Overwolf keeps each app in Extensions\\<app id>\\<version>\\ and moves
    to a new version folder with every update, so every version folder is searched and the newest one that has the pictures wins."""
    bases = []
    for var in ("LOCALAPPDATA", "APPDATA", "PROGRAMFILES(X86)", "PROGRAMFILES"):
        v = os.environ.get(var)
        if v:
            bases += [Path(v) / "Overwolf" / "Extensions", Path(v) / "Overwolf" / "Overwolf" / "Extensions", Path(v) / "AlecaFrame"]
    best, best_key = "", None
    for base in bases:
        try:
            if not base.is_dir():
                continue
            apps = [base] + [d for d in base.iterdir() if d.is_dir()]
            for app in apps:
                versions = [app] + [v for v in app.iterdir() if v.is_dir()]
                for ver in versions:
                    for sub in ("", "assets", "app", "app/assets", "Assets"):
                        root = ver / sub if sub else ver
                        if _valid(root):
                            key = _version_key(ver)
                            if best_key is None or key > best_key:
                                best, best_key = str(root), key
        except OSError:
            continue
    return best


def assets_in_use() -> str:
    """The icons folder in use: the one typed in Settings if it is valid, else (when allowed) the one found by itself."""
    d = str(CFG.get("assets_dir") or "").strip()
    if d and _valid(Path(d)):
        return d
    if not CFG.get("assets_auto", True):
        return d
    cur = _auto["path"]
    if cur and _valid(Path(cur)):                    # still there
        return cur
    if time.time() - _auto["when"] > 60:             # a new Overwolf version moved it: search again (at most once a minute)
        _auto["when"] = time.time()
        _auto["path"] = find_assets() or None
        _cache.clear()
    return _auto["path"] or d


def _root():
    d = assets_in_use()
    return Path(d) if d else None


def pixmap(rel: str, size: int = 0):
    """QPixmap of img/<rel> from the assets folder (None if not set or not found)."""
    root = _root()
    if not root:
        return None
    key = (str(root), rel, size)
    if len(_cache) > 500:                  # sizes change while the Builds cards are resized: keep the cache small
        _cache.clear()
    if key in _cache:
        return _cache[key]
    pm = None
    for base in (root / "img", root / "assets" / "img", root):
        f = base / rel
        if f.is_file():
            p = QPixmap(str(f))
            if not p.isNull():
                pm = p.scaledToHeight(size, Qt.TransformationMode.SmoothTransformation) if size else p
            break
    _cache[key] = pm
    return pm


def shard(color: str, tauforged: bool, size: int = 36):
    return pixmap(f"archonShards/{color.lower()}{'_mythic' if tauforged else ''}.webp", size)


ARCANE_PICTURE = {"C": "bronze", "U": "silver", "R": "gold", "L": "primed"}
WALLET_FILES = {"endo": "endo.png", "plat": "platinum.png", "ducats": "ducats.png", "aya": "aya.webp",
                "regal": "regalAya.webp", "credits": "credits.png"}


def arcane(name: str, height: int = 52):
    """The generic picture for an Arcane's rarity (bronze, silver, gold, primed) from the icons folder; None without it."""
    import loadouts
    rar = loadouts.data().get("arcrar", {}).get(name)
    return pixmap(f"arcanes/{ARCANE_PICTURE[rar]}.webp", height) if rar else None


def wallet(kind: str, height: int = 20):
    f = WALLET_FILES.get(kind)
    return pixmap(f, height) if f else None


POLARITY_COLORS = {"madurai": "#d9573b", "vazarin": "#3b8fd9", "naramon": "#e0b83a", "zenurik": "#8c5be0", "unairu": "#8a8f98",
                   "penjaga": "#3fbf6a", "umbra": "#b13b8c", "universal": "#aaaaaa"}


def polarity(name: str, size: int = 16):
    """The polarity symbol: the picture from the icons folder, else a small coloured badge with its initial."""
    if not name:
        return None
    pm = pixmap(f"polarities/{name}.png", size)
    if pm is not None:
        return pm
    key = ("pol", name, size)
    if key not in _cache:
        img = QPixmap(size, size)
        img.fill(Qt.GlobalColor.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(POLARITY_COLORS.get(name, "#888888")))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(0, 0, size - 1, size - 1)
        p.setPen(QColor("#101010"))
        f = QFont()
        f.setBold(True)
        f.setPixelSize(max(8, int(size * 0.62)))
        p.setFont(f)
        p.drawText(img.rect(), Qt.AlignmentFlag.AlignCenter, name[0].upper())
        p.end()
        _cache[key] = img
    return _cache[key]
