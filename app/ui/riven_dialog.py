"""Revealed rivens of your inventory -> Quantframe's riven stock, after a check window."""
import threading
import time

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout, QHeaderView, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from app.trade import quantframe as Q
from app.game import rivens as R
from app.core.i18n import t
from app.core.uiutil import role
from app.core.uiutil import HINT_STYLE, MUTED_STYLE

COL_CHECK, COL_WEAPON, COL_NAME, COL_STATS, COL_RANK, COL_SENT = range(6)


class RivenDialog(QDialog):
    progress = pyqtSignal(int, int, str)
    finished_all = pyqtSignal()

    def __init__(self, items, skipped=(), parent=None, market=None, sender=None, amap=None):
        super().__init__(parent)
        self.items, self.market = items, market
        self._sender, self._amap = sender, amap
        self.setWindowTitle(t("riv.title"))
        self.resize(900, 520)
        note = QLabel(t("riv.note"))
        note.setWordWrap(True)
        role(note, "hint")
        self.table = QTableWidget(len(items), 6)
        self.table.setHorizontalHeaderLabels(["", t("riv.col.weapon"), t("riv.col.name"), t("riv.col.stats"),
                                              t("riv.col.rank"), t("qf.col.sent")])
        self.table.verticalHeader().hide()
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(COL_STATS, QHeaderView.ResizeMode.Stretch)
        for c in (COL_CHECK, COL_WEAPON, COL_NAME, COL_RANK, COL_SENT):
            hdr.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        sent = R.load_sent()
        self.checks = []
        for i, r in enumerate(items):
            chk = QCheckBox()
            when = sent.get(r["id"])
            chk.setChecked(when is None)
            self.table.setItem(i, COL_CHECK, QTableWidgetItem())
            self.table.setCellWidget(i, COL_CHECK, chk)
            self.table.setItem(i, COL_WEAPON, self._cell(r["weapon"]))
            self.table.setItem(i, COL_NAME, self._cell(r["mod_name"]))
            self.table.setItem(i, COL_STATS, self._cell(R.describe(r)))
            self.table.setItem(i, COL_RANK, self._cell(t("riv.rank", rank=r["rank"], rolls=r["rerolls"])))
            self.table.setItem(i, COL_SENT, self._cell("" if when is None else time.strftime("%d/%m", time.localtime(when))))
            self.checks.append(chk)
        self.status = QLabel(t("riv.skipped", n=len(skipped), why=", ".join(sorted(set(skipped))[:3])) if skipped else "")
        self.status.setWordWrap(True)
        role(self.status, "muted")
        self.btn_send = QPushButton(t("qf.send"))
        self.btn_send.setDefault(True)
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        box.rejected.connect(self.reject)
        row = QHBoxLayout()
        row.addWidget(self.status, 1)
        row.addWidget(self.btn_send)
        row.addWidget(box)
        lay = QVBoxLayout(self)
        lay.addWidget(note)
        lay.addWidget(self.table, 1)
        lay.addLayout(row)
        self.btn_send.clicked.connect(self.send)
        self.progress.connect(self._on_progress)
        self.finished_all.connect(self._on_finished)
        self._errors, self._ok = [], 0

    @staticmethod
    def _cell(text):
        it = QTableWidgetItem(text)
        it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
        return it

    def chosen(self):
        return [r for i, r in enumerate(self.items) if self.checks[i].isChecked()]

    def send(self):
        todo = self.chosen()
        if not todo:
            self.status.setText(t("qf.none"))
            return
        self.btn_send.setEnabled(False)
        self._errors, self._ok = [], 0
        sender = self._sender

        def work():
            try:
                amap = self._amap or R.load_attribute_map(self.market)
            except Exception as ex:
                self.progress.emit(len(todo), len(todo), t("riv.noattrs", err=f"{type(ex).__name__}: {ex}"))
                self.finished_all.emit()
                return
            for n, r in enumerate(todo, start=1):
                label = f"{r['weapon']} {r['mod_name']}"
                try:
                    body = R.payload(r, amap)
                    (sender or (lambda b: Q.post("/stock_riven", b)))(body)
                    R.mark_sent(r["id"])
                    self.progress.emit(n, len(todo), "")
                except (Q.QuantframeError, ValueError) as ex:
                    msg = str(ex)
                    self.progress.emit(n, len(todo), f"{label}: {msg}")
                    if "cannot reach" in msg or "address must" in msg:
                        break
            self.finished_all.emit()
        threading.Thread(target=work, daemon=True).start()

    def _on_progress(self, done, total, err):
        if err:
            self._errors.append(err)
        else:
            self._ok += 1
        self.status.setText(t("qf.progress", done=done, total=total))

    def _on_finished(self):
        self.btn_send.setEnabled(True)
        text = t("qf.done", ok=self._ok, failed=len(self._errors))
        if self._errors:
            text += "\n" + "\n".join(self._errors[:4])
        self.status.setText(text)
