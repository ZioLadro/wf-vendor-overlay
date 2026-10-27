"""Recommendations tab: what is worth buying with standing (see recommend.py for the formula)."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QHBoxLayout, QHeaderView, QLabel, QPushButton, QSpinBox,
    QTableWidget, QVBoxLayout, QWidget,
)

from config import CFG, save_config
from i18n import t
from standing import afford_text, get_store
from overlay import volume_color
from recommend import recommend
from uiutil import role
from uiutil import (
    HINT_STYLE, MAXRANK_COLOR, MUTED_STYLE, PRICE_COLOR, STANDING_COLOR, Cell, attach_item_menu, kind_label,
    thousands,
)


class RecommendTab(QWidget):
    def __init__(self, market, refresher):
        super().__init__()
        self.market, self.refresher = market, refresher
        self._missing = []

        self.vendor = QComboBox()
        self.kind = QComboBox()
        self.kind.addItem(t("prices.alltypes"), None)
        for k in ("mod", "arcane", "other"):
            self.kind.addItem(kind_label(k), k)
        self.min_vol = QSpinBox(minimum=0, maximum=100000, value=int(CFG["rec_min_volume"]))
        self.min_price = QSpinBox(minimum=0, maximum=100000, value=int(CFG["rec_min_price"]))
        self.min_price.setSuffix(" p")

        self.best_only = QCheckBox(t("rec.best_per_vendor"))
        self.best_only.setToolTip(t("rec.best_per_vendor.tip"))
        self.best_only.setChecked(bool(CFG["rec_best_per_vendor"]))
        top = QHBoxLayout()
        top.addWidget(QLabel(t("rec.vendor")))
        top.addWidget(self.vendor, 1)
        top.addWidget(self.best_only)
        top.addWidget(self.kind)
        top.addWidget(QLabel(t("rec.min_volume")))
        top.addWidget(self.min_vol)
        top.addWidget(QLabel(t("rec.min_price")))
        top.addWidget(self.min_price)

        self.summary = QLabel("")
        role(self.summary, "muted")
        self.summary.setWordWrap(True)
        self.btn_fetch = QPushButton(t("rec.fetch"))
        self.btn_fetch.setToolTip(t("rec.fetch.tip"))
        bar = QHBoxLayout()
        bar.addWidget(self.summary, 1)
        bar.addWidget(self.btn_fetch)

        self.headers = [t("col.rank"), t("col.item"), t("col.vendor"), t("col.cost"), t("col.reqrank"),
                        t("col.price"), t("col.volume"), t("col.ppk"), t("col.score")]
        self.table = QTableWidget(0, len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for c in (0, 2, 3, 4, 5, 6, 7, 8):
            hdr.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSortIndicator(0, Qt.SortOrder.AscendingOrder)

        hint = QLabel(t("rec.hint"))
        role(hint, "hint")
        hint.setWordWrap(True)

        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addLayout(bar)
        lay.addWidget(self.table, 1)
        lay.addWidget(hint)

        attach_item_menu(self.table, 1)
        self.fill_vendors()
        self.vendor.currentIndexChanged.connect(lambda _: self.refresh(force=True))
        self.kind.currentIndexChanged.connect(lambda _: self.refresh(force=True))
        self.best_only.toggled.connect(self._best_toggled)
        self.min_vol.valueChanged.connect(self._limits_changed)
        self.min_price.valueChanged.connect(self._limits_changed)
        self.btn_fetch.clicked.connect(lambda: self.refresher.start(self._missing, CFG["refresh_skip_age"]))

    def fill_vendors(self):
        cur = self.vendor.currentData()
        names = sorted({e["v"] for r in self.market.snapshot() for e in r["standing"]})
        self.vendor.blockSignals(True)
        self.vendor.clear()
        self.vendor.addItem(t("prices.allvendors"), None)
        for v in names:
            self.vendor.addItem(v, v)
        self.vendor.setCurrentIndex(max(0, self.vendor.findData(cur)))
        self.vendor.blockSignals(False)

    def _best_toggled(self, on):
        save_config({"rec_best_per_vendor": bool(on)})
        self.refresh(force=True)

    def _limits_changed(self):
        save_config({"rec_min_volume": self.min_vol.value(), "rec_min_price": self.min_price.value()})
        self.refresh(force=True)

    def set_busy(self, busy: bool):
        self.btn_fetch.setEnabled(not busy and bool(self._missing))

    def refresh(self, force=False):
        rows = self.market.snapshot()
        if self.vendor.count() <= 1:
            self.fill_vendors()
        # rebuild only when the data or a filter changed: this runs every 2 s
        sig = hash((get_store().version, self.vendor.currentData(), self.kind.currentData(), self.min_vol.value(),
                    self.min_price.value(), self.best_only.isChecked(), self.refresher.busy)
                   + tuple((r["slug"], len(r["standing"]), r["price"], r["pmax"], r["vol"], r["updated"]) for r in rows))
        if not force and sig == getattr(self, "_sig", None):
            return
        self._sig = sig
        picks, self._missing = recommend(
            rows, vendor=self.vendor.currentData(), kind=self.kind.currentData(),
            min_volume=self.min_vol.value(), min_price=self.min_price.value(),
            per_vendor=1 if self.best_only.isChecked() and self.vendor.currentData() is None else None)
        tb = self.table
        hdr = tb.horizontalHeader()
        sec, order = hdr.sortIndicatorSection(), hdr.sortIndicatorOrder()
        vpos = tb.verticalScrollBar().value()
        tb.setUpdatesEnabled(False)
        tb.setSortingEnabled(False)
        tb.setRowCount(0)
        tb.setRowCount(len(picks))
        for i, p in enumerate(picks, start=0):
            cells = [
                Cell(str(i + 1), i),
                Cell(p["name"], p["name"].lower(), center=False),
                Cell(p["vendor"], p["vendor"].lower(), center=False),
                Cell(thousands(p["cost"]), p["cost"], STANDING_COLOR),
                Cell(str(p["rank"]) if p["rank"] else "–", p["rank"]),
                Cell(f"{p['price']}p", p["price"], PRICE_COLOR),
                Cell(str(p["vol"]), p["vol"], volume_color(p["vol"])),
                Cell(f"{p['ppk']:.1f}", p["ppk"], MAXRANK_COLOR),
                Cell(f"{p['score']:.1f}", p["score"]),
            ]
            cells[1].setToolTip(kind_label(p["kind"]) + "\n\n" + afford_text(
                [{"v": p["vendor"], "s": p["cost"], "r": p["rank"], "t": p.get("tag")}]))
            cells[1].setData(Qt.ItemDataRole.UserRole, p["slug"])
            for c, cell in enumerate(cells):
                tb.setItem(i, c, cell)
        tb.setSortingEnabled(True)
        tb.sortByColumn(sec, order)
        tb.verticalScrollBar().setValue(vpos)
        tb.setUpdatesEnabled(True)

        n = len(self._missing)
        if picks:
            text = t("rec.summary", n=len(picks))
        else:
            text = t("rec.empty")
        if n:
            text += " " + t("rec.missing", n=n)
        self.summary.setText(text)
        self.btn_fetch.setText(t("rec.fetch_n", n=n) if n else t("rec.fetch"))
        self.btn_fetch.setEnabled(bool(n) and not self.refresher.busy)
