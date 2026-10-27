"""Builds tab: mod lists (from an Overframe link or pasted) checked against your inventory and the market prices."""
import threading

from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QDesktopServices
from PyQt6.QtWidgets import (
    QAbstractItemView, QDialog, QDialogButtonBox, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton, QSplitter, QTableWidget, QVBoxLayout,
    QWidget,
)

import builds as B
from creators_dialog import CreatorsDialog
from config import CFG
from i18n import t
from overlay import volume_color
from uiutil import DIM_COLOR, HINT_STYLE, MUTED_STYLE, PRICE_COLOR, Cell, attach_item_menu

GREEN, AMBER, RED = QColor(110, 220, 140), QColor(255, 205, 110), QColor(255, 120, 120)
STATUS = {B.OK: ("builds.st.ok", GREEN), B.LOW: ("builds.st.low", AMBER),
          B.MISSING: ("builds.st.missing", RED), B.UNKNOWN: ("builds.st.unknown", DIM_COLOR)}


class ReviewDialog(QDialog):
    """Shows the mods found; you uncheck the wrong ones and add the missing ones before saving."""

    def __init__(self, market, name, found, parent=None, note=""):
        super().__init__(parent)
        self.market = market
        self.setWindowTitle(t("builds.review.title"))
        self.resize(480, 560)
        self.name = QLineEdit(name)
        self.list = QListWidget()
        pre = 0
        for slug, nm in found:
            self._add(slug, nm, checked=pre < B.MAX_PRECHECKED)
            pre += 1
        self.add_edit = QLineEdit()
        self.add_edit.setPlaceholderText(t("builds.review.addmod"))
        self.add_edit.returnPressed.connect(self._add_typed)
        btn_add = QPushButton("+")
        btn_add.clicked.connect(self._add_typed)
        hint = QLabel(note or t("builds.review.hint", n=len(found)))
        hint.setWordWrap(True)
        hint.setStyleSheet(HINT_STYLE)
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        row = QHBoxLayout()
        row.addWidget(self.add_edit, 1)
        row.addWidget(btn_add)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(t("builds.review.name")))
        lay.addWidget(self.name)
        lay.addWidget(hint)
        lay.addWidget(self.list, 1)
        lay.addLayout(row)
        lay.addWidget(box)

    def _add(self, slug, name, checked=True):
        it = QListWidgetItem(name)
        it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        it.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        it.setData(Qt.ItemDataRole.UserRole, slug)
        self.list.addItem(it)

    def _add_typed(self):
        text = self.add_edit.text().strip()
        if not text:
            return
        slug = self.market.slug_for_name(B.expand(text))
        if not slug:
            m = self.market.match(text, 80)
            slug = m.slug if m else None
        if slug:
            self._add(slug, self.market.info(slug).get("name", text))
        else:
            self._add(None, text)                  # kept by name: not a warframe.market item (cannot be priced)
        self.add_edit.clear()
        self.list.scrollToBottom()

    def result_mods(self):
        out = []
        for i in range(self.list.count()):
            it = self.list.item(i)
            if it.checkState() == Qt.CheckState.Checked:
                out.append((it.data(Qt.ItemDataRole.UserRole), it.text()))
        return out


class BuildsTab(QWidget):
    fetched = pyqtSignal(object, object, str)       # (page html | None, error | None, url)

    def __init__(self, market, refresher, inventory):
        super().__init__()
        self.market, self.refresher, self.inventory = market, refresher, inventory
        self.store = B.BuildStore()
        self._shown = None
        self._missing_prices = []
        self._pending_name = None
        self._fallback = []
        self.fetched.connect(self._on_page)

        self.btn_link = QPushButton(t("builds.add_link"))
        self.btn_text = QPushButton(t("builds.add_text"))
        self.btn_rename = QPushButton(t("builds.rename"))
        self.btn_remove = QPushButton(t("builds.remove"))
        self.btn_open = QPushButton(t("builds.open"))
        self.btn_creators = QPushButton(t("builds.creators"))
        self.btn_creators.setToolTip(t("builds.creators.tip"))
        self.btn_wish = QPushButton(t("qf.btn.wish"))
        self.btn_wish.setToolTip(t("qf.btn.wish.tip"))
        self.btn_fetch = QPushButton(t("builds.fetch"))
        self.btn_fetch.setToolTip(t("builds.fetch.tip"))
        bar = QHBoxLayout()
        for b in (self.btn_link, self.btn_text, self.btn_creators, self.btn_rename, self.btn_remove, self.btn_open):
            bar.addWidget(b)
        bar.addStretch(1)
        bar.addWidget(self.btn_wish)
        bar.addWidget(self.btn_fetch)

        self.list = QListWidget()
        self.list.setMinimumWidth(240)
        self.title = QLabel("")
        self.title.setStyleSheet("font-size: 15px; font-weight: bold;")
        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet(MUTED_STYLE)
        self.headers = [t("builds.col.mod"), t("builds.col.status"), t("col.price"), t("col.volume"), t("builds.col.cost")]
        self.table = QTableWidget(0, len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in (1, 2, 3, 4):
            hdr.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        attach_item_menu(self.table, 0)
        hint = QLabel(t("builds.hint"))
        hint.setWordWrap(True)
        hint.setStyleSheet(HINT_STYLE)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(self.title)
        rl.addWidget(self.summary)
        rl.addWidget(self.table, 1)
        split = QSplitter()
        split.addWidget(self.list)
        split.addWidget(right)
        split.setStretchFactor(1, 1)
        lay = QVBoxLayout(self)
        lay.addLayout(bar)
        lay.addWidget(split, 1)
        lay.addWidget(hint)

        self.btn_link.clicked.connect(self.add_link)
        self.btn_text.clicked.connect(self.add_text)
        self.btn_wish.clicked.connect(self.send_wish)
        self.btn_creators.clicked.connect(self.open_creators)
        self.btn_rename.clicked.connect(self.rename)
        self.btn_remove.clicked.connect(self.remove)
        self.btn_open.clicked.connect(self.open_link)
        self.btn_fetch.clicked.connect(lambda: self.refresher.start(self._missing_prices, CFG["refresh_skip_age"]))
        self.list.currentItemChanged.connect(lambda *_: self.show_build())
        self.refresh(force=True)

    # ---------- adding ----------
    def add_link(self):
        url, ok = QInputDialog.getText(self, t("builds.add_link"), t("builds.link.prompt"))
        if not ok or not url.strip():
            return
        self._fetch_url(url)

    def _fetch_url(self, url, name=None):
        try:
            url = B.check_url(url)
        except B.BuildError as e:
            QMessageBox.warning(self, t("builds.add_link"), t("builds.fetch.error", err=e))
            return
        self._pending_name = name
        self.btn_link.setEnabled(False)
        self.summary.setText(t("builds.fetching"))

        def work():
            try:
                self.fetched.emit(B.fetch_page(url), None, url)
            except Exception as e:
                self.fetched.emit(None, str(e), url)
        threading.Thread(target=work, daemon=True).start()

    def _on_page(self, page, err, url):
        self.btn_link.setEnabled(True)
        self.summary.setText("")
        if err or page is None:
            self._pending_name, self._fallback = None, []
            QMessageBox.warning(self, t("builds.add_link"), t("builds.fetch.error", err=err))
            return
        found = B.extract_mods(B.page_text(page), self.market)
        note = ""
        if not found:                           # mods only inside the page's data: look there too (noisier)
            found = B.extract_mods(B.page_text(page, with_scripts=True), self.market)
            note = t("builds.review.noisy", n=len(found)) if found else t("builds.review.none")
        if not found and self._fallback:                  # nothing in the page: the video description's mods
            found, note = self._fallback, ""
        self._review(self._pending_name or B.page_title(page) or t("builds.untitled"), found, url, note)
        self._pending_name, self._fallback = None, []

    def send_wish(self):
        """The missing mods of the selected build -> Quantframe's wish list, after a check window."""
        from quantframe_dialog import SendDialog, entries_from_missing
        b = self._current()
        if not b:
            return
        entries = entries_from_missing(B.evaluate(b, self.inventory, self.market), self.market)
        if not entries:
            QMessageBox.information(self, t("qf.btn.wish"), t("qf.empty.wish"))
            return
        SendDialog("wish", entries, self).exec()

    def open_creators(self):
        dlg = CreatorsDialog(self.market, self)
        dlg.add_requested.connect(self._from_creator)
        dlg.exec()

    def _from_creator(self, v):
        """A video chosen in the creators window: its Overframe link if it has one (the page is read), otherwise the
        mod names found in its description."""
        name = f"{v['title']} ({v['channel']})"[:80]
        if v["links"]:
            self._fallback = [(s, n) for s, n in v["mods"]]
            self._fetch_url(v["links"][0], name)
        else:
            self._review(name, [(s, n) for s, n in v["mods"]], v["url"])

    def add_text(self):
        dlg = QDialog(self)
        dlg.setWindowTitle(t("builds.add_text"))
        dlg.resize(420, 420)
        edit = QPlainTextEdit()
        edit.setPlaceholderText(t("builds.text.placeholder"))
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(dlg.accept)
        box.rejected.connect(dlg.reject)
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel(t("builds.text.prompt")))
        lay.addWidget(edit, 1)
        lay.addWidget(box)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        found = B.parse_list(edit.toPlainText(), self.market)
        self._review(t("builds.untitled"), found, "")

    def _review(self, name, found, url, note=""):
        dlg = ReviewDialog(self.market, name, found, self, note)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        mods = dlg.result_mods()
        if not mods:
            return
        b = self.store.add(dlg.name.text().strip() or t("builds.untitled"), mods, url)
        self.refresh(force=True, select=b["id"])

    # ---------- editing ----------
    def _current(self):
        it = self.list.currentItem()
        return self.store.get(it.data(Qt.ItemDataRole.UserRole)) if it else None

    def rename(self):
        b = self._current()
        if not b:
            return
        name, ok = QInputDialog.getText(self, t("builds.rename"), t("builds.rename.prompt"), text=b["name"])
        if ok and name.strip():
            self.store.rename(b["id"], name)
            self.refresh(force=True, select=b["id"])

    def remove(self):
        b = self._current()
        if not b:
            return
        if QMessageBox.question(self, t("builds.remove"), t("builds.confirm.remove", name=b["name"])) \
                == QMessageBox.StandardButton.Yes:
            self.store.remove(b["id"])
            self.refresh(force=True)

    def open_link(self):
        b = self._current()
        if b and b.get("url"):
            QDesktopServices.openUrl(QUrl(b["url"]))

    def set_busy(self, busy: bool):
        self.btn_fetch.setEnabled(not busy and bool(self._missing_prices))

    # ---------- display ----------
    def refresh(self, force=False, select=None):
        """Rebuilds the list of builds (the cheapest to complete first) and the selected build's table."""
        cur = select or (self.list.currentItem().data(Qt.ItemDataRole.UserRole) if self.list.currentItem() else None)
        scored = [(b, B.evaluate(b, self.inventory, self.market)) for b in self.store.builds]
        scored.sort(key=lambda x: (x[1]["missing"] > 0, x[1]["cost"], x[1]["missing"], x[0]["name"].lower()))
        sig = (cur, tuple((b["id"], b["name"], e["missing"], e["cost"], e["low"], len(e["no_price"])) for b, e in scored))
        if not force and sig == self._shown:
            return
        self._shown = sig
        self.list.blockSignals(True)
        self.list.clear()
        for b, ev in scored:
            if ev["missing"] == 0:
                tail = t("builds.list.ready")
            else:
                tail = t("builds.list.missing", n=ev["missing"], cost=f"{ev['cost']:,}".replace(",", " "))
            it = QListWidgetItem(f"{b['name']}\n{tail}")
            it.setData(Qt.ItemDataRole.UserRole, b["id"])
            it.setForeground(GREEN if ev["missing"] == 0 else QColor(230, 230, 230))
            self.list.addItem(it)
            if b["id"] == cur:
                self.list.setCurrentItem(it)
        if self.list.currentRow() < 0 and self.list.count():
            self.list.setCurrentRow(0)
        self.list.blockSignals(False)
        self.show_build()

    def show_build(self):
        b = self._current()
        for w in (self.btn_rename, self.btn_remove, self.btn_wish):
            w.setEnabled(b is not None)
        self.btn_open.setEnabled(bool(b and b.get("url")))
        tb = self.table
        tb.setSortingEnabled(False)
        tb.setRowCount(0)
        if not b:
            self.title.setText(t("builds.empty"))
            self.summary.setText("")
            self._missing_prices = []
            self.btn_fetch.setEnabled(False)
            return
        ev = B.evaluate(b, self.inventory, self.market)
        self.title.setText(b["name"])
        tb.setRowCount(len(ev["rows"]))
        for i, r in enumerate(ev["rows"]):
            key, color = STATUS[r["status"]]
            price = "–" if r["price"] is None else f"{int(r['price'])}p"
            cells = [Cell(r["name"], r["name"].lower(), center=False), Cell(t(key), i, color),
                     Cell(price, r["price"] or 0, PRICE_COLOR),
                     Cell("–" if r["vol"] is None else str(r["vol"]), r["vol"] or 0,
                          volume_color(r["vol"]) if r["vol"] is not None else None),
                     Cell(f"{r['cost']}p" if r["cost"] else "–", r["cost"])]
            cells[0].setData(Qt.ItemDataRole.UserRole, r["slug"])
            for c, cell in enumerate(cells):
                tb.setItem(i, c, cell)
        tb.setSortingEnabled(True)
        tb.sortByColumn(1, Qt.SortOrder.AscendingOrder)       # the build's own order (the status cell carries the index)
        self._missing_prices = ev["no_price"]
        self.btn_fetch.setEnabled(bool(self._missing_prices) and not self.refresher.busy)
        parts = []
        if ev["missing"] == 0:
            parts.append(t("builds.sum.ready", total=ev["total"]))
        else:
            parts.append(t("builds.sum.missing", n=ev["missing"], total=ev["total"],
                           cost=f"{ev['cost']:,}".replace(",", " ")))
        if ev["no_price"]:
            parts.append(t("builds.sum.noprice", n=len(ev["no_price"])))
        if ev["low"]:
            parts.append(t("builds.sum.low", n=ev["low"]))
        if ev["unknown"]:
            parts.append(t("builds.sum.unknown", n=ev["unknown"]))
        self.summary.setText("  ·  ".join(parts))
