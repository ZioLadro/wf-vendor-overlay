"""Dialog with the inventory advice (ducats / selling)."""
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QHeaderView, QLabel, QPushButton, QTableWidget, QVBoxLayout, QAbstractItemView

from advice import ducat_advice, sell_advice
from i18n import t
from overlay import volume_color
from uiutil import role
from uiutil import (DIM_COLOR, HINT_STYLE, MUTED_STYLE, PRICE_COLOR, STYLE, Cell, attach_item_menu, num_key)


class AdviceDialog(QDialog):
    select_requested = pyqtSignal(list)         # slugs to select in the inventory table

    def __init__(self, kind: str, rows, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.setWindowTitle(t("advice." + kind + ".title"))
        self.resize(900, 560)
        if kind == "ducat":
            data, self.missing = ducat_advice(rows)
            heads = ["col.item", "col.owned", "advice.col.ducats", "advice.col.total_ducats", "col.price",
                     "advice.col.plat_lost", "col.volume", "advice.col.ratio", "advice.col.verdict"]
        else:
            data, self.missing = sell_advice(rows)
            heads = ["col.item", "col.owned", "col.price", "col.volume", "advice.col.sellable",
                     "advice.col.expected", "advice.col.score"]
        self.data = data
        intro = QLabel(t("advice." + kind + ".intro"))
        intro.setWordWrap(True)
        role(intro, "muted")
        self.table = QTableWidget(len(data), len(heads))
        self.table.setHorizontalHeaderLabels([t(h) for h in heads])
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        for i, x in enumerate(data):
            if kind == "ducat":
                cells = [Cell(x["name"], x["name"].lower(), center=False), Cell(str(x["n"]), x["n"]),
                         Cell(str(x["ducats"]), x["ducats"]), Cell(str(x["total_ducats"]), x["total_ducats"]),
                         Cell(f"{x['price']}p", x["price"], PRICE_COLOR), Cell(f"{x['plat_lost']}p", x["plat_lost"]),
                         Cell(str(x["vol"]), x["vol"], volume_color(x["vol"])), Cell(f"{x['ratio']:.1f}", x["ratio"]),
                         Cell(t("advice.verdict.ducat") if x["ducat"] else t("advice.verdict.sell"), int(x["ducat"]),
                              PRICE_COLOR if x["ducat"] else DIM_COLOR)]
            else:
                cells = [Cell(x["name"], x["name"].lower(), center=False), Cell(str(x["n"]), x["n"]),
                         Cell(f"{x['price']}p", x["price"], PRICE_COLOR), Cell(str(x["vol"]), x["vol"], volume_color(x["vol"])),
                         Cell(str(x["sellable"]), x["sellable"]), Cell(f"{x['expected']}p", x["expected"]),
                         Cell(f"{x['score']:.1f}", x["score"])]
            cells[0].setData(Qt.ItemDataRole.UserRole, x["slug"])
            for c, cell in enumerate(cells):
                self.table.setItem(i, c, cell)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in range(1, len(heads)):
            hdr.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(len(heads) - 1 if kind == "sell" else 7, Qt.SortOrder.DescendingOrder)
        attach_item_menu(self.table, 0)
        note = QLabel(t("advice.missing", n=len(self.missing)) if self.missing else "")
        role(note, "hint")
        note.setWordWrap(True)
        empty = QLabel(t("advice.empty") if not data else "")
        btn_sel = QPushButton(t("advice.select"))
        btn_sel.setToolTip(t("advice.select.tip"))
        btn_sel.clicked.connect(self._select)
        btn_close = QPushButton(t("advice.close"))
        btn_close.clicked.connect(self.accept)
        bottom = QHBoxLayout()
        bottom.addWidget(note, 1)
        bottom.addWidget(btn_sel)
        bottom.addWidget(btn_close)
        lay = QVBoxLayout(self)
        lay.addWidget(intro)
        lay.addWidget(empty)
        lay.addWidget(self.table, 1)
        lay.addLayout(bottom)

    def _select(self):
        rows = {i.row() for i in self.table.selectedIndexes()}
        if not rows:
            rows = {r for r in range(self.table.rowCount())
                    if (self.kind == "sell" or self.table.item(r, 8).text() == t("advice.verdict.ducat"))}
        self.select_requested.emit([self.table.item(r, 0).data(Qt.ItemDataRole.UserRole) for r in rows])
        self.accept()
