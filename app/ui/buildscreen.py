"""The in-game upgrade screen, shared by the Builds tab (your loadouts, read only) and the build planner (a simulator).

Laid out like the game's: the title (UPGRADES / ITEM [rank]) with the Forma count, the configuration tabs (A, B, C…), on
the left the capacity bar and the stats, in the middle the slots (Aura / Stance / Exilus on top, the eight mods in two
rows of four), on the right the Arcanes (and the Exilus of guns), under them the Incarnon evolution path and, in the
planner, the mod library (search, polarity filter, sort, two rows of cards to click or drag onto a slot).

The screen only shows a model (see BuildScreen.show) and reports what the user does through signals; the planner keeps
the build and redraws."""
from PyQt6.QtCore import QMimeData, QPoint, QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QDrag, QFont, QFontMetrics, QPainter, QPainterPath, QPen, QRadialGradient
from PyQt6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea,
    QSizePolicy, QToolButton, QToolTip, QVBoxLayout, QWidget,
)

from app.game import buildcalc as BC
from app.game import loadouts as LO
from app.ui import icons
from app.ui import previews
from app.ui.buildcards import _scaled, pips
from html import escape as escape_html
from PyQt6.QtCore import QUrl
from app.core.i18n import t
from app.core.uiutil import role

MIME = "application/x-wfvo-mod"
RARITY_COLOR = {"C": "#b07d4f", "U": "#c4c9d4", "R": "#d9b44a", "L": "#e9e9ff", "riven": "#a77be0"}
ACCENT = "#5fd7e6"                     # Incarnon / selection glow
UP, DOWN = "#7ee08f", "#ff7b72"


def rarity(name: str, arcane=False) -> str:
    d = LO.data()
    return (d.get("arcrar") if arcane else d.get("rarity", {})).get(name, "") if name else ""


def _clear(layout):
    while layout.count():
        it = layout.takeAt(0)
        w = it.widget()
        if w:
            w.hide()
            w.deleteLater()
        elif it.layout():
            _clear(it.layout())


# ---------- cards ----------
CARD_ASPECT = 0.46                     # height / width of a card: landscape, like the game's upgrade screen


def land_width(avail: int, height: int = 0) -> int:
    """Card width that makes the stats panel, four cards and the Arcane column fill `avail` pixels."""
    w = (avail - 300 - 14 * 2 - 8 * 4 - 48) // 5
    return max(150, min(300, w))


def _riven_lines(rv):
    out = []
    for a in rv.get("attributes") or []:
        v = a.get("value")
        if a.get("spliced"):
            out.append(("❄ ? " + a["label"].split(" (")[0], "#9fe3ff"))
            continue
        txt = "?" if v is None else f"{v:+g}%" if a.get("pct") else f"{v:+g}"
        out.append((f"{txt} {a['label'].split(' (')[0]}", "#9fd8a6" if a.get("positive") else "#e0584a"))
    return out


class Card(QWidget):
    """A mod / Arcane card drawn like the game's (landscape): the picture dimmed behind the name, the drain and the
    mod's polarity top right (green: matches the slot, red: does not), the slot's polarity top left, the rank as pips,
    a frame in the rarity's colour. Slot cards (in a build) are drop targets and have a menu; library cards can be
    dragged. Signals: clicked(), menu(global pos), dropped(name)."""
    clicked = pyqtSignal()
    menu = pyqtSignal(QPoint)
    dropped = pyqtSignal(str)

    def __init__(self, slot, w, editable=False, selected=False, locked=False, library=False, owned=None):
        super().__init__()
        self.slot, self.editable, self.selected, self.locked, self.library = slot, editable, selected, locked, library
        self.owned = owned
        self.name = slot.get("name") or ""
        arcane_slot = slot.get("role") == "arcane" and not library
        self.setFixedSize(int(w), int(w * (0.62 if arcane_slot else CARD_ASPECT)))   # an Arcane: taller, no card
        self._press = None
        arcane = slot.get("role") == "arcane"
        rv = slot.get("riven")
        self.frame = RARITY_COLOR["riven"] if rv else RARITY_COLOR.get(rarity(self.name, arcane), "")
        self.pic = None
        if self.name and not rv:
            if arcane:
                self.pic = icons.arcane(self.name, int(self.height() * 0.8))
            else:
                f = previews.by_name(self.name, wiki_only=True, fetch=not library)
                if f:
                    self.pic = _scaled(f, max(40, int(self.width() * 1.1)))
        if editable or library:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        if editable and not library:
            self.setAcceptDrops(not locked)
            self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self.customContextMenuRequested.connect(lambda p: self.menu.emit(self.mapToGlobal(p)))
        self._tooltip()

    def _tooltip(self):
        self.setToolTip("")                             # built when the mouse rests on the card (see event)

    def tip_text(self) -> str:
        """The card's tooltip: name, rank, what it does at that rank (wiki, else the bundled data), at max rank, the
        picture, how many you own."""
        from html import escape
        from app.game import modtext
        s, n = self.slot, self.name
        if self.locked:
            return t("bs.locked." + ("arcane" if s.get("role") == "arcane" else "exilus"))
        if not n:
            return t("builds.slot." + s.get("role", "general")) if s.get("role") not in (None, "general") else ""
        if s.get("riven"):
            rv = s["riven"]
            return t("builds.riven.tip", weapon=rv.get("weapon", ""), rerolls=rv.get("rerolls", 0))
        arcane = s.get("role") == "arcane"
        eff = modtext.effect(n, s.get("rank"), s.get("max"), arcane=arcane)
        mx = eff.get("max") or s.get("max")
        rank = eff.get("rank") if eff else s.get("rank")
        parts = [f"<b>{escape(n)}</b>" + (f" &nbsp;·&nbsp; {t('builds.rank', rank=mx if rank is None else rank, max=mx)}" if mx else "")]
        if eff:
            parts.append("<span style='color:#7fd7ff'>" + escape(eff["text"]).replace("\n", "<br>") + "</span>")
            if eff["rank"] != eff["max"]:
                parts.append("<span style='color:#9aa4b2'>" + t("bs.tip.max", n=eff["max"]) + "<br>"
                             + escape(eff["max_text"]).replace("\n", "<br>") + "</span>")
            parts.append("<span style='color:#6b7280; font-size:small'>" + t("bs.tip.src." + eff["source"]) + "</span>")
        f = previews.by_name(n, wiki_only=True, fetch=False) if not arcane else None
        if f:
            parts.append(f"<img src='{f.as_posix()}' width='200'>")
        if self.owned:
            parts.append(t("bs.owned", n=self.owned["n"], rank=self.owned.get("rank", 0)))
        return "<br>".join(parts)

    def event(self, e):
        from PyQt6.QtCore import QEvent
        if e.type() == QEvent.Type.ToolTip:
            text = self.tip_text()
            if text:
                QToolTip.showText(e.globalPos(), text, self)
            else:
                QToolTip.hideText()
            return True
        return super().event(e)

    # --- drawing ---
    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        W, H = self.width(), self.height()
        if self.slot.get("role") == "arcane":
            self._paint_arcane(p, W, H)
            p.end()
            return
        r = QRectF(1.5, 1.5, W - 3, H - 3)
        path = QPainterPath()
        path.addRoundedRect(r, 7, 7)
        s, name = self.slot, self.name
        if self.selected:                                  # the glow of the selected slot
            for k, alpha in ((5, 40), (3, 90)):
                p.setPen(QPen(QColor(95, 215, 230, alpha), k * 2))
                p.drawRoundedRect(r, 7, 7)
        grad = __import__("PyQt6.QtGui", fromlist=["QLinearGradient"]).QLinearGradient(0, 0, 0, H)
        grad.setColorAt(0, QColor("#252c38" if name else "#161a21"))
        grad.setColorAt(1, QColor("#14171d" if name else "#111419"))
        p.fillPath(path, QBrush(grad))
        p.save()
        p.setClipPath(path)
        if self.pic is not None and not self.pic.isNull():
            pm = self.pic
            if s.get("role") == "arcane":                  # an Arcane: its picture on the left, whole
                p.setOpacity(0.85)
                p.drawPixmap(int(W * 0.06), int((H - pm.height()) / 2), pm)
            else:                                          # a mod: its art fills the card, dimmed
                p.setOpacity(0.38)
                x = (W - pm.width()) / 2
                y = (H - pm.height()) / 2 - H * 0.12
                p.drawPixmap(int(x), int(y), pm)
            p.setOpacity(1.0)
            shade = __import__("PyQt6.QtGui", fromlist=["QLinearGradient"]).QLinearGradient(0, 0, 0, H)
            shade.setColorAt(0.35, QColor(0, 0, 0, 0))
            shade.setColorAt(1, QColor(0, 0, 0, 170))
            p.fillRect(self.rect(), QBrush(shade))
        p.restore()
        col = QColor(ACCENT if self.selected else (self.frame or ("#3a4250" if name else "#2c323c")))
        pen = QPen(col, 2 if (self.frame or self.selected) else 1)
        if not name and not self.selected:
            pen.setStyle(Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.drawPath(path)
        big = max(10, int(H * 0.15))
        small = max(8, int(H * 0.11))
        f = QFont(self.font())
        # slot polarity (top left) and the role (Aura, Exilus…)
        x = 8
        spol = s.get("pol") or ""
        if spol and not self.library:
            pm = icons.polarity(spol, max(12, int(H * 0.16)))
            if pm is not None:
                p.drawPixmap(x, 6, pm)
                x += pm.width() + 4
        role_ = s.get("role", "general")
        if role_ != "general" and not self.library:
            f.setPixelSize(small)
            f.setBold(False)
            p.setFont(f)
            p.setPen(QColor("#9aa4b2"))
            p.drawText(QRectF(x, 4, W * 0.5, small + 6), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       t("builds.slot." + role_).upper())
        # drain and the mod's polarity (top right)
        if name and s.get("drain") is not None and role_ != "arcane":
            d = s["drain"]
            txt = str(abs(d)) if d >= 0 else f"+{abs(d)}"
            state = s.get("state") or ""
            f.setPixelSize(big)
            f.setBold(True)
            p.setFont(f)
            fm = QFontMetrics(f)
            mp = icons.polarity(s.get("mpol") or "", max(12, int(H * 0.16))) if s.get("mpol") else None
            bw = fm.horizontalAdvance(txt) + (mp.width() + 4 if mp is not None else 0) + 12
            box = QRectF(W - bw - 6, 5, bw, big + 6)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, 150))
            p.drawRoundedRect(box, 4, 4)
            p.setPen(QColor({"match": "#7ee08f", "mismatch": "#ff7b72"}.get(state, "#ffffff")))
            p.drawText(box.adjusted(6, 0, 0, 0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, txt)
            if mp is not None:
                p.drawPixmap(int(box.right() - mp.width() - 5), int(box.center().y() - mp.height() / 2), mp)
        # the name (or the Riven's stats)
        rv = s.get("riven")
        if rv and rv.get("attributes"):
            f.setPixelSize(max(8, int(H * 0.105)))
            f.setBold(False)
            p.setFont(f)
            lines = _riven_lines(rv)
            y = H * 0.26
            for txt, c in lines[:4]:
                p.setPen(QColor(c))
                p.drawText(QRectF(8, y, W - 16, H * 0.14), Qt.AlignmentFlag.AlignCenter,
                           QFontMetrics(f).elidedText(txt, Qt.TextElideMode.ElideRight, W - 16))
                y += H * 0.14
        if name:
            f.setPixelSize(max(10, int(H * 0.17)))
            f.setBold(False)
            p.setFont(f)
            p.setPen(QColor("#ffffff"))
            label = name.replace(" (Riven)", "")
            area = QRectF(8, H * (0.62 if rv and rv.get("attributes") else 0.36), W - 16, H * 0.36)
            if s.get("role") == "arcane" and self.pic is not None:
                area = QRectF(W * 0.06 + self.pic.width() + 6, H * 0.2, W - W * 0.06 - self.pic.width() - 12, H * 0.5)
            p.drawText(area, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, label)
            mx = s.get("max")
            if mx:
                f.setPixelSize(max(8, int(H * 0.11)))
                p.setFont(f)
                p.setPen(QColor("#5fb8ff"))
                p.drawText(QRectF(0, H * 0.80, W, H * 0.16), Qt.AlignmentFlag.AlignCenter, pips(s.get("rank"), mx))
        elif not self.locked:
            p.setPen(QColor("#4b5260"))
            f.setPixelSize(big)
            p.setFont(f)
            spm = icons.build(role_, int(H * 0.42)) if role_ in ("aura", "exilus", "stance") else None
            if spm is not None:                         # an empty Aura / Exilus / Stance slot: its own picture, faint
                p.setOpacity(0.35)
                p.drawPixmap(int((W - spm.width()) / 2), int((H - spm.height()) / 2), spm)
                p.setOpacity(1.0)
            else:
                p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "—")
        if self.locked:
            f.setPixelSize(max(14, int(H * 0.3)))
            p.setFont(f)
            p.setPen(QColor("#8b93a3"))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "🔒")
        if self.owned and self.library:
            f.setPixelSize(max(8, int(H * 0.11)))
            f.setBold(True)
            p.setFont(f)
            txt = f"×{self.owned['n']}"
            fm = QFontMetrics(f)
            box = QRectF(6, H - fm.height() - 8, fm.horizontalAdvance(txt) + 8, fm.height() + 2)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, 160))
            p.drawRoundedRect(box, 3, 3)
            p.setPen(QColor("#ffd98a"))
            p.drawText(box, Qt.AlignmentFlag.AlignCenter, txt)
        p.end()

    def _paint_arcane(self, p, W, H):
        """An Arcane as the game draws it: no card, the Arcane's generic picture (its rarity's), the name under it, the
        rank as ◈ / ◇. An empty slot: the outline of an Arcane, with a lock when the slot is not unlocked."""
        name, s = self.name, self.slot
        icon_h = int(H * (0.58 if name else 0.66))
        top = 4
        if self.selected:
            g = QRadialGradient(QPointF(W / 2, top + icon_h / 2), icon_h * 0.9)
            g.setColorAt(0, QColor(95, 215, 230, 90))
            g.setColorAt(1, QColor(95, 215, 230, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(g))
            p.drawEllipse(QPointF(W / 2, top + icon_h / 2), icon_h * 0.9, icon_h * 0.9)
        pm = icons.arcane(name, icon_h) if name else icons.build("arcane_empty", icon_h)
        if pm is not None and not pm.isNull():
            p.drawPixmap(int((W - pm.width()) / 2), top, pm)
        else:                                          # no icons folder (or an empty slot): a drawn Arcane frame
            col = QColor(self.frame or ("#c4c9d4" if name else "#3f4652"))
            _arcane_shape(p, QRectF((W - icon_h * 1.45) / 2, top, icon_h * 1.45, icon_h), col, filled=bool(name))
        if self.locked:
            f = QFont(self.font())
            f.setPixelSize(max(12, int(icon_h * 0.36)))
            p.setFont(f)
            p.setPen(QColor("#9aa4b2"))
            p.drawText(QRectF(0, top, W, icon_h), Qt.AlignmentFlag.AlignCenter, "🔒")
        f = QFont(self.font())
        if name:
            f.setPixelSize(max(10, int(H * 0.16)))
            f.setBold(True)
            p.setFont(f)
            p.setPen(QColor("#d6dae2"))
            p.drawText(QRectF(2, top + icon_h + 1, W - 4, H * 0.2), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                       QFontMetrics(f).elidedText(name, Qt.TextElideMode.ElideRight, W - 4))
            mx = s.get("max") or 0
            if mx:
                r = mx if s.get("rank") is None else max(0, min(int(s["rank"]), mx))
                f.setPixelSize(max(9, int(H * 0.12)))
                f.setBold(False)
                p.setFont(f)
                p.setPen(QColor("#c9ced8"))
                p.drawText(QRectF(0, top + icon_h + H * 0.2, W, H * 0.16), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                           " ".join("◈" if k < r else "◇" for k in range(mx)))
        elif not self.locked:
            f.setPixelSize(max(9, int(H * 0.11)))
            p.setFont(f)
            p.setPen(QColor("#6b7280"))
            p.drawText(QRectF(0, top + icon_h + 2, W, H * 0.2), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                       t("builds.slot.arcane").upper())

    # --- mouse, drag and drop ---
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._press = e.position().toPoint()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self.library and self._press is not None and (e.position().toPoint() - self._press).manhattanLength() > 8:
            self._press = None
            drag = QDrag(self)
            md = QMimeData()
            md.setData(MIME, self.name.encode("utf-8"))
            drag.setMimeData(md)
            drag.setPixmap(self.grab())
            drag.exec(Qt.DropAction.CopyAction)
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self._press is not None and (self.editable or self.library):
            self.clicked.emit()
        self._press = None
        super().mouseReleaseEvent(e)

    def dragEnterEvent(self, e):
        if e.mimeData().hasFormat(MIME):
            e.acceptProposedAction()

    def dropEvent(self, e):
        name = bytes(e.mimeData().data(MIME)).decode("utf-8")
        if name:
            self.dropped.emit(name)
            e.acceptProposedAction()


def _arcane_shape(p, r: QRectF, col: QColor, filled=True):
    """The generic Arcane frame: a half dome on a base, with the round emblem in the middle (drawn when the icons
    folder is not set, and as the outline of an empty slot)."""
    p.save()
    w, h = r.width(), r.height()
    cx, base = r.center().x(), r.top() + h * 0.86
    dome = QPainterPath()
    dome.moveTo(r.left() + w * 0.06, base)
    dome.arcTo(QRectF(r.left() + w * 0.06, r.top() + h * 0.06, w * 0.88, h * 1.6), 180, -180)
    dome.closeSubpath()
    pen = QPen(col, max(1.5, h * 0.045))
    if not filled:
        pen.setStyle(Qt.PenStyle.DashLine)
    p.setPen(pen)
    p.setBrush(QColor(col.red(), col.green(), col.blue(), 50) if filled else Qt.BrushStyle.NoBrush)
    p.drawPath(dome)
    p.drawRoundedRect(QRectF(r.left(), base - h * 0.02, w, h * 0.12), 3, 3)
    rad = h * 0.3
    emblem = QPointF(cx, r.top() + h * 0.48)
    p.setBrush(QColor(15, 30, 40, 220) if filled else Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor("#4fe3f0") if filled else col, max(1.5, h * 0.04)))
    p.drawEllipse(emblem, rad, rad)
    if filled:
        p.drawEllipse(emblem, rad * 0.45, rad * 0.45)
    p.restore()


def library_slot(name, info, arcane=False) -> dict:
    mx = (info[2] if info else 0) if not arcane else _arcane_max(name)
    return {"role": "arcane" if arcane else "general", "name": name, "rank": mx, "max": mx, "pol": "",
            "mpol": info[0] if info else "", "drain": (info[1] + mx if info[1] >= 0 else info[1] - mx) if info else None,
            "state": ""}


def _arcane_max(name):
    for n, mx in LO.data().get("arcanes", {}).values():
        if n == name:
            return mx or 5
    return 5


# ---------- the stats panel on the left ----------
def _fmt(key, v):
    if isinstance(v, str):
        return v
    if key in ("crit_chance", "status"):
        return f"{v * 100:.1f}%".replace(".0%", "%")
    if key == "crit_damage":
        return f"{v:.2f}x".replace(".00x", "x")
    if key in ("reload",):
        return f"{v:.2f}s"
    if key in ("range",):
        return f"{v:.1f}m"
    if key in ("combo",):
        return f"{v:g}s"
    if key in ("follow",):
        return f"{v * 100:.0f}%"
    if key in ("magazine",):
        return f"{int(round(v))}"
    if abs(v) >= 1000:
        return f"{v:,.0f}"
    if abs(v - round(v)) < 1e-6 and key not in ("crit_damage",):
        return str(int(round(v)))
    return f"{v:.2f}".rstrip("0").rstrip(".") if abs(v) < 100 else f"{v:.1f}"


def _icon_html(f, size=14) -> str:
    return f"<img src='{QUrl.fromLocalFile(f).toString()}' width='{size}' height='{size}'>&nbsp;" if f else ""


def _row(grid, r, label, base, val, key="", better_high=True, bold=False, icon=None):
    """A stat line: [icon] label … base ▸ value. icon: a picture file (AlecaFrame's icons folder) or None."""
    lab = QLabel(_icon_html(icon) + escape_html(label) if icon else label)
    lab.setStyleSheet("color: #c9ced8;" + (" font-weight: bold;" if bold else ""))
    grid.addWidget(lab, r, 0)
    same = isinstance(base, str) or base is None or abs(float(base) - float(val)) < 1e-6
    if same:
        txt = _fmt(key, val)
    else:
        up = (float(val) > float(base)) == better_high
        txt = (f"<span style='color:#8b93a3'>{_fmt(key, base)}</span> ▸ "
               f"<span style='color:{UP if up else DOWN}'>{_fmt(key, val)}</span>")
    v = QLabel(txt)
    v.setAlignment(Qt.AlignmentFlag.AlignRight)
    v.setStyleSheet("font-weight: bold;")
    grid.addWidget(v, r, 1)


def _head(text):
    h = QLabel(text.upper())
    h.setStyleSheet("font-weight: bold; color: #ffffff; letter-spacing: 1px; margin-top: 8px;")
    return h


PANEL_W = 300


def capacity_detail(m: dict) -> str:
    """Capacity, slot by slot (tooltip): the slot's polarity and where it comes from (Forma in the game file, the item's
    own, placed where it fits best), the mod, its rank and drain. To compare with the game when the numbers differ."""
    from html import escape
    rows = []
    for s in m.get("slots") or []:
        if s.get("role") == "arcane":
            continue
        pol = t("pol." + s["pol"]) if s.get("pol") else t("pol.none")
        src = {"forma": " (Forma)", "innate": " (" + t("bs.cap.innate") + ")"}.get(s.get("pol_src") or "", "")
        role = t("builds.slot." + s["role"]) if s.get("role") not in (None, "general") else ""
        if s.get("name"):
            dr = s.get("drain")
            drain = "" if dr is None else (f"+{-dr}" if dr < 0 else str(dr))
            mod = f"{escape(s['name'])} r{s['rank'] if s.get('rank') is not None else '?'}/{s.get('max') or '?'}"
            rows.append(f"{role + ' · ' if role else ''}{mod}: <b>{drain}</b> · {pol}{src}")
        elif role:
            rows.append(f"{role}: — · {pol}{src}")
    return "<br>".join(rows)


def stats_panel(m: dict) -> QFrame:
    """CAPACITY used/total with its bar, then the stats: a Warframe's (health… strength), a weapon's (fire rate…, crit,
    status, every damage type, total, DPS), the Kuva / Tenet / Coda bonus element, the other bonuses of the mods."""
    box = QFrame()
    box.setObjectName("bsstats")
    box.setStyleSheet("#bsstats { background: rgba(10, 8, 16, 170); border: 1px solid #3a3346; border-radius: 4px; }"
                      " #bsstats QLabel { background: transparent; }")
    lay = QVBoxLayout(box)
    lay.setContentsMargins(10, 8, 10, 10)
    lay.setSpacing(2)
    cap = m.get("capacity")
    if cap:
        used, total = cap.get("used", 0), cap.get("total", 0)
        head = QHBoxLayout()
        a = QLabel(t("builds.capacity").upper())
        a.setStyleSheet("font-size: 15px; font-weight: bold; letter-spacing: 1px;")
        b = QLabel(f"{total - used}/{total}")               # as the game shows it: capacity left / total
        b.setToolTip(t("bs.cap.tip", used=used, total=total))
        b.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {DOWN if used > total else '#ffffff'};")
        head.addWidget(a)
        head.addStretch(1)
        head.addWidget(b)
        lay.addLayout(head)
        bar = QFrame()
        bar.setFixedHeight(5)
        frac = 0 if not total else max(0.0, min(1.0, used / total))
        fill = DOWN if used > total else "#d8dde6"
        bar.setStyleSheet(f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {fill}, stop:{frac:.3f} {fill},"
                          f" stop:{min(1.0, frac + 0.001):.3f} #3b3f48, stop:1 #3b3f48); border-radius: 2px;")
        detail = capacity_detail(m)
        bar.setToolTip(t("builds.capacity.tip", level=m.get("level", 30), reactor=t("builds.reactor") if m.get("reactor") else "")
                       + ("<br><br>" + detail if detail else ""))
        b.setToolTip(b.toolTip() + ("<br><br>" + detail if detail else ""))
        lay.addWidget(bar)
    elif m.get("capacity_none"):
        c = QLabel(t("builds.capacity.none"))
        c.setWordWrap(True)
        role(c, "hint")
        lay.addWidget(c)
    if m.get("valence"):
        lay.addWidget(_head(t("bs.valence")))
        g = QGridLayout()
        _row(g, 0, t("dmg." + m["valence"]["element"].lower()), None, f"{m['valence']['pct']:.1f}%".replace(".0%", "%"),
             icon=icons.damage_path(m["valence"]["element"]))
        lay.addLayout(g)
    wf = m.get("wf_stats") or {}
    if wf:
        base = m.get("wf_base") or {}
        g = QGridLayout()
        g.setVerticalSpacing(1)
        fmt = {"sprint": lambda v: v, "duration": lambda v: v, "efficiency": lambda v: v, "range": lambda v: v,
               "strength": lambda v: v}
        r = 0
        for key in BC.STAT_ORDER[:5]:
            if key in wf:
                _row(g, r, t("builds.stat." + key), base.get(key), wf[key], "sprint" if key == "sprint" else "",
                     icon=icons.stat_path(key))
                r += 1
        lay.addLayout(g)
        lay.addWidget(_head(t("bs.ability")))
        g = QGridLayout()
        g.setVerticalSpacing(1)
        r = 0
        for key in BC.STAT_ORDER[5:]:
            if key in wf:
                f = icons.stat_path(key)
                lab = QLabel(_icon_html(f) + escape_html(t("builds.stat." + key)) if f else t("builds.stat." + key))
                lab.setStyleSheet("color: #c9ced8;")
                g.addWidget(lab, r, 0)
                v = QLabel(f"{wf[key]:g}%")
                v.setAlignment(Qt.AlignmentFlag.AlignRight)
                v.setStyleSheet("font-weight: bold;" + (f" color: {UP};" if wf[key] > 100 else (f" color: {DOWN};" if wf[key] < 100 else "")))
                g.addWidget(v, r, 1)
                r += 1
        lay.addLayout(g)
        _ = fmt
    ws = m.get("weapon")
    if ws:
        lay.addWidget(_head(t("bs.sec." + ("melee" if ws["melee"] else "gun"))))
        g = QGridLayout()
        g.setVerticalSpacing(1)
        for r, (key, b0, b1) in enumerate(ws["rows"]):
            _row(g, r, t("bs.stat." + key), b0, b1, key, better_high=key != "reload", icon=icons.stat_path(key))
        lay.addLayout(g)
        lay.addWidget(_head(t("bs.sec.damage")))
        g = QGridLayout()
        g.setVerticalSpacing(1)
        r = 0
        for key, b0, b1 in ws["crit"]:
            _row(g, r, t("bs.stat." + key), b0, b1, key, icon=icons.stat_path(key))
            r += 1
        for el, b0, b1 in ws["damage"]:
            _row(g, r, t("dmg." + el.lower()), b0, b1, icon=icons.damage_path(el))
            r += 1
        _row(g, r, t("bs.stat.total"), ws["total"][0], ws["total"][1], bold=True)
        _row(g, r + 1, t("bs.stat.dps"), ws["dps"][0], ws["dps"][1], bold=True)
        g.itemAtPosition(r + 1, 0).widget().setToolTip(t("bs.stat.dps.tip"))
        lay.addLayout(g)
    bonus = m.get("bonus") or {}
    if ws:
        shown = {"Damage", "Melee Damage", "Multishot", "Critical Chance", "Critical Damage", "Status Chance",
                 "Fire Rate", "Attack Speed", "Magazine Capacity", "Reload Speed", "Impact", "Puncture", "Slash"} \
            | set(BC.ELEMENTS) | set(BC.COMBINED)
        bonus = {k: v for k, v in bonus.items() if k not in shown}
    if bonus and not wf:
        lay.addWidget(_head(t("bs.sec.other")))
        g = QGridLayout()
        g.setVerticalSpacing(1)
        for r, (label, v) in enumerate(bonus.items()):
            lab = QLabel(label)
            lab.setStyleSheet("color: #c9ced8;")
            lab.setWordWrap(True)
            g.addWidget(lab, r, 0)
            val = QLabel(f"{v:+g}%")
            val.setAlignment(Qt.AlignmentFlag.AlignRight)
            val.setStyleSheet("font-weight: bold;")
            g.addWidget(val, r, 1)
        lay.addLayout(g)
    note = QLabel(t("bs.note." + ("wf" if wf else "weapon" if ws else "other")))
    note.setWordWrap(True)
    role(note, "hint")
    note.setStyleSheet("margin-top: 6px;")
    lay.addWidget(note)
    lay.addStretch(1)
    box.setFixedWidth(PANEL_W)                       # a fixed width, so the height the text needs is known
    box.setMinimumHeight((lay.totalHeightForWidth(PANEL_W) if lay.hasHeightForWidth() else lay.sizeHint().height()) + 16)
    return box


# ---------- the Incarnon evolution path ----------
class IncarnonPath(QWidget):
    """The evolution tiers (I…V) left to right, the perks of each tier stacked, the chosen ones lit and joined by a
    glowing line (like the game's Incarnon screen); tiers not unlocked are dim. Editable: click a perk to choose it."""
    picked = pyqtSignal(int, int)

    COL_W, NODE, ROW_H = 150, 14, 56

    def __init__(self, tiers, chosen, unlocked, editable=False, count=None):
        super().__init__()
        self.tiers = [list(x) for x in (tiers or [])]
        # as many tiers as the weapon has: Evolution V only where it exists (Incarnon built in)
        n = count or max(len(self.tiers), 4)
        self.tiers = self.tiers[:n]
        chosen = list(chosen or [])[:n]
        while len(self.tiers) < n:
            self.tiers.append([])
        self.chosen = list(chosen or []) + [-1] * (n - len(chosen or []))
        self.unlocked, self.editable = unlocked, editable
        self.setMouseTracking(True)
        rows = max([max(1, len(x)) for x in self.tiers] + [1])
        self.setMinimumSize(self.COL_W * n + 20, 30 + rows * self.ROW_H)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

    def _nodes(self):
        """[(tier, index, centre, name)] — a tier without names still has one node (its perk, unnamed)."""
        out = []
        h = self.height()
        for ti, names in enumerate(self.tiers):
            opts = names or [""]
            x = 10 + ti * self.COL_W + self.COL_W / 2
            top = 28 + (h - 28 - len(opts) * self.ROW_H) / 2
            for k, name in enumerate(opts):
                out.append((ti, k, QPointF(x, top + k * self.ROW_H + self.ROW_H / 2 - 8), name))
        return out

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        f = QFont(self.font())
        f.setPixelSize(11)
        p.setFont(f)
        fm = QFontMetrics(f)
        nodes = self._nodes()
        lit = [nd for nd in nodes if self.chosen[nd[0]] == nd[1] and nd[0] < self.unlocked]
        # tier headers
        for ti in range(len(self.tiers)):
            on = ti < self.unlocked
            p.setPen(QColor("#ffffff" if on else "#6b7280"))
            p.drawText(QRectF(10 + ti * self.COL_W, 4, self.COL_W, 18), Qt.AlignmentFlag.AlignHCenter,
                       t("bs.inc.tier", n=["I", "II", "III", "IV", "V"][ti] if ti < 5 else ti + 1))
        # the glowing line through the chosen perks
        lit.sort(key=lambda nd: nd[0])
        for a, b in zip(lit, lit[1:]):
            if b[0] != a[0] + 1:
                continue
            for wdt, alpha in ((7, 50), (3, 140), (1.5, 255)):
                p.setPen(QPen(QColor(95, 215, 230, alpha), wdt))
                p.drawLine(a[2], b[2])
        for ti, k, c, name in nodes:
            on = ti < self.unlocked
            chosen = self.chosen[ti] == k
            r = self.NODE
            if chosen and on:
                g = QRadialGradient(c, r * 2.2)
                g.setColorAt(0, QColor(95, 215, 230, 150))
                g.setColorAt(1, QColor(95, 215, 230, 0))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(g))
                p.drawEllipse(c, r * 2.2, r * 2.2)
            p.setBrush(QColor("#0b0d12"))
            p.setPen(QPen(QColor(ACCENT if chosen and on else ("#5d6676" if on else "#363b45")), 2))
            if ti == 0:                                    # tier I: a diamond, as the game draws the Incarnon form
                path = QPainterPath()
                path.moveTo(c.x(), c.y() - r)
                path.lineTo(c.x() + r, c.y())
                path.lineTo(c.x(), c.y() + r)
                path.lineTo(c.x() - r, c.y())
                path.closeSubpath()
                p.drawPath(path)
            else:
                p.drawEllipse(c, r, r)
            if chosen and on:
                p.setBrush(QColor(ACCENT))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(c, r * 0.38, r * 0.38)
            label = name or (t("inc.form") if ti == 0 else ("—" if not on else "?"))
            text = fm.elidedText(label, Qt.TextElideMode.ElideRight, self.COL_W - 10)
            box = QRectF(c.x() - self.COL_W / 2 + 5, c.y() + r + 3, self.COL_W - 10, 16)
            p.setPen(Qt.PenStyle.NoPen)                      # a dark band under the name: readable over the line
            p.setBrush(QColor(11, 13, 18, 200))
            tw = fm.horizontalAdvance(text) + 8
            p.drawRoundedRect(QRectF(c.x() - tw / 2, box.y(), tw, 16), 3, 3)
            p.setPen(QColor("#ffffff" if chosen and on else ("#aab2c0" if on else "#5b6270")))
            p.drawText(box, Qt.AlignmentFlag.AlignCenter, text)
        p.end()

    def _hit(self, pos):
        for ti, k, c, name in self._nodes():
            if abs(pos.x() - c.x()) <= self.COL_W / 2 - 4 and -self.NODE - 4 <= pos.y() - c.y() <= self.NODE + 20:
                return ti, k, name
        return None

    def mouseMoveEvent(self, e):
        hit = self._hit(e.position())
        if hit and hit[2]:
            QToolTip.showText(e.globalPosition().toPoint(), hit[2], self)
        self.setCursor(Qt.CursorShape.PointingHandCursor if hit and self.editable else Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, e):
        hit = self._hit(e.position())
        if hit and self.editable and e.button() == Qt.MouseButton.LeftButton:
            self.picked.emit(hit[0], hit[1])


# ---------- the mod library ----------
class ModLibrary(QWidget):
    """Search, polarity filter, sort and the compatible mods as two rows of cards (scroll sideways). picked(name): a card
    was clicked."""
    picked = pyqtSignal(str)
    LIMIT = 240

    def __init__(self):
        super().__init__()
        self.names, self.owned, self.arcane, self.cw, self._sig = [], {}, False, 110, None
        self.search = QLineEdit()
        self.search.setPlaceholderText(t("bs.lib.search"))
        self.search.setClearButtonEnabled(True)
        self.search.setMaximumWidth(320)
        self.pols = QButtonGroup(self)
        self.pols.setExclusive(True)
        bar = QHBoxLayout()
        bar.addWidget(self.search)
        bar.addSpacing(10)
        for n, pol in enumerate([""] + BC.POLARITIES[:-1]):
            b = QToolButton()
            b.setCheckable(True)
            b.setChecked(pol == "")
            if pol:
                pm = icons.polarity(pol, 18)
                if pm is not None:
                    b.setIcon(__import__("PyQt6.QtGui", fromlist=["QIcon"]).QIcon(pm))
                b.setToolTip(t("pol." + pol))
            else:
                b.setText("∞")
                b.setToolTip(t("bs.lib.all"))
            b.setProperty("pol", pol)
            self.pols.addButton(b, n)
            bar.addWidget(b)
        bar.addSpacing(10)
        self.sort = QComboBox()
        for key in ("rank", "name", "drain", "polarity", "owned"):
            self.sort.addItem(t("bs.lib.sort." + key), key)
        self.only_owned = QCheckBox(t("bs.lib.owned"))
        self.only_owned.setToolTip(t("bs.lib.owned.tip"))
        self.count = QLabel("")
        role(self.count, "muted")
        bar.addWidget(self.count)
        bar.addStretch(1)
        bar.addWidget(self.only_owned)
        bar.addWidget(QLabel(t("bs.lib.sortby")))
        bar.addWidget(self.sort)
        self.what = QLabel("")
        self.what.setStyleSheet("font-weight: bold; letter-spacing: 1px;")
        self.host = QWidget()
        self.grid = QGridLayout(self.host)
        self.grid.setContentsMargins(2, 2, 2, 2)
        self.grid.setSpacing(6)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.scroll = QScrollArea()
        self.scroll.setWidget(self.host)
        self.scroll.setWidgetResizable(False)          # the cards keep their size: the strip scrolls sideways
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.addWidget(self.what)
        lay.addLayout(bar)
        lay.addWidget(self.scroll)
        self._timer = QTimer(self, singleShot=True, interval=180, timeout=self._fill)
        self.search.textChanged.connect(lambda _t: self._timer.start())
        self.pols.idClicked.connect(lambda _i: self._fill())
        self.sort.currentIndexChanged.connect(lambda _i: self._fill())
        self.only_owned.toggled.connect(lambda _c: self._fill())

    def set_mods(self, names, owned, arcane=False, what="", cw=110):
        sig = (tuple(names), id(owned), arcane, cw)
        self.what.setText(what.upper())
        if sig == self._sig:
            return
        self._sig = sig
        self.names, self.owned, self.arcane, self.cw = list(names), owned or {}, arcane, cw
        self.only_owned.setEnabled(bool(self.owned))
        self._fill()

    def _fill(self):
        text = self.search.text().strip().lower()
        pol = self.pols.checkedButton().property("pol") if self.pols.checkedButton() else ""
        rows = []
        for n in self.names:
            if text and text not in n.lower():
                continue
            info = None if self.arcane else BC.mod_info(n)
            if pol and (not info or info[0] != pol):
                continue
            own = self.owned.get(n)
            if self.only_owned.isChecked() and self.owned and not own:
                continue
            rows.append((n, info, own))
        key = self.sort.currentData()
        rk = {"C": 0, "U": 1, "R": 2, "L": 3}
        if key == "name":
            rows.sort(key=lambda r: r[0].lower())
        elif key == "drain":
            rows.sort(key=lambda r: (-(r[1][1] + r[1][2]) if r[1] else 0, r[0].lower()))
        elif key == "polarity":
            rows.sort(key=lambda r: ((r[1] or [""])[0] or "~", r[0].lower()))
        elif key == "owned":
            rows.sort(key=lambda r: (not r[2], -((r[2] or {}).get("n", 0)), r[0].lower()))
        else:                                   # rank: the highest max rank, then rarity
            rows.sort(key=lambda r: (-((r[1] or [0, 0, _arcane_max(r[0])])[2]),
                                     -rk.get(rarity(r[0], self.arcane), 0), r[0].lower()))
        self.host.setUpdatesEnabled(False)
        _clear(self.grid)
        cw = self.cw
        for k, (n, info, own) in enumerate(rows[:self.LIMIT]):
            c = Card(library_slot(n, info, self.arcane), cw, library=True, owned=own)
            c.clicked.connect(lambda n=n: self.picked.emit(n))
            self.grid.addWidget(c, k % 2, k // 2)
        n = min(len(rows), self.LIMIT)                  # not resized by the scroll area: as wide as its cards
        ch = int(cw * CARD_ASPECT)
        self.host.resize(max(1, (n + 1) // 2) * (cw + 6) + 4, 2 * ch + 6 + 4)
        self.host.setUpdatesEnabled(True)
        self.count.setText(t("bs.lib.count", n=len(rows)) + (" " + t("bs.lib.limit", n=self.LIMIT) if len(rows) > self.LIMIT else ""))
        h = int(cw * CARD_ASPECT) * 2 + 6 * 3 + self.scroll.horizontalScrollBar().sizeHint().height() + 4
        self.scroll.setFixedHeight(h)


# ---------- the screen ----------
class BuildScreen(QWidget):
    """Shows a build model (see show()). In the planner (editable) it reports the user's actions:
    slot_clicked(i), slot_menu(i, global pos), slot_dropped(i, name), config_selected(i), config_added(),
    perk_picked(tier, index)."""
    slot_clicked = pyqtSignal(int)
    slot_menu = pyqtSignal(int, QPoint)
    slot_dropped = pyqtSignal(int, str)
    config_selected = pyqtSignal(int)
    config_added = pyqtSignal()
    perk_picked = pyqtSignal(int, int)

    def __init__(self, editable=False):
        super().__init__()
        self.editable = editable
        self.setObjectName("buildscreen")
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(6)
        self.lay.setAlignment(Qt.AlignmentFlag.AlignTop)

    def clear(self):
        _clear(self.lay)

    def show_model(self, m: dict, cw: int, extra_top=None):
        """m: {"kind","item","title","rank","forma","configs": [{"label","active","tip"}], "slots", "capacity",
        "wf_stats","wf_base","weapon","bonus","valence","incarnon": {"tiers","chosen","unlocked","head","pic"},
        "locked": {"exilus","arcane"}, "selected", "subtitle"}. extra_top: a widget put under the configuration tabs
        (the planner's options)."""
        self.setUpdatesEnabled(False)
        try:
            self.clear()
            self._title(m)
            self._configs(m)
            if extra_top is not None:
                self.lay.addWidget(extra_top)
            body = QHBoxLayout()
            body.setSpacing(14)
            body.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            body.addWidget(stats_panel(m), 0, Qt.AlignmentFlag.AlignTop)
            body.addLayout(self._slots(m, cw), 1)
            wrap = QWidget()
            wrap.setLayout(body)
            self.lay.addWidget(wrap)
            if m.get("incarnon"):
                self._incarnon(m["incarnon"])
        finally:
            self.setUpdatesEnabled(True)

    def _title(self, m):
        row = QHBoxLayout()
        row.setSpacing(10)
        pic = m.get("pic")
        if pic is not None:
            lab = QLabel()
            lab.setPixmap(pic)
            row.addWidget(lab)
        title = QLabel(f"{t('bs.upgrades')} / {m.get('title') or m.get('item', '')}"
                       + (f"  [{m['rank']}]" if m.get("rank") is not None else ""))
        title.setStyleSheet("font-size: 22px; font-weight: 300; letter-spacing: 3px;")
        row.addWidget(title)
        if m.get("forma") is not None:
            pm = icons.build("forma", 26)
            if pm is not None:                          # AlecaFrame's Forma picture, else a star
                ic = QLabel()
                ic.setPixmap(pm)
                ic.setToolTip(t("bs.forma.tip", n=m["forma"]))
                row.addWidget(ic)
            fm = QLabel(f"{'' if pm is not None else '✦ '}{m['forma']}")
            fm.setToolTip(t("bs.forma.tip", n=m["forma"]))
            fm.setStyleSheet("font-size: 18px; color: #e0c46c;" + ("" if pm is not None else " margin-left: 6px;"))
            row.addWidget(fm)
        for key, on, tip in m.get("upgrades") or []:      # Orokin Reactor / Catalyst, adapters: lit when installed
            pm = icons.build(key, 26)
            if pm is None:
                continue
            ic = QLabel()
            if not on:
                from PyQt6.QtGui import QPixmap as _QP
                faded = _QP(pm.size())
                faded.fill(Qt.GlobalColor.transparent)
                pp = QPainter(faded)
                pp.setOpacity(0.25)
                pp.drawPixmap(0, 0, pm)
                pp.end()
                pm = faded
            ic.setPixmap(pm)
            ic.setToolTip(tip)
            row.addWidget(ic)
        row.addStretch(1)
        self.lay.addLayout(row)
        if m.get("subtitle"):
            sub = QLabel(m["subtitle"])
            sub.setWordWrap(True)
            role(sub, "muted")
            if m.get("subtitle_tip"):
                sub.setToolTip(m["subtitle_tip"])
            self.lay.addWidget(sub)

    def _configs(self, m):
        cfgs = m.get("configs") or []
        if not cfgs and not self.editable:
            return
        row = QHBoxLayout()
        row.setSpacing(2)
        row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        group = QButtonGroup(self)
        group.setExclusive(True)
        for i, c in enumerate(cfgs):
            b = QPushButton(c["label"].upper())
            b.setCheckable(True)
            b.setChecked(bool(c.get("active")))
            b.setFlat(True)
            b.setObjectName("bscfg")
            b.setStyleSheet("#bscfg { font-size: 15px; letter-spacing: 1px; padding: 4px 14px; border: none;"
                            " border-bottom: 3px solid transparent; color: #aab2c0; }"
                            " #bscfg:checked { color: #ffffff; border-bottom: 3px solid #ffffff; }"
                            " #bscfg:hover { color: #ffffff; }")
            if c.get("tip"):
                b.setToolTip(c["tip"])
            b.clicked.connect(lambda _c=False, i=i: self.config_selected.emit(i))
            group.addButton(b)
            row.addWidget(b)
        if self.editable:
            add = QPushButton("⊕")
            add.setFlat(True)
            add.setToolTip(t("bs.cfg.add"))
            add.setStyleSheet("font-size: 18px; border: none; color: #aab2c0; padding: 0 8px;")
            add.clicked.connect(lambda: self.config_added.emit())
            row.addWidget(add)
        self._cfg_group = group
        self.lay.addLayout(row)

    def _card(self, m, i, cw):
        s = m["slots"][i]
        locked = (s["role"] == "exilus" and (m.get("locked") or {}).get("exilus")) or \
                 (s["role"] == "arcane" and (m.get("locked") or {}).get("arcane"))
        c = Card(s, cw, editable=self.editable, selected=self.editable and m.get("selected") == i, locked=bool(locked))
        if self.editable:
            c.clicked.connect(lambda i=i: self.slot_clicked.emit(i))
            c.menu.connect(lambda pos, i=i: self.slot_menu.emit(i, pos))
            c.dropped.connect(lambda name, i=i: self.slot_dropped.emit(i, name))
        return c

    def _slots(self, m, cw):
        """Special slots on top (Exilus of guns on the right), the general ones in rows of four (five for companions),
        the Arcanes on the right."""
        slots = m["slots"]
        guns = m.get("kind") in ("primary", "secondary", "archgun")
        special = [i for i, s in enumerate(slots) if s["role"] in ("aura", "stance") or (s["role"] == "exilus" and not guns)]
        right = [i for i, s in enumerate(slots) if s["role"] == "arcane"] + \
                [i for i, s in enumerate(slots) if s["role"] == "exilus" and guns]
        general = [i for i, s in enumerate(slots) if s["role"] == "general"]
        cols = 5 if len(general) == 10 else 4
        out = QHBoxLayout()
        out.setSpacing(14)
        out.setAlignment(Qt.AlignmentFlag.AlignTop)
        g = QGridLayout()
        g.setSpacing(8)
        g.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        top = 0
        if special:
            start = max(0, (cols - len(special)) // 2)
            for n, i in enumerate(special):
                g.addWidget(self._card(m, i, cw), 0, start + n)
            top = 1
        elif m.get("unique"):                            # Kuva / Tenet / Coda: the row the game calls UNIQUE TRAIT
            lab = QLabel("◈  " + t("bs.unique").upper())
            lab.setFixedHeight(22)
            lab.setStyleSheet("font-size: 15px; font-weight: bold; letter-spacing: 1px;")
            g.addWidget(lab, 0, 0, 1, cols)
            top = 1
        for n, i in enumerate(general):
            g.addWidget(self._card(m, i, cw), top + n // cols, n % cols)
        out.addLayout(g)
        if right:
            col = QVBoxLayout()
            col.setSpacing(8)
            col.setAlignment(Qt.AlignmentFlag.AlignTop)
            if special or m.get("unique"):                  # level with the first row of mods
                col.addSpacing(int(cw * CARD_ASPECT) + 8 if special else 30)
            for i in right:
                col.addWidget(self._card(m, i, cw))
            out.addLayout(col)
        out.addStretch(1)
        return out

    def _incarnon(self, inc):
        head = QHBoxLayout()
        lab = QLabel(("✦  " + t("builds.sec.incarnon")).upper())
        lab.setStyleSheet(f"font-weight: bold; letter-spacing: 1px; color: {ACCENT}; margin-top: 6px;")
        head.addWidget(lab)
        if inc.get("head"):
            sub = QLabel(inc["head"])
            role(sub, "muted")
            head.addWidget(sub)
        head.addStretch(1)
        self.lay.addLayout(head)
        if inc.get("note"):
            n = QLabel(inc["note"])
            n.setWordWrap(True)
            role(n, "hint")
            self.lay.addWidget(n)
        if inc.get("show_path", True):
            path = IncarnonPath(inc.get("tiers"), inc.get("chosen"), inc.get("unlocked", 0), editable=self.editable,
                                count=inc.get("count"))
            path.setToolTip(t("inc.tip"))
            if self.editable:
                path.picked.connect(self.perk_picked.emit)
            sc = QScrollArea()
            sc.setWidget(path)
            sc.setWidgetResizable(False)
            sc.setFrameShape(QFrame.Shape.NoFrame)
            sc.setFixedHeight(path.minimumHeight() + 18)
            sc.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            path.resize(path.minimumSize())
            self.lay.addWidget(sc)


def wf_base_stats(item: str) -> dict:
    """A Warframe's stats at rank 30 without mods (for the base ▸ modded arrows)."""
    fr = LO.data().get("frames", {}).get(item)
    if not fr:
        return {}
    return {"health": fr[0], "shield": fr[1], "armor": fr[2], "energy": fr[3], "sprint": fr[4]}


def incarnon_model(inc_kind: str, page: str, chosen: list, unlocked: int, head: str = "", note: str = "") -> dict:
    """The Incarnon part of a model: the perk names of the wiki page (asked in the background when missing)."""
    from app.game import incarnon as INC
    tiers = INC.perks(page) or []
    count = INC.tier_count(inc_kind, page)
    return {"tiers": tiers[:count], "chosen": list(chosen or [])[:count], "unlocked": min(unlocked, count), "count": count,
            "head": head, "note": note, "kind": inc_kind,
            "page": page}
