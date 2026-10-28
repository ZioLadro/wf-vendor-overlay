"""In-game standing plan: a small window over the game (always on top, semi-transparent) listing what to buy with standing
(the Recommendations' picks), how much standing is still missing and what to do to earn it.

It can be moved (drag the title bar), resized (corner grip), collapsed, made more or less transparent, and shown/hidden
with a hotkey (Settings: key_goals, F6 by default). It is interactive: tick an item you bought (it stays until the game
file confirms the purchase), right-click an item to hide it or open it on warframe.market. It is read again every time
AlecaFrame rewrites lastData.dat. The OCR never reads its area (it would see item names in it)."""
import sys
import time

from PyQt6.QtCore import QPoint, QRect, Qt, QTimer, QUrl
from PyQt6.QtGui import QAction, QColor, QDesktopServices, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QFrame, QHBoxLayout, QLabel, QMenu, QPushButton, QScrollArea, QSizeGrip, QVBoxLayout, QWidget,
)

import goals as G


def cursor_visible() -> bool:
    """True when the mouse cursor is on screen. In a mission Warframe hides it (camera control), in menus, the Orbiter's
    consoles and vendors it shows it. Off Windows (or if the check fails) the answer is always True."""
    if sys.platform != "win32":
        return True
    try:
        import ctypes
        from ctypes import wintypes

        class CURSORINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD), ("hCursor", wintypes.HANDLE),
                        ("ptScreenPos", wintypes.POINT)]
        ci = CURSORINFO()
        ci.cbSize = ctypes.sizeof(CURSORINFO)
        if not ctypes.windll.user32.GetCursorInfo(ctypes.byref(ci)):
            return True
        return bool(ci.flags & 1) and bool(ci.hCursor)        # CURSOR_SHOWING, and a cursor shape at all
    except Exception:
        return True


def set_click_through(widget, on: bool):
    """Lets mouse clicks pass through the window to the game (Windows: WS_EX_TRANSPARENT on the layered window), without
    re-creating it."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        u = ctypes.windll.user32
        hwnd = int(widget.winId())
        get = getattr(u, "GetWindowLongPtrW", u.GetWindowLongW)
        put = getattr(u, "SetWindowLongPtrW", u.SetWindowLongW)
        get.restype = ctypes.c_ssize_t
        put.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
        ex = get(ctypes.c_void_p(hwnd), -20)                 # GWL_EXSTYLE
        new = (ex | 0x20 | 0x80000) if on else (ex & ~0x20)  # WS_EX_TRANSPARENT (| WS_EX_LAYERED)
        if new != ex:
            put(ctypes.c_void_p(hwnd), -20, new)
    except Exception:
        pass
from config import CFG, save_config
from i18n import t
from uiutil import market_url, thousands


def _n(v) -> str:
    return "–" if v is None else thousands(v)


class GoalsOverlay(QWidget):
    def __init__(self, market, inv, store):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.market, self.inv, self.store = market, inv, store
        self.plan = G.Plan()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)      # showing it does not take the focus from the game
        self.setWindowTitle(t("goals.title"))
        self.setMinimumSize(240, 90)
        self._drag = None
        self._sig = None
        self._shown_sig = None
        self._collapsed = bool(CFG.get("goals_collapsed", False))

        self.head = QWidget()
        self.head.setObjectName("goalshead")
        self.head.setCursor(Qt.CursorShape.SizeAllCursor)
        self.title = QLabel(t("goals.title").upper())
        self.title.setObjectName("goalstitle")
        h = QHBoxLayout(self.head)
        h.setContentsMargins(10, 4, 4, 4)
        h.addWidget(self.title, 1)
        self.btn_refresh = self._tool("⟳", t("goals.refresh"), lambda: self.refresh(force=True))
        self.btn_menu = self._tool("⚙", t("goals.options"), self._options)
        self.btn_fold = self._tool("▾", t("goals.fold"), self._fold)
        self.btn_close = self._tool("✕", t("goals.hide", key=CFG.get("key_goals", "")), self.toggle)
        for b in (self.btn_refresh, self.btn_menu, self.btn_fold, self.btn_close):
            h.addWidget(b)
        self.head.installEventFilter(self)
        self.title.installEventFilter(self)

        self.body = QWidget()
        self.body.setObjectName("goalsbody")
        self.rows = QVBoxLayout(self.body)
        self.rows.setContentsMargins(10, 4, 10, 6)
        self.rows.setSpacing(2)
        self.rows.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.body)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setObjectName("goalsscroll")
        self.grip = QSizeGrip(self)
        foot = QHBoxLayout()
        foot.setContentsMargins(8, 0, 2, 2)
        self.status = QLabel("")
        self.status.setObjectName("goalsfoot")
        foot.addWidget(self.status, 1)
        foot.addWidget(self.grip, 0, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(1, 1, 1, 1)
        lay.setSpacing(0)
        lay.addWidget(self.head)
        lay.addWidget(self.scroll, 1)
        lay.addLayout(foot)
        self._style()

        g = CFG.get("goals_geom") or []
        if len(g) == 4:
            self.setGeometry(QRect(*[int(x) for x in g]))
        else:
            scr = QApplication.primaryScreen().availableGeometry()
            self.setGeometry(scr.right() - 380, scr.top() + 140, 340, 420)
        self._apply_fold()
        self._timer = QTimer(self, interval=3000, timeout=self.refresh)
        # shown when you want it (hotkey / ✕) and no vendor is on screen: over a vendor it steps aside
        self._wanted = bool(CFG.get("goals_visible", False))
        self._vendor = False
        self._restore = QTimer(self, singleShot=True, interval=1500, timeout=self._vendor_gone)
        # clickable only while the cursor is visible (menus, consoles): in a mission clicks go through to the game
        self._clickable = True
        self._cursor_timer = QTimer(self, interval=250, timeout=self._check_cursor)
        self._save_timer = QTimer(self, singleShot=True, interval=600, timeout=self._save_geom)

    # ---------- look ----------
    def _tool(self, text, tip, fn):
        b = QPushButton(text)
        b.setObjectName("goalsbtn")
        b.setToolTip(tip)
        b.setFixedSize(24, 22)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(lambda _c=False: fn())
        return b

    def _style(self):
        """Look of a quest tracker: almost no panel, gold quest titles, white objectives with their progress, completed
        ones in green, small grey hints, every text with a dark outline so it reads over the game."""
        fs = int(CFG.get("goals_font", 12))
        self.setStyleSheet(f"""
            QWidget {{ color: #ffffff; font-size: {fs}px; background: transparent; }}
            #goalshead {{ background: transparent; border-bottom: 1px solid rgba(255, 209, 0, 90); }}
            #goalstitle {{ font-weight: bold; color: #ffd100; letter-spacing: 1px; font-size: {fs + 1}px; }}
            #goalsbtn {{ background: transparent; border: none; color: #c8b37a; padding: 0; font-size: {fs}px; }}
            #goalsbtn:hover {{ color: #ffd100; }}
            #goalsfoot {{ color: #9a9a9a; font-size: {max(9, fs - 2)}px; }}
            QLabel[g="quest"] {{ color: #ffd100; font-weight: bold; font-size: {fs + 1}px; }}
            QLabel[g="sub"] {{ color: #b8b8b8; font-size: {max(9, fs - 1)}px; }}
            QLabel[g="obj"] {{ color: #ffffff; }}
            QLabel[g="ready"] {{ color: #40ff40; }}
            QLabel[g="wait"] {{ color: #ffd100; }}
            QLabel[g="act"] {{ color: #a0a0a0; font-size: {max(9, fs - 1)}px; font-style: italic; }}
            QLabel[g="done"] {{ color: #ffd100; font-weight: bold; }}
            QCheckBox {{ spacing: 5px; color: #ffffff; }}
            QCheckBox::indicator {{ width: 10px; height: 10px; border: 1px solid #c8b37a; background: rgba(0, 0, 0, 120); }}
            QCheckBox::indicator:checked {{ background: #40ff40; border-color: #40ff40; }}
            QScrollBar:vertical {{ background: transparent; width: 6px; }}
            QScrollBar::handle:vertical {{ background: rgba(255, 209, 0, 70); border-radius: 3px; min-height: 20px; }}
            QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
            QMenu {{ background: #1b1b1b; border: 1px solid #6e5a1e; color: #ffffff; }}
            QMenu::item:selected {{ background: #3a3216; }}
        """)

    def paintEvent(self, _e):
        """A soft dark band that fades out to the right, like a quest tracker over the game (opacity in ⚙)."""
        from PyQt6.QtGui import QLinearGradient
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        alpha = int(255 * max(0, min(100, int(CFG.get("goals_opacity", 45)))) / 100)
        grad = QLinearGradient(0, 0, self.width(), 0)
        grad.setColorAt(0.0, QColor(0, 0, 0, alpha))
        grad.setColorAt(0.75, QColor(0, 0, 0, int(alpha * 0.7)))
        grad.setColorAt(1.0, QColor(0, 0, 0, int(alpha * 0.15)))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad)
        p.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 6, 6)

    @staticmethod
    def _shadow(w):
        """Dark outline around the text, so it stays readable on any part of the game."""
        from PyQt6.QtWidgets import QGraphicsDropShadowEffect
        eff = QGraphicsDropShadowEffect(w)
        eff.setBlurRadius(2)
        eff.setOffset(1, 1)
        eff.setColor(QColor(0, 0, 0, 255))
        w.setGraphicsEffect(eff)
        return w

    def _label(self, text, kind, wrap=True):
        lab = QLabel(text)
        lab.setProperty("g", kind)
        lab.setWordWrap(wrap)
        return self._shadow(lab)

    # ---------- moving, resizing, folding ----------
    def eventFilter(self, obj, ev):
        t_ = ev.type()
        if t_ == ev.Type.MouseButtonPress and ev.button() == Qt.MouseButton.LeftButton:
            self._drag = ev.globalPosition().toPoint() - self.frameGeometry().topLeft()
            return True
        if t_ == ev.Type.MouseMove and self._drag is not None:
            self.move(ev.globalPosition().toPoint() - self._drag)
            return True
        if t_ == ev.Type.MouseButtonRelease and self._drag is not None:
            self._drag = None
            self._save_geom()
            return True
        if t_ == ev.Type.MouseButtonDblClick:
            self._fold()
            return True
        return super().eventFilter(obj, ev)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if not self._collapsed:
            self._save_timer.start()

    def _save_geom(self):
        g = self.geometry()
        h = g.height() if not self._collapsed else int((CFG.get("goals_geom") or [0, 0, 0, 420])[3])
        save_config({"goals_geom": [g.x(), g.y(), g.width(), h]})

    def _fold(self):
        self._collapsed = not self._collapsed
        save_config({"goals_collapsed": self._collapsed})
        self._apply_fold()

    def _apply_fold(self):
        self.scroll.setVisible(not self._collapsed)
        self.status.setVisible(not self._collapsed)
        self.grip.setVisible(not self._collapsed)
        self.btn_fold.setText("▸" if self._collapsed else "▾")
        if self._collapsed:
            self.setMinimumHeight(0)
            self.resize(self.width(), self.head.sizeHint().height() + 4)
        else:
            self.setMinimumHeight(90)
            g = CFG.get("goals_geom") or []
            self.resize(self.width(), int(g[3]) if len(g) == 4 else 420)

    # ---------- options ----------
    def _options(self):
        m = QMenu(self)

        def choice(title, key, values, fmt):
            sub = m.addMenu(title)
            for v in values:
                a = QAction(fmt(v), sub, checkable=True)
                a.setChecked(CFG.get(key) == v)
                a.triggered.connect(lambda _c=False, k=key, val=v: self._set(k, val))
                sub.addAction(a)
        choice(t("goals.opt.opacity"), "goals_opacity", [40, 60, 75, 82, 90, 100], lambda v: f"{v}%")
        choice(t("goals.opt.font"), "goals_font", [10, 11, 12, 13, 14, 16, 18], lambda v: f"{v}px")
        choice(t("goals.opt.items"), "goals_items", [3, 5, 8, 12, 20], str)
        for key, label in (("goals_per_vendor", "goals.opt.pervendor"), ("goals_activities", "goals.opt.activities"),
                           ("goals_only_short", "goals.opt.onlyshort"),
                           ("goals_click_only_cursor", "goals.opt.cursor")):
            a = QAction(t(label), m, checkable=True)
            a.setChecked(bool(CFG.get(key)))
            a.triggered.connect(lambda c, k=key: self._set(k, bool(c)))
            m.addAction(a)
        m.addSeparator()
        a = QAction(t("goals.opt.reset"), m)
        a.triggered.connect(lambda: (self.plan.reset(), self.refresh(force=True)))
        m.addAction(a)
        m.exec(self.btn_menu.mapToGlobal(QPoint(0, self.btn_menu.height())))

    def _set(self, key, value):
        save_config({key: value})
        self._style()
        self.update()
        self.refresh(force=True)

    # ---------- showing ----------
    def toggle(self):
        """Hotkey / ✕ / tray: you want it shown or not (remembered). Over a vendor screen it stays hidden until the vendor
        closes."""
        self._wanted = not self._wanted
        save_config({"goals_visible": self._wanted})
        self._apply_visibility()

    def start(self):
        self._apply_visibility()

    def vendor_shown(self, on: bool):
        """The overlay found a vendor (prices shown on the game): the plan hides at once, and comes back a moment after
        the vendor screen is gone (a rescan while scrolling does not make it flash)."""
        if on:
            self._restore.stop()
            if not self._vendor:
                self._vendor = True
                self._apply_visibility()
        elif self._vendor and not self._restore.isActive():
            self._restore.start()

    def _vendor_gone(self):
        self._vendor = False
        self._apply_visibility()

    def _apply_visibility(self):
        want = self._wanted and not self._vendor
        if want and not self.isVisible():
            self.show()
            self.raise_()
        elif not want and self.isVisible():
            self.hide()

    def showEvent(self, e):
        super().showEvent(e)
        self.refresh(force=True)
        self._timer.start()
        self._clickable = True
        self._check_cursor()
        self._cursor_timer.start()

    def hideEvent(self, e):
        super().hideEvent(e)
        self._timer.stop()
        self._cursor_timer.stop()

    def _check_cursor(self):
        """In a mission (no cursor) the plan lets every click through to the game and its buttons fade; as soon as the
        cursor comes back (menu, console, vendor) it can be used again. Setting goals_click_only_cursor."""
        on = (not CFG.get("goals_click_only_cursor", True)) or cursor_visible()
        if on == self._clickable:
            return
        self._clickable = on
        set_click_through(self, not on)
        for b in (self.btn_refresh, self.btn_menu, self.btn_fold, self.btn_close):
            b.setVisible(on)                              # no buttons to aim at while they cannot be clicked
        self.head.setCursor(Qt.CursorShape.SizeAllCursor if on else Qt.CursorShape.ArrowCursor)

    def screen_rect_px(self):
        """Its rectangle in physical pixels (None if hidden): the OCR must not read the item names in it."""
        if not self.isVisible():
            return None
        g, r = self.frameGeometry(), self.devicePixelRatioF()
        return (g.x() * r, g.y() * r, g.width() * r, g.height() * r)

    def refresh(self, force=False):
        """Rebuilt when the game file was read again (standing, inventory), the prices changed, or every minute."""
        sig = (self.store.version, self.inv.imported, len(self.inv.items), int(time.time() // 60))
        if not force and sig == self._sig:
            return
        self._sig = sig
        try:
            data = G.build(self.plan, self.market, self.inv, self.store)
        except Exception as e:
            import logbus
            logbus.error("plan", f"{type(e).__name__}: {e}")
            return
        for c in data["confirmed"]:
            self.status.setText(t("goals.confirmed", name=c["name"]))
        shown = repr((data["groups"], [d["name"] for d in data["done"][-3:]], CFG.get("goals_activities"),
                      CFG.get("goals_only_short")))
        if shown == self._shown_sig and not force:
            return
        self._shown_sig = shown
        self._draw(data)

    def _clear(self):
        while self.rows.count():
            it = self.rows.takeAt(0)
            w = it.widget()
            if w:
                w.setParent(None)
                w.deleteLater()                        # spacers (addSpacing) need nothing more

    def _draw(self, data):
        """One "quest" per syndicate: gold title with ? (something to buy now) or ! (standing still to earn), a grey line
        with rank, standing and what is earnable today, then the objectives (each purchase, the standing to earn) and,
        in grey, how to earn it. Confirmed purchases close the list like completed quests."""
        self.body.setUpdatesEnabled(False)
        self._clear()
        groups = data["groups"]
        if CFG.get("goals_only_short"):
            groups = [g for g in groups if g["short"]]
        if not groups:
            self.rows.addWidget(self._label(t("goals.empty"), "act"))
        for g in groups:
            ready = any(it.get("can") for it in g["items"])
            icon = "?" if ready else "!"
            self.rows.addSpacing(6)
            self.rows.addWidget(self._label(f"{icon}  {g['name']}", "quest"))
            sub = []
            if g.get("rank") is not None:
                sub.append(t("goals.q.rank", r=g["rank"]))
            sub.append(t("goals.q.standing", n=_n(g["standing"])) if g.get("standing") is not None else t("goals.q.unknown"))
            if g.get("daily") is not None:
                sub.append(t("goals.daily", n=_n(g["daily"])) + (f"/{_n(g['cap'])}" if g.get("cap") else ""))
            self.rows.addWidget(self._label("   " + " · ".join(sub), "sub"))
            for it in g["items"]:
                self.rows.addWidget(self._item_row(it))
            if g["short"] and g.get("standing") is not None:
                best = min((x for x in g["items"] if x.get("need")), key=lambda x: x["need"], default=None)
                if best:
                    d = best.get("days")
                    when = t("goals.today") if d == 1 else (t("goals.days", n=d) if d else "")
                    have = max(0, g["standing"])
                    self.rows.addWidget(self._label(
                        f"   - {t('goals.q.earn', n=_n(best['need']))}: {_n(have)}/{_n(have + best['need'])}"
                        + (f"  ({when})" if when else ""), "obj"))
            if CFG.get("goals_activities", True) and g["activities"]:
                for a in g["activities"]:
                    self.rows.addWidget(self._label("      ◦ " + a, "act"))
        recent = [d for d in data["done"] if time.time() - d.get("t", 0) < 86400][-3:]
        if recent:
            self.rows.addSpacing(6)
            self.rows.addWidget(self._label(t("goals.recent"), "quest"))
            for d in reversed(recent):
                self.rows.addWidget(self._label(
                    f"   ✔ {d['name']} ({d['vendor']}) · {time.strftime('%H:%M', time.localtime(d['t']))}", "done"))
        n = sum(len(g["items"]) for g in data["groups"])
        if not any(c for c in data["confirmed"]):
            self.status.setText(t("goals.foot", n=n))
        self.body.setUpdatesEnabled(True)

    def _item_row(self, it):
        """An objective: "- Buy <item> (0/1)", white; green when it can be bought now; the tick box marks it bought."""
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(12, 0, 0, 0)
        h.setSpacing(4)
        cb = QCheckBox()
        cb.setChecked(bool(it.get("ticked")))
        cb.setToolTip(t("goals.item.tip", vendor=it["vendor"], cost=_n(it["cost"]), price=it.get("price") or "–",
                        vol=it.get("vol") or "–", rank=it.get("rank") or 0))
        cb.toggled.connect(lambda on, k=it["key"]: (self.plan.tick(k, on), self.refresh(force=True)))
        h.addWidget(cb)
        if it.get("ticked"):
            text, kind = t("goals.q.wait", name=it["name"]), "wait"
        elif it["can"]:
            text, kind = t("goals.q.ready", name=it["name"], n=it["can"], cost=_n(it["cost"])), "ready"
        else:
            text, kind = t("goals.q.buy", name=it["name"], cost=_n(it["cost"])), "obj"
        if it.get("rank_ok") is False:
            text += "  " + t("goals.rank", r=it.get("rank"))
        lab = self._label(text, kind)
        lab.setToolTip(cb.toolTip())
        h.addWidget(lab, 1)
        for w in (row, cb, lab):
            w.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            w.customContextMenuRequested.connect(lambda pos, w=w, i=it: self._item_menu(w, pos, i))
        return row

    def _item_menu(self, w, pos, it):
        m = QMenu(self)
        a = m.addAction(t("goals.menu.hide"))
        a.triggered.connect(lambda: (self.plan.hide(it["key"]), self.refresh(force=True)))
        b = m.addAction(t("goals.menu.market"))
        b.triggered.connect(lambda: QDesktopServices.openUrl(QUrl(market_url(it["slug"]))))
        m.exec(w.mapToGlobal(pos))
