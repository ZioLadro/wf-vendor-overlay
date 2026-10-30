"""A Warframe's abilities under its stats, as the game's upgrade screen shows them: the passive and the four abilities
(the Helminth one in place of the ability it replaces), each with a tooltip: name, description, energy cost with the
build's Ability Efficiency and the build's Strength / Duration / Range.

Data (tools/build_loadouts.py, from DE's Public Export): abil: ability path -> [description, icon address, energy
cost]; passive: Warframe path -> description; suitpath: Warframe name -> path; suits: path -> its 4 ability paths.
The icons are DE's own (content.warframe.com), downloaded once into the data folder (abilities/) when first shown.
The game's per-ability numbers (metres, seconds, damage) are not in any public export: the tooltip gives the build's
multipliers instead."""
import hashlib
import queue
import re
import threading

from PyQt6.QtCore import QObject, QPointF, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QHBoxLayout, QWidget

from app.core.config import APP_DIR
from app.core.i18n import t
from app.game import loadouts as LO

DIR = APP_DIR / "abilities"
_q = queue.Queue()
_pending = set()
_worker = None


class _N(QObject):
    ready = pyqtSignal()


_notify = None


def notifier():
    global _notify
    if _notify is None:
        _notify = _N()
    return _notify


def _file(url: str):
    name = re.sub(r"[^\w.-]", "_", url.split("/")[-1].split("!")[0]) or "icon.png"
    return DIR / (hashlib.md5(url.encode()).hexdigest()[:8] + "_" + name)


def icon_path(url: str):
    """The icon on disk, or None (then it is asked for in the background)."""
    if not url:
        return None
    f = _file(url)
    if f.exists():
        return f
    if f.with_suffix(".none").exists():                    # the wiki had no picture for it
        return None
    if url not in _pending:
        _pending.add(url)
        notifier()
        _q.put(url)
        _start()
    return None


def _start():
    global _worker
    if _worker is None or not _worker.is_alive():
        _worker = threading.Thread(target=_run, daemon=True, name="ability-icons")
        _worker.start()


def _run():
    import time
    import requests
    from app.trade.market import HEADERS
    got = 0
    while True:
        try:
            url = _q.get(timeout=2)
        except queue.Empty:
            break
        try:
            h = {"User-Agent": HEADERS["User-Agent"]}
            src = url
            if url.startswith("wiki:"):                    # the main picture of a wiki article, full size
                q = requests.get("https://wiki.warframe.com/api.php", headers=h, timeout=15, params={
                    "action": "query", "format": "json", "titles": url[5:], "redirects": 1, "prop": "pageimages",
                    "piprop": "original"})
                pages = (q.json().get("query") or {}).get("pages") or {}
                src = next((p.get("original", {}).get("source") for p in pages.values() if p.get("original")), "")
                if not src:                                # none: the caller falls back on the next picture
                    DIR.mkdir(parents=True, exist_ok=True)
                    _file(url).with_suffix(".none").write_bytes(b"")
                    got += 1
                    continue
            r = requests.get(src, headers=h, timeout=20)
            if r.status_code == 200 and (r.content[:4] == b"\x89PNG" or r.content[:4] == b"RIFF"
                                         or r.content[:3] == b"\xff\xd8\xff"):
                DIR.mkdir(parents=True, exist_ok=True)
                _file(url).write_bytes(r.content)
                got += 1
        except Exception:
            pass
        time.sleep(0.15)
    if got:
        try:
            notifier().ready.emit()
        except Exception:
            pass


# ---------- the model ----------
def _clean(text: str) -> str:
    """A description with the game's placeholders (|DAMAGE|) shown as a dot: their numbers are not public."""
    text = re.sub(r"\|[A-Z0-9_]+\|%?", "…", text or "")
    return re.sub(r"\s+", " ", text).strip()


def ability_info(path: str, slot=None, helminth=False) -> dict:
    d = LO.data()
    row = (d.get("abil") or {}).get(path) or ["", "", None]
    return {"path": path, "name": (d.get("abilities") or {}).get(path) or path.rsplit("/", 1)[-1],
            "desc": _clean(row[0]), "icon": row[1], "cost": row[2], "slot": slot, "helminth": helminth}


def model(item: str, helminth=None) -> list:
    """[passive, ability 1…4] of a Warframe by name; helminth: {"slot": 1-4, "path": ability path} (or a name)."""
    d = LO.data()
    path = (d.get("suitpath") or {}).get(item)
    if not path:
        return []
    out = [{"path": "", "name": t("abil.passive"), "desc": _clean((d.get("passive") or {}).get(path, "")),
            "icon": "", "cost": None, "slot": 0, "helminth": False, "passive": True}]
    own = (d.get("suits") or {}).get(path) or []
    hs = int((helminth or {}).get("slot") or 0)
    hp = (helminth or {}).get("path") or ""
    if not hp and (helminth or {}).get("ability"):              # only the name (an older reading): find its path
        name = helminth["ability"]
        hp = next((p for p, n in (d.get("abilities") or {}).items() if n == name), "")
    for i, ap in enumerate(own[:4]):
        if hs == i + 1 and hp:
            info = ability_info(hp, i + 1, helminth=True)
            info["replaced"] = (d.get("abilities") or {}).get(ap, "")
            out.append(info)
        else:
            out.append(ability_info(ap, i + 1))
    return out


def helminth_choices() -> list:
    """[(name, path)] the planner offers for the Helminth: the Helminth's own abilities, then every Warframe's (the
    game lets you subsume one per Warframe; which one is not in the public data, so all are listed)."""
    d = LO.data()
    names = d.get("abilities") or {}
    own = sorted(((n, p) for p, n in names.items() if "/Helminth" in p and p in (d.get("abil") or {})))
    seen, frames = set(), []
    for suit, paths in sorted((d.get("suits") or {}).items()):
        if "Prime" in suit or "Umbra" in suit:
            continue
        for p in paths:
            n = names.get(p)
            if n and n not in seen:
                seen.add(n)
                frames.append((n, p))
    return own + sorted(frames)


# ---------- the widget ----------
def tooltip_html(a: dict, wf: dict) -> str:
    """Name, description, energy cost (with the build's efficiency) and the build's ability stats."""
    def pct(key):
        v = wf.get(key)
        return None if v is None else float(v)
    rows = []
    if a.get("cost") is not None:
        eff = pct("efficiency") or 100.0
        cost = float(a["cost"]) * max(0.25, 2 - eff / 100)
        col = "#ff7b72" if cost > a["cost"] + 1e-9 else ("#7ee08f" if cost < a["cost"] - 1e-9 else "#ffffff")
        rows.append((t("abil.cost"), f"<span style='color:{col}'>{cost:.2f}".rstrip("0").rstrip(".") + "</span>"
                     + f" <span style='color:#8b93a3'>({a['cost']:g})</span>"))
    for key in ("strength", "duration", "range", "efficiency"):
        v = pct(key)
        if v is not None and not a.get("passive"):
            col = "#7ee08f" if v > 100 else ("#ff7b72" if v < 100 else "#ffffff")
            rows.append((t("builds.stat." + key), f"<span style='color:{col}'>{v:g}%</span>"))
    head = f"<b style='font-size:14px'>{a['name'].upper()}</b>"
    if a.get("helminth"):
        head += f"<br><span style='color:#c79bff'>{t('abil.helminth', replaced=a.get('replaced') or '?')}</span>"
    table = "".join(f"<tr><td style='color:#aab2c0; padding-right:16px'>{k}</td><td align='right'>{v}</td></tr>"
                    for k, v in rows)
    return (f"<div style='max-width:340px'>{head}<p>{a.get('desc') or ''}</p>"
            + (f"<table width='100%'>{table}</table>" if table else "")
            + (f"<p style='color:#8b93a3; font-size:11px'>{t('abil.note')}</p>" if rows and not a.get("passive") else "")
            + "</div>")


class AbilityIcon(QWidget):
    def __init__(self, a: dict, wf: dict, size=40):
        super().__init__()
        self.a, self.wf = a, wf
        self.setFixedSize(QSize(size, size + 4))
        self.setToolTip(tooltip_html(a, wf))

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        s = self.width()
        r = QRectF(2, 2, s - 4, s - 4)
        ring = QColor("#b98cff") if self.a.get("helminth") else QColor("#8d96a6")
        p.setPen(QPen(ring, 1.6))
        p.setBrush(QColor(12, 14, 20, 200))
        p.drawEllipse(r)
        f = icon_path(self.a.get("icon") or "")
        pm = QPixmap(str(f)) if f else QPixmap()
        if not pm.isNull():
            k = (s - 12) / max(pm.width(), pm.height())
            w, h = pm.width() * k, pm.height() * k
            p.drawPixmap(QRectF((s - w) / 2, (s - h) / 2, w, h), pm, QRectF(pm.rect()))
        else:                                              # passive (no icon) or not downloaded yet
            fnt = QFont(self.font())
            fnt.setPixelSize(int(s * 0.38))
            fnt.setBold(True)
            p.setFont(fnt)
            p.setPen(QColor("#c9ced8"))
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, "◈" if self.a.get("passive") else str(self.a.get("slot") or ""))
        if self.a.get("helminth"):                         # a small Helminth mark
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#9b6cff"))
            p.drawEllipse(QPointF(s - 7, s - 5), 4.5, 4.5)
        p.end()


class AbilityBar(QWidget):
    """The passive and the four abilities in a row (redrawn when their icons arrive)."""

    def __init__(self, abilities: list, wf: dict):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(8)
        self.icons = [AbilityIcon(a, wf) for a in abilities]
        for w in self.icons:
            lay.addWidget(w)
        lay.addStretch(1)
        notifier().ready.connect(self._refresh)

    def _refresh(self):
        try:
            for w in self.icons:
                w.update()
        except RuntimeError:                               # the widget is gone
            pass

