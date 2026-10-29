"""Mod card frames from the Warframe wiki (https://wiki.warframe.com/w/Mod/Assets): the parts the game's own cards are
made of (top and bottom border, background, side and corner lights, the backer of the drain, rank line and pips), per
rarity (Common, Uncommon, Rare, Legendary, Riven, Galvanized, Amalgam, Peculiar…). The wiki took them from the Warframe
Companion app / the Arsenal Twitch extension.

The page is read once through the standard MediaWiki API (the list of its pictures, then each picture's address), the
pictures are kept in the data folder (modframes/) and read again after 30 days; nothing else is asked of the wiki. The
parts are recognised by their file names ("Rare Mod Top Border", "Mod Rank Pip"…, spaces or not), so a renamed file is
simply left out. Missing parts or no connection: the Builds cards are drawn as before.

The Builds cards are landscape (as in the game's upgrade screen) while the parts were made for the tall card: they are
drawn at one common scale (the card's width over the top border's), borders at the top and bottom, lights on the sides,
the backer behind the drain, the rank pips on the rank line."""
import json
import re
import threading
import time

from app.core.config import APP_DIR, CFG

PAGE = "Mod/Assets"
DIR = APP_DIR / "modframes"
INDEX = DIR / "index.json"
MAX_AGE = 30 * 86400
API = "https://wiki.warframe.com/api.php"

RARITIES = ("common", "uncommon", "rare", "legendary", "riven", "galvanized", "amalgam", "peculiar")
# part key -> words its file name contains (normalised: lower case, letters only)
PARTS = (("topborder", ("topborder",)), ("bottomborder", ("bottomborder",)), ("background", ("background",)),
         ("backer", ("backer",)), ("sidelight", ("sidelight", "sidesmoke")), ("cornerlight", ("cornerlight",)),
         ("bottomlight", ("bottomlight",)), ("typetab", ("typetab",)), ("rankline", ("rankline",)),
         ("rankpip", ("rankpip",)), ("empty", ("emptymodslot", "emptyslot")))
FALLBACK = {"galvanized": "uncommon", "amalgam": "legendary", "peculiar": "legendary", "riven": "uncommon"}
CODE = {"C": "common", "U": "uncommon", "R": "rare", "L": "legendary", "riven": "riven"}

_lock = threading.Lock()
_state = {"index": None, "busy": False, "pix": {}}


def _norm(s) -> str:
    return re.sub(r"[^a-z]", "", str(s or "").lower())


def classify(filename: str):
    """(rarity or "", part, side) of a file of the page, or None. side: "left" / "right" / ""."""
    n = _norm(re.sub(r"\.(png|webp|jpg|gif)$", "", filename, flags=re.I))
    part = next((k for k, words in PARTS if any(w in n for w in words)), None)
    if not part:
        return None
    rar = ""
    for r in sorted(RARITIES, key=len, reverse=True):     # "uncommon" before "common"
        if r in n:
            rar = r
            break
    side = "left" if "left" in n else ("right" if "right" in n else "")
    return rar, part, side


def _index() -> dict:
    if _state["index"] is None:
        try:
            _state["index"] = json.loads(INDEX.read_text(encoding="utf-8"))
        except Exception:
            _state["index"] = {}
    return _state["index"]


def enabled() -> bool:
    return bool(CFG.get("mod_frames", True))


def ensure():
    """Reads the page's pictures in the background when they are missing or 30 days old (once per run)."""
    if not enabled():
        return
    idx = _index()
    if idx.get("files") and time.time() - float(idx.get("t") or 0) < MAX_AGE:
        return
    with _lock:
        if _state["busy"]:
            return
        _state["busy"] = True
    threading.Thread(target=_download, daemon=True, name="modframes").start()


def _download():
    import requests
    from app.core import logbus
    from app.trade.market import HEADERS
    h = {"User-Agent": HEADERS["User-Agent"]}
    try:
        r = requests.get(API, params={"action": "parse", "page": PAGE, "prop": "images", "format": "json"},
                         headers=h, timeout=15)
        r.raise_for_status()
        names = [n for n in (r.json().get("parse") or {}).get("images") or [] if classify(n)]
        if not names:
            logbus.add("builds", "mod frames: no card parts on the wiki page", "warn")
            return
        DIR.mkdir(parents=True, exist_ok=True)
        files = dict(_index().get("files") or {})
        for i in range(0, len(names), 40):                 # the addresses, 40 files per request
            batch = names[i:i + 40]
            q = requests.get(API, params={"action": "query", "format": "json", "prop": "imageinfo",
                                          "iiprop": "url|size", "titles": "|".join("File:" + n for n in batch)},
                             headers=h, timeout=15)
            q.raise_for_status()
            for page in (q.json().get("query") or {}).get("pages", {}).values():
                info = (page.get("imageinfo") or [{}])[0]
                title = str(page.get("title") or "").split(":", 1)[-1].replace(" ", "_")
                if not info.get("url") or not title:
                    continue
                time.sleep(0.3)
                d = requests.get(info["url"], headers=h, timeout=15)
                if d.status_code == 200 and (d.content[:4] in (b"\x89PNG", b"RIFF") or d.content[:3] == b"\xff\xd8\xff"):
                    (DIR / title).write_bytes(d.content)
                    files[title] = [info.get("width"), info.get("height")]
        with _lock:
            _state["index"] = {"t": time.time(), "files": files}
            _state["pix"].clear()
            INDEX.write_text(json.dumps(_state["index"]), encoding="utf-8")
        logbus.add("builds", f"mod frames from the wiki: {len(files)} parts", "ok")
    except Exception as e:
        logbus.add("builds", f"mod frames from the wiki: {type(e).__name__}: {e}", "warn")
    finally:
        _state["busy"] = False


def parts(rarity: str) -> dict:
    """{part: (file, side)} for a rarity (common … peculiar), the rarity's own parts first, then its fallback's, then
    the shared ones (rank line and pip)."""
    files = _index().get("files") or {}
    found = {}
    for want in (rarity, FALLBACK.get(rarity, ""), ""):
        for f in files:
            c = classify(f)
            if not c or c[0] != want:
                continue
            rar, part, side = c
            key = part + (":" + side if side else "")
            found.setdefault(key, f)
    return found


def _pix(file):
    from PyQt6.QtGui import QPixmap
    pm = _state["pix"].get(file)
    if pm is None:
        pm = QPixmap(str(DIR / file))
        _state["pix"][file] = pm
    return pm if not pm.isNull() else None


def rarity_of(name: str, code: str, riven=False) -> str:
    if riven:
        return "riven"
    for word in ("Galvanized", "Amalgam", "Peculiar"):
        if name.startswith(word + " "):
            return word.lower()
    return CODE.get(code, "")


def available(rar: str) -> bool:
    return enabled() and bool(rar) and "topborder" in parts(rar) and "bottomborder" in parts(rar)


def paint_back(p, W, H, rar: str) -> bool:
    """The rarity's background over the whole card (cover). False when there is none."""
    ps = parts(rar)
    f = ps.get("background")
    pm = _pix(f) if f else None
    if pm is None:
        return False
    from PyQt6.QtCore import QRectF
    s = max(W / pm.width(), H / pm.height())
    w, h = pm.width() * s, pm.height() * s
    p.drawPixmap(QRectF((W - w) / 2, (H - h) / 2, w, h), pm, QRectF(pm.rect()))
    return True


def paint_front(p, W, H, rar: str, rank=None, mx=None):
    """Borders, lights, backer and rank pips over the card. Returns the backer's rectangle (or None) so the drain can be
    drawn on it."""
    from PyQt6.QtCore import QRectF
    ps = parts(rar)
    top = _pix(ps.get("topborder")) if ps.get("topborder") else None
    bottom = _pix(ps.get("bottomborder")) if ps.get("bottomborder") else None
    if top is None or bottom is None:
        return None
    s = W / top.width()                                    # one scale for every part (they were made together)

    def put(pm, x, y, mirror=False, max_h=None):
        w, h = pm.width() * s, pm.height() * s
        if max_h and h > max_h:                            # never taller than the room it has on a landscape card
            k = max_h / h
            w, h = w * k, h * k
        if mirror:
            p.save()
            p.translate(x + w, y)
            p.scale(-1, 1)
            p.drawPixmap(QRectF(0, 0, w, h), pm, QRectF(pm.rect()))
            p.restore()
        else:
            p.drawPixmap(QRectF(x, y, w, h), pm, QRectF(pm.rect()))
        return w, h

    def side_pair(key, y_of):
        left = ps.get(key + ":left") or ps.get(key)
        right = ps.get(key + ":right")
        pl = _pix(left) if left else None
        if pl is None:
            return
        w, h = pl.width() * s, min(pl.height() * s, H)
        y = y_of(h)
        put(pl, 0, y, max_h=H)
        pr = _pix(right) if right else None
        if pr is not None:
            put(pr, W - pr.width() * s, y, max_h=H)
        else:
            put(pl, W - w, y, mirror=True, max_h=H)

    side_pair("sidelight", lambda h: (H - h) / 2)
    side_pair("cornerlight", lambda h: H - h)
    bl = _pix(ps["bottomlight"]) if ps.get("bottomlight") else None
    if bl is not None:
        w = bl.width() * s
        put(bl, (W - w) / 2, H - bl.height() * s)
    _w, th = put(top, 0, 0, max_h=H * 0.32)
    bw, bh = bottom.width() * s, bottom.height() * s
    if bh > H * 0.36:
        bw, bh = bw * H * 0.36 / bh, H * 0.36
    put(bottom, (W - bw) / 2, H - bh, max_h=H * 0.36)
    # the rank: the line across the bottom border, a pip per rank (dim when not reached)
    if mx:
        line = _pix(ps["rankline"]) if ps.get("rankline") else None
        pip = _pix(ps["rankpip"]) if ps.get("rankpip") else None
        cy = H - bh * 0.55
        if line is not None:
            lw, lh = min(line.width() * s, W * 0.8), line.height() * s
            put(line, (W - lw) / 2, cy - lh / 2, max_h=max(2.0, H * 0.06))
        if pip is not None:
            r = mx if rank is None else max(0, min(int(rank), int(mx)))
            pw, ph = pip.width() * s, pip.height() * s
            gap = pw * 1.15
            x0 = (W - gap * (mx - 1) - pw) / 2
            for i in range(int(mx)):
                p.setOpacity(1.0 if i < r else 0.28)
                p.drawPixmap(QRectF(x0 + i * gap, cy - ph / 2, pw, ph), pip, QRectF(pip.rect()))
            p.setOpacity(1.0)
    backer = _pix(ps["backer"]) if ps.get("backer") else None
    if backer is not None:
        w, h = backer.width() * s, backer.height() * s
        if h > H * 0.3:
            w, h = w * H * 0.3 / h, H * 0.3
        rect = QRectF(W - w - W * 0.03, th * 0.15, w, h)
        p.drawPixmap(rect, backer, QRectF(backer.rect()))
        return rect
    return None


def has_pips(rar: str) -> bool:
    return available(rar) and "rankpip" in parts(rar)
