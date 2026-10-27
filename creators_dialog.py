"""Window listing the videos of the followed YouTube channels that carry a build (Overframe link / mod list)."""
import threading
import time

from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QAbstractItemView, QDialog, QHBoxLayout, QHeaderView, QLabel, QPushButton, QTableWidget, QVBoxLayout,
)

import creators as C
from config import CFG
from i18n import t
from uiutil import HINT_STYLE, MUTED_STYLE, Cell


def configured_channels():
    return C.parse_channels(CFG["creator_channels"]) or list(C.parse_channels(C.DEFAULT_SETTING))


class CreatorsDialog(QDialog):
    loaded = pyqtSignal(object, object)             # (videos, errors) from the worker thread
    add_requested = pyqtSignal(dict)                # the chosen video entry

    def __init__(self, market, parent=None):
        super().__init__(parent)
        self.market, self.videos = market, []
        self.setWindowTitle(t("creators.title"))
        self.resize(900, 520)
        self.status = QLabel("")
        self.status.setStyleSheet(MUTED_STYLE)
        self.status.setWordWrap(True)
        self.btn_refresh = QPushButton(t("creators.refresh"))
        self.btn_add = QPushButton(t("creators.add"))
        self.btn_video = QPushButton(t("creators.open_video"))
        top = QHBoxLayout()
        top.addWidget(self.status, 1)
        top.addWidget(self.btn_refresh)
        self.headers = [t("creators.col.date"), t("creators.col.channel"), t("creators.col.title"),
                        t("creators.col.links"), t("creators.col.mods")]
        self.table = QTableWidget(0, len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        for c in (0, 1, 3, 4):
            hdr.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        hint = QLabel(t("creators.hint"))
        hint.setWordWrap(True)
        hint.setStyleSheet(HINT_STYLE)
        bottom = QHBoxLayout()
        bottom.addWidget(self.btn_video)
        bottom.addStretch(1)
        bottom.addWidget(self.btn_add)
        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(self.table, 1)
        lay.addWidget(hint)
        lay.addLayout(bottom)

        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_add.clicked.connect(self._add)
        self.btn_video.clicked.connect(self._open_video)
        self.table.doubleClicked.connect(lambda _: self._add())
        self.table.itemSelectionChanged.connect(self._buttons)
        self.loaded.connect(self._on_done)
        cache = C.load_cache()
        if cache.get("videos"):
            self._fill(cache["videos"], cache.get("errors", []), cache.get("time"))
        else:
            self.status.setText(t("creators.empty"))
        self._buttons()

    def _buttons(self):
        has = self._selected() is not None
        self.btn_add.setEnabled(has)
        self.btn_video.setEnabled(has)

    def _selected(self):
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows:
            return None
        i = self.table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        return self.videos[i] if i is not None and 0 <= i < len(self.videos) else None

    def refresh(self):
        self.btn_refresh.setEnabled(False)
        self.status.setText(t("creators.loading"))
        channels, per, market = configured_channels(), int(CFG["creator_videos"]), self.market

        def work():
            try:
                vids, errs = C.collect(market, channels, per)
            except Exception as e:              # never leave the button disabled
                vids, errs = [], [("", f"{type(e).__name__}: {e}")]
            self.loaded.emit(vids, errs)
        threading.Thread(target=work, daemon=True).start()

    def _on_done(self, vids, errs):
        self.btn_refresh.setEnabled(True)
        if vids or not C.load_cache().get("videos"):
            C.save_cache(vids, errs)
            self._fill(vids, errs, time.time())
        else:                                    # all failed: keep showing the previous list
            self._fill(C.load_cache()["videos"], errs, C.load_cache().get("time"))

    def _fill(self, vids, errs, when):
        self.videos = vids
        tb = self.table
        tb.setSortingEnabled(False)
        tb.setRowCount(len(vids))
        for i, v in enumerate(vids):
            cells = [Cell(v["published"], v["published"]), Cell(v["channel"], v["channel"].lower(), center=False),
                     Cell(v["title"], v["title"].lower(), center=False),
                     Cell("✓" if v["links"] else "–", len(v["links"])), Cell(str(len(v["mods"])), len(v["mods"]))]
            cells[0].setData(Qt.ItemDataRole.UserRole, i)
            for c, cell in enumerate(cells):
                tb.setItem(i, c, cell)
        tb.setSortingEnabled(True)
        tb.sortByColumn(0, Qt.SortOrder.DescendingOrder)
        text = t("creators.count", n=len(vids), time=time.strftime("%d/%m %H:%M", time.localtime(when or 0)))
        if errs:
            text += "  ·  " + t("creators.errors", n=len(errs), first=f"{errs[0][0]}: {errs[0][1]}")
        bad = C.unresolved(CFG["creator_channels"])
        if bad:
            text += "  ·  " + t("creators.unresolved", items=", ".join(bad[:3]))
        self.status.setText(text)
        self._buttons()

    def _add(self):
        v = self._selected()
        if v:
            self.add_requested.emit(v)
            self.accept()

    def _open_video(self):
        v = self._selected()
        if v:
            QDesktopServices.openUrl(QUrl(v["url"]))
