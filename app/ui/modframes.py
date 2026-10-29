"""Mod card frames from the Warframe wiki (https://wiki.warframe.com/w/Mod/Assets): the parts the game's own cards are
made of, per metal / rarity (Bronze = Common, Silver = Uncommon, Gold = Rare, Legendary, Riven, Galvanized, Peculiar,
Amalgam). The wiki took them from the Warframe Companion app / the Arsenal Twitch extension.

The files are named <Metal><Part>.png: FrameTop (the top edge with the rarity's ornament and two legs going down),
FrameBottom (the curved tray at the bottom with its uprights), Background, TopRightBacker (the drain's box), LowerTab,
SideLight, CornerLights; shared: RankCompleteLine and RankSlotActive (the rank line and a lit pip), BlankMod. They are
asked for by name through the standard MediaWiki API (plus whatever else the page lists that is recognised), kept in
the data folder (modframes/) and read again after 30 days. The page's "Avionic" frames (Railjack) are left out.

The Builds cards are landscape like the game's upgrade screen; the game builds those from the same two pieces: the
FrameTop across the top and the FrameBottom across the bottom, their legs making the sides. The background and the
mod's art fill the inside, the drain sits on the TopRightBacker, the rank pips on the rank line under the card.
Missing parts or no connection: the simple cards."""
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
VERSION = 3

METALS = {"bronze": "common", "silver": "uncommon", "gold": "rare", "legendary": "legendary", "riven": "riven",
          "galvanized": "galvanized", "peculiar": "peculiar", "amalgam": "amalgam",
          # the page's captions use the rarities' names
          "uncommon": "uncommon", "common": "common", "rare": "rare"}
# part key -> words of its file name / caption (normalised: lower case, letters only)
PARTS = (("topborder", ("frametop", "topborder")), ("bottomborder", ("framebottom", "bottomborder")),
         ("background", ("background",)), ("backer", ("toprightbacker", "backer")),
         ("sidelight", ("sidelight", "sidesmoke")), ("cornerlight", ("cornerlight",)), ("bottomlight", ("bottomlight",)),
         ("typetab", ("lowertab", "typetab")), ("rankline", ("rankcompleteline", "rankline")),
         ("rankpipoff", ("rankslotinactive", "rankslotempty", "rankslotunlit")),
         ("rankpip", ("rankslotactive", "rankpip", "rankslot")), ("empty", ("blankmod", "emptymodslot", "emptyslot")))
SHARED = ("rankline", "rankpip", "rankpipoff", "empty")
FALLBACK = {"galvanized": "uncommon", "amalgam": "legendary", "peculiar": "legendary", "riven": "uncommon",
            "uncommon": "common"}
CODE = {"C": "common", "U": "uncommon", "R": "rare", "L": "legendary", "riven": "riven"}
KNOWN = [m + p + ".png" for m in ("Bronze", "Silver", "Gold", "Legendary", "Riven", "Galvanized", "Peculiar", "Amalgam")
         for p in ("FrameTop", "FrameBottom", "Background", "TopRightBacker")] + \
        ["RankCompleteLine.png", "RankSlotActive.png", "RankSlotInactive.png", "RankSlotEmpty.png", "BlankMod.png"]

_lock = threading.Lock()
_state = {"index": None, "busy": False, "pix": {}}


def _norm(s) -> str:
    return re.sub(r"[^a-z]", "", str(s or "").lower())


def classify(filename: str):
    """(rarity or "", part, side) of a file, or None. Railjack's Avionic frames are not mod frames."""
    n = _norm(re.sub(r"\.(png|webp|jpg|gif)$", "", filename, flags=re.I))
    if "avionic" in n:
        return None
    part = next((k for k, words in PARTS if any(w in n for w in words)), None)
    if not part:
        return None
    rar = ""
    for word in sorted(METALS, key=len, reverse=True):    # "uncommon" before "common"
        if word in n:
            rar = METALS[word]
            break
    if part in SHARED:
        rar = ""
    side = "left" if "left" in n else ("right" if n.endswith("right") else "")
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


class _Notifier:
    """Tells the Builds tab (in the GUI thread) that the parts arrived, so its cards are drawn again."""
    obj = None

    @classmethod
    def get(cls):
        if cls.obj is None:
            from PyQt6.QtCore import QObject, pyqtSignal

            class N(QObject):
                ready = pyqtSignal()
            cls.obj = N()
        return cls.obj


def notifier():
    """A QObject whose `ready` signal fires once new parts are on disk (create it in the GUI thread)."""
    return _Notifier.get()


def _usable(idx) -> bool:
    return any((DIR / f).exists() for f in idx.get("files") or {})


def ensure(force=False):
    """Reads the parts in the background when they are missing, of an older layout or 30 days old (once per run)."""
    if not enabled():
        return
    notifier()                                             # created here, in the GUI thread
    idx = _index()
    if not force and idx.get("v") == VERSION and _usable(idx) and time.time() - float(idx.get("t") or 0) < MAX_AGE:
        return
    if not force and idx.get("v") == VERSION and time.time() - float(idx.get("tried") or 0) < 3600:
        return                                             # failed less than an hour ago: not again yet
    with _lock:
        if _state["busy"]:
            return
        _state["busy"] = True
    threading.Thread(target=_download, daemon=True, name="modframes").start()


def page_files(html: str) -> list:
    """[(file name, caption)] of the page's pictures in page order (the caption: the text after the picture up to the
    next one, with the section title in front)."""
    import html as H
    from urllib.parse import unquote
    out, section = [], ""
    marks = [(m.start(), "h", m.group(1)) for m in re.finditer(r"<h[2-4][^>]*>(.*?)</h[2-4]>", html, re.S)]
    marks += [(m.start(), "f", m.group(1)) for m in re.finditer(r'href="[^"]*?/(?:File|Image):([^"#?]+)"', html)]
    marks.sort()
    for n, (pos, kind, val) in enumerate(marks):
        if kind == "h":
            section = H.unescape(re.sub(r"<[^>]+>", " ", val)).strip()
            continue
        name = unquote(H.unescape(val)).replace(" ", "_")
        end = marks[n + 1][0] if n + 1 < len(marks) else len(html)
        chunk = html[pos:end]
        chunk = chunk[chunk.find(">") + 1:]
        text = re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", chunk))).strip()[:120]
        if not (out and out[-1][0] == name):
            out.append((name, (section + " | " + text).strip(" |")))
    return out


def _label(name: str, caption: str = ""):
    """The part a file is: from its own name first (<Metal><Part>), else from its caption on the page."""
    c = classify(name)
    if c or "avionic" in _norm(name):
        return c
    cap = caption.split(" | ", 1)[-1]
    return classify(cap) if cap else None


def _download():
    import requests
    from app.core import logbus
    from app.trade.market import HEADERS
    h = {"User-Agent": HEADERS["User-Agent"]}
    step = "page"
    try:
        labels = {n: _label(n) for n in KNOWN}
        try:                                               # whatever else the page shows (new rarities…)
            r = requests.get(API, params={"action": "parse", "page": PAGE, "prop": "text|images", "format": "json"},
                             headers=h, timeout=20)
            r.raise_for_status()
            parse = r.json().get("parse") or {}
            pairs = page_files((parse.get("text") or {}).get("*") or "")
            pairs += [(n.replace(" ", "_"), "") for n in parse.get("images") or []]
            for name, cap in pairs:
                c = _label(name, cap)
                if c and name not in labels:
                    labels[name] = c
        except Exception as e:
            logbus.add("builds", f"mod frames: wiki page not read ({type(e).__name__}), asking for the known files", "warn")
        labels = {n: "|".join(c) for n, c in labels.items() if c}
        DIR.mkdir(parents=True, exist_ok=True)
        files, names = {}, list(labels)
        step = "files"
        for i in range(0, len(names), 40):                 # the addresses, 40 files per request
            q = requests.get(API, params={"action": "query", "format": "json", "prop": "imageinfo", "iiprop": "url",
                                          "titles": "|".join("File:" + n for n in names[i:i + 40])},
                             headers=h, timeout=20)
            q.raise_for_status()
            data = q.json().get("query") or {}
            back = {x.get("to"): x.get("from") for x in data.get("normalized") or []}
            for page in (data.get("pages") or {}).values():
                info = (page.get("imageinfo") or [{}])[0]
                title = str(page.get("title") or "")
                title = (back.get(title) or title).split(":", 1)[-1].replace(" ", "_")
                if not info.get("url") or title not in labels:
                    continue
                time.sleep(0.25)
                d = requests.get(info["url"], headers=h, timeout=20)
                if d.status_code == 200 and (d.content[:4] in (b"\x89PNG", b"RIFF") or d.content[:3] == b"\xff\xd8\xff"):
                    safe = re.sub(r"[^\w.-]", "_", title)
                    (DIR / safe).write_bytes(d.content)
                    files[safe] = labels[title]
        for old in DIR.glob("*.png"):                      # parts of an older download that are not used any more
            if old.name not in files:
                try:
                    old.unlink()
                except OSError:
                    pass
        with _lock:
            _state["index"] = {"v": VERSION, "t": time.time(), "files": files}
            _state["pix"].clear()
            INDEX.write_text(json.dumps(_state["index"]), encoding="utf-8")
        logbus.add("builds", f"mod frames from the wiki: {len(files)} parts saved", "ok" if files else "warn")
        if files:
            try:
                notifier().ready.emit()
            except Exception:
                pass
    except Exception as e:
        logbus.add("builds", f"mod frames from the wiki ({step}): {type(e).__name__}: {e}", "warn")
        with _lock:
            idx = dict(_index())
            idx.update(v=VERSION, tried=time.time())
            _state["index"] = idx
            try:
                DIR.mkdir(parents=True, exist_ok=True)
                INDEX.write_text(json.dumps(idx), encoding="utf-8")
            except OSError:
                pass
    finally:
        _state["busy"] = False


def parts(rarity: str) -> dict:
    """{part: file} for a rarity: its own parts, then its fallback's (Silver without its own: Bronze's shape), then the
    shared ones. Only parts of the current layout (index version) count."""
    idx = _index()
    if idx.get("v") != VERSION:
        return {}
    files = idx.get("files") or {}
    found, chain, r = {}, [], rarity
    while r and r not in chain:
        chain.append(r)
        r = FALLBACK.get(r, "")
    for want in chain + [""]:
        for f, lab in files.items():
            c = lab.split("|") if isinstance(lab, str) and lab.count("|") == 2 else None
            if not c or c[0] != want or not (DIR / f).exists():
                continue
            found.setdefault(c[1], f)
    return found


def _pix(file):
    from PyQt6.QtGui import QPixmap
    if not file:
        return None
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
    ps = parts(rar)
    return enabled() and bool(rar) and "topborder" in ps and "bottomborder" in ps


def has_pips(rar: str) -> bool:
    return available(rar) and "rankpip" in parts(rar)


def _bbox(pm):
    """The visible part of a piece (alpha > 40) as a QRectF of its pixels: many pieces sit on a larger transparent
    canvas (Galvanized and Peculiar on 512 px), only the Riven's fill theirs."""
    from PyQt6.QtCore import QRectF
    from PyQt6.QtGui import QImage
    key = ("bbox", pm.cacheKey())
    hit = _state["pix"].get(key)
    if hit is not None:
        return hit
    img = pm.toImage().convertToFormat(QImage.Format.Format_ARGB32)
    w, h = img.width(), img.height()
    ptr = img.constBits()
    ptr.setsize(img.sizeInBytes())
    data = bytes(ptr)
    bpl = img.bytesPerLine()
    rows = [y for y in range(h) if max(data[y * bpl + 3: y * bpl + w * 4: 4]) > 40]
    if not rows:
        r = QRectF(0, 0, w, h)
    else:
        cols = [0] * w
        for y in rows:
            line = data[y * bpl + 3: y * bpl + w * 4: 4]
            for x in range(w):
                if line[x] > 40:
                    cols[x] = 1
        xs = [x for x in range(w) if cols[x]]
        r = QRectF(xs[0], rows[0], xs[-1] - xs[0] + 1, rows[-1] - rows[0] + 1)
    _state["pix"][key] = r
    return r


def inner(W, H):
    """The inside of the frame (where the background and the art go)."""
    from PyQt6.QtCore import QRectF
    return QRectF(W * 0.02, H * 0.035, W * 0.96, H * 0.86)


def paint_back(p, W, H, rar: str) -> bool:
    """The rarity's background stretched over the inside of the card. False when there is none."""
    from PyQt6.QtCore import QRectF
    pm = _pix(parts(rar).get("background"))
    if pm is None:
        return False
    p.drawPixmap(inner(W, H), pm, QRectF(pm.rect()))
    return True


def paint_front(p, W, H, rar: str, rank=None, mx=None):
    """The frame over the card: the visible part of the FrameTop across the top and of the FrameBottom across the
    bottom, both the card's full width (their legs are the sides), the rank pips on the rank line in the tray, the
    drain's backer top right (its rectangle is returned so the drain is written on it)."""
    from PyQt6.QtCore import QRectF
    ps = parts(rar)
    top, bottom = _pix(ps.get("topborder")), _pix(ps.get("bottomborder"))
    if top is None or bottom is None:
        return None
    tb, bb = _bbox(top), _bbox(bottom)
    th = tb.height() * W / tb.width()
    bh = bb.height() * W / bb.width()
    # a piece taller than the card (Riven, Peculiar: their legs reach the other end) is cut, never squeezed
    bh_draw = min(bh, H)
    src = QRectF(bb.left(), bb.bottom() - bb.height() * bh_draw / bh, bb.width(), bb.height() * bh_draw / bh)
    p.drawPixmap(QRectF(0, H - bh_draw, W, bh_draw), bottom, src)
    th_draw = min(th, H)
    p.drawPixmap(QRectF(0, 0, W, th_draw), top, QRectF(tb.left(), tb.top(), tb.width(), tb.height() * th_draw / th))
    if mx:
        line, pip, off = _pix(ps.get("rankline")), _pix(ps.get("rankpip")), _pix(ps.get("rankpipoff"))
        cy = H - H * 0.085
        if line is not None:
            lb = _bbox(line)
            lw = W * 0.6
            p.drawPixmap(QRectF((W - lw) / 2, cy + H * 0.03, lw, max(2.0, H * 0.03)), line, lb)
        if pip is not None:
            r = int(mx) if rank is None else max(0, min(int(rank), int(mx)))
            d = max(5.0, min(H * 0.075, W * 0.5 / max(1, int(mx))))
            gap = d * 1.3
            x0 = (W - gap * (int(mx) - 1) - d) / 2
            for i in range(int(mx)):
                srcp = pip if i < r or off is None else off
                p.setOpacity(1.0 if i < r else (0.9 if off is not None else 0.25))
                p.drawPixmap(QRectF(x0 + i * gap, cy - d / 2, d, d), srcp, QRectF(srcp.rect()))
            p.setOpacity(1.0)
    backer = _pix(ps.get("backer"))
    if backer is not None:
        h = H * 0.21
        w = max(h * backer.width() / backer.height(), W * 0.25)
        rect = QRectF(W - w - W * 0.06, H * 0.1, w, h)
        p.drawPixmap(rect, backer, QRectF(backer.rect()))
        return rect
    return None
