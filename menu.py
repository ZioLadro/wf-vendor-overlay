"""Price-list window: tabs "Price list", "Recommendations" and "Settings"."""
import threading
import time

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QProgressBar,
    QPushButton, QTabWidget, QTableWidget, QVBoxLayout, QWidget,
)

from config import CFG, save_config
from inventory import Inventory
from inventory_tab import InventoryTab
from i18n import t
from market_auth import MarketAccount
from overlay import volume_color
from recommend_tab import RecommendTab
from refresher import Refresher
from settings_tab import SettingsTab
from uiutil import (
    DIM_COLOR, HINT_STYLE, MAXRANK_COLOR, MUTED_STYLE, PRICE_COLOR, STYLE, Cell, age_text, kind_label,
    attach_item_menu, make_icon, num_key, standing_cell,  # noqa: F401  (make_icon re-exported for main.py)
)

C_NAME, C_VENDOR, C_STANDING, C_KIND, C_PRICE, C_PMAX, C_VOL, C_UPD = range(8)


class PricesTab(QWidget):
    """Every tradable item sold by the vendors, with prices, volume and standing cost."""
    message = pyqtSignal(str)            # text for the window's status line
    baro_done = pyqtSignal(str)          # Baro download finished (emitted from its thread)

    def __init__(self, market, refresher):
        super().__init__()
        self.market, self.refresher = market, refresher
        self._baro = None
        self._sig = None                 # fingerprint of the displayed data (avoids useless rebuilds)
        self._built = 0.0

        self.search = QLineEdit(placeholderText=t("prices.search"), clearButtonEnabled=True)
        self.vendor = QComboBox()
        self.kind = QComboBox()
        self.kind.addItem(t("prices.alltypes"), None)
        for k in ("mod", "arcane", "other"):
            self.kind.addItem(kind_label(k), k)
        self.hide_zero = QCheckBox(t("prices.hide_zero"))
        self.hide_zero.setToolTip(t("prices.hide_zero.tip"))
        self.hide_zero.setChecked(bool(CFG["hide_zero_volume"]))
        self.count = QLabel("")
        self.count.setStyleSheet(MUTED_STYLE)
        self.fill_vendors()

        top = QHBoxLayout()
        top.addWidget(self.search, 1)
        top.addWidget(self.vendor)
        top.addWidget(self.kind)
        top.addWidget(self.hide_zero)
        top.addWidget(self.count)

        self.btn_vis = QPushButton(t("prices.update_shown"))
        self.btn_vis.setToolTip(t("prices.update_shown.tip"))
        self.btn_sel = QPushButton(t("prices.update_selected"))
        self.btn_sel.setToolTip(t("prices.update_selected.tip"))
        self.btn_baro = QPushButton(t("prices.update_baro"))
        self.btn_baro.setToolTip(t("prices.update_baro.tip"))
        actions = QHBoxLayout()
        actions.addWidget(self.btn_vis)
        actions.addWidget(self.btn_sel)
        actions.addStretch(1)
        actions.addWidget(self.btn_baro)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            t("col.item"), t("col.vendor"), t("col.standing"), t("col.type"), t("col.price"),
            t("col.pmax"), t("col.volume"), t("col.updated")])
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(C_NAME, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(C_VENDOR, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(C_VENDOR, 190)
        for c in range(C_STANDING, 8):
            hdr.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSortIndicator(C_NAME, Qt.SortOrder.AscendingOrder)

        hint = QLabel(t("prices.hint"))
        hint.setStyleSheet(HINT_STYLE)
        hint.setWordWrap(True)

        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addLayout(actions)
        lay.addWidget(self.table, 1)
        lay.addWidget(hint)

        attach_item_menu(self.table, C_NAME)
        self.hide_zero.toggled.connect(self._hide_zero_changed)
        self.search.textChanged.connect(lambda _: self.refresh(force=True))
        self.kind.currentIndexChanged.connect(lambda _: self.refresh(force=True))
        self.vendor.currentIndexChanged.connect(lambda _: self.refresh(force=True))
        self.btn_vis.clicked.connect(self.update_shown)
        self.btn_sel.clicked.connect(self.update_selected)
        self.btn_baro.clicked.connect(self.update_baro)
        self.baro_done.connect(self._on_baro_done)

    def fill_vendors(self):
        cur = self.vendor.currentData()
        self.vendor.blockSignals(True)
        self.vendor.clear()
        self.vendor.addItem(t("prices.allvendors"), None)
        for v in self.market.vendor_names():
            self.vendor.addItem(v, v)
        self.vendor.setCurrentIndex(max(0, self.vendor.findData(cur)))
        self.vendor.blockSignals(False)

    def _hide_zero_changed(self, on):
        save_config({"hide_zero_volume": bool(on)})
        self.refresh(force=True)

    def set_busy(self, busy: bool):
        for b in (self.btn_vis, self.btn_sel):
            b.setEnabled(not busy)

    # ---------- data ----------
    def refresh(self, force=False):
        rows = self.market.snapshot()
        q = self.search.text().strip().lower()
        kind = self.kind.currentData()
        vendor = self.vendor.currentData()
        total = len(rows)
        hide0 = self.hide_zero.isChecked()
        rows = [r for r in rows if (kind is None or r["kind"] == kind) and q in r["name"].lower()
                and (vendor is None or vendor in r["vendors"]) and not (hide0 and r["vol"] == 0)]

        # rebuild only when the data changed (or every 30 s so "x min ago" moves on)
        sig = hash(tuple((r["slug"], len(r["standing"]), r["price"], r["pmax"], r["vol"], r["updated"])
                         for r in rows))
        now = time.monotonic()
        if not force and sig == self._sig and now - self._built < 30:
            return
        self._sig, self._built = sig, now

        tb = self.table
        hdr = tb.horizontalHeader()
        sec, order = hdr.sortIndicatorSection(), hdr.sortIndicatorOrder()
        vpos = tb.verticalScrollBar().value()
        selected = {tb.item(i.row(), 0).data(Qt.ItemDataRole.UserRole) for i in tb.selectedIndexes()
                    if tb.item(i.row(), 0)}
        tb.setUpdatesEnabled(False)
        tb.setSortingEnabled(False)
        tb.setRowCount(0)                # rebuild from scratch: much faster than replacing 1200+ rows
        tb.setRowCount(len(rows))
        for i, r in enumerate(rows):
            p, pm, v = r["price"], r["pmax"], r["vol"]
            vend = ", ".join(r["vendors"])
            cells = [
                Cell(r["name"], r["name"].lower(), center=False),
                Cell(vend, vend.lower(), center=False),
                standing_cell(r["standing"]),
                Cell(kind_label(r["kind"]), r["kind"]),
                Cell("–" if p is None else f"{p}p", num_key(p), PRICE_COLOR if p is not None else DIM_COLOR),
                (Cell("–" if pm is None else f"{pm}p", num_key(pm), MAXRANK_COLOR if pm is not None else DIM_COLOR)
                 if r["ranked"] else Cell("", (0, 0))),
                Cell("–" if v is None else str(v), num_key(v), volume_color(v) if v is not None else DIM_COLOR),
                Cell(age_text(r["updated"]), r["updated"] or 0),
            ]
            cells[0].setData(Qt.ItemDataRole.UserRole, r["slug"])
            cells[1].setToolTip("\n".join(r["vendors"]))
            if r["ranked"]:
                cells[C_PMAX].setToolTip(t("tip.price_at_rank", n=r["max_rank"]))
            for c, cell in enumerate(cells):
                tb.setItem(i, c, cell)
        tb.setSortingEnabled(True)
        tb.sortByColumn(sec, order)
        if selected:
            sm = tb.selectionModel()
            for i in range(tb.rowCount()):
                if tb.item(i, 0).data(Qt.ItemDataRole.UserRole) in selected:
                    sm.select(tb.model().index(i, 0), sm.SelectionFlag.Select | sm.SelectionFlag.Rows)
        tb.verticalScrollBar().setValue(vpos)
        tb.setUpdatesEnabled(True)
        self.count.setText(t("prices.count_of", n=len(rows), total=total) if len(rows) != total
                           else t("prices.count", n=total))

    # ---------- updating prices / volumes ----------
    def _slugs(self, selected_only: bool) -> list:
        tb = self.table
        rows = sorted({i.row() for i in tb.selectedIndexes()}) if selected_only else range(tb.rowCount())
        return [tb.item(r, 0).data(Qt.ItemDataRole.UserRole) for r in rows if tb.item(r, 0)]

    def update_shown(self):
        self.refresher.start(self._slugs(False), CFG["refresh_skip_age"])

    def update_selected(self):
        self.refresher.start(self._slugs(True), 0)

    def update_baro(self):
        if self._baro and self._baro.is_alive():
            return
        self.btn_baro.setEnabled(False)
        self.message.emit(t("baro.downloading"))
        vendors, sig = self.market.vendors, self.baro_done

        def run():
            try:
                _ok, msg = vendors.refresh_baro()
            except Exception as e:
                msg = t("baro.error", err=e)
            sig.emit(msg)

        self._baro = threading.Thread(target=run, daemon=True)
        self._baro.start()

    def _on_baro_done(self, msg):
        self.btn_baro.setEnabled(True)
        self.message.emit(msg)
        self.fill_vendors()
        self.refresh(force=True)


class PriceList(QWidget):
    visibility = pyqtSignal(bool)        # True when the window opens, False when it closes
    restart_requested = pyqtSignal()     # the Settings tab asks to restart the program

    def __init__(self, market):
        super().__init__()
        self.market = market
        self.setWindowTitle(t("window.title"))
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self.resize(1080, 680)
        self.setStyleSheet(STYLE)

        self.refresher = Refresher(market, self)
        self.prices = PricesTab(market, self.refresher)
        self.inventory = Inventory()
        self.account = MarketAccount(market)
        self.inv_tab = InventoryTab(market, self.refresher, self.inventory, self.account)
        self.recommend = RecommendTab(market, self.refresher)
        self.settings = SettingsTab()
        self.settings.restart_requested.connect(self.restart_requested)
        self.tabs = QTabWidget()
        self.tabs.addTab(self.prices, t("tab.prices"))
        self.tabs.addTab(self.inv_tab, t("tab.inventory"))
        self.tabs.addTab(self.recommend, t("tab.recommend"))
        self.tabs.addTab(self.settings, t("tab.settings"))

        # status bar shared by the tabs (progress of the updates)
        self.bar = QProgressBar()
        self.bar.setVisible(False)
        self.status = QLabel("")
        self.status.setStyleSheet(MUTED_STYLE)
        self.btn_stop = QPushButton(t("job.stop"))
        self.btn_stop.setEnabled(False)
        bottom = QHBoxLayout()
        bottom.addWidget(self.status, 2)
        bottom.addWidget(self.bar, 1)
        bottom.addWidget(self.btn_stop)

        lay = QVBoxLayout(self)
        lay.addWidget(self.tabs, 1)
        lay.addLayout(bottom)

        self._timer = QTimer(self, timeout=self._tick)
        self.tabs.currentChanged.connect(lambda _: self._tick(force=True))
        self.btn_stop.clicked.connect(self.refresher.cancel)
        self.refresher.started.connect(self._on_started)
        self.refresher.progress.connect(self._on_progress)
        self.refresher.finished.connect(self._on_finished)
        self.prices.message.connect(self.status.setText)

    def _tick(self, force=False):
        w = self.tabs.currentWidget()
        if w is self.prices:
            self.prices.refresh(force=force)
        elif w is self.inv_tab:
            self.inv_tab.refresh(force=force)
        elif w is self.recommend:
            self.recommend.refresh(force=force)

    def _set_busy(self, busy: bool):
        self.bar.setVisible(busy)
        self.btn_stop.setEnabled(busy)
        self.prices.set_busy(busy)
        self.recommend.set_busy(busy)
        self.inv_tab.set_busy(busy)

    def _on_started(self, total):
        self._set_busy(True)
        self.bar.setRange(0, total)
        self.bar.setValue(0)
        self.status.setText(f"0 / {total}")

    def _on_progress(self, done, total, errors):
        self.bar.setMaximum(total)
        self.bar.setValue(done)
        self.status.setText(f"{done} / {total}" + (t("job.errors_short", n=errors) if errors else ""))

    def _on_finished(self, msg):
        self._set_busy(False)
        self.status.setText(msg)
        self._tick(force=True)

    # ---------- window ----------
    def toggle(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow()

    def showEvent(self, e):
        super().showEvent(e)
        self._tick(force=True)
        self._timer.start(int(CFG["menu_refresh_ms"]))
        self.visibility.emit(True)

    def hideEvent(self, e):
        super().hideEvent(e)
        self._timer.stop()
        self.refresher.cancel()          # closing the window stops any update in progress
        self.visibility.emit(False)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(e)
