"""Riven flip tab: rivens listed on warframe.market below what comparable ones are worth (price, sales, stats, the price
history the program collects, DE's weekly in-game trades). Scans by hand or by itself every N hours (riven_auto_hours).

Deals: the table (best expected profit a day first), filters (riven type, weapon, sort), and under it the selected
riven's details: how the fair price is made, the comparable rivens and the weapon's price history. A right click marks a
riven as contacted, records it in the journal as bought, hides its weapon or seller. The best deals are checked again
live (seller in game now? still listed?), and a good one with its seller online can play a sound.
Journal: the rivens you bought, listed and sold, with the profit; what they sold for corrects the fair price."""
import threading
import time

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QDesktopServices, QGuiApplication, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QProgressBar,
    QPushButton, QSplitter, QTableWidget, QTabWidget, QVBoxLayout, QWidget,
)

from app.trade import rivenmarket as M
from app.game import rivens as R
from app.core.config import CFG, save_config
from app.core.i18n import t
from app.core.uiutil import role
from app.core.uiutil import DIM_COLOR, PRICE_COLOR, Cell

GREEN, AMBER, RED = QColor(110, 220, 140), QColor(255, 205, 110), QColor(255, 120, 120)
COLS = ["weapon", "riven", "stats", "rank", "price", "fair", "de", "trend", "margin", "perday", "score", "sales", "listed",
        "age", "seller"]
TYPES = ("rifle", "shotgun", "pistol", "melee", "archgun", "kitgun", "zaw")
JCOLS = ["weapon", "riven", "buy", "fair", "state", "list", "sold", "profit", "days"]


def describe_listing(l, index):
    parts = []
    for a in l["attrs"]:
        tag = index.get(a["url"])
        label = a["url"].replace("_", " ")
        if tag:
            lab = next((v[4] for typ in R.data()["types"].values() for k, v in typ.items() if k == tag), label)
            label = lab
        parts.append(f"{round(float(a['value']), 1):+g} {label}")
    return ", ".join(parts)


def _days(d):
    it = CFG.get("language") == "it"
    if d is None:
        return "–"
    if d < 1:
        return "<1 g" if it else "<1 d"
    return f"{d:.0f} g" if it else f"{d:.0f} d"


class HistoryChart(QWidget):
    """The weapon's daily median and cheapest asking price (the program's own history), and DE's weekly median."""

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(120)
        self.hist, self.de = [], None

    def set_data(self, hist, de=None):
        self.hist, self.de = list(hist or []), de
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(34, 8, -8, -18)
        pal = self.palette()
        p.setPen(QPen(pal.mid().color(), 1))
        p.drawRect(r)
        if len(self.hist) < 2:
            p.setPen(pal.text().color())
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, t("rflip.chart.empty"))
            return
        days = [h[0] for h in self.hist]
        vals = [h[1] for h in self.hist] + [h[2] for h in self.hist] + ([self.de] if self.de else [])
        lo, hi = 0, max(vals) * 1.1 or 1
        d0, d1 = min(days), max(days)
        x = lambda d: r.left() + (d - d0) / max(1, d1 - d0) * r.width()
        y = lambda v: r.bottom() - (v - lo) / (hi - lo) * r.height()
        for idx, color in ((1, QColor(120, 200, 255)), (2, QColor(110, 220, 140))):
            path = QPainterPath()
            for n, h in enumerate(self.hist):
                pt = QPointF(x(h[0]), y(h[idx]))
                path.moveTo(pt) if n == 0 else path.lineTo(pt)
            p.setPen(QPen(color, 2))
            p.drawPath(path)
        if self.de:
            p.setPen(QPen(QColor(255, 205, 110), 1, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(r.left(), y(self.de)), QPointF(r.right(), y(self.de)))
        p.setPen(pal.text().color())
        f = p.font()
        f.setPointSizeF(max(7.0, f.pointSizeF() - 1))
        p.setFont(f)
        p.drawText(QRectF(0, r.top() - 6, 32, 14), Qt.AlignmentFlag.AlignRight, f"{int(hi)}")
        p.drawText(QRectF(0, r.bottom() - 8, 32, 14), Qt.AlignmentFlag.AlignRight, "0")
        p.drawText(QRectF(r.left(), r.bottom() + 2, r.width(), 14), Qt.AlignmentFlag.AlignLeft,
                   time.strftime("%d/%m", time.gmtime(d0 * 86400)))
        p.drawText(QRectF(r.left(), r.bottom() + 2, r.width(), 14), Qt.AlignmentFlag.AlignRight,
                   time.strftime("%d/%m", time.gmtime(d1 * 86400)))
        p.drawText(QRectF(r.left() + 4, r.top() + 2, r.width() - 8, 14), Qt.AlignmentFlag.AlignLeft, t("rflip.chart.legend"))


class RivenFlipTab(QWidget):
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(int, str)
    queue_scan = pyqtSignal()

    def __init__(self, market):
        super().__init__()
        self.market = market
        self.store = M.Store()
        self.cancel = threading.Event()
        self.running = False
        self._weapons, self._index, self._rows, self._shown_rows = {}, {}, [], []
        self._sig = None
        self._alerted = set()
        self.progress.connect(self._on_progress)
        self.queue_scan.connect(lambda: self.start_scan(auto=True))
        self.finished.connect(self._on_finished)

        self.btn_scan = QPushButton(t("rflip.scan"))
        self.btn_scan.setToolTip(t("rflip.scan.tip"))
        role(self.btn_scan, "primary")
        self.btn_stop = QPushButton(t("job.stop"))
        self.btn_stop.setEnabled(False)
        self.btn_open = QPushButton(t("rflip.open"))
        self.btn_whisper = QPushButton(t("rflip.whisper"))
        self.btn_whisper.setToolTip(t("rflip.whisper.tip"))
        bar = QHBoxLayout()
        bar.addWidget(self.btn_scan)
        bar.addWidget(self.btn_stop)
        bar.addStretch(1)
        bar.addWidget(self.btn_whisper)
        bar.addWidget(self.btn_open)

        # filters
        self.f_type = QComboBox()
        self.f_type.addItem(t("rflip.f.alltypes"), "")
        for ty in TYPES:
            self.f_type.addItem(t("rflip.type." + ty), ty)
        self.f_text = QLineEdit()
        self.f_text.setPlaceholderText(t("rflip.f.weapon"))
        self.f_text.setClearButtonEnabled(True)
        self.f_sort = QComboBox()
        self.f_sort.addItem(t("rflip.sort.day"), "day")
        self.f_sort.addItem(t("rflip.sort.margin"), "margin")
        self.f_sort.setCurrentIndex(max(0, self.f_sort.findData(CFG.get("riven_sort") or "day")))
        self.f_sort.setToolTip(t("rflip.sort.tip"))
        self.f_contacted = QCheckBox(t("rflip.f.contacted"))
        self.f_contacted.setChecked(True)
        fl = QHBoxLayout()
        fl.addWidget(QLabel(t("rflip.f.show")))
        fl.addWidget(self.f_type)
        fl.addWidget(self.f_text, 1)
        fl.addWidget(QLabel(t("rflip.f.sort")))
        fl.addWidget(self.f_sort)
        fl.addWidget(self.f_contacted)
        self.btn_unhide = QPushButton(t("rflip.unhide"))
        self.btn_unhide.setToolTip(t("rflip.unhide.tip"))
        fl.addWidget(self.btn_unhide)
        # more filters (kept in riven_table_filters): price, fair price, profit, profit a day, score, in-game popularity,
        # sales, re-rolls, age, seller online now
        from PyQt6.QtWidgets import QGridLayout, QSpinBox
        saved = dict(CFG.get("riven_table_filters") or {})
        self.f_num = {}
        fl2 = QGridLayout()
        fl2.setHorizontalSpacing(6)
        for key, lo, hi, step, default in (("price_max", 0, 100000, 10, 0), ("fair_min", 0, 100000, 10, 0),
                                           ("margin_min", 0, 100000, 10, 0), ("perday_min", 0, 10000, 5, 0),
                                           ("score_min", 0, 100, 5, 0), ("pop_min", 0, 200, 1, 0),
                                           ("sales_min", 0, 1000, 1, 0), ("rerolls_max", -1, 999, 1, -1),
                                           ("age_max", 0, 365, 1, 0)):
            sb = QSpinBox()
            sb.setRange(lo, hi)
            sb.setSingleStep(step)
            sb.setValue(int(saved.get(key, default)))
            sb.setSpecialValueText(t("rflip.tf.any"))       # the lowest value = no filter
            sb.setToolTip(t("rflip.tf." + key + ".tip"))
            sb.setKeyboardTracking(False)
            sb.valueChanged.connect(lambda _v: self._filters_changed())
            n = len(self.f_num)
            fl2.addWidget(QLabel(t("rflip.tf." + key)), n // 5, (n % 5) * 2, Qt.AlignmentFlag.AlignRight)
            fl2.addWidget(sb, n // 5, (n % 5) * 2 + 1)
            self.f_num[key] = sb
        self.f_combo = QCheckBox(t("rflip.tf.combo"))
        self.f_combo.setToolTip(t("rflip.tf.combo.tip"))
        self.f_combo.setChecked(bool(saved.get("combo_only")))
        self.f_combo.toggled.connect(lambda _c: self._filters_changed())
        fl2.addWidget(self.f_combo, 1, 8)
        self.f_online = QCheckBox(t("rflip.tf.online"))
        self.f_online.setToolTip(t("rflip.tf.online.tip"))
        self.f_online.setChecked(bool(saved.get("online_now")))
        self.f_online.toggled.connect(lambda _c: self._filters_changed())
        fl2.addWidget(self.f_online, 1, 9)
        reset = QPushButton(t("rflip.tf.reset"))
        reset.clicked.connect(self._filters_reset)
        fl2.addWidget(reset, 1, 10)
        fl2.setColumnStretch(11, 1)
        self.f_type.currentIndexChanged.connect(lambda _i: self._fill())
        self.f_text.textChanged.connect(lambda _s: self._fill())
        self.f_contacted.toggled.connect(lambda _c: self._fill())
        self.f_sort.currentIndexChanged.connect(self._sort_changed)
        self.btn_unhide.clicked.connect(self._unhide)

        self.note = QLabel(t("rflip.note"))
        self.note.setWordWrap(True)
        role(self.note, "hint")
        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        role(self.summary, "muted")
        self.accuracy = QLabel("")
        self.accuracy.setWordWrap(True)
        role(self.accuracy, "hint")
        self.bar = QProgressBar()
        self.bar.setVisible(False)

        self.table = QTableWidget(0, len(COLS))
        self.table.setHorizontalHeaderLabels([t("rflip.col." + c) for c in COLS])
        for i, c in enumerate(COLS):
            tip = t("rflip.col." + c + ".tip")
            if tip != "rflip.col." + c + ".tip":
                self.table.horizontalHeaderItem(i).setToolTip(tip)
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setSortingEnabled(True)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(COLS.index("stats"), QHeaderView.ResizeMode.Stretch)
        for i, c in enumerate(COLS):
            if c != "stats":
                hdr.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)

        # the selected riven: how the fair price is made, comparables, history
        self.detail = QLabel(t("rflip.detail.pick"))
        self.detail.setWordWrap(True)
        self.detail.setTextFormat(Qt.TextFormat.RichText)
        self.detail.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.comps = QTableWidget(0, 4)
        self.comps.setHorizontalHeaderLabels([t("rflip.comp.kind"), t("rflip.col.score"), t("rflip.col.price"),
                                              t("rflip.col.stats")])
        self.comps.verticalHeader().hide()
        self.comps.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.comps.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        for i in range(3):
            self.comps.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        self.chart = HistoryChart()
        dw = QWidget()
        dl = QHBoxLayout(dw)
        dl.setContentsMargins(0, 0, 0, 0)
        left = QVBoxLayout()
        left.addWidget(self.detail)
        left.addWidget(self.chart, 1)
        dl.addLayout(left, 2)
        dl.addWidget(self.comps, 3)
        split = QSplitter(Qt.Orientation.Vertical)
        split.addWidget(self.table)
        split.addWidget(dw)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)

        deals = QWidget()
        lay = QVBoxLayout(deals)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addLayout(fl)
        lay.addLayout(fl2)
        lay.addWidget(split, 1)

        # the journal
        self.jtable = QTableWidget(0, len(JCOLS))
        self.jtable.setHorizontalHeaderLabels([t("rflip.j." + c) for c in JCOLS])
        self.jtable.verticalHeader().hide()
        self.jtable.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.jtable.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.jtable.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.jtable.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.jsummary = QLabel("")
        self.jsummary.setWordWrap(True)
        role(self.jsummary, "muted")
        jnote = QLabel(t("rflip.j.note"))
        jnote.setWordWrap(True)
        role(jnote, "hint")
        jb = QHBoxLayout()
        for key, fn in (("listed", self._j_listed), ("sold", self._j_sold), ("kept", self._j_kept), ("remove", self._j_remove)):
            b = QPushButton(t("rflip.j.btn." + key))
            b.clicked.connect(fn)
            jb.addWidget(b)
        jb.addStretch(1)
        jw = QWidget()
        jl = QVBoxLayout(jw)
        jl.addWidget(jnote)
        jl.addWidget(self.jsummary)
        jl.addWidget(self.jtable, 1)
        jl.addLayout(jb)

        self.pages = QTabWidget()
        self.pages.addTab(deals, t("rflip.page.deals"))
        self.pages.addTab(jw, t("rflip.page.journal"))

        root = QVBoxLayout(self)
        root.addLayout(bar)
        root.addWidget(self.note)
        self.auto = QLabel("")
        role(self.auto, "hint")
        root.addWidget(self.auto)
        root.addWidget(self.summary)
        root.addWidget(self.accuracy)
        root.addWidget(self.bar)
        root.addWidget(self.pages, 1)

        self.btn_scan.clicked.connect(lambda: self.start_scan(auto=False))
        self.btn_stop.clicked.connect(self.cancel.set)
        self.btn_open.clicked.connect(self.open_selected)
        self.btn_whisper.clicked.connect(self.copy_whisper)
        self.table.doubleClicked.connect(lambda _i: self.open_selected())
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._menu)
        self.table.itemSelectionChanged.connect(self._show_detail)
        # scheduled scans: checked every minute, whether the tab is shown or not
        self._auto_timer = QTimer(self, interval=60_000, timeout=self._auto_check)
        self._auto_timer.start()
        QTimer.singleShot(5000, self._auto_check)
        # live check of the best deals: the seller's status now, and whether the riven is still listed
        self.live = M.LiveChecker(lambda: list(self._rows), lambda: self.running, market=self.market,
                                  on_change=self._live_changed)
        self.live.start()
        self._live_timer = QTimer(self, interval=4000, timeout=self._live_tick)
        self._live_timer.start()
        try:
            from app.trade import rivenweekly as WK
            WK.refresh()                           # DE's weekly in-game trades, in the background (once a day)
        except Exception:
            pass

    # ---------- live check and alerts ----------
    def _live_changed(self, listing, now, before):
        """(live thread) a deal's seller came online / the riven went: written to the log."""
        from app.core import logbus
        what = f"{listing.get('name', '')} {listing.get('price', '')}p ({listing.get('seller', '')})"
        if now.get("gone"):
            logbus.add("riven", f"no longer listed: {what}", "warn")
        elif now.get("status") in ("ingame", "online") and before.get("status") not in ("ingame", "online"):
            logbus.add("riven", f"seller {now['status']} now: {what}", "ok")

    def _live_tick(self):
        self._apply_live()
        self._alerts()
        self._trades()

    def _trades(self):
        """Riven trades the game's log saw (EE.log, like Quantframe): bought / sold go into the journal by themselves."""
        try:
            from app.game.eelog import LOCATION
            new = LOCATION.trades_since(getattr(self, "_trade_seq", 0))
        except Exception:
            return
        if not new:
            return
        self._trade_seq = new[-1]["seq"]
        from app.core import logbus
        changed = False
        for tr in new:
            for line in self.store.journal_trade(tr, self._rows, self._weapons):
                logbus.add("riven", line, "ok")
                changed = True
        if changed:
            self.refresh(force=True)

    def _alerts(self):
        """A sound (Settings > Sounds) and a Console line when a deal with at least riven_alert_margin of profit has
        its seller in game / online (by the live check, or by the scan when not checked yet). Once per riven."""
        least = int(CFG.get("riven_alert_margin") or 0)
        if least <= 0:
            return
        for r in self._rows[:int(CFG.get("riven_live_top") or 10) or 10]:
            l = r["listing"]
            if l["id"] in self._alerted or r["margin"] < least or r.get("contacted"):
                continue
            x = M.live(l)
            st = x.get("status") if x else l.get("status")
            if (x and x.get("gone")) or st not in ("ingame", "online"):
                continue
            self._alerted.add(l["id"])
            from app.core import logbus, sound
            sound.play("deal")
            logbus.add("riven", f"deal: {r['weapon']} {l['name']} {l['price']}p, profit +{r['margin']}p, "
                                f"{l['seller']} {t('rflip.status.' + st)}", "ok")
            self.summary.setText(t("rflip.alert", weapon=r["weapon"], riven=l["name"], price=l["price"],
                                   margin=r["margin"], seller=l["seller"]))

    def _apply_live(self):
        """The seller column (and the rows of rivens no longer listed) from the live checks."""
        col = COLS.index("seller")
        for i in range(self.table.rowCount()):
            cell = self.table.item(i, col)
            if cell is None:
                continue
            l = cell.data(Qt.ItemDataRole.UserRole)
            if not isinstance(l, dict):
                continue
            x = M.live(l)
            if not x:
                continue
            ago = int((time.time() - x["t"]) // 60)
            when = t("rflip.live.ago", m=ago) if ago >= 1 else t("rflip.live.now")
            mark = "✉ " if (self.store.d.get("contacted") or {}).get(str(l["id"])) else ""
            if x.get("gone"):
                text, color = f"{mark}{l['seller']} · {t('rflip.live.gone')}", RED
            else:
                st = x.get("status") or l.get("status") or "?"
                text = (f"{mark}{'●' if st in ('ingame', 'online') else '○'} {l['seller']} "
                        f"({t('rflip.status.' + st) if st in ('ingame', 'online', 'offline') else st}) · {when}")
                color = GREEN if st == "ingame" else AMBER if st == "online" else DIM_COLOR
            if cell.text() != text:
                cell.setText(text)
                cell.setForeground(QBrush(color))
                cell.setToolTip(t("rflip.live.tip"))

    # ---------- scheduled scans ----------
    def next_auto(self):
        """When the next automatic scan is due (epoch seconds), or None when they are off."""
        hours = float(CFG.get("riven_auto_hours") or 0)
        if hours <= 0:
            return None
        return int(self.store.d.get("last_scan") or 0) + hours * 3600

    def _auto_check(self):
        if not self.running:
            self.refresh()                     # the deals also when the tab is not shown (live check, alerts)
        due = self.next_auto()
        if due is None:
            self.auto.setText(t("rflip.auto.off"))
            return
        now = time.time()
        if not self.running and now >= due:
            M.log("scheduled scan")
            from app.core import logbus
            logbus.add("riven", "scheduled riven scan started")
            self.start_scan(auto=True)
            return
        left = max(0, due - now)
        self.auto.setText(t("rflip.auto.next", h=CFG.get("riven_auto_hours"),
                            left=(f"{int(left // 3600)}h {int(left % 3600 // 60):02d}m" if left >= 3600 else f"{int(left // 60)}m")))

    # ---------- scanning (own thread, own request limiter) ----------
    def set_busy(self, _busy):
        pass

    def start_scan(self, auto=False):
        if self.running:
            return
        from app.trade import netguard
        if not netguard.claim("rivens"):            # the price update is talking to the site: never both at once
            if auto:
                return                              # the timer tries again in a minute
            self.summary.setText(t("rflip.queued"))
            netguard.when_free(self.queue_scan.emit)
            return
        self.summary.setText(t("rflip.starting"))
        from app.core import sound
        sound.play("riven")
        M.log("scan button pressed")
        self.running = True
        self.cancel.clear()
        self.btn_scan.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.bar.setVisible(True)
        self.bar.setRange(0, 0)
        limiter = M.Limiter(market=self.market)

        def work():
            try:
                done, err = M.scan(limiter, self.store, progress=lambda d, n, name: self.progress.emit(d, n, name),
                                   cancel=self.cancel)
            except Exception as e:                      # never let a thread die silently
                import traceback
                M.log("scan crashed:\n" + traceback.format_exc())
                done, err = 0, f"{type(e).__name__}: {e}"
            self.finished.emit(done, err)
        threading.Thread(target=work, daemon=True, name="riven-scan").start()

    def _on_progress(self, done, total, name):
        self.bar.setRange(0, max(1, total))
        self.bar.setValue(done)
        if name:
            left = max(0, total - done) * M.Limiter().interval
            eta = t("rflip.eta.min", n=max(1, round(left / 60))) if left >= 90 else t("rflip.eta.sec", n=int(left))
            self.summary.setText(t("rflip.scanning", done=done, total=total, name=name, eta=eta))

    def _on_finished(self, done, err):
        self.running = False
        from app.trade import netguard
        netguard.release("rivens")
        if err:
            from app.core import logbus
            logbus.error("riven", err)
        QTimer.singleShot(0, self._auto_check)
        self.btn_scan.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.bar.setVisible(False)
        self.refresh(force=True, scanned=done, error=err)

    # ---------- showing ----------
    def _load_lists(self):
        try:
            import json
            w = json.loads(M.WEAPONS_FILE.read_text(encoding="utf-8")).get("data") or []
            a = json.loads(M.ATTRS_FILE.read_text(encoding="utf-8")).get("data") or []
        except Exception:
            return False
        self._weapons = {x["url_name"]: x for x in w}
        self._index = M.stat_index(a)
        return bool(self._weapons and self._index)

    def _sort_changed(self, _i):
        save_config({"riven_sort": self.f_sort.currentData()})
        self.refresh(force=True)

    def refresh(self, force=False, scanned=None, error=""):
        if self.running:
            return
        from app.trade import rivenweekly as WK
        sig = (self.store.version, WK._load().get("week"), tuple(str(CFG[k]) for k in CFG if k.startswith("riven_")))
        if not force and sig == self._sig:
            return
        self._sig = sig
        if not self._load_lists():
            self.summary.setText(t("rflip.empty") + (("\n" + t("rflip.error", err=error)) if error else ""))
            self.table.setRowCount(0)
            return
        self._rows = M.opportunities(self.store, self._weapons, self._index)
        self.store.note_deals(self._rows)
        self._fill()
        scanned_w = len(self.store.d["weapons"])
        text = t("rflip.summary", rows=len(self._rows), weapons=scanned_w)
        if scanned is not None:
            text = t("rflip.scanned", n=scanned) + " " + text
        if error:
            text += "\n" + t("rflip.error", err=error)
        de = WK._load()
        if de.get("week"):
            text += " " + t("rflip.de.week", week=de["week"].replace("_", " "), src=de.get("src") or "DE")
        self.summary.setText(text)
        bt = M.backtest(self.store, self._weapons, self._index)
        self.accuracy.setText(t("rflip.accuracy", n=bt["n"], mae=f"{bt['mae'] * 100:.0f}",
                                bias=f"{bt['bias'] * 100:+.0f}") if bt else t("rflip.accuracy.none"))
        self._fill_journal()

    def _filters_changed(self):
        vals = {k: sb.value() for k, sb in self.f_num.items()}
        vals["online_now"] = self.f_online.isChecked()
        vals["combo_only"] = self.f_combo.isChecked()
        save_config({"riven_table_filters": vals})
        self._fill()

    def _filters_reset(self):
        for k, sb in self.f_num.items():
            sb.blockSignals(True)
            sb.setValue(sb.minimum())
            sb.blockSignals(False)
        self.f_online.setChecked(False)
        self.f_combo.setChecked(False)
        self._filters_changed()

    def _visible_rows(self):
        ty, txt = self.f_type.currentData() or "", self.f_text.text().strip().lower()
        f = {k: sb.value() for k, sb in self.f_num.items()}
        out = []
        for r in self._rows:
            l = r["listing"]
            if (f["price_max"] and l["price"] > f["price_max"]) or (f["fair_min"] and r["fair"] < f["fair_min"]) \
                    or (f["margin_min"] and r["margin"] < f["margin_min"]) or (f["perday_min"] and r["per_day"] < f["perday_min"]) \
                    or (f["score_min"] and r["score"] < f["score_min"]) or (f["pop_min"] and r.get("pop", 0) < f["pop_min"]) \
                    or (f["sales_min"] and (r["days"] < 1 or r["sales"] < f["sales_min"])) \
                    or (f["rerolls_max"] >= 0 and l["rerolls"] > f["rerolls_max"]) \
                    or (f["age_max"] and r.get("age") is not None and r["age"] > f["age_max"]):
                continue
            if self.f_combo.isChecked() and not r.get("combo"):
                continue
            if self.f_online.isChecked():
                x = M.live(l)
                st = x.get("status") if x else l.get("status")
                if (x and x.get("gone")) or st not in ("ingame", "online"):
                    continue
            if ty and r.get("type") != ty:
                continue
            if txt and txt not in r["weapon"].lower() and txt not in r["listing"]["name"].lower():
                continue
            if not self.f_contacted.isChecked() and r.get("contacted"):
                continue
            out.append(r)
        return out

    def _fill(self):
        rows = self._visible_rows()[:500]
        self._shown_rows = rows
        self.table.setSortingEnabled(False)
        self.table.clearContents()
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            l = r["listing"]
            sales = f"{r['sales']}" if r["days"] >= 1 else "–"
            tr = r["t7"] if r["t7"] is not None else r["t30"]
            tr_text = "–" if tr is None else f"{tr * 100:+.0f}%" + (" ⚠" if r["t7"] is not None and r["t7"] < -0.05 else "")
            tr_color = None if tr is None else GREEN if tr > 0.03 else RED if tr < -0.05 else DIM_COLOR
            de = r.get("de")
            de_text = "–" if not de else f"{de['median']:.0f}p" + ("" if de.get("own") else " *")
            mark = "✉ " if r.get("contacted") else ""
            price_text = f"{l['price']}p" + (" ⚖" if r.get("bid") else "")
            vals = [
                (r["weapon"], r["weapon"].lower(), None),
                (("★ " if r.get("combo") else "") + l["name"], l["name"].lower(), AMBER if r.get("combo") else None),
                (describe_listing(l, self._index), None, None),
                (f"{l['rank']} · {l['rerolls']}↻", (l["rank"], l["rerolls"]), None),
                (price_text, l["price"], PRICE_COLOR),
                (f"{r['fair']}p" + (" ✔" if "sold" in r["basis"] else ""), r["fair"], None),
                (de_text, de["median"] if de else -1, DIM_COLOR if de and not de.get("own") else None),
                (tr_text, -9 if tr is None else tr, tr_color),
                (f"+{r['margin']}p", r["margin"], GREEN if r["margin"] >= 2 * int(CFG["riven_min_margin"]) else AMBER),
                (f"{r['per_day']:.0f}p", r["per_day"], GREEN if r["per_day"] >= 20 else None),
                (f"{r['score']:.0f}", r["score"], GREEN if r["score"] >= 75 else AMBER if r["score"] >= 55 else RED),
                (sales, r["sales"] if r["days"] >= 1 else -1, None), (str(r["n"]), r["n"], DIM_COLOR),
                (_days(r.get("age")), -1 if r.get("age") is None else r["age"], DIM_COLOR if (r.get("age") or 0) > 7 else None),
                (f"{mark}{l['seller']} ({t('rflip.status.' + l['status']) if l['status'] in ('ingame', 'online', 'offline') else l['status']})",
                 l["seller"].lower(), DIM_COLOR if r.get("contacted") else None),
            ]
            for c, (text, key, color) in enumerate(vals):
                cell = Cell(text, text if key is None else key, color, center=c not in (0, 1, 2, COLS.index("seller")))
                cell.setData(Qt.ItemDataRole.UserRole + 1, i)
                self.table.setItem(i, c, cell)
            self.table.item(i, COLS.index("seller")).setData(Qt.ItemDataRole.UserRole, dict(l))
            self.table.item(i, COLS.index("fair")).setToolTip(self._fair_tip(r))
            self.table.item(i, COLS.index("de")).setToolTip(self._de_tip(r))
            if r.get("combo"):
                self.table.item(i, 1).setToolTip(t("rflip.combo.tip", combo=self._combo_text(r["combo"][0]),
                                                   p=f"{r['combo'][1]:.0f}", n=r["combo"][2]))
            self.table.item(i, COLS.index("perday")).setToolTip(t("rflip.tip.perday", d=f"{r['exp_days']:.1f}",
                                                                 m=r["margin"]))
            self.table.item(i, COLS.index("trend")).setToolTip(self._trend_tip(r))
            self.table.item(i, 0).setToolTip(self._trend_tip(r))
            if r.get("bid"):
                self.table.item(i, COLS.index("price")).setToolTip(t("rflip.tip.bid", top=l.get("top_bid") or "–",
                                                                    buyout=l.get("buyout") or "–"))
        self.table.setSortingEnabled(True)
        self._apply_live()

    def _fair_tip(self, r):
        lines = [t("rflip.tip.ask", p=r["ask"]) if r["ask"] is not None else t("rflip.tip.noask")]
        lines.append(t("rflip.tip.sold", p=r["got"], n=r["n_sold"]) if r["got"] is not None
                     else t("rflip.tip.nosold", n=r["n_sold"]))
        lines.append(t("rflip.tip.de", p=r["de_fair"]) if r.get("de_fair") is not None else t("rflip.tip.node"))
        if r["t7"] is not None and r["t7"] < -0.05:
            lines.append(t("rflip.tip.falling", pct=f"{-max(-0.3, r['t7']) * 100:.0f}"))
        if abs(r.get("calib", 1.0) - 1.0) > 0.005:
            lines.append(t("rflip.tip.calib", pct=f"{(r['calib'] - 1) * 100:+.0f}"))
        return "\n".join(lines)

    def _de_tip(self, r):
        de = r.get("de")
        if not de:
            return t("rflip.tip.node")
        rolled = r["listing"]["rerolls"] > 0
        out = t("rflip.tip.dehead", kind=t("rflip.de.rolled" if rolled else "rflip.de.unrolled"),
                med=f"{de['median']:.0f}", avg=f"{de['avg']:.0f}", lo=f"{de['min']:.0f}", hi=f"{de['max']:.0f}",
                pop=f"{de['pop']:.0f}")
        if not de.get("own"):
            out += "\n" + t("rflip.tip.detype")
        if de.get("trend") is not None:
            out += "\n" + t("rflip.tip.detrend", pct=f"{de['trend'] * 100:+.0f}")
        return out

    def _trend_tip(self, r):
        f = lambda x: "–" if x is None else f"{x * 100:+.0f}%"
        lines = [t("rflip.tip.trend", med=r["median"] if r["median"] is not None else "–", t7=f(r["t7"]), t30=f(r["t30"]),
                   days=r["hist_days"])]
        if r["sell_days"] is not None:
            lines.append(t("rflip.tip.selldays", n=r["n_sold"], d=f"{r['sell_days']:.1f}"))
        return "\n".join(lines)

    def _show_detail(self):
        r = self._selected()
        if not r:
            self.detail.setText(t("rflip.detail.pick"))
            self.comps.setRowCount(0)
            self.chart.set_data([])
            return
        l = r["listing"]
        parts = []
        for name, v in (("sold", r.get("got")), ("ask", r.get("ask")), ("de", r.get("de_fair"))):
            parts.append(f"{t('rflip.basis.' + name)}: <b>{v}p</b>" if v is not None else f"{t('rflip.basis.' + name)}: –")
        calib = f" × {r['calib']:.2f} ({t('rflip.basis.calib')})" if abs(r.get("calib", 1) - 1) > 0.005 else ""
        self.detail.setText(
            f"<b>{r['weapon']} {l['name']}</b> · {l['price']}p → {t('rflip.col.fair').lower()} <b>{r['fair']}p</b>{calib}<br>"
            + " · ".join(parts) + "<br>"
            + t("rflip.detail.sell", d=f"{r['exp_days']:.1f}", pd=f"{r['per_day']:.0f}", m=r["margin"]) + "<br>"
            + self._graded(l, r["type"])
            + (("<br>" + t("rflip.combos") + " " + ", ".join(
                f"{'<b>' if c[3] else ''}{self._combo_text(c[0])} {c[1]:.0f}p ({c[2]}){'</b>' if c[3] else ''}"
                for c in r["combos"][:4])) if r.get("combos") else ""))
        comps = M.comparables(self.store, r, self._index)
        self.comps.setRowCount(len(comps))
        for i, (s, p, x, kind) in enumerate(comps):
            for c, text in enumerate((t("rflip.comp." + kind), f"{s:.0f}", f"{p}p", describe_listing(x, self._index))):
                cell = Cell(text, text, GREEN if kind == "sold" and c == 0 else None, center=c < 3)
                self.comps.setItem(i, c, cell)
        hist = (self.store.d["weapons"].get(r["url"]) or {}).get("hist") or []
        self.chart.set_data(hist, (r.get("de") or {}).get("median") if (r.get("de") or {}).get("own") else None)

    def _combo_text(self, pair):
        names = {}
        for typ in R.data()["types"].values():
            for k, v in typ.items():
                names.setdefault(k, v[4])
        return " + ".join(names.get(tg, str(tg).replace("_", " ")) for tg in pair)

    def _graded(self, l, wtype):
        """The stats with how well each rolled (S best … D worst of the game's 90-110 % range; ? = not known)."""
        colors = {"S": "#e8c547", "A": "#4fbf6a", "B": "#5aa9e6", "C": "#b48ce0", "D": "#e0584a", "?": "#9aa4b2"}
        parts = []
        for a, (tag, _v, g) in zip(l["attrs"], M.roll_grades(l, wtype, self._index)):
            label = describe_listing({"attrs": [a]}, self._index)
            parts.append(f"{label} <b style='color:{colors[g]}'>{g}</b>")
        return t("rflip.detail.rolls") + " " + ", ".join(parts)

    # ---------- actions ----------
    def _selected(self):
        idx = self.table.currentRow()
        if idx < 0:
            return None
        item = self.table.item(idx, 0)
        if item is None:
            return None
        n = item.data(Qt.ItemDataRole.UserRole + 1)
        return self._shown_rows[n] if isinstance(n, int) and 0 <= n < len(self._shown_rows) else None

    def _menu(self, pos):
        from PyQt6.QtWidgets import QMenu
        if self.table.itemAt(pos) is None:
            return
        self.table.selectRow(self.table.itemAt(pos).row())
        r = self._selected()
        if not r:
            return
        l = r["listing"]
        m = QMenu(self)
        m.addAction(t("rflip.whisper"), self.copy_whisper)
        m.addAction(t("rflip.open"), self.open_selected)
        m.addSeparator()
        if r.get("contacted"):
            m.addAction(t("rflip.m.uncontacted"), lambda: self._contacted(r, False))
        else:
            m.addAction(t("rflip.m.contacted"), lambda: self._contacted(r, True))
        m.addAction(t("rflip.m.bought"), lambda: self._bought(r))
        m.addSeparator()
        m.addAction(t("rflip.m.hideweapon", weapon=r["weapon"]), lambda: self._hide("riven_hidden_weapons", r["weapon"]))
        m.addAction(t("rflip.m.hideseller", seller=l["seller"]), lambda: self._hide("riven_hidden_sellers", l["seller"]))
        m.exec(self.table.viewport().mapToGlobal(pos))

    def _contacted(self, r, on):
        self.store.set_contacted(r["listing"]["id"], on)
        self.refresh(force=True)

    def _bought(self, r):
        price, ok = QInputDialog.getInt(self, t("rflip.m.bought"), t("rflip.j.ask.buy", riven=r["listing"]["name"]),
                                        int(r["listing"]["price"]), 0, 1_000_000)
        if ok:
            self.store.journal_buy(r, price)
            self.store.set_contacted(r["listing"]["id"], True)
            self.refresh(force=True)
            self.pages.setCurrentIndex(1)

    def _hide(self, key, value):
        cur = list(CFG.get(key) or [])
        if value not in cur:
            save_config({key: cur + [value]})
        self.refresh(force=True)

    def _unhide(self):
        n = len(CFG.get("riven_hidden_weapons") or []) + len(CFG.get("riven_hidden_sellers") or [])
        if n:
            save_config({"riven_hidden_weapons": [], "riven_hidden_sellers": []})
            self.summary.setText(t("rflip.unhidden", n=n))
            self.refresh(force=True)

    def open_selected(self):
        r = self._selected()
        if r:
            QDesktopServices.openUrl(QUrl(M.auction_url(r["listing"])))

    def copy_whisper(self):
        r = self._selected()
        if r:
            QGuiApplication.clipboard().setText(M.whisper(r))
            self.summary.setText(t("rflip.copied", seller=r["listing"]["seller"]))
            if not r.get("contacted"):
                self.store.set_contacted(r["listing"]["id"], True)        # a whisper copied = contacted
                r["contacted"] = int(time.time())

    # ---------- journal ----------
    def _fill_journal(self):
        j = self.store.journal()
        self.jtable.setRowCount(len(j))
        now = time.time()
        for i, e in enumerate(reversed(j)):
            n = len(j) - 1 - i
            profit = (e["sold"] - e["buy"]) if e.get("sold") is not None else None
            end = e.get("t_sold") or now
            vals = (e["weapon"], e["riven"], f"{e['buy']}p", f"{e['fair']}p", t("rflip.j.state." + e["state"]),
                    f"{e['list']}p" if e.get("list") else "–", f"{e['sold']}p" if e.get("sold") is not None else "–",
                    (f"{profit:+d}p" if profit is not None else "–"), _days((end - e["t_buy"]) / 86400))
            for c, text in enumerate(vals):
                color = (GREEN if profit and profit > 0 else RED if profit and profit < 0 else None) if c == 7 else None
                cell = Cell(text, text, color, center=c > 1)
                cell.setData(Qt.ItemDataRole.UserRole, n)
                if e.get("auto") and c == 4:
                    cell.setToolTip(t("rflip.j.auto"))
                self.jtable.setItem(i, c, cell)
        s = self.store.journal_summary()
        cal = self.store.calibration().get("*")
        self.jsummary.setText(t("rflip.j.summary", n=s["n_sold"], profit=f"{s['profit']:+d}", held=s["n_held"],
                                invested=s["invested"], days=f"{s['days']:.1f}" if s["days"] is not None else "–")
                              + " " + (t("rflip.j.calib", pct=f"{(cal - 1) * 100:+.0f}") if cal else t("rflip.j.nocalib")))

    def _jsel(self):
        i = self.jtable.currentRow()
        it = self.jtable.item(i, 0) if i >= 0 else None
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    def _j_listed(self):
        n = self._jsel()
        if n is None:
            return
        e = self.store.journal()[n]
        p, ok = QInputDialog.getInt(self, t("rflip.j.btn.listed"), t("rflip.j.ask.list"), int(e.get("list") or e["fair"]),
                                    0, 1_000_000)
        if ok:
            self.store.journal_set(n, state="listed", list=p, t_list=int(time.time()))
            self._fill_journal()

    def _j_sold(self):
        n = self._jsel()
        if n is None:
            return
        e = self.store.journal()[n]
        p, ok = QInputDialog.getInt(self, t("rflip.j.btn.sold"), t("rflip.j.ask.sold"), int(e.get("list") or e["fair"]),
                                    0, 1_000_000)
        if ok:
            self.store.journal_set(n, state="sold", sold=p, auto=False)
            self.refresh(force=True)

    def _j_kept(self):
        n = self._jsel()
        if n is not None:
            self.store.journal_set(n, state="kept")
            self._fill_journal()

    def _j_remove(self):
        n = self._jsel()
        if n is not None:
            self.store.journal_remove(n)
            self.refresh(force=True)
