"""Syndicate logos for the player strip, taken from the Warframe wiki (wiki.warframe.com) when they are first needed.

For each syndicate the wiki article's main picture is asked for through the standard MediaWiki API (pageimages); if the
article has none, a picture of the article whose file name says Sigil / Icon / Logo / Symbol / Emblem is used. One polite
request at a time, with this program's User-Agent. The pictures are saved as PNG in the data folder (icons\\<tag>.png),
never downloaded twice; a syndicate whose logo was not found is asked again only after a day. Without them (or offline)
the strip keeps its drawn badges. Turned off together with item pictures (Settings > Item pictures in tooltips)."""
import json
import queue
import threading
import time

import requests

from config import APP_DIR, CFG

DIR = APP_DIR / "icons"
FAILED_FILE = DIR / "_not_found.json"
WIKI_API = "https://wiki.warframe.com/api.php"
RETRY = 24 * 3600
GAP = 0.6
PAGE = {"KahlSyndicate": "Kahl's Garrison", "PerrinSyndicate": "Perrin Sequence", "LibrarySyndicate": "Cephalon Simaris",
        "EntratiLabSyndicate": "Cavia", "ZarimanSyndicate": "The Holdfasts", "CetusSyndicate": "Ostron",
        "SolarisSyndicate": "Solaris United", "VoxSyndicate": "Vox Solaris", "VentKidsSyndicate": "Ventkids"}
WORDS = ("sigil", "icon", "logo", "symbol", "emblem", "insignia")

_q = queue.Queue()
_pending = set()
_worker = None
_lock = threading.Lock()
done_count = 0                 # grows at every logo saved: the strip redraws when it changes


def _failed() -> dict:
    try:
        return json.loads(FAILED_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _mark_failed(tag):
    with _lock:
        d = _failed()
        d[tag] = int(time.time())
        try:
            DIR.mkdir(parents=True, exist_ok=True)
            FAILED_FILE.write_text(json.dumps(d), encoding="utf-8")
        except OSError:
            pass


def _api(params):
    from market import HEADERS
    r = requests.get(WIKI_API, params=dict(params, action="query", format="json", redirects=1),
                     headers={"User-Agent": HEADERS["User-Agent"]}, timeout=10)
    r.raise_for_status()
    return r.json().get("query", {})


def _image_url(title: str):
    """URL of the logo picture of a wiki article, or None."""
    q = _api({"titles": title, "prop": "pageimages", "piprop": "thumbnail|original", "pithumbsize": 96})
    for page in (q.get("pages") or {}).values():
        if page.get("thumbnail", {}).get("source"):
            return page["thumbnail"]["source"]
        if page.get("original", {}).get("source"):
            return page["original"]["source"]
    time.sleep(GAP)
    q = _api({"titles": title, "prop": "images", "imlimit": 100})
    compact = title.replace(" ", "").replace("'", "").lower()
    files = []
    for page in (q.get("pages") or {}).values():
        files += [im["title"] for im in page.get("images") or [] if im.get("title")]
    cands = [f for f in files if any(w in f.lower() for w in WORDS) and not f.lower().endswith(".svg")]
    cands.sort(key=lambda f: (compact[:6] not in f.lower().replace(" ", "").replace("_", ""), len(f)))
    if not cands:
        return None
    time.sleep(GAP)
    q = _api({"titles": cands[0], "prop": "imageinfo", "iiprop": "url", "iiurlwidth": 96})
    for page in (q.get("pages") or {}).values():
        info = (page.get("imageinfo") or [{}])[0]
        return info.get("thumburl") or info.get("url")
    return None


def _fetch(tag, name):
    from PyQt6.QtGui import QImage
    from market import HEADERS
    url = _image_url(PAGE.get(tag, name))
    if not url:
        return False
    time.sleep(GAP)
    r = requests.get(url, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=10)
    if r.status_code != 200:
        return False
    img = QImage()
    if not img.loadFromData(r.content) or img.isNull():
        return False
    DIR.mkdir(parents=True, exist_ok=True)
    return img.save(str(DIR / f"{tag}.png"), "PNG")


def _run():
    global done_count
    while True:
        tag, name = _q.get()
        import logbus
        try:
            if _fetch(tag, name):
                done_count += 1
                logbus.add("logos", f"{name}: logo saved", "ok")
            else:
                _mark_failed(tag)
                logbus.add("logos", f"{name}: no logo found on the wiki (asked again in a day)", "warn")
        except Exception as e:
            _mark_failed(tag)
            logbus.error("logos", f"{name}: {type(e).__name__}: {e}")
        finally:
            _pending.discard(tag)
            time.sleep(GAP)


def want(tag: str, name: str):
    """The strip has no logo for this syndicate: asks the wiki for it in the background (once)."""
    global _worker
    if not CFG.get("item_previews", True) or tag in _pending or (DIR / f"{tag}.png").exists():
        return
    if time.time() - _failed().get(tag, 0) < RETRY:
        return
    _pending.add(tag)
    if _worker is None:
        _worker = threading.Thread(target=_run, daemon=True, name="wiki-logos")
        _worker.start()
    _q.put((tag, name))
