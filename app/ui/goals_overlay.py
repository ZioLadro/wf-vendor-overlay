"""In-game Activities overlay (once the "standing plan"): a small window over the game (always on top, semi-transparent) listing what to buy with standing
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

from app.game import goals as G


def cursor_info():
    """(showing, (x, y), pinned): whether Windows shows its cursor, where it is (physical pixels) and whether it is
    confined to a tiny area (ClipCursor: camera control in a mission). Warframe hides the Windows cursor in a mission,
    but in many menus it also draws its OWN cursor with the Windows one hidden, so "showing" alone is not enough (see
    GoalsOverlay._check_cursor). Off Windows (or if the check fails): (True, None, False)."""
    if sys.platform != "win32":
        return True, None, False
    try:
        import ctypes
        from ctypes import wintypes

        class CURSORINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD), ("hCursor", wintypes.HANDLE),
                        ("ptScreenPos", wintypes.POINT)]
        u = ctypes.windll.user32
        ci = CURSORINFO()
        ci.cbSize = ctypes.sizeof(CURSORINFO)
        if not u.GetCursorInfo(ctypes.byref(ci)):
            return True, None, False
        showing = bool(ci.flags & 1) and bool(ci.hCursor)         # CURSOR_SHOWING, and a cursor shape at all
        clip = wintypes.RECT()
        pinned = bool(u.GetClipCursor(ctypes.byref(clip))) and (clip.right - clip.left <= 8 or clip.bottom - clip.top <= 8)
        return showing, (ci.ptScreenPos.x, ci.ptScreenPos.y), pinned
    except Exception:
        return True, None, False


def cursor_visible() -> bool:
    return cursor_info()[0]


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
from app.core.config import CFG, save_config
from app.core.i18n import t
from app.core.uiutil import market_url, thousands


def _left(seconds) -> str:
    s = max(0, int(seconds))
    d, h, m = s // 86400, s % 86400 // 3600, s % 3600 // 60
    return f"{d}d {h}h" if d else (f"{h}h {m:02d}m" if h else f"{m}m")


def _n(v) -> str:
    return "–" if v is None else thousands(v)


class GoalsOverlay(QWidget):
    def __init__(self, market, inv, store):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.market, self.inv, self.store = market, inv, store
        self.plan = G.get_plan()
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
        # clickable only while the cursor is visible (menus, consoles): in a mission clicks go through to the game
        self._clickable = True
        self._last_pos, self._moved_at = None, 0.0
        self._cursor_timer = QTimer(self, interval=150, timeout=self._check_cursor)
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
        title, text = CFG.get("goals_title_color") or "#ffd100", CFG.get("goals_text_color") or "#ffffff"
        ready, hint = CFG.get("goals_ready_color") or "#40ff40", CFG.get("goals_hint_color") or "#a0a0a0"
        soon = CFG.get("goals_soon_color") or "#7fd7ff"
        fam = CFG.get("goals_font_family") or ""
        family = f"font-family: '{fam}';" if fam else ""
        self._style_sig = (fs, title, text, ready, hint, fam, soon)
        self.setStyleSheet(f"""
            QWidget {{ color: {text}; font-size: {fs}px; background: transparent; {family} }}
            #goalshead {{ background: transparent; border-bottom: 1px solid rgba(255, 209, 0, 90); }}
            #goalstitle {{ font-weight: bold; color: {title}; letter-spacing: 1px; font-size: {fs + 1}px; }}
            #goalsbtn {{ background: transparent; border: none; color: #c8b37a; padding: 0; font-size: {fs}px; }}
            #goalsbtn:hover {{ color: {title}; }}
            #goalsfoot {{ color: #9a9a9a; font-size: {max(9, fs - 2)}px; }}
            QLabel[g="quest"] {{ color: {title}; font-weight: bold; font-size: {fs + 1}px; }}
            QLabel[g="sub"] {{ color: #b8b8b8; font-size: {max(9, fs - 1)}px; }}
            QLabel[g="obj"] {{ color: {text}; }}
            QLabel[g="ready"] {{ color: {ready}; }}
            QLabel[g="wait"] {{ color: {title}; }}
            QLabel[g="soon"] {{ color: {soon}; }}
            QLabel[g="act"] {{ color: {hint}; font-size: {max(9, fs - 1)}px; font-style: italic; }}
            QLabel[g="done"] {{ color: {title}; font-weight: bold; }}
            QCheckBox {{ spacing: 5px; color: {text}; }}
            QCheckBox::indicator {{ width: 10px; height: 10px; border: 1px solid #c8b37a; background: rgba(0, 0, 0, 120); }}
            QCheckBox::indicator:checked {{ background: {ready}; border-color: {ready}; }}
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
                           ("goals_click_only_cursor", "goals.opt.cursor"), ("goals_weekly", "goals.opt.weekly"),
                           ("goals_quests", "goals.opt.quests"), ("goals_where", "goals.opt.where"), ("goals_routine", "goals.opt.routine"),
                           ("goals_repeat", "goals.opt.repeat"), ("goals_by_reset", "goals.opt.byreset")):
            a = QAction(t(label), m, checkable=True)
            a.setChecked(bool(CFG.get(key)))
            a.triggered.connect(lambda c, k=key: self._set(k, bool(c)))
            m.addAction(a)
        m.addSeparator()
        n_unsent = sum(e["qty"] for e in self.plan.unsent())
        qf = QAction(t("goals.qf", n=n_unsent), m)
        qf.setEnabled(n_unsent > 0)
        qf.triggered.connect(self.send_to_quantframe)
        m.addAction(qf)
        tr = QAction(t("goals.opt.trackall"), m)
        tr.setEnabled(bool(CFG.get("goals_untracked")))
        tr.triggered.connect(lambda: self._set_untracked([]))
        m.addAction(tr)
        a = QAction(t("goals.opt.reset"), m)
        a.triggered.connect(lambda: (self.plan.reset(), self.refresh(force=True)))
        m.addAction(a)
        m.exec(self.btn_menu.mapToGlobal(QPoint(0, self.btn_menu.height())))

    def send_to_quantframe(self):
        """The purchases Activities confirmed (and not sent yet) -> Quantframe's stock, after the usual check window."""
        from app.trade import quantframe as Q
        from app.ui.quantframe_dialog import SendDialog
        entries = []
        for e in self.plan.unsent():
            info = self.market.info(e["slug"]) or {}
            entries.append(dict(e, name=info.get("name") or e["name"], rank=0 if info.get("max_rank", 0) > 0 else None))
        if not entries:
            return
        start = time.time() - 1
        SendDialog("stock", entries, self, all_checked=True).exec()
        sent = {e["slug"] for e in entries if (Q.sent_before("stock", e["slug"], e["rank"]) or {}).get("t", 0) >= start}
        if sent:
            self.plan.mark_sent(sent)

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
        """The OCR recognised a vendor (prices shown on the game): the plan switches itself off and stays off until you
        turn it on again with the hotkey (F6). Nothing happens when the vendor closes."""
        if on and self._wanted:
            self._wanted = False
            save_config({"goals_visible": False})
            self._apply_visibility()
            from app.core import logbus
            logbus.add("plan", "vendor recognised: Activities switched off (the hotkey turns it on again)")

    def _apply_visibility(self):
        want = self._wanted
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
        on = (not CFG.get("goals_click_only_cursor", True)) or self._cursor_free()
        if on == self._clickable:
            return
        self._clickable = on
        set_click_through(self, not on)
        for b in (self.btn_refresh, self.btn_menu, self.btn_fold, self.btn_close):
            b.setVisible(on)                              # no buttons to aim at while they cannot be clicked
        self.head.setCursor(Qt.CursorShape.SizeAllCursor if on else Qt.CursorShape.ArrowCursor)

    def _cursor_free(self) -> bool:
        """True when you are using a cursor, Windows' or the game's own: Windows shows its cursor, OR the cursor is over
        this window, it is moving freely (not confined to a tiny area) and it moved in the last 2 seconds. In a mission the
        camera keeps the (hidden) cursor still, usually in the middle of the game, so it never "walks" onto the window;
        in menus Warframe hides the Windows cursor and draws its own, which moves the real one along with it."""
        showing, pos, pinned = cursor_info()
        if showing or pos is None:
            return True
        now = time.monotonic()
        if pos != self._last_pos:
            self._last_pos, self._moved_at = pos, now
        r = self.screen_rect_px()
        inside = bool(r) and r[0] <= pos[0] < r[0] + r[2] and r[1] <= pos[1] < r[1] + r[3]
        return inside and not pinned and (self._clickable or now - self._moved_at < 2.0)

    def screen_rect_px(self):
        """Its rectangle in physical pixels (None if hidden): the OCR must not read the item names in it."""
        if not self.isVisible():
            return None
        g, r = self.frameGeometry(), self.devicePixelRatioF()
        return (g.x() * r, g.y() * r, g.width() * r, g.height() * r)

    def _style_changed(self) -> bool:
        sig = (int(CFG.get("goals_font", 12)), CFG.get("goals_title_color") or "#ffd100", CFG.get("goals_text_color") or "#ffffff",
               CFG.get("goals_ready_color") or "#40ff40", CFG.get("goals_hint_color") or "#a0a0a0", CFG.get("goals_font_family") or "",
               CFG.get("goals_soon_color") or "#7fd7ff")
        return sig != getattr(self, "_style_sig", None)

    def refresh(self, force=False):
        """Rebuilt when the game file was read again (standing, inventory), the prices changed, or every minute."""
        from app.game import weekly as WK
        from app.game import quests as Q
        if self._style_changed():                       # colours / font changed in Settings
            self._style()
            self.update()
            force = True
        sig = (self.store.version, self.inv.imported, len(self.inv.items), int(time.time() // 60), WK.get().version,
               Q._state["fetched"], repr(CFG.get("goals_untracked")),
               tuple(CFG.get(k) for k in ("goals_items", "goals_per_vendor", "goals_repeat", "goals_activities",
                                          "goals_only_short", "goals_where", "goals_weekly", "goals_quests",
                                          "goals_cal_rows", "goals_routine", "goals_opacity")))
        if not force and sig == self._sig:
            return
        self._sig = sig
        try:
            data = G.build(self.plan, self.market, self.inv, self.store)
        except Exception as e:
            from app.core import logbus
            logbus.error("plan", f"{type(e).__name__}: {e}")
            return
        for c in data["confirmed"]:
            self.status.setText(t("goals.confirmed", name=c["name"]))
        shown = repr((data["groups"], [d["name"] for d in data["done"][-3:]], CFG.get("goals_activities"),
                      WK.get().version, CFG.get("goals_untracked"), CFG.get("goals_weekly"), int(time.time() // 60),
                      Q._state["fetched"], CFG.get("goals_quests"), CFG.get("goals_where"), CFG.get("goals_routine"), repr(CFG.get("goals_manual_done")),
                      self.inv.imported,
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
                w.hide()
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
            title = self._label(f"{icon}  {g['name']}", "quest")
            self._menu_on(title, lambda pos, w=title, g=g: self._quest_menu(w, pos, g))
            self.rows.addWidget(title)
            sub = []
            if g.get("rank") is not None:
                sub.append(t("goals.q.rank", r=g["rank"]))
            sub.append(t("goals.q.standing", n=_n(g["standing"])) if g.get("standing") is not None else t("goals.q.unknown"))
            if g.get("daily") is not None:
                sub.append(t("goals.daily", n=_n(g["daily"])) + (f"/{_n(g['cap'])}" if g.get("cap") else "")
                           + ("  " + t("goals.reset.in", left=_left(86400 - time.time() % 86400))
                              if CFG.get("goals_by_reset", True) else ""))
            self.rows.addWidget(self._label("   " + " · ".join(sub), "sub"))
            for it in g["items"]:
                self.rows.addWidget(self._item_row(it))
                place = self._place_label(it)
                if place:
                    self.rows.addWidget(place)
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
                untracked = set(CFG.get("goals_untracked") or [])
                for n, a in enumerate(g["activities"]):
                    key = f"{g['tag']}|{n}"
                    if key in untracked or f"{g['tag']}|*" in untracked:
                        continue
                    lab = self._label("      ◦ " + a, "act")
                    self._menu_on(lab, lambda pos, w=lab, k=key: self._activity_menu(w, pos, k))
                    self.rows.addWidget(lab)
        if CFG.get("goals_weekly", True):
            self._draw_weekly()
        if CFG.get("goals_quests", True):
            self._draw_quests()
        if CFG.get("goals_routine", True):
            self._draw_routine()
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
        elif it.get("buy"):
            text, kind = t("goals.q.ready", name=it["name"], n=it["buy"], cost=_n(it["cost"] * it["buy"])), "ready"
            if it.get("reset_buy") and CFG.get("goals_by_reset", True):       # and more copies with today's standing
                text += "  " + t("goals.q.reset.more", n=it["reset_buy"], earn=_n(it["reset_earn"]))
        elif it.get("reset_buy") and CFG.get("goals_by_reset", True):
            text, kind = t("goals.q.reset", name=it["name"], n=it["reset_buy"], cost=_n(it["cost"] * it["reset_buy"]),
                           earn=_n(it["reset_earn"])), "soon"
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

    def _place_label(self, it):
        """Where to buy the item (⌖ NPC, place), on its own line under it; None when off or unknown."""
        if not CFG.get("goals_where", True):
            return None
        from app.game import places
        place = places.where(it.get("tag"), it.get("vendor"), it.get("name"))
        if not place:
            return None
        pl = self._label("          ⌖ " + place, "act")
        pl.setToolTip(t("goals.where.tip", place=place))
        return pl

    # ---------- weekly offers ----------
    def _draw_weekly(self):
        """The weekly offers you follow (Weekly tab), like a weekly quest: what is left to buy and when it resets, plus the
        purchases to identify (click one to say which offer it was)."""
        from app.game import weekly as WK
        w = WK.get()
        now = time.time()
        tracked = [o for o in w.offers(False) if o["tracked"] and o.get("active") is not False]
        unknown = w.unknown()
        if not tracked and not unknown:
            return
        self.rows.addSpacing(6)
        reset = WK.next_reset(now)
        self.rows.addWidget(self._label("⟳  " + t("goals.weekly"), "quest"))
        self.rows.addWidget(self._label("   " + t("goals.weekly.sub", left=_left(reset - now)), "sub"))
        for o in sorted(tracked, key=lambda o: (o["bought"] >= o["limit"], o["vendor_name"], o["name"])):
            qty = f" ×{thousands(o['qty'])}" if o["qty"] > 1 else ""
            done = o["bought"] >= o["limit"]
            lab = self._label(f"   - {o['vendor_name']}: {o['name']}{qty} ({o['bought']}/{o['limit']})"
                              + (" " + t("weekly.ocr") if o.get("ocr") else ""), "ready" if done else "obj")
            lab.setToolTip(t("goals.weekly.tip", cost=", ".join(f"{thousands(n)} {c}" for n, c in o["cost"]) or "–"))
            self._menu_on(lab, lambda pos, wd=lab, o=o: self._weekly_menu(wd, pos, o))
            self.rows.addWidget(lab)
        for u in unknown:
            lab = self._label("   ? " + t("goals.weekly.unknown", vendor=u["vendor_name"], n=u["n"]), "wait")
            lab.setToolTip(t("goals.weekly.unknown.tip", region=w.region or "–"))
            lab.setCursor(Qt.CursorShape.PointingHandCursor)
            self._menu_on(lab, lambda pos, wd=lab, u=u: self._identify_menu(wd, pos, u))
            lab.mousePressEvent = lambda e, wd=lab, u=u: self._identify_menu(wd, e.position().toPoint(), u)
            self.rows.addWidget(lab)

    def _raw_inv(self):
        import os
        from app.game import aleca
        from app.game import weekly as WK
        p = self.inv.path if self.inv.path and os.path.exists(self.inv.path) else aleca.find_data_file()
        try:
            return WK.raw_inventory(p) if p else None
        except Exception:
            return None

    def _section(self, key, icon, title, sub):
        """A quest block title with its grey line; right-click untracks the whole block. False if untracked."""
        if f"{key}|*" in set(CFG.get("goals_untracked") or []):
            return False
        self.rows.addSpacing(6)
        lab = self._label(f"{icon}  {title}", "quest")
        self._menu_on(lab, lambda pos, w=lab, k=key, n=title: self._quest_menu(w, pos, {"tag": k, "name": n}))
        self.rows.addWidget(lab)
        if sub:
            self.rows.addWidget(self._label("   " + sub, "sub"))
        return True

    def _draw_quests(self):
        """Nightwave's weekly challenges and the 1999 Calendar's, from DE's world state, with what the game file says you
        completed (green ✔). Read again in the background every 10 minutes."""
        from app.game import quests as Q
        Q.refresh_async()
        ws = Q.cached()
        if not ws:
            return
        inv = self._raw_inv()
        now = time.time()
        nw = Q.nightwave(ws, inv)
        if nw and (nw["weekly"] or nw["daily"]):
            left = _left(min([c["expiry"] for c in nw["weekly"] if c["expiry"]] or [nw["expiry"] or now]) - now)
            done_n = sum(1 for c in nw["weekly"] + nw["daily"] if c["done"])
            sub = t("quests.nw.sub2", left=left, done=done_n, n=len(nw["weekly"]) + len(nw["daily"]))
            if self._section("nightwave", "☾", t("quests.nw"), sub):
                for c in nw["daily"] + nw["weekly"]:
                    tag = {"elite": " ★", "daily": " ☼"}.get(c["kind"], "")
                    if c["done"]:
                        text, kind = f"   ✔ {c['name']}{tag}", "ready"
                    else:
                        count = f" {_n(c['progress'])}/{_n(c['required'])}" if c["required"] > 1 else ""
                        dl = ("  · " + _left(c["expiry"] - now)) if c["kind"] == "daily" and c["expiry"] else ""
                        text, kind = f"   - {c['name']}{tag}{count} ({_n(c['standing'])}){dl}", "obj"
                    tip = f"{c['name']}{tag}\n{c['desc']}\n{_n(c['standing'])} standing · {_n(c['progress'])}/{_n(c['required'])}"
                    lab = self._label(text, kind)
                    lab.setToolTip(tip)
                    self.rows.addWidget(lab)
                    if c["desc"] and not c["done"]:          # the goal in a few words, under the name
                        d = self._label("      " + c["desc"], "act")
                        d.setToolTip(tip)
                        self.rows.addWidget(d)
        cal = Q.calendar(ws, inv)
        if cal and cal["challenges"]:
            done = [c for c in cal["challenges"] if c["done"]]
            todo = [c for c in cal["challenges"] if not c["done"]]
            sub = t("quests.cal.sub", season=cal["season"], left=_left((cal["expiry"] or now) - now),
                    done=len(done), n=len(cal["challenges"]))
            if self._section("calendar", "▦", t("quests.cal"), sub):
                if not cal["known"]:
                    self.rows.addWidget(self._label("   " + t("quests.cal.unknown"), "act"))
                for c in todo[:int(CFG.get("goals_cal_rows", 4))]:
                    kind = "wait" if c["active"] else "obj"
                    act = ("  " + t("quests.cal.active") + (f" {_n(c['progress'])}/{_n(c['required'])}" if c.get("required") else "")
                           if c["active"] else "")
                    self.rows.addWidget(self._label(f"   - {c['name']}{act}", kind))
                    if c["desc"]:
                        self.rows.addWidget(self._label("      " + c["desc"], "act"))

    def _draw_routine(self):
        """Sortie, Archon Hunt, Elite Deep / Temporal Archimedea and Descendia: done or not, from the game file. What the
        file cannot tell (Archimedea finished?) can be ticked by hand with a right-click, until the reset."""
        from app.game import quests as Q
        rows = Q.routine(Q.cached(), self._raw_inv())
        if not rows:
            return
        now = time.time()
        manual = {k: v for k, v in (CFG.get("goals_manual_done") or {}).items() if v > now}
        n_done = sum(1 for r in rows if r["done"] or r["key"] in manual)
        if not self._section("routine", "⚔", t("quests.rt"), t("quests.rt.sub", done=n_done, n=len(rows))):
            return
        s = self.store
        if s.trades is not None:                       # trades left today (from the same game file)
            from app.game.standing import trades_stale
            stale = trades_stale(s.synced)
            tr = self._label(f"   ⇄ {t('bar.trades', n=s.trades)}" + (f"/{s.mr}" if s.mr else "") + (" ⚠" if stale else ""),
                             "ready" if s.trades and not stale else "obj")
            tr.setToolTip(t("bar.trades.tip", when=time.strftime("%d/%m %H:%M", time.localtime(s.synced)) if s.synced else "–")
                          + (" " + t("bar.trades.stale") if stale else ""))
            self.rows.addWidget(tr)
        for r in rows:
            done = bool(r["done"]) or r["key"] in manual
            left = ("  · " + t("quests.rt.reset", left=_left(r["expiry"] - now))) if r.get("expiry") and not done else ""
            prog = f" {r['progress']}" if r["progress"] else ""
            if done:
                lab = self._label(f"   ✔ {r['name']}{prog}", "ready")
            else:
                lab = self._label(f"   - {r['name']}{prog}{left}" + (" (?)" if r["done"] is None else ""), "obj")
            tip = t("quests.rt.unknown") if r["done"] is None and not done else ""
            lab.setToolTip((tip + "\n" if tip else "") + t("quests.rt.tip"))
            self._menu_on(lab, lambda pos, w=lab, r=r, d=done: self._routine_menu(w, pos, r, d))
            self.rows.addWidget(lab)

    def _routine_menu(self, w, pos, r, done):
        cur = {k: v for k, v in (CFG.get("goals_manual_done") or {}).items() if v > time.time()}
        m = QMenu(self)
        if r["key"] in cur:
            a = m.addAction(t("quests.rt.unmark"))
            a.triggered.connect(lambda: self._set_manual({k: v for k, v in cur.items() if k != r["key"]}))
        elif not done:
            a = m.addAction(t("quests.rt.mark"))
            until = r.get("expiry") or (time.time() + 86400)
            a.triggered.connect(lambda: self._set_manual(dict(cur, **{r["key"]: until})))
        b = m.addAction(t("goals.untrack.all", name=t("quests.rt")))
        b.triggered.connect(lambda: self._set_untracked(list(CFG.get("goals_untracked") or []) + ["routine|*"]))
        m.exec(w.mapToGlobal(pos))

    def _set_manual(self, d):
        save_config({"goals_manual_done": d})
        self.refresh(force=True)

    def _weekly_menu(self, w, pos, o):
        from app.game import weekly as WK
        m = QMenu(self)
        a = m.addAction(t("goals.weekly.untrack"))
        a.triggered.connect(lambda: (WK.get().track(o["vendor"], o["id"], False), self.refresh(force=True)))
        m.exec(w.mapToGlobal(pos))

    def _identify_menu(self, w, pos, u):
        """Which offer was it? The ones whose item went up in your inventory come first (★)."""
        from app.game import weekly as WK
        m = QMenu(self)
        m.addSection(t("goals.weekly.which", vendor=u["vendor_name"]))
        for i in u["items"]:
            star = "★ " if i["id"] in u["candidates"] else ""
            qty = f" ×{thousands(i['qty'])}" if i["qty"] > 1 else ""
            a = m.addAction(star + i["name"] + qty)
            a.triggered.connect(lambda _c=False, s=i["id"]: (WK.get().identify(u["key"], s), self.refresh(force=True)))
        m.addSeparator()
        sk = m.addAction(t("weekly.skip"))
        sk.triggered.connect(lambda: (WK.get().identify(u["key"], WK.SKIP), self.refresh(force=True)))
        m.exec(w.mapToGlobal(pos))

    # ---------- tracking the activities ----------
    def _menu_on(self, w, handler):
        """Right-click menu on a line, when tracking from the overlay is allowed (Settings)."""
        if not CFG.get("goals_track_interact", True):
            return
        w.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        w.customContextMenuRequested.connect(handler)

    def _set_untracked(self, keys):
        save_config({"goals_untracked": sorted(set(keys))})
        self.refresh(force=True)

    def _activity_menu(self, w, pos, key):
        m = QMenu(self)
        a = m.addAction(t("goals.untrack.one"))
        a.triggered.connect(lambda: self._set_untracked(list(CFG.get("goals_untracked") or []) + [key]))
        m.exec(w.mapToGlobal(pos))

    def _quest_menu(self, w, pos, g):
        cur = list(CFG.get("goals_untracked") or [])
        m = QMenu(self)
        whole = f"{g['tag']}|*"
        if whole in cur or any(k.startswith(g["tag"] + "|") for k in cur):
            a = m.addAction(t("goals.track.all", name=g["name"]))
            a.triggered.connect(lambda: self._set_untracked([k for k in cur if not k.startswith(g["tag"] + "|")]))
        if whole not in cur:
            b = m.addAction(t("goals.untrack.all", name=g["name"]))
            b.triggered.connect(lambda: self._set_untracked(cur + [whole]))
        m.exec(w.mapToGlobal(pos))

    def _item_menu(self, w, pos, it):
        m = QMenu(self)
        a = m.addAction(t("goals.menu.hide"))
        a.triggered.connect(lambda: (self.plan.hide(it["key"]), self.refresh(force=True)))
        b = m.addAction(t("goals.menu.market"))
        b.triggered.connect(lambda: QDesktopServices.openUrl(QUrl(market_url(it["slug"]))))
        m.exec(w.mapToGlobal(pos))
