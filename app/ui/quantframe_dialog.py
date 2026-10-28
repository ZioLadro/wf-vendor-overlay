"""Confirmation window before sending items to Quantframe: choose what and how many."""
import threading
import time

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout, QHeaderView, QLabel, QPushButton,
    QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from app.trade import quantframe as Q
from app.core.i18n import t
from app.core.uiutil import role
from app.core.uiutil import HINT_STYLE, MUTED_STYLE

COL_CHECK, COL_NAME, COL_RANK, COL_QTY, COL_SENT = range(5)


class SendDialog(QDialog):
    """kind: "stock" (Quantframe's stock: its Live Scraper may list the items) or "wish" (its wish list).
    entries: [{"slug", "name", "rank": int | None, "qty": int}]"""
    progress = pyqtSignal(int, int, str)            # done, total, error text ("" = ok)
    finished_all = pyqtSignal()

    def __init__(self, kind, entries, parent=None, sender=None, all_checked=False):
        super().__init__(parent)
        self.kind, self.entries = kind, entries
        self._send = sender or (Q.send_stock if kind == "stock" else Q.send_wish)
        self.setWindowTitle(t("qf.title." + kind))
        self.resize(560, 520)
        note = QLabel(t("qf.note." + kind))
        note.setWordWrap(True)
        role(note, "hint")
        self.table = QTableWidget(len(entries), 5)
        self.table.setHorizontalHeaderLabels(["", t("qf.col.item"), t("qf.col.rank"), t("qf.col.qty"),
                                              t("qf.col.sent")])
        self.table.verticalHeader().hide()
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(COL_NAME, QHeaderView.ResizeMode.Stretch)
        for c in (COL_CHECK, COL_RANK, COL_QTY, COL_SENT):
            hdr.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        self.checks, self.spins = [], []
        for i, e in enumerate(entries):
            prev = Q.sent_before(kind, e["slug"], e.get("rank"))
            chk = QCheckBox()
            # sent before: unchecked, to avoid counting twice (unless these are new copies: Activities purchases)
            chk.setChecked((all_checked or prev is None) and e["qty"] > 0)
            spin = QSpinBox(minimum=1, maximum=100000, value=max(1, int(e["qty"])))
            wrap = QTableWidgetItem()
            self.table.setItem(i, COL_CHECK, wrap)
            self.table.setCellWidget(i, COL_CHECK, chk)
            self.table.setItem(i, COL_NAME, self._cell(e["name"]))
            self.table.setItem(i, COL_RANK, self._cell("–" if e.get("rank") is None else str(e["rank"])))
            self.table.setCellWidget(i, COL_QTY, spin)
            sent = "" if prev is None else t("qf.sent", qty=prev["qty"], date=time.strftime("%d/%m", time.localtime(prev["t"])))
            self.table.setItem(i, COL_SENT, self._cell(sent))
            self.checks.append(chk)
            self.spins.append(spin)
        self.status = QLabel("")
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
        return [dict(e, qty=self.spins[i].value()) for i, e in enumerate(self.entries) if self.checks[i].isChecked()]

    def send(self):
        todo = self.chosen()
        if not todo:
            self.status.setText(t("qf.none"))
            return
        self.btn_send.setEnabled(False)
        self._errors, self._ok = [], 0
        kind, sender = self.kind, self._send

        def work():
            for n, e in enumerate(todo, start=1):
                try:
                    sender(e["slug"], e["qty"], e.get("rank"))
                    Q.mark_sent(kind, e["slug"], e.get("rank"), e["qty"])
                    self.progress.emit(n, len(todo), "")
                except Q.QuantframeError as ex:
                    msg = str(ex)
                    self.progress.emit(n, len(todo), f"{e['name']}: {msg}")
                    if "cannot reach" in msg or "address must" in msg:
                        break                                  # nothing will work: stop
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


def entries_from_rows(rows):
    """Inventory rows (build_rows) -> entries: ranked items are sent per rank (copies at rank 0 and at max rank)."""
    out = []
    for r in rows:
        if r["ranked"]:
            if r["n"] > 0:
                out.append({"slug": r["slug"], "name": r["name"], "rank": 0, "qty": r["n"]})
            if r["m"] > 0:
                out.append({"slug": r["slug"], "name": r["name"], "rank": r["max_rank"], "qty": r["m"]})
        elif r["n"] + r["m"] > 0:
            out.append({"slug": r["slug"], "name": r["name"], "rank": None, "qty": r["n"] + r["m"]})
    return out
