"""Riven flip tab: rivens listed on warframe.market below what comparable ones are worth (price, sales, stats)."""
import threading
import time

from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QDesktopServices, QGuiApplication
from PyQt6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QProgressBar, QPushButton, QTableWidget, QVBoxLayout, QWidget,
)

import rivenmarket as M
import rivens as R
from config import CFG
from i18n import t
from uiutil import DIM_COLOR, HINT_STYLE, MUTED_STYLE, PRICE_COLOR, Cell, num_key

GREEN, AMBER, RED = QColor(110, 220, 140), QColor(255, 205, 110), QColor(255, 120, 120)
COLS = ["weapon", "riven", "stats", "rank", "price", "fair", "margin", "score", "sales", "listed", "seller"]


def describe_listing(l, index):
    parts = []
    for a in l["attrs"]:
        tag = index.get(a["url"])
        label = a["url"].replace("_", " ")
        if tag:
            lab = next((v[4] for typ in R.data()["types"].values() for k, v in typ.items() if k == tag), label)
            label = lab
        parts.append(f"{a['value']:+g} {label}")
    return ", ".join(parts)


class RivenFlipTab(QWidget):
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(int, str)

    def __init__(self, market):
        super().__init__()
        self.market = market
        self.store = M.Store()
        self.cancel = threading.Event()
        self.running = False
        self._weapons, self._index, self._rows = {}, {}, []
        self._sig = None
        self.progress.connect(self._on_progress)
        self.finished.connect(self._on_finished)

        self.btn_scan = QPushButton(t("rflip.scan"))
        self.btn_scan.setToolTip(t("rflip.scan.tip"))
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

        self.note = QLabel(t("rflip.note"))
        self.note.setWordWrap(True)
        self.note.setStyleSheet(HINT_STYLE)
        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet(MUTED_STYLE)
        self.bar = QProgressBar()
        self.bar.setVisible(False)

        self.table = QTableWidget(0, len(COLS))
        self.table.setHorizontalHeaderLabels([t("rflip.col." + c) for c in COLS])
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setSortingEnabled(True)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(COLS.index("stats"), QHeaderView.ResizeMode.Stretch)
        for i, c in enumerate(COLS):
            if c != "stats":
                hdr.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        lay = QVBoxLayout(self)
        lay.addLayout(bar)
        lay.addWidget(self.note)
        lay.addWidget(self.summary)
        lay.addWidget(self.bar)
        lay.addWidget(self.table, 1)
        self.btn_scan.clicked.connect(self.start_scan)
        self.btn_stop.clicked.connect(self.cancel.set)
        self.btn_open.clicked.connect(self.open_selected)
        self.btn_whisper.clicked.connect(self.copy_whisper)
        self.table.doubleClicked.connect(lambda _i: self.open_selected())

    # ---------- scanning (own thread, own request limiter) ----------
    def set_busy(self, _busy):
        pass

    def start_scan(self):
        if self.running:
            return
        self.summary.setText(t("rflip.starting"))
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
            self.summary.setText(t("rflip.scanning", done=done, total=total, name=name))

    def _on_finished(self, done, err):
        self.running = False
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

    def refresh(self, force=False, scanned=None, error=""):
        if self.running:
            return
        sig = (self.store.version, tuple(CFG[k] for k in CFG if k.startswith("riven_")))
        if not force and sig == self._sig:
            return
        self._sig = sig
        if not self._load_lists():
            self.summary.setText(t("rflip.empty") + (("\n" + t("rflip.error", err=error)) if error else ""))
            self.table.setRowCount(0)
            return
        self._rows = M.opportunities(self.store, self._weapons, self._index)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self._rows))
        for i, r in enumerate(self._rows[:500]):
            l = r["listing"]
            sales = f"{r['sales']}" if r["days"] >= 1 else "–"
            vals = [
                (r["weapon"], r["weapon"].lower(), None), (l["name"], l["name"].lower(), None),
                (describe_listing(l, self._index), None, None),
                (f"{l['rank']} · {l['rerolls']}↻", (l["rank"], l["rerolls"]), None),
                (f"{l['price']}p", l["price"], PRICE_COLOR), (f"{r['fair']}p", r["fair"], None),
                (f"+{r['margin']}p", r["margin"], GREEN if r["margin"] >= 2 * int(CFG["riven_min_margin"]) else AMBER),
                (f"{r['score']:.0f}", r["score"], GREEN if r["score"] >= 75 else AMBER if r["score"] >= 55 else RED),
                (sales, r["sales"] if r["days"] >= 1 else -1, None), (str(r["n"]), r["n"], DIM_COLOR),
                (f"{l['seller']} ({l['status']})", l["seller"].lower(), None),
            ]
            for c, (text, key, color) in enumerate(vals):
                self.table.setItem(i, c, Cell(text, text if key is None else key, color, center=c not in (0, 1, 2, 10)))
        self.table.setSortingEnabled(True)
        scanned_w = len(self.store.d["weapons"])
        text = t("rflip.summary", rows=len(self._rows), weapons=scanned_w)
        if scanned is not None:
            text = t("rflip.scanned", n=scanned) + " " + text
        if error:
            text += "\n" + t("rflip.error", err=error)
        self.summary.setText(text)

    # ---------- actions ----------
    def _selected(self):
        idx = self.table.currentRow()
        if idx < 0:
            return None
        item = self.table.item(idx, 0)
        # rows are sorted by the user: find the listing again through the weapon and riven name + price cells
        name, price = self.table.item(idx, 1).text(), self.table.item(idx, 4).text()
        for r in self._rows:
            if r["weapon"] == item.text() and r["listing"]["name"] == name and f"{r['listing']['price']}p" == price:
                return r
        return None

    def open_selected(self):
        r = self._selected()
        if r:
            QDesktopServices.openUrl(QUrl(M.auction_url(r["listing"])))

    def copy_whisper(self):
        r = self._selected()
        if r:
            QGuiApplication.clipboard().setText(M.whisper(r))
            self.summary.setText(t("rflip.copied", seller=r["listing"]["seller"]))
