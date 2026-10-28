"""Weekly tab: vendor offers with a purchase limit (Teshin, Ironwake, Nightcap, Archimedean, Acrithis…), what you bought
this period, when the limits reset, and which offers you follow in the standing plan overlay. Purchases the program could
not identify are listed on top, to pick from the vendor's offers (see weekly.py)."""
import os
import time

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QHBoxLayout, QHeaderView, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from app.game import aleca
from app.game import weekly as WK
from app.core.i18n import t
from app.core.uiutil import Cell, role, thousands


def left(seconds) -> str:
    s = max(0, int(seconds))
    d, h, m = s // 86400, s % 86400 // 3600, s % 3600 // 60
    return f"{d}d {h}h" if d else (f"{h}h {m:02d}m" if h else f"{m}m")


def cost_text(cost) -> str:
    return " + ".join(f"{thousands(n)} {name}" for n, name in cost) if cost else "–"


class WeeklyTab(QWidget):
    COLS = ("vendor", "item", "cost", "bought", "resets", "track")

    def __init__(self, inventory, market=None):
        super().__init__()
        self.inventory, self.market = inventory, market
        self.w = WK.get()
        self._shown = None
        self.unknown_box = QFrame()
        self.unknown_box.setObjectName("weeklyunknown")
        self.unknown_box.setStyleSheet("#weeklyunknown { border: 1px solid #c9a227; border-radius: 6px; }")
        self.unknown_lay = QVBoxLayout(self.unknown_box)
        self.vendor = QComboBox()
        self.weekly_only = QCheckBox(t("weekly.only7"))
        self.weekly_only.setChecked(True)
        self.only_tracked = QCheckBox(t("weekly.onlytracked"))
        self.show_inactive = QCheckBox(t("weekly.inactive"))
        self.show_inactive.setToolTip(t("weekly.inactive.tip"))
        self.summary = QLabel("")
        role(self.summary, "muted")
        bar = QHBoxLayout()
        bar.addWidget(QLabel(t("weekly.vendor")))
        bar.addWidget(self.vendor, 1)
        bar.addWidget(self.weekly_only)
        bar.addWidget(self.only_tracked)
        bar.addWidget(self.show_inactive)
        self.btn_qf = QPushButton(t("rec.qf"))
        self.btn_qf.setToolTip(t("rec.qf.tip"))
        self.btn_qf.clicked.connect(self.send_to_quantframe)
        bar.addWidget(self.btn_qf)
        self.table = QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels([t("weekly.col." + c) for c in self.COLS])
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        hint = QLabel(t("weekly.hint"))
        hint.setWordWrap(True)
        role(hint, "hint")
        lay = QVBoxLayout(self)
        lay.addWidget(self.unknown_box)
        lay.addLayout(bar)
        lay.addWidget(self.summary)
        lay.addWidget(self.table, 1)
        lay.addWidget(hint)
        self.vendor.currentIndexChanged.connect(lambda _i: self.refresh(force=True))
        self.weekly_only.toggled.connect(lambda _c: self.refresh(force=True))
        self.only_tracked.toggled.connect(lambda _c: self.refresh(force=True))
        self.show_inactive.toggled.connect(lambda _c: self.refresh(force=True))
        self.table.itemChanged.connect(self._track_changed)
        # the game file is checked every few seconds (only its date is read unless it changed), visible or not: the
        # standing plan overlay shows the same data
        self._timer = QTimer(self, interval=5000, timeout=self.sync)
        self._timer.start()
        QTimer.singleShot(2000, self.sync)

    # ---------- data ----------
    def _path(self):
        p = self.inventory.path
        if not p or not os.path.exists(p):
            p = aleca.find_data_file()
        return p if p and os.path.exists(p) else ""

    def sync(self):
        path = self._path()
        if not path:
            return
        try:
            inv = WK.raw_inventory(path)
            WK.read_deltas(path)
            if inv is not None and (id(inv), WK._deltas_cache["key"]) != getattr(self, "_synced", None):
                self._synced = (id(inv), WK._deltas_cache["key"])
                self.w.sync(inv, WK.read_deltas(path))
        except Exception as e:
            from app.core import logbus
            logbus.error("weekly", f"{type(e).__name__}: {e}")
        if self.isVisible():
            self.refresh()

    # ---------- showing ----------
    def refresh(self, force=False):
        sig = (self.w.version, self.vendor.currentData(), self.weekly_only.isChecked(), self.only_tracked.isChecked(),
               self.show_inactive.isChecked(),
               int(time.time() // 60))
        if not force and sig == self._shown:
            return
        self._shown = sig
        self._fill_vendors()
        self._draw_unknown()
        now = time.time()
        rows = [o for o in self.w.offers(self.weekly_only.isChecked())
                if (not self.vendor.currentData() or o["vendor"] == self.vendor.currentData())
                and (not self.only_tracked.isChecked() or o["tracked"])
                and (self.show_inactive.isChecked() or o.get("active") is not False)]
        tb = self.table
        tb.blockSignals(True)
        tb.setSortingEnabled(False)
        tb.setRowCount(len(rows))
        for r, o in enumerate(rows):
            reset = o["expiry"] or (WK.next_reset(now) if o["hours"] == 168 else None)
            done = o["bought"] >= o["limit"]
            vname = o["vendor_name"] + ("  " + t("weekly.ev.on") if o.get("active") else "  " + t("weekly.ev.off")
                                        if o.get("active") is False else "")
            cells = [Cell(vname, o["vendor_name"].lower(), center=False),
                     Cell(o["name"] + (f" ×{thousands(o['qty'])}" if o["qty"] > 1 else ""), o["name"].lower(), center=False),
                     Cell(cost_text(o["cost"]), cost_text(o["cost"]).lower(), center=False),
                     Cell(f"{o['bought']}/{o['limit']}" + ("  ✔" if done else ""), o["bought"] / max(1, o["limit"])),
                     Cell(left(reset - now) if reset else "–", reset or 0)]
            for c, cell in enumerate(cells):
                tb.setItem(r, c, cell)
            tr = Cell("", 1 if o["tracked"] else 0)
            tr.setFlags(tr.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            tr.setCheckState(Qt.CheckState.Checked if o["tracked"] else Qt.CheckState.Unchecked)
            tr.setData(Qt.ItemDataRole.UserRole, (o["vendor"], o["id"]))
            tr.setToolTip(t("weekly.track.tip"))
            tb.setItem(r, 5, tr)
        tb.setSortingEnabled(True)
        tb.blockSignals(False)
        tb.resizeColumnsToContents()
        tb.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        n_b = sum(1 for o in rows if o["bought"])
        self.summary.setText(t("weekly.summary", n=len(rows), b=n_b, reset=left(WK.next_reset(now) - now),
                               region=self.w.region or "–"))

    def send_to_quantframe(self):
        """The purchases the Activities overlay confirmed from the game file (Martyr Symbiosis at the Entrati, Aerial Bond
        at Solaris United…) and not sent yet -> Quantframe's stock, after the usual check window."""
        import time as _time
        from PyQt6.QtWidgets import QMessageBox
        from app.game import goals as G
        from app.trade import quantframe as Q
        from app.ui.quantframe_dialog import SendDialog
        plan = G.get_plan()
        entries = []
        for e in plan.unsent():
            info = (self.market.info(e["slug"]) if self.market else None) or {}
            entries.append(dict(e, name=info.get("name") or e["name"], rank=0 if info.get("max_rank", 0) > 0 else None))
        if not entries:
            QMessageBox.information(self, t("rec.qf"), t("rec.qf.empty"))
            return
        start = _time.time() - 1
        SendDialog("stock", entries, self, all_checked=True).exec()
        sent = {e["slug"] for e in entries if (Q.sent_before("stock", e["slug"], e["rank"]) or {}).get("t", 0) >= start}
        if sent:
            plan.mark_sent(sent)

    def _track_changed(self, item):
        if item.column() != 5 or item.data(Qt.ItemDataRole.UserRole) is None:
            return
        vendor, offer = item.data(Qt.ItemDataRole.UserRole)
        self.w.track(vendor, offer, item.checkState() == Qt.CheckState.Checked)

    def _fill_vendors(self):
        cur = self.vendor.currentData()
        names = sorted({(v["name"], k) for k, v in WK.data().items()})
        if self.vendor.count() == len(names) + 1:
            return
        self.vendor.blockSignals(True)
        self.vendor.clear()
        self.vendor.addItem(t("weekly.allvendors"), "")
        for name, k in names:
            self.vendor.addItem(name, k)
        self.vendor.setCurrentIndex(max(0, self.vendor.findData(cur)))
        self.vendor.blockSignals(False)

    def _draw_unknown(self):
        while self.unknown_lay.count():
            it = self.unknown_lay.takeAt(0)
            w = it.widget()
            if w:
                w.hide()
                w.deleteLater()
            elif it.layout():
                while it.layout().count():
                    x = it.layout().takeAt(0).widget()
                    if x:
                        x.hide()
                        x.deleteLater()
        unk = self.w.unknown()
        self.unknown_box.setVisible(bool(unk))
        if not unk:
            return
        head = QLabel(t("weekly.unknown.head", n=len(unk), region=self.w.region or "–"))
        head.setWordWrap(True)
        head.setStyleSheet("font-weight: bold; color: #c9a227;")
        self.unknown_lay.addWidget(head)
        now = time.time()
        for u in unk:
            row = QHBoxLayout()
            lab = QLabel(t("weekly.unknown.row", vendor=u["vendor_name"], n=u["n"], left=left(u["expiry"] - now)))
            box = QComboBox()
            for i in u["items"]:
                star = "★ " if i["id"] in u["candidates"] else ""
                box.addItem(star + i["name"] + (f" ×{thousands(i['qty'])}" if i["qty"] > 1 else ""), i["id"])
            box.addItem(t("weekly.skip"), WK.SKIP)
            ok = QPushButton(t("weekly.confirm"))
            ok.clicked.connect(lambda _c=False, k=u["key"], b=box: (self.w.identify(k, b.currentData()), self.refresh(force=True)))
            row.addWidget(lab)
            row.addWidget(box, 1)
            row.addWidget(ok)
            self.unknown_lay.addLayout(row)
