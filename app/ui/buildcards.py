"""Mod cards laid out like the in-game build screen: Aura / Exilus on top, the 8 mods in two rows of four, the Arcanes on the
right, capacity and the stat recap beside them. Shared by the Builds view of your loadouts and by the build planner."""
from PyQt6.QtCore import QEvent, QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from app.ui import icons
from app.ui import previews
from app.core.i18n import t
from app.core.uiutil import role

CARD_W = 128                                          # default card width; the height keeps the proportion CARD_RATIO
CARD_RATIO = 1.24
MIN_W, MAX_W = 92, 230
STATE_COLOR = {"match": "#4fbf6a", "mismatch": "#e0584a", "": ""}


def card_width(avail: int, height: int = 0) -> int:
    """Card width that makes four mod cards, the Arcane column and the stat panel fill `avail` pixels (Arcane cards are as big as
    the mod cards, so the proportions hold at every size)."""
    panel = min(300, max(190, int(avail * 0.2)))
    rest = avail - panel - 12 - 10 - 18 - 24
    cw = rest // 5
    if height:                                         # three rows of cards (special + two) plus the header should fit too
        cw = min(cw, int((height - 120) / (3 * CARD_RATIO + 0.1)))
    return max(MIN_W, min(MAX_W, cw))


class Scaler(QObject):
    """Redraws a view with a new card width when the scroll area that holds it is resized (debounced, in steps of 6 px)."""

    def __init__(self, view, redraw, area=None, fn=None, start=CARD_W):
        super().__init__(view)
        self.view, self.redraw, self.cw, self.area = view, redraw, start, area
        self.fn = fn or card_width                     # the width rule (portrait cards here, landscape in buildscreen)
        self._viewport = None
        self._timer = QTimer(self, singleShot=True, interval=90, timeout=self._apply)

    def attach(self):
        """Call once the view sits in its scroll area (showEvent)."""
        if self._viewport is not None:
            return
        w = self.area or self.view.parentWidget()
        while w is not None and not isinstance(w, QScrollArea):
            w = w.parentWidget()
        if w is not None:
            self._viewport = w.viewport()
            self._viewport.installEventFilter(self)
            self._timer.start()

    def eventFilter(self, obj, ev):
        if obj is self._viewport and ev.type() == QEvent.Type.Resize:
            self._timer.start()
        return False

    def _apply(self):
        if self._viewport is None:
            return
        cw = self.fn(self._viewport.width(), self._viewport.height())
        if abs(cw - self.cw) >= 6:
            self.cw = cw
            self.redraw()


_pix = {}


def _scaled(path, height):
    """A picture file scaled to a height, kept in a small cache (cards are redrawn at every resize step)."""
    key = (str(path), height)
    pm = _pix.get(key)
    if pm is None:
        if len(_pix) > 600:
            _pix.clear()
        pm = QPixmap(str(path))
        pm = pm.scaledToHeight(height, Qt.TransformationMode.SmoothTransformation) if not pm.isNull() else pm
        _pix[key] = pm
    return pm


def pips(rank, mx) -> str:
    """Rank as diamonds: ◆◆◆◇◇ (a number when the mod has too many ranks to draw)."""
    if not mx:
        return ""
    r = mx if rank is None else max(0, min(int(rank), mx))
    return "◆" * r + "◇" * (mx - r) if mx <= 10 else f"{r}/{mx}"


def _pol_label(pol, size=15):
    lab = QLabel()
    pm = icons.polarity(pol, size) if pol else None
    if pm is not None:
        lab.setPixmap(pm)
    return lab


class ModCard(QFrame):
    """One slot. slot: {"role","name","rank","max","pol","mpol","drain","state"}; role: general|aura|exilus|stance|arcane."""
    clicked = pyqtSignal()

    def __init__(self, slot, clickable=False, cw=CARD_W, fetch=True):
        super().__init__()
        small = max(8, round(cw / 13))
        base = max(9, round(cw / 11))
        name, kind_role = slot.get("name") or "", slot.get("role", "general")
        self.setObjectName("modcard")
        border = "#3a4250" if name else "#2c323c"
        frozen = bool((slot.get("riven") or {}).get("spliced"))
        if frozen:                                      # a spliced Riven: shown "frozen" (Riven Splicers come from Glacial Defiance)
            self.setStyleSheet("#modcard { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1d3a4d, stop:0.55 #18262f,"
                               " stop:1 #1b2027); border: 2px solid #8fd3ff; border-radius: 6px; }"
                               " #modcard QLabel { color: #eaf7ff; background: transparent; }")
        else:
            self.setStyleSheet(f"#modcard {{ background: #1b2027; border: 1px {'solid' if name else 'dashed'} {border}; border-radius: 6px; }}"
                               " #modcard QLabel { color: #e8eaed; background: transparent; }")
        self.setFixedSize(cw, int(cw * CARD_RATIO))
        self._clickable = clickable
        if clickable:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(1)
        top = QHBoxLayout()
        top.setSpacing(3)
        spol = slot.get("pol") or ""
        left = _pol_label(spol, max(14, cw // 9))
        if spol:
            left.setToolTip(t("builds.slotpol", pol=t("pol." + spol)))
        top.addWidget(left)
        cap = QLabel(t("builds.slot." + kind_role) if kind_role != "general" else ("❄ " + t("builds.spliced") if frozen else ""))
        cap.setStyleSheet(f"font-size: {small + 1}px; color: #9aa4b2;")
        top.addWidget(cap)
        top.addStretch(1)
        if name and slot.get("drain") is not None and kind_role != "arcane":
            dr = QLabel(str(abs(slot["drain"])) if slot["drain"] >= 0 else f"+{abs(slot['drain'])}")
            col = STATE_COLOR.get(slot.get("state") or "", "")
            dr.setStyleSheet(f"font-weight: bold; font-size: {base + 1}px;" + (f" color: {col};" if col else ""))
            top.addWidget(dr)
            mp = _pol_label(slot.get("mpol") or "", max(14, cw // 9))
            if slot.get("mpol"):
                mp.setToolTip(t("builds.modpol", pol=t("pol." + slot["mpol"])))
            top.addWidget(mp)
        lay.addLayout(top)
        pic = QLabel()
        pic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pm = None
        if name and kind_role == "arcane":
            pm = icons.arcane(name, int(cw * 0.5))
        elif name and not slot.get("riven"):              # pictures from the Warframe wiki only (Rivens have none)
            f = previews.by_name(name, kind="art", fetch=fetch)       # the mod's artwork inside the card
            f = f or previews.by_name(name, kind="card", fetch=False)
            if f:
                pm = _scaled(f, int(cw * 0.5))
        if pm is not None and not pm.isNull():
            pic.setPixmap(pm if pm.height() == int(cw * 0.5) else pm.scaledToHeight(int(cw * 0.5), Qt.TransformationMode.SmoothTransformation))
        mx0 = slot.get("max")
        rank_txt = (t("builds.rank", rank=mx0 if slot.get("rank") is None else slot["rank"], max=mx0)) if name and mx0 else ""
        if name and kind_role != "arcane" and not slot.get("riven"):
            f = previews.by_name(name, kind="card", fetch=fetch)
            if f:                                           # hover: the whole mod card
                self.setToolTip(f"<b>{name}</b><br><img src='{f.as_posix()}' width='220'><br>{rank_txt}")
            else:
                self.setToolTip(f"<b>{name}</b><br>{rank_txt}")
        elif name and kind_role == "arcane":
            self.setToolTip(f"<b>{name}</b><br>{rank_txt}")
        for w in (pic,):
            w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        rv = slot.get("riven")
        if rv and rv.get("attributes"):                  # a Riven: its stats instead of a picture
            lines = []
            for a in rv["attributes"]:
                v = a["value"]
                if a.get("spliced"):                     # the spliced stat: icy, value not in the game data
                    lines.append(f"<span style='color:#9fe3ff; font-weight:bold'>❄ {'+' if a['positive'] else '−'}? {a['label']}</span>")
                    continue
                txt = "?" if v is None else f"{v:+g}%" if a["pct"] else (f"x{v:g}" if a["tag"].endswith(("Grineer", "Corpus", "Infested")) else f"{v:+g}")
                lines.append(f"<span style='color:{'#e0584a' if not a['positive'] else '#9fd8a6'}'>{txt} {a['label'].split(' (')[0]}</span>")
            st = QLabel("<br>".join(lines))
            st.setStyleSheet(f"font-size: {small}px;")
            st.setWordWrap(True)
            st.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(st, 1)
            self.setToolTip(t("builds.riven.tip", weapon=rv.get("weapon", ""), rerolls=rv.get("rerolls", 0))
                            + ("\n" + t("builds.spliced.tip") if frozen else ""))
        else:
            lay.addWidget(pic, 1)
        lab = QLabel(name or "—")
        lab.setWordWrap(True)
        lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lab.setStyleSheet(f"font-size: {base}px;")
        if not name:
            lab.setStyleSheet(f"font-size: {base}px; color: #6b7280;")
        lay.addWidget(lab)
        mx = slot.get("max")
        if name and mx:
            pp = QLabel(pips(slot.get("rank"), mx))
            pp.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pp.setStyleSheet(f"font-size: {small + 1}px; color: #c9a227;")
            lay.addWidget(pp)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self._clickable:
            self.clicked.emit()
        super().mouseReleaseEvent(e)


def stats_panel(capacity: dict, stats: dict, level: int = 30, reactor: bool = True, bonus: dict | None = None) -> QFrame:
    """Capacity (free / total) and the Warframe stat recap."""
    box = QFrame()
    box.setMinimumWidth(190)
    box.setMaximumWidth(300)
    box.setObjectName("statbox")
    box.setStyleSheet("#statbox { border: 1px solid palette(mid); border-radius: 6px; }")
    lay = QVBoxLayout(box)
    lay.setContentsMargins(10, 8, 10, 8)
    lay.setSpacing(2)
    if capacity:
        free = capacity.get("free", 0)
        cap = QLabel(f"<b>{t('builds.capacity')}</b>&nbsp;&nbsp;<span style='color:{'#e0584a' if free < 0 else '#4fbf6a'}'>"
                     f"{free}</span> / {capacity.get('total', 0)}")
        cap.setToolTip(t("builds.capacity.tip", level=level, reactor=t("builds.reactor") if reactor else ""))
        lay.addWidget(cap)
    else:                                              # exalted weapons: their slot polarities are not in the public data
        cap = QLabel(t("builds.capacity.none"))
        cap.setWordWrap(True)
        role(cap, "hint")
        lay.addWidget(cap)
    if stats:
        head = QLabel(t("builds.stats"))
        role(head, "muted")
        head.setStyleSheet("font-weight: bold; margin-top: 6px;")
        lay.addWidget(head)
        g = QGridLayout()
        g.setHorizontalSpacing(14)
        g.setVerticalSpacing(1)
        fmt = {"sprint": lambda v: f"{v:.2f}".rstrip("0").rstrip("."), "duration": lambda v: f"{v:g}%", "efficiency": lambda v: f"{v:g}%",
               "range": lambda v: f"{v:g}%", "strength": lambda v: f"{v:g}%"}
        from app.game import buildcalc as BC
        for n, key in enumerate(BC.STAT_ORDER):
            if key not in stats:
                continue
            g.addWidget(QLabel(t("builds.stat." + key)), n, 0)
            val = QLabel(fmt.get(key, str)(stats[key]))
            val.setAlignment(Qt.AlignmentFlag.AlignRight)
            val.setStyleSheet("font-weight: bold;")
            g.addWidget(val, n, 1)
        lay.addLayout(g)
        note = QLabel(t("builds.stats.note"))
        note.setWordWrap(True)
        role(note, "hint")
        lay.addWidget(note)
    if bonus:
        head = QLabel(t("builds.bonus"))
        role(head, "muted")
        head.setStyleSheet("font-weight: bold; margin-top: 6px;")
        lay.addWidget(head)
        g = QGridLayout()
        g.setHorizontalSpacing(14)
        g.setVerticalSpacing(1)
        for n, (label, v) in enumerate(bonus.items()):
            g.addWidget(QLabel(label), n, 0)
            val = QLabel(f"{v:+g}%")
            val.setAlignment(Qt.AlignmentFlag.AlignRight)
            val.setStyleSheet("font-weight: bold;")
            g.addWidget(val, n, 1)
        lay.addLayout(g)
        note = QLabel(t("builds.bonus.note"))
        note.setWordWrap(True)
        role(note, "hint")
        lay.addWidget(note)
    return box


def cards_widget(slots, on_click=None, cw=CARD_W) -> QWidget:
    """The cards of a build. Left: special slots then the general ones in two rows of four; right: Arcanes.
    on_click(index) is called with the slot's position in `slots` when the planner makes the cards clickable."""
    root = QWidget()
    h = QHBoxLayout(root)
    h.setContentsMargins(0, 0, 0, 0)
    h.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
    left = QVBoxLayout()
    left.setSpacing(6)
    left.setAlignment(Qt.AlignmentFlag.AlignTop)
    right = QVBoxLayout()
    right.setSpacing(6)
    right.setAlignment(Qt.AlignmentFlag.AlignTop)

    def card(i):
        c = ModCard(slots[i], clickable=on_click is not None, cw=cw)
        if on_click:
            c.clicked.connect(lambda i=i: on_click(i))
        return c
    special = [i for i, s in enumerate(slots) if s["role"] in ("aura", "exilus", "stance")]
    general = [i for i, s in enumerate(slots) if s["role"] == "general"]
    arcanes = [i for i, s in enumerate(slots) if s["role"] == "arcane"]
    if special:
        row = QHBoxLayout()
        row.setSpacing(6)
        row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        for i in special:
            row.addWidget(card(i))
        left.addLayout(row)
    g = QGridLayout()
    g.setSpacing(6)
    for n, i in enumerate(general):
        g.addWidget(card(i), n // 4, n % 4)
    left.addLayout(g)
    for i in arcanes:
        right.addWidget(card(i))
    h.addLayout(left)
    h.addSpacing(10)
    h.addLayout(right)
    return root
