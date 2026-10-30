"""Weekly tab, two more pages: the Tenet / Coda weapons on offer (Ergo Glast, Eleanor: renewed every 4 days, each with
its bonus element) and the Duviri Circuit (this week's Warframes and Incarnon Genesis adapters, and a calendar of the
next weeks). The data: app/game/rotations.py. The pictures are DE's (data "figure"), downloaded once."""
import time
from datetime import datetime, timezone

from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView, QFrame, QHBoxLayout, QHeaderView, QLabel, QScrollArea, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from app.core.i18n import t
from app.core.uiutil import role
from app.game import loadouts as LO
from app.game import rotations as R
from app.ui import icons


def _left(sec: float) -> str:
    s = max(0, int(sec))
    d, h, m = s // 86400, s % 86400 // 3600, s % 3600 // 60
    return f"{d}d {h}h" if d else (f"{h}h {m:02d}m" if h else f"{m}m")


def _day(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).astimezone().strftime("%a %d/%m %H:%M")


def _pic(name: str, size: int):
    """DE's picture of an item, scaled (None while it downloads)."""
    from app.ui import abilitybar
    url = (LO.data().get("figure") or {}).get(name)
    f = abilitybar.icon_path(url) if url else None
    if f is None:
        return None
    pm = QPixmap(str(f))
    if pm.isNull():
        return None
    return pm.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)


class ItemCard(QFrame):
    """A picture, a name and a line under it."""

    def __init__(self, name: str, sub: str = "", sub_icon=None, size: int = 96, tip: str = ""):
        super().__init__()
        self.setObjectName("rotcard")
        self.setStyleSheet("#rotcard { background: rgba(10, 12, 18, 150); border: 1px solid #3a4250; border-radius: 8px; }"
                           " #rotcard QLabel { background: transparent; }")
        self.name, self.size = name, size
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(4)
        self.pic = QLabel()
        self.pic.setFixedSize(size, size)
        self.pic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.pic, 0, Qt.AlignmentFlag.AlignHCenter)
        lab = QLabel(name)
        lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lab.setWordWrap(True)
        lab.setStyleSheet("font-weight: bold;")
        lay.addWidget(lab)
        if sub:
            s = QLabel((icons_html(sub_icon) if sub_icon else "") + sub)
            s.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(s)
        self.setFixedWidth(size + 40)
        if tip:
            self.setToolTip(tip)
        self.load()

    def load(self):
        pm = _pic(self.name, self.size)
        if pm is not None:
            self.pic.setPixmap(pm)
        else:
            self.pic.setText("…")


def icons_html(path) -> str:
    return f"<img src='{path}' width='16' height='16'> " if path else ""


class _Page(QWidget):
    """A scrolling page redrawn every minute (cycles end) and when pictures arrive."""

    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(self.scroll)
        self._timer = QTimer(self, interval=60_000, timeout=self.rebuild)
        from app.ui import abilitybar
        abilitybar.notifier().ready.connect(self._pictures)
        self._built = False

    def showEvent(self, e):
        super().showEvent(e)
        self.rebuild()
        self._timer.start()

    def hideEvent(self, e):
        super().hideEvent(e)
        self._timer.stop()

    def _pictures(self):
        try:
            for c in self.findChildren(ItemCard):
                c.load()
        except RuntimeError:
            pass

    def _body(self) -> QVBoxLayout:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(w)
        return lay

    @staticmethod
    def _head(lay, text, sub=""):
        h = QLabel(text.upper())
        role(h, "section")
        h.setStyleSheet("font-size: 15px; font-weight: bold; letter-spacing: 1px; margin-top: 8px;")
        lay.addWidget(h)
        if sub:
            s = QLabel(sub)
            s.setWordWrap(True)
            role(s, "muted")
            lay.addWidget(s)

    @staticmethod
    def _row(cards) -> QWidget:
        w = QWidget()
        g = QHBoxLayout(w)
        g.setContentsMargins(0, 0, 0, 0)
        g.setSpacing(10)
        g.setAlignment(Qt.AlignmentFlag.AlignLeft)
        for c in cards:
            g.addWidget(c)
        g.addStretch(1)
        return w


class _WikiNote(QObject):
    arrived = pyqtSignal()


class NemesisWeaponsPage(_Page):
    """Ergo Glast's Tenet weapons and Eleanor's Coda weapons now and in the next cycle, with the bonuses players
    reported on the wiki for this cycle."""

    def __init__(self):
        super().__init__()
        self._wiki = _WikiNote()
        self._wiki.arrived.connect(self.rebuild, Qt.ConnectionType.QueuedConnection)

    def rebuild(self):
        from app.game import wikireports as WR
        lay = self._body()
        now = time.time()
        for vendor in ("tenet", "coda"):
            cur = R.offers(vendor, now)
            if not cur:
                continue
            v = (R.data().get("vendors") or {}).get(vendor, {})
            who = v.get("who", "")
            WR.refresh(vendor, [i["name"] for i in v.get("items") or []], self._wiki.arrived.emit)
            seen = WR.current(vendor, cur["start"], cur["end"])
            self._head(lay, t("rot." + vendor, who=who),
                       t("rot.cycle." + vendor, end=_day(cur["end"]), left=_left(cur["end"] - now)))
            cards = []
            for i in cur["items"]:
                r = seen.get(i["name"])
                if r:
                    day = datetime.fromtimestamp(r["date"], timezone.utc).strftime("%d/%m")
                    cards.append(ItemCard(i["name"], f"{r['pct']:g}% {r['element']}", None, 96,
                                          t("rot.tip.wiki", name=i["name"], pct=f"{r['pct']:g}", el=r["element"],
                                            day=day)))
                else:
                    cards.append(ItemCard(i["name"], t("rot.bonus.game"), None, 96, t("rot.tip2", name=i["name"])))
            lay.addWidget(self._row(cards))
            nxt = R.offers(vendor, cur["end"] + 60)
            if nxt and vendor == "coda":                   # Ergo Glast always has the same five
                sub = QLabel(t("rot.next", start=_day(nxt["start"])) + "  " + ", ".join(i["name"] for i in nxt["items"]))
                sub.setWordWrap(True)
                role(sub, "hint")
                lay.addWidget(sub)
        note = QLabel(t("rot.note.wiki"))
        note.setWordWrap(True)
        role(note, "hint")
        lay.addWidget(note)


class CircuitPage(_Page):
    """This week's Circuit and a calendar of the next 12 weeks."""

    def rebuild(self):
        lay = self._body()
        now = time.time()
        weeks = R.circuit(12, now)
        if not weeks:
            return
        w0 = weeks[0]
        self._head(lay, t("rot.circuit.normal"), t("rot.circuit.ends", end=_day(w0["end"]), left=_left(w0["end"] - now))
                   + ("" if w0.get("live") else "  " + t("rot.circuit.computed")))
        lay.addWidget(self._row([ItemCard(n, "", None, 110) for n in w0["normal"]]))
        self._head(lay, t("rot.circuit.hard"))
        lay.addWidget(self._row([ItemCard(n, t("rot.genesis"), None, 96) for n in w0["hard"]]))
        self._head(lay, t("rot.calendar"))
        tab = QTableWidget(len(weeks), 3)
        tab.setHorizontalHeaderLabels([t("rot.col.week"), t("rot.col.normal"), t("rot.col.hard")])
        tab.verticalHeader().setVisible(False)
        tab.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tab.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        tab.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        tab.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        tab.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        for r, w in enumerate(weeks):
            start = datetime.fromtimestamp(w["start"], timezone.utc).strftime("%d/%m")
            end = datetime.fromtimestamp(w["end"] - 1, timezone.utc).strftime("%d/%m")
            for c, text in enumerate((f"{start} – {end}" + ("  ◀" if r == 0 else ""),
                                      ", ".join(w["normal"]), ", ".join(w["hard"]))):
                it = QTableWidgetItem(text)
                if r == 0:
                    f = it.font()
                    f.setBold(True)
                    it.setFont(f)
                tab.setItem(r, c, it)
        tab.setMinimumHeight(30 + 30 * len(weeks))
        lay.addWidget(tab)
        note = QLabel(t("rot.circuit.note"))
        note.setWordWrap(True)
        role(note, "hint")
        lay.addWidget(note)

