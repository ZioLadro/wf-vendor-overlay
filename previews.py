"""Small item pictures for tooltips (a preview when you hover an item).

The pictures are the ones warframe.market itself publishes for every item (static assets, documented at
https://warframe.market/static/assets/). They are downloaded one at a time, only for items you hover, kept in the
data folder and never downloaded twice; if the site cannot be reached the tooltips simply stay text-only.
If warframe.market has no picture for an item, the item's File: page on the Warframe wiki (wiki.warframe.com, the
standard MediaWiki API, one polite request at a time with this program's User-Agent) is tried instead.
This does not read AlecaFrame's own image files.
"""
import re
import queue
import threading
import time

import requests

from config import APP_DIR, CFG

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


def _file(key):
    return DIR / (re.sub(r"[^a-z0-9_.-]+", "_", key.lower()) + ".png")


def _save(r):
    if r.status_code == 200 and r.content[:4] == b"\x89PNG":
        return r.content
    return None


def _from_market(slug):
    thumb = (_market.info(slug) or {}).get("thumb") if _market and slug else ""
    if not thumb:
        return None
    from market import HEADERS
    return _save(requests.get(BASE + thumb.lstrip("/"), headers=HEADERS, timeout=10))


def _from_wiki(name):
    """The wiki's picture for the item (File:<name>.png), found through the MediaWiki API."""
    from market import HEADERS
    h = {"User-Agent": HEADERS["User-Agent"]}
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


def _run():
    fails = 0
    while True:
        key, slug, name = _q.get()
        try:
            if _file(key).exists():
                continue
            if fails >= 3:                                    # the sites do not answer: stop trying for a while
                time.sleep(600)
                fails = 0
            data = _from_market(slug)
            if data is None and name:
                data = _from_wiki(name)
            if data:
                DIR.mkdir(parents=True, exist_ok=True)
                _file(key).write_bytes(data)
                fails = 0
            else:
                _failed[key] = time.time()
        except Exception:
            _failed[key] = time.time()
            fails += 1
        finally:
            _pending.discard(key)
            time.sleep(GAP)


def pending() -> int:
    """Pictures still waiting to be downloaded."""
    return len(_pending)


def by_name(name, slug=None):
    """File of the picture of an item known by name (a mod or Arcane of a loadout, say); asks for it if missing."""
    global _worker
    if not CFG.get("item_previews", True) or not name:
        return None
    slug = slug or (_market.slug_for_name(name) if _market else None)
    key = slug or "wiki_" + name
    f = _file(key)
    if f.exists():
        return f
    if key in _pending or time.time() - _failed.get(key, 0) < 3600:
        return None
    _pending.add(key)
    if _worker is None:
        _worker = threading.Thread(target=_run, daemon=True)
        _worker.start()
    _q.put((key, slug, name))
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
