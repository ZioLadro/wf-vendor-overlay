"""Mod cards laid out like the in-game build screen: Aura / Exilus on top, the 8 mods in two rows of four, the Arcanes on the
right, capacity and the stat recap beside them. Shared by the Builds view of your loadouts and by the build planner."""
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

import icons
import previews
from i18n import t
from uiutil import role

CARD_W, CARD_H = 128, 158
STATE_COLOR = {"match": "#4fbf6a", "mismatch": "#e0584a", "": ""}


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

    def __init__(self, slot, clickable=False):
        super().__init__()
        name, kind_role = slot.get("name") or "", slot.get("role", "general")
        self.setObjectName("modcard")
        border = "#3a4250" if name else "#2c323c"
        self.setStyleSheet(f"#modcard {{ background: #1b2027; border: 1px {'solid' if name else 'dashed'} {border}; border-radius: 6px; }}"
                           " #modcard QLabel { color: #e8eaed; background: transparent; }")
        self.setFixedSize(CARD_W, CARD_H)
        self._clickable = clickable
        if clickable:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(1)
        top = QHBoxLayout()
        top.setSpacing(3)
        spol = slot.get("pol") or ""
        left = _pol_label(spol)
        if spol:
            left.setToolTip(t("builds.slotpol", pol=t("pol." + spol)))
        top.addWidget(left)
        cap = QLabel(t("builds.slot." + kind_role) if kind_role != "general" else "")
        cap.setStyleSheet("font-size: 10px; color: #9aa4b2;")
        top.addWidget(cap)
        top.addStretch(1)
        if name and slot.get("drain") is not None and kind_role != "arcane":
            dr = QLabel(str(abs(slot["drain"])) if slot["drain"] >= 0 else f"+{abs(slot['drain'])}")
            col = STATE_COLOR.get(slot.get("state") or "", "")
            dr.setStyleSheet("font-weight: bold;" + (f" color: {col};" if col else ""))
            top.addWidget(dr)
            mp = _pol_label(slot.get("mpol") or "")
            if slot.get("mpol"):
                mp.setToolTip(t("builds.modpol", pol=t("pol." + slot["mpol"])))
            top.addWidget(mp)
        lay.addLayout(top)
        pic = QLabel()
        pic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pm = None
        if name and kind_role == "arcane":
            pm = icons.arcane(name, 64)
        elif name:
            f = previews.by_name(name)
            if f:
                pm = QPixmap(str(f))
        if pm is not None and not pm.isNull():
            pic.setPixmap(pm.scaledToHeight(64, Qt.TransformationMode.SmoothTransformation))
        rv = slot.get("riven")
        if rv and rv.get("attributes"):                  # a Riven: its stats instead of a picture
            lines = []
            for a in rv["attributes"]:
                v = a["value"]
                txt = f"{v:+g}%" if a["pct"] else (f"x{v:g}" if a["tag"].endswith(("Grineer", "Corpus", "Infested")) else f"{v:+g}")
                lines.append(f"<span style='color:{'#e0584a' if not a['positive'] else '#9fd8a6'}'>{txt} {a['label'].split(' (')[0]}</span>")
            st = QLabel("<br>".join(lines))
            st.setStyleSheet("font-size: 9px;")
            st.setWordWrap(True)
            st.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(st, 1)
            self.setToolTip(t("builds.riven.tip", weapon=rv.get("weapon", ""), rerolls=rv.get("rerolls", 0)))
        else:
            lay.addWidget(pic, 1)
        lab = QLabel(name or "—")
        lab.setWordWrap(True)
        lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lab.setStyleSheet("font-size: 11px;")
        if not name:
            lab.setStyleSheet("font-size: 11px; color: #6b7280;")
        lay.addWidget(lab)
        mx = slot.get("max")
        if name and mx:
            pp = QLabel(pips(slot.get("rank"), mx))
            pp.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pp.setToolTip(t("builds.rank", rank=mx if slot.get("rank") is None else slot["rank"], max=mx))
            pp.setStyleSheet("font-size: 10px; color: #c9a227;")
            lay.addWidget(pp)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self._clickable:
            self.clicked.emit()
        super().mouseReleaseEvent(e)


def stats_panel(capacity: dict, stats: dict, level: int = 30, reactor: bool = True, bonus: dict | None = None) -> QFrame:
    """Capacity (free / total) and the Warframe stat recap."""
    box = QFrame()
    box.setObjectName("statbox")
    box.setStyleSheet("#statbox { border: 1px solid palette(mid); border-radius: 6px; }")
    lay = QVBoxLayout(box)
    lay.setContentsMargins(10, 8, 10, 8)
    lay.setSpacing(2)
    free = capacity.get("free", 0)
    cap = QLabel(f"<b>{t('builds.capacity')}</b>&nbsp;&nbsp;<span style='color:{'#e0584a' if free < 0 else '#4fbf6a'}'>"
                 f"{free}</span> / {capacity.get('total', 0)}")
    cap.setToolTip(t("builds.capacity.tip", level=level, reactor=t("builds.reactor") if reactor else ""))
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
        import buildcalc as BC
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


def cards_widget(slots, on_click=None) -> QWidget:
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
        c = ModCard(slots[i], clickable=on_click is not None)
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
