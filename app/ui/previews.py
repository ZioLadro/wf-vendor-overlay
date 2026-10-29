"""Small item pictures for tooltips (a preview when you hover an item).

The pictures are the ones warframe.market itself publishes for every item (static assets, documented at
https://warframe.market/static/assets/). They are downloaded one at a time, only for items you hover, kept in the
data folder and never downloaded twice; if the site cannot be reached the tooltips simply stay text-only.
If warframe.market has no picture for an item (and for the Builds tab's pictures, first of all), the WFCD image CDN is
tried: https://cdn.warframestat.us/img/<file>, the file named for that item in data/images.json (WFCD/warframe-items,
tools/build_images.py), one request per picture. Last, the item's File: page on the Warframe wiki (wiki.warframe.com,
the standard MediaWiki API, one polite request at a time with this program's User-Agent).
This does not read AlecaFrame's own image files.
"""
import re
import queue
import threading
import time

import requests

from app.core.config import APP_DIR, CFG

BASE = "https://warframe.market/static/assets/"
DIR = APP_DIR / "img"
GAP = 0.5            # seconds between two downloads (gentle with the site)

_market = None
_q = queue.Queue()
_pending, _failed = set(), {}
_worker = None


def set_market(market):
    global _market
    _market = market


WIKI_API = "https://wiki.warframe.com/api.php"
CDN = "https://cdn.warframestat.us/img/"
_images = None


def cdn_file(name):
    """The WFCD CDN's file for an item name (data/images.json), or None."""
    global _images
    if _images is None:
        try:
            import json
            from app.core.paths import DATA
            _images = json.loads((DATA / "images.json").read_text(encoding="utf-8")).get("images") or {}
        except Exception:
            _images = {}
    return _images.get(name) or _images.get(re.sub(r"\s*\(.*?\)\s*$", "", name or ""))


def _from_cdn(name):
    f = cdn_file(name)
    if not f:
        return None
    from app.trade.market import HEADERS
    return _save(requests.get(CDN + f, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=10))


def _file(key):
    return DIR / (re.sub(r"[^a-z0-9_.-]+", "_", key.lower()) + ".png")


def _save(r):
    """PNG bytes of a downloaded picture (other formats are converted), or None."""
    if r.status_code != 200 or not r.content:
        return None
    if r.content[:4] == b"\x89PNG":
        return r.content
    try:
        from PyQt6.QtCore import QBuffer, QByteArray, QIODevice
        from PyQt6.QtGui import QImage
        img = QImage()
        if not img.loadFromData(r.content) or img.isNull():
            return None
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        img.save(buf, "PNG")
        return bytes(ba)
    except Exception:
        return None


def _from_market(slug):
    thumb = (_market.info(slug) or {}).get("thumb") if _market and slug else ""
    if not thumb:
        return None
    from app.trade.market import HEADERS
    return _save(requests.get(BASE + thumb.lstrip("/"), headers=HEADERS, timeout=10))


def _from_wiki(name):
    """The wiki's picture for the item, through the MediaWiki API: the main picture of the item's article (pageimages:
    the mod card, the Warframe, the weapon), else the file File:<name>.png."""
    from app.trade.market import HEADERS
    h = {"User-Agent": HEADERS["User-Agent"]}
    r = requests.get(WIKI_API, params={"action": "query", "format": "json", "titles": name, "redirects": 1,
                                       "prop": "pageimages", "piprop": "thumbnail|original", "pithumbsize": 320},
                     headers=h, timeout=10)
    if r.status_code == 200:
        for page in (r.json().get("query", {}).get("pages") or {}).values():
            src = (page.get("thumbnail") or {}).get("source") or (page.get("original") or {}).get("source")
            if src:
                time.sleep(GAP)
                data = _save(requests.get(src, headers=h, timeout=10))
                if data:
                    return data
    time.sleep(GAP)
    title = "File:" + name.replace(" ", "_") + ".png"
    r = requests.get(WIKI_API, params={"action": "query", "format": "json", "titles": title, "prop": "imageinfo",
                                       "iiprop": "url"}, headers=h, timeout=10)
    if r.status_code != 200:
        return None
    for page in (r.json().get("query", {}).get("pages") or {}).values():
        info = (page.get("imageinfo") or [{}])[0]
        if info.get("url"):
            return _save(requests.get(info["url"], headers=h, timeout=10))
    return None


_cards_ok = set()                                     # card pictures already checked to be whole cards
_done = [0, 0]                                         # pictures saved, not found / failed (Console)


def _portrait(path) -> bool:
    """True when a picture is taller than wide (a whole mod card from the wiki; the CDN's mod art is wider)."""
    try:
        from PyQt6.QtGui import QImageReader
        s = QImageReader(str(path)).size()
        return s.height() > s.width() * 1.1
    except Exception:
        return True


def _is_mod(name) -> bool:
    try:
        from app.game import loadouts as LO
        return name in LO.data().get("mst", {})
    except Exception:
        return False


def _run():
    from app.core import logbus
    fails = 0
    while True:
        key, slug, name, mode = _q.get()
        try:
            if _file(key).exists():
                continue
            if fails >= 3:                                    # the sites do not answer: stop trying for a while
                logbus.add("pictures", "the sites do not answer: pausing the downloads for 10 minutes", "warn")
                time.sleep(600)
                fails = 0
            data, src = None, ""
            order = {"art": ("cdn", "wiki"), "card": ("wiki", "cdn")}.get(mode, ("market", "cdn", "wiki"))
            for how in order:
                if data is not None:
                    break
                if how == "market":
                    src, data = "warframe.market", _from_market(slug)
                elif how == "cdn" and name:
                    src, data = "cdn.warframestat.us", _from_cdn(name)
                elif how == "wiki" and name:
                    src, data = "wiki", _from_wiki(name)
            if data:
                DIR.mkdir(parents=True, exist_ok=True)
                _file(key).write_bytes(data)
                fails = 0
                _done[0] += 1
                logbus.add("pictures", f"{name or slug}: saved ({src})", "ok")
            else:
                _failed[key] = time.time()
                _done[1] += 1
                logbus.add("pictures", f"{name or slug}: no picture found", "warn")
        except Exception as e:
            _failed[key] = time.time()
            fails += 1
            _done[1] += 1
            logbus.error("pictures", f"{name or slug}: {type(e).__name__}: {e}")
        finally:
            _pending.discard(key)
            logbus.progress("pictures", _done[0] + _done[1], _done[0] + _done[1] + len(_pending),
                            f"{len(_pending)} waiting")
            time.sleep(GAP)


def prefetch(names):
    """Asks in the background for the wiki pictures of these names that are not on disk yet (Builds: at start)."""
    n = 0
    for name in dict.fromkeys(x for x in names if x):
        if by_name(name, wiki_only=True) is None:
            n += 1
    return n


def pending() -> int:
    """Pictures still waiting to be downloaded."""
    return len(_pending)


def by_name(name, slug=None, wiki_only=False, fetch=True, kind=None):
    """File of the picture of an item known by name (a mod or Arcane of a loadout, say); asks for it if missing.
    wiki_only: the picture of the Builds tab, kept apart from the market's (kind "card": the whole mod card from the
    wiki, for tooltips; kind "art": the mod's artwork from the WFCD CDN, inside the build's cards).
    fetch=False: only a picture already downloaded (the planner's mod library: hundreds of cards)."""
    global _worker
    if not CFG.get("item_previews", True) or not name:
        return None
    mode = "market"
    if wiki_only or kind:
        slug = None
        mode = kind or "card"
    else:
        slug = slug or (_market.slug_for_name(name) if _market else None)
    key = slug or ("art_" if mode == "art" else "wiki_") + name
    f = _file(key)
    if mode == "card" and key not in _cards_ok and f.exists() and _is_mod(name) and not _portrait(f):
        # 0.4.7-0.4.8 saved the CDN's artwork under the card's name: it becomes the artwork, the card is read again
        art = _file("art_" + name)
        try:
            if not art.exists():
                f.replace(art)
            else:
                f.unlink()
        except OSError:
            return f
    if f.exists():
        if mode == "card":
            _cards_ok.add(key)
        return f
    if not fetch:
        return None
    if key in _pending or time.time() - _failed.get(key, 0) < 3600:
        return None
    _pending.add(key)
    if _worker is None:
        _worker = threading.Thread(target=_run, daemon=True)
        _worker.start()
    _q.put((key, slug, name, mode))
    return None


def path(slug):
    """File of the item's picture if it is already downloaded; otherwise asks for it (shown next time)."""
    if not slug:
        return None
    info = _market.info(slug) if _market else {}
    return by_name((info or {}).get("name"), slug)


def tooltip(slug, name, extra=""):
    f = path(slug)
    img = f'<br><img src="{f.as_posix()}" width="96">' if f else ""
    return f"<b>{name}</b>{img}" + (f"<br>{extra}" if extra else "")
