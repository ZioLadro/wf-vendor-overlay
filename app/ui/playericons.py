"""The player's profile glyph (avatar) and Mastery Rank emblem for the player strip.

Which picture: data/player_icons.json (tools/build_player_icons.py): glyph item -> game icon path, rank -> emblem path.
The picture itself comes from browse.wf, which hosts the game's icons by their path (one request per picture, in the
background, with this program's User-Agent), and is kept in the data folder (img/player/…), never downloaded twice.
Turned off together with the item pictures (Settings > Item pictures in tooltips)."""
import json
import threading
import time

import requests

from app.core.config import APP_DIR, CFG
from app.core.paths import DATA

BASE = "https://browse.wf"
DIR = APP_DIR / "img" / "player"
_data = None
_lock = threading.Lock()
_pending, _failed = set(), {}
done_count = 0                         # grows when a picture arrives (the strip then redraws)


def _icons():
    global _data
    if _data is None:
        try:
            _data = json.loads((DATA / "player_icons.json").read_text(encoding="utf-8"))
        except Exception:
            _data = {"avatars": {}, "mastery": {}}
    return _data


def avatar_icon(glyph):
    return _icons()["avatars"].get(str(glyph or ""))


def mastery_icon(mr):
    if mr is None:
        return None
    m = _icons()["mastery"]
    return m.get(str(int(mr))) or (m.get(str(max(int(k) for k in m))) if m and int(mr) > 0 else None)


def currency(name: str):
    """{"name","path","icon"} of a currency / resource by name (data/player_icons.json), or None."""
    return (_icons().get("currencies") or {}).get(str(name or "").lower())


def currency_pixmap(name: str, height: int = 18):
    """The currency's icon (AlecaFrame's icons folder is not organised by name: the game icon, from browse.wf), or None
    until it is downloaded."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QPixmap
    c = currency(name)
    f = path_for(c["icon"]) if c and c.get("icon") else None
    pm = QPixmap(f) if f else QPixmap()
    return None if pm.isNull() else pm.scaledToHeight(height, Qt.TransformationMode.SmoothTransformation)


def local(icon_path):
    return DIR / str(icon_path).strip("/").replace("/", "_")


def path_for(icon_path):
    """The saved picture's file path, or None (then asked for in the background)."""
    if not icon_path:
        return None
    f = local(icon_path)
    if f.exists() and f.stat().st_size > 0:
        return str(f)
    if CFG.get("item_previews", True):
        _want(icon_path)
    return None


def _want(icon_path):
    with _lock:
        if icon_path in _pending or time.time() - _failed.get(icon_path, 0) < 3600:
            return
        _pending.add(icon_path)
    threading.Thread(target=_get, args=(icon_path,), daemon=True, name="player-icon").start()


def _get(icon_path):
    global done_count
    from app.trade.market import HEADERS
    try:
        r = requests.get(BASE + icon_path, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=20)
        r.raise_for_status()
        if not r.content or not r.headers.get("content-type", "image").startswith("image"):
            raise ValueError("not a picture")
        DIR.mkdir(parents=True, exist_ok=True)
        local(icon_path).write_bytes(r.content)
        done_count += 1
    except Exception as e:
        _failed[icon_path] = time.time()
        try:
            from app.core import logbus
            logbus.error("player", f"picture {icon_path}: {type(e).__name__}: {e}")
        except Exception:
            pass
    finally:
        with _lock:
            _pending.discard(icon_path)
