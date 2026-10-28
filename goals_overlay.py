"""In-game standing plan: a small window over the game (always on top, semi-transparent) listing what to buy with standing
(the Recommendations' picks), how much standing is still missing and what to do to earn it.

It can be moved (drag the title bar), resized (corner grip), collapsed, made more or less transparent, and shown/hidden
with a hotkey (Settings: key_goals, F6 by default). It is interactive: tick an item you bought (it stays until the game
file confirms the purchase), right-click an item to hide it or open it on warframe.market. It is read again every time
AlecaFrame rewrites lastData.dat. The OCR never reads its area (it would see item names in it)."""
import time

from PyQt6.QtCore import QPoint, QRect, Qt, QTimer, QUrl
from PyQt6.QtGui import QAction, QColor, QDesktopServices, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QFrame, QHBoxLayout, QLabel, QMenu, QPushButton, QScrollArea, QSizeGrip, QVBoxLayout, QWidget,
)

import goals as G
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
        self.title = QLabel(t("goals.title"))
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
        fs = int(CFG.get("goals_font", 12))
        self.setStyleSheet(f"""
            QWidget {{ color: #e8eaed; font-size: {fs}px; background: transparent; }}
            #goalshead {{ background: rgba(20, 26, 36, 200); border-top-left-radius: 8px; border-top-right-radius: 8px; }}
            #goalstitle {{ font-weight: bold; color: #c9a227; }}
            #goalsbtn {{ background: rgba(255,255,255,18); border: none; border-radius: 4px; padding: 0; font-size: {fs}px; }}
            #goalsbtn:hover {{ background: rgba(255,255,255,50); }}
            #goalsfoot {{ color: #8c96a8; font-size: {max(9, fs - 2)}px; }}
            QLabel[g="group"] {{ color: #9fd3ff; font-weight: bold; margin-top: 6px; }}
            QLabel[g="act"] {{ color: #a8b0bf; font-size: {max(9, fs - 1)}px; }}
            QLabel[g="ok"] {{ color: #4fbf6a; }} QLabel[g="need"] {{ color: #e0b83a; }} QLabel[g="done"] {{ color: #4fbf6a; }}
            QCheckBox {{ spacing: 6px; }}
            QCheckBox::indicator {{ width: 12px; height: 12px; border: 1px solid #8c96a8; border-radius: 3px;
                                    background: rgba(0, 0, 0, 90); }}
            QCheckBox::indicator:checked {{ background: #4fbf6a; border-color: #4fbf6a; }}
            QScrollBar:vertical {{ background: transparent; width: 8px; }}
            QScrollBar::handle:vertical {{ background: rgba(255,255,255,60); border-radius: 4px; min-height: 20px; }}
            QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
            QMenu {{ background: #1b2027; border: 1px solid #3a4250; }} QMenu::item:selected {{ background: #2d3650; }}
        """)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        alpha = int(255 * max(20, min(100, int(CFG.get("goals_opacity", 82)))) / 100)
        p.setBrush(QColor(16, 20, 28, alpha))
        p.setPen(QPen(QColor(201, 162, 39, 150), 1))
        p.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 8, 8)

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
                           ("goals_only_short", "goals.opt.onlyshort")):
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

    def hideEvent(self, e):
        super().hideEvent(e)
        self._timer.stop()

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
                w.deleteLater()

    def _draw(self, data):
        self.body.setUpdatesEnabled(False)
        self._clear()
        groups = data["groups"]
        if CFG.get("goals_only_short"):
            groups = [g for g in groups if g["short"]]
        if not groups:
            lab = QLabel(t("goals.empty"))
            lab.setWordWrap(True)
            lab.setProperty("g", "act")
            self.rows.addWidget(lab)
        for g in groups:
            daily = f" · {t('goals.daily', n=_n(g['daily']))}" if g.get("daily") is not None else ""
            if g.get("cap") and g.get("daily") is not None:
                daily += f"/{_n(g['cap'])}"
            rank = f" · R{g['rank']}" if g.get("rank") is not None else ""
            head = QLabel(f"{g['name']}  {_n(g['standing'])}{rank}{daily}")
            head.setProperty("g", "group")
            head.setWordWrap(True)
            self.rows.addWidget(head)
            for it in g["items"]:
                self.rows.addWidget(self._item_row(it))
            if CFG.get("goals_activities", True) and g["activities"]:
                for a in g["activities"]:
                    lab = QLabel("• " + a)
                    lab.setProperty("g", "act")
                    lab.setWordWrap(True)
                    self.rows.addWidget(lab)
        recent = [d for d in data["done"] if time.time() - d.get("t", 0) < 86400][-3:]
        if recent:
            head = QLabel(t("goals.recent"))
            head.setProperty("g", "group")
            self.rows.addWidget(head)
            for d in reversed(recent):
                lab = QLabel(f"✔ {d['name']} ({d['vendor']}) · {time.strftime('%H:%M', time.localtime(d['t']))}")
                lab.setProperty("g", "done")
                self.rows.addWidget(lab)
        n = sum(len(g["items"]) for g in data["groups"])
        if not any(c for c in data["confirmed"]):
            self.status.setText(t("goals.foot", n=n))
        self.body.setUpdatesEnabled(True)

    def _item_row(self, it):
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)
        cb = QCheckBox(f"{it['name']}")
        cb.setChecked(bool(it.get("ticked")))
        cb.setToolTip(t("goals.item.tip", vendor=it["vendor"], cost=_n(it["cost"]), price=it.get("price") or "–",
                        vol=it.get("vol") or "–", rank=it.get("rank") or 0))
        cb.toggled.connect(lambda on, k=it["key"]: (self.plan.tick(k, on), self.refresh(force=True)))
        h.addWidget(cb, 1)
        if it.get("ticked"):
            st = QLabel(t("goals.waiting"))
            st.setProperty("g", "need")
        elif it["can"]:
            st = QLabel(t("goals.can", n=it["can"], cost=_n(it["cost"])))
            st.setProperty("g", "ok")
        elif it["need"] is not None:
            d = it.get("days")
            when = t("goals.today") if d == 1 else (t("goals.days", n=d) if d else "")
            st = QLabel(t("goals.need", n=_n(it["need"])) + (f" · {when}" if when else ""))
            st.setProperty("g", "need")
            st.setToolTip(t("goals.need.tip"))
        else:
            st = QLabel(_n(it["cost"]))
        if it.get("rank_ok") is False:
            st.setText(st.text() + "  " + t("goals.rank", r=it.get("rank")))
        h.addWidget(st)
        row.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        row.customContextMenuRequested.connect(lambda pos, w=row, i=it: self._item_menu(w, pos, i))
        cb.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        cb.customContextMenuRequested.connect(lambda pos, w=cb, i=it: self._item_menu(w, pos, i))
        return row

    def _item_menu(self, w, pos, it):
        m = QMenu(self)
        a = m.addAction(t("goals.menu.hide"))
        a.triggered.connect(lambda: (self.plan.hide(it["key"]), self.refresh(force=True)))
        b = m.addAction(t("goals.menu.market"))
        b.triggered.connect(lambda: QDesktopServices.openUrl(QUrl(market_url(it["slug"]))))
        m.exec(w.mapToGlobal(pos))
