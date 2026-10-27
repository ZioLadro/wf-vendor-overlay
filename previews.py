"""Small item pictures for tooltips (a preview when you hover an item).

The pictures are the ones warframe.market itself publishes for every item (static assets, documented at
https://warframe.market/static/assets/). They are downloaded one at a time, only for items you hover, kept in the
data folder and never downloaded twice; if the site cannot be reached the tooltips simply stay text-only.
This does not read AlecaFrame's own image files.
"""
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


def _file(slug):
    return DIR / (slug + ".png")


def _run():
    fails = 0
    while True:
        slug = _q.get()
        try:
            thumb = (_market.info(slug) or {}).get("thumb") if _market else ""
            if not thumb or _file(slug).exists():
                continue
            if fails >= 3:                                    # the site does not answer: stop trying for a while
                time.sleep(600)
                fails = 0
            from market import HEADERS
            r = requests.get(BASE + thumb.lstrip("/"), headers=HEADERS, timeout=10)
            if r.status_code == 200 and r.content[:4] == b"\x89PNG":
                DIR.mkdir(parents=True, exist_ok=True)
                _file(slug).write_bytes(r.content)
                fails = 0
            else:
                _failed[slug] = time.time()
                fails += 1 if r.status_code >= 500 or r.status_code == 429 else 0
        except Exception:
            _failed[slug] = time.time()
            fails += 1
        finally:
            _pending.discard(slug)
            time.sleep(GAP)


def path(slug):
    """File of the item's picture if it is already downloaded; otherwise asks for it (shown next time)."""
    global _worker
    if not CFG.get("item_previews", True) or not slug:
        return None
    f = _file(slug)
    if f.exists():
        return f
    if slug in _pending or time.time() - _failed.get(slug, 0) < 3600 or not _market:
        return None
    if not (_market.info(slug) or {}).get("thumb"):
        return None
    _pending.add(slug)
    if _worker is None:
        _worker = threading.Thread(target=_run, daemon=True)
        _worker.start()
    _q.put(slug)
    return None


def tooltip(slug, name, extra=""):
    f = path(slug)
    img = f'<br><img src="{f.as_posix()}" width="96">' if f else ""
    return f"<b>{name}</b>{img}" + (f"<br>{extra}" if extra else "")
