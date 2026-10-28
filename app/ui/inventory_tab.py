"""Inventory tab: your items with market prices, filters like AlecaFrame's, and one-click sell orders."""
import json
import hashlib

from app.game import aleca
import os
import time

from PyQt6.QtCore import QStringListModel, Qt
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QCompleter, QDialog, QDialogButtonBox,
    QFileDialog, QFormLayout, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QMessageBox,
    QPlainTextEdit, QPushButton, QSpinBox, QTableWidget, QVBoxLayout, QWidget,
)

from app.core.config import CFG, save_config
from app.core.i18n import t
from app.ui.advice_dialog import AdviceDialog
from app.game.inventory import Inventory, build_rows, parse_file, parse_text
from app.trade.market_auth import MarketAccount, MarketError
from app.scan.overlay import volume_color
from app.core.uiutil import role
from app.core.uiutil import (
    DIM_COLOR, HINT_STYLE, MAXRANK_COLOR, MUTED_STYLE, PRICE_COLOR, Cell, age_text, refresh_ages, attach_item_menu,
    num_key,
)

CATEGORIES = ["set", "warframe_part", "weapon_part", "mod", "arcane", "relic", "other"]
C_NAME, C_CAT, C_OWNED, C_PRICE, C_PMAX, C_VALUE, C_DUCAT, C_VOL, C_LISTED, C_UPD = range(10)


class ItemDialog(QDialog):
    """Add or edit an item: name (with completion), copies, and copies at max rank (mods/arcanes)."""

    def __init__(self, market, parent=None, slug=None, n=1, m=0):
        super().__init__(parent)
        self.market, self.slug = market, slug
        self.setWindowTitle(t("inv.item.title"))
        names = sorted(n for n, _ in market.pairs())
        self.name = QLineEdit()
        comp = QCompleter(QStringListModel(names), self)
        comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        comp.setFilterMode(Qt.MatchFlag.MatchContains)
        self.name.setCompleter(comp)
        self.n = QSpinBox(minimum=0, maximum=999999, value=n)
        self.m = QSpinBox(minimum=0, maximum=999999, value=m)
        self.m.setToolTip(t("inv.item.max.tip"))
        if slug:
            self.name.setText(market.info(slug)["name"])
            self.name.setReadOnly(True)
        form = QFormLayout()
        form.addRow(t("inv.item.name"), self.name)
        form.addRow(t("inv.item.owned"), self.n)
        form.addRow(t("inv.item.maxed"), self.m)
        self.msg = QLabel("")
        self.msg.setStyleSheet("color: #e07a7a;")
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(self._ok)
        box.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(self.msg)
        lay.addWidget(box)

    def _ok(self):
        slug = self.slug or self.market.slug_for_name(self.name.text())
        if not slug:
            self.msg.setText(t("inv.item.unknown"))
            return
        if self.n.value() + self.m.value() == 0:
            self.msg.setText(t("inv.item.zero"))
            return
        self.slug = slug
        self.accept()


class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("inv.login.title"))
        self.email = QLineEdit()
        self.password = QLineEdit(echoMode=QLineEdit.EchoMode.Password)
        form = QFormLayout()
        form.addRow(t("inv.login.email"), self.email)
        form.addRow(t("inv.login.password"), self.password)
        note = QLabel(t("inv.login.note"))
        note.setWordWrap(True)
        role(note, "hint")
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(note)
        lay.addWidget(box)
        self.setMinimumWidth(380)


class SellDialog(QDialog):
    """Confirms ONE sell order, showing exactly what will be sent to warframe.market."""

    def __init__(self, row, account, suggested, max_qty_by_rank, parent=None):
        super().__init__(parent)
        self.row, self.account = row, account
        self.setWindowTitle(t("inv.sell.title", name=row["name"]))
        self.rank = QComboBox()
        if row["ranked"]:
            if max_qty_by_rank["0"]:
                self.rank.addItem(t("inv.sell.rank0"), 0)
            if max_qty_by_rank["max"]:
                self.rank.addItem(t("inv.sell.rankmax", n=row["max_rank"]), row["max_rank"])
        self.qty = QSpinBox(minimum=1, maximum=9999)
        self.price = QSpinBox(minimum=1, maximum=1000000)
        self.visible = QCheckBox(t("inv.sell.visible"))
        self.visible.setChecked(True)
        self._caps, self._suggested = max_qty_by_rank, suggested
        self.rank.currentIndexChanged.connect(self._rank_changed)
        self.qty.valueChanged.connect(self._preview)
        self.price.valueChanged.connect(self._preview)
        self.visible.toggled.connect(self._preview)
        form = QFormLayout()
        form.addRow(QLabel(f"<b>{row['name']}</b>"))
        if row["ranked"]:
            form.addRow(t("inv.sell.rank"), self.rank)
        form.addRow(t("inv.sell.qty"), self.qty)
        form.addRow(t("inv.sell.price"), self.price)
        form.addRow(self.visible)
        self.info = QLabel("")
        role(self.info, "muted")
        self.preview = QPlainTextEdit(readOnly=True)
        self.preview.setMaximumHeight(110)
        self.preview.setStyleSheet("font-family: Consolas, monospace; font-size: 11px;")
        self.btn_place = QPushButton(t("inv.sell.place"))
        self.btn_skip = QPushButton(t("inv.sell.skip"))
        self.btn_cancel = QPushButton(t("inv.sell.cancel_all"))
        self.btn_place.setDefault(True)
        buttons = QHBoxLayout()
        buttons.addWidget(self.btn_cancel)
        buttons.addStretch(1)
        buttons.addWidget(self.btn_skip)
        buttons.addWidget(self.btn_place)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(self.info)
        lay.addWidget(QLabel(t("inv.sell.request")))
        lay.addWidget(self.preview)
        lay.addLayout(buttons)
        self.setMinimumWidth(460)
        self.result_code = "skip"
        self.btn_place.clicked.connect(lambda: self._done("place"))
        self.btn_skip.clicked.connect(lambda: self._done("skip"))
        self.btn_cancel.clicked.connect(lambda: self._done("cancel"))
        self._rank_changed()

    def _done(self, code):
        self.result_code = code
        self.accept()

    def current_rank(self):
        r = self.row
        if not r["ranked"]:
            return None
        return self.rank.currentData() if self.rank.count() else 0

    def _rank_changed(self):
        key = "max" if (self.row["ranked"] and self.current_rank() == self.row["max_rank"]) else "0"
        cap = max(1, self._caps[key])
        self.qty.setMaximum(cap)
        self.qty.setValue(cap)
        sug = self._suggested.get(key)
        self.price.setValue(max(1, sug) if sug else 1)
        self.info.setText(t("inv.sell.market", price=sug) if sug else t("inv.sell.noprice"))
        self._preview()

    def values(self):
        return {"price": self.price.value(), "qty": self.qty.value(), "rank": self.current_rank(),
                "visible": self.visible.isChecked()}

    def _preview(self, *_):
        v = self.values()
        req = self.account.order_request(self.row["id"] or "?", v["price"], v["qty"], v["rank"], v["visible"])
        self.preview.setPlainText(f"{req['method']} {req['url']}\n" + json.dumps(req["body"], indent=2))


class InventoryTab(QWidget):
    def __init__(self, market, refresher, inventory: Inventory, account: MarketAccount):
        super().__init__()
        self.market, self.refresher, self.inv, self.account = market, refresher, inventory, account

        self.search = QLineEdit(placeholderText=t("prices.search"), clearButtonEnabled=True)
        self.category = QComboBox()
        self.category.addItem(t("cat.all"), None)
        for c in CATEGORIES:
            self.category.addItem(t("cat." + c), c)
        self.min_plat = QComboBox()
        for v in (0, 5, 10, 15):
            self.min_plat.addItem(t("inv.minplat.any") if v == 0 else t("inv.minplat", n=v), v)
        self.part_type = self._tri(t("inv.parttype"), [(None, t("inv.any")), ("prime", t("inv.prime")), ("normal", t("inv.normal"))])
        self.vaulted = self._tri(t("inv.vaulted"), [(None, t("inv.any")), (True, t("inv.yes")), (False, t("inv.no"))])
        self.listed = self._tri(t("inv.listed"), [(None, t("inv.any")), (True, t("inv.yes")), (False, t("inv.no"))])
        self.multiple = QCheckBox(t("inv.multiple"))
        self.exclude_max = QCheckBox(t("inv.exclude_max"))
        self.exclude_max.setToolTip(t("inv.exclude_max.tip"))
        self.exclude_max.setChecked(bool(CFG["inv_exclude_maxed"]))
        self.exclude_inst = QCheckBox(t("inv.exclude_inst"))
        self.exclude_inst.setToolTip(t("inv.exclude_inst.tip"))
        self.exclude_inst.setChecked(bool(CFG["inv_exclude_installed"]))
        self.hide_zero = QCheckBox(t("prices.hide_zero"))
        self.hide_zero.setToolTip(t("prices.hide_zero.tip"))
        self.hide_zero.setChecked(bool(CFG["inv_hide_zero_volume"]))
        self.min_vol = QSpinBox()
        self.min_vol.setRange(0, 9999)
        self.min_vol.setPrefix(t("inv.minvol") + " ")
        self.min_vol.setToolTip(t("inv.minvol.tip"))
        self.min_vol.setValue(int(CFG["inv_min_volume"]))

        row1 = QHBoxLayout()
        row1.addWidget(self.search, 1)
        row1.addWidget(self.category)
        row1.addWidget(self.min_plat)
        row2 = QHBoxLayout()
        for lbl, cb in (self.part_type, self.vaulted, self.listed):
            row2.addWidget(QLabel(lbl))
            row2.addWidget(cb)
        row2.addWidget(self.multiple)
        row2.addWidget(self.exclude_max)
        row2.addWidget(self.exclude_inst)
        row2.addWidget(self.hide_zero)
        row2.addWidget(self.min_vol)
        row2.addStretch(1)

        self.btn_import = QPushButton(t("inv.import"))
        self.btn_import.setToolTip(t("inv.import.tip"))
        self.btn_reload = QPushButton(t("inv.reload"))
        self.btn_reload.setToolTip(t("inv.reload.tip"))
        self.btn_paste = QPushButton(t("inv.paste"))
        self.btn_add = QPushButton(t("inv.add"))
        self.btn_edit = QPushButton(t("inv.edit"))
        self.btn_remove = QPushButton(t("inv.remove"))
        self.btn_prices = QPushButton(t("inv.update_prices"))
        self.btn_prices.setToolTip(t("inv.update_prices.tip"))
        self.btn_sell = QPushButton(t("inv.sell"))
        self.btn_sell.setToolTip(t("inv.sell.tip"))
        self.btn_ducat = QPushButton(t("advice.ducat.btn"))
        self.btn_ducat.setToolTip(t("advice.ducat.tip"))
        self.btn_rankup = QPushButton(t("advice.rankup.btn"))
        self.btn_rankup.setToolTip(t("advice.rankup.tip"))
        self.btn_advice_sell = QPushButton(t("advice.sell.btn"))
        self.btn_advice_sell.setToolTip(t("advice.sell.tip"))
        self.btn_qf = QPushButton(t("qf.btn"))
        self.btn_qf.setToolTip(t("qf.btn.tip"))
        self.btn_riven = QPushButton(t("riv.btn"))
        self.btn_riven.setToolTip(t("riv.btn.tip"))
        self.btn_account = QPushButton("")
        actions = QVBoxLayout()                    # two rows: the data on the left of each, the advice and market on the right
        row_a, row_b = QHBoxLayout(), QHBoxLayout()
        for b in (self.btn_import, self.btn_reload, self.btn_paste, self.btn_add, self.btn_edit, self.btn_remove):
            row_a.addWidget(b)
        row_a.addStretch(1)
        row_a.addWidget(self.btn_prices)
        row_a.addWidget(self.btn_account)
        for b in (self.btn_ducat, self.btn_advice_sell, self.btn_rankup):
            row_b.addWidget(b)
        row_b.addStretch(1)
        for b in (self.btn_sell, self.btn_qf, self.btn_riven):
            row_b.addWidget(b)
        actions.addLayout(row_a)
        actions.addLayout(row_b)

        self.summary = QLabel("")
        role(self.summary, "muted")
        self.summary.setWordWrap(True)

        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels([
            t("col.item"), t("col.category"), t("col.owned"), t("col.price"), t("col.pmax"), t("col.value"), t("col.ducats"),
            t("col.volume"), t("col.listed"), t("col.updated")])
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(C_NAME, QHeaderView.ResizeMode.Stretch)
        for c in range(1, 10):
            hdr.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSortIndicator(C_VALUE, Qt.SortOrder.DescendingOrder)
        attach_item_menu(self.table, C_NAME)

        hint = QLabel(t("inv.hint"))
        role(hint, "hint")
        hint.setWordWrap(True)

        lay = QVBoxLayout(self)
        lay.addLayout(row1)
        lay.addLayout(row2)
        lay.addLayout(actions)
        lay.addWidget(self.summary)
        lay.addWidget(self.table, 1)
        lay.addWidget(hint)

        for w in (self.category, self.min_plat, self.part_type[1], self.vaulted[1], self.listed[1]):
            w.currentIndexChanged.connect(lambda _: self.refresh(force=True))
        self.search.textChanged.connect(lambda _: self.refresh(force=True))
        self.multiple.toggled.connect(lambda _: self.refresh(force=True))
        self.hide_zero.toggled.connect(self._hide_zero_changed)
        self.min_vol.valueChanged.connect(self._min_vol_changed)
        self.btn_ducat.clicked.connect(lambda: self.show_advice("ducat"))
        self.btn_advice_sell.clicked.connect(lambda: self.show_advice("sell"))
        self.btn_rankup.clicked.connect(lambda: self.show_advice("rankup"))
        self.exclude_inst.toggled.connect(self._exclude_inst_changed)
        self.exclude_max.toggled.connect(self._exclude_changed)
        self.btn_import.clicked.connect(self.import_file)
        self.btn_paste.clicked.connect(self.paste_list)
        self.btn_reload.clicked.connect(self.reload_file)
        self.btn_add.clicked.connect(self.add_item)
        self.btn_edit.clicked.connect(self.edit_item)
        self.table.doubleClicked.connect(lambda _: self.edit_item())
        self.btn_remove.clicked.connect(self.remove_items)
        self.btn_prices.clicked.connect(self.update_prices)
        self.btn_sell.clicked.connect(self.sell_selected)
        self.btn_qf.clicked.connect(self.send_to_quantframe)
        self.btn_riven.clicked.connect(self.send_rivens)
        self.btn_account.clicked.connect(self.toggle_account)
        self._account_text()

    @staticmethod
    def _tri(label, options):
        cb = QComboBox()
        for value, text in options:
            cb.addItem(text, value)
        return label, cb

    def _min_vol_changed(self, v):
        save_config({"inv_min_volume": int(v)})
        self.refresh(force=True)

    def _hide_zero_changed(self, on):
        save_config({"inv_hide_zero_volume": bool(on)})
        self.refresh(force=True)

    def show_advice(self, kind):
        """Ducat / selling advice over everything you own (the table filters do not apply)."""
        rows, _ = build_rows(self.inv, self.market, exclude_maxed=self.exclude_max.isChecked(),
                             exclude_installed=self.exclude_inst.isChecked())
        dlg = AdviceDialog(kind, rows, self)
        dlg.select_requested.connect(self.select_slugs)
        dlg.exec()

    def select_slugs(self, slugs):
        """Selects these items in the table (those hidden by the filters cannot be selected)."""
        want, tb = set(slugs), self.table
        tb.clearSelection()
        sm = tb.selectionModel()
        for r in range(tb.rowCount()):
            if tb.item(r, 0).data(Qt.ItemDataRole.UserRole) in want:
                sm.select(tb.model().index(r, 0), sm.SelectionFlag.Select | sm.SelectionFlag.Rows)

    def _exclude_inst_changed(self, on):
        save_config({"inv_exclude_installed": bool(on)})
        self.refresh(force=True)

    def _exclude_changed(self, on):
        save_config({"inv_exclude_maxed": bool(on)})
        self.refresh(force=True)

    def set_busy(self, busy: bool):
        self.btn_prices.setEnabled(not busy)

    # ---------- table ----------
    def _rows(self):
        return build_rows(
            self.inv, self.market, query=self.search.text(), category=self.category.currentData(),
            min_plat=self.min_plat.currentData(), exclude_maxed=self.exclude_max.isChecked(), exclude_installed=self.exclude_inst.isChecked(),
            multiple=self.multiple.isChecked(), part_type=self.part_type[1].currentData(),
            vaulted=self.vaulted[1].currentData(), listed=self.listed[1].currentData(),
            hide_zero_volume=self.hide_zero.isChecked(), min_volume=self.min_vol.value())

    def refresh(self, force=False):
        rows, total = self._rows()
        sig = hash((len(self.inv.items), tuple((r["slug"], r["n"], r["m"], r["price"], r["pmax"], r["vol"],
                                                r["updated"], (r["order"] or {}).get("t")) for r in rows)))
        now = time.monotonic()
        if not force and sig == getattr(self, "_sig", None):
            if now - getattr(self, "_built", 0) >= 30:     # nothing changed: only the "x min ago" texts move on
                self._built = now
                refresh_ages(self.table, C_UPD)
            return
        self._sig, self._built = sig, now
        tb = self.table
        hdr = tb.horizontalHeader()
        sec, order = hdr.sortIndicatorSection(), hdr.sortIndicatorOrder()
        selected = {tb.item(i.row(), 0).data(Qt.ItemDataRole.UserRole) for i in tb.selectedIndexes()
                    if tb.item(i.row(), 0)}
        vpos = tb.verticalScrollBar().value()
        tb.setUpdatesEnabled(False)
        tb.setSortingEnabled(False)
        tb.setRowCount(0)
        tb.setRowCount(len(rows))
        for i, r in enumerate(rows):
            p, pm, v = r["price"], r["pmax"], r["vol"]
            owned = str(r["n"]) if not r["m"] else (t("inv.owned.max", n=r["n"], m=r["m"]) if r["n"] else
                                                     t("inv.owned.onlymax", m=r["m"]))
            o = r["order"]
            cells = [
                Cell(r["name"], r["name"].lower(), center=False),
                Cell(t("cat." + r["category"]), r["category"]),
                Cell(owned, r["n"] + r["m"]),
                Cell("–" if p is None else f"{p}p", num_key(p), PRICE_COLOR if p is not None else DIM_COLOR),
                (Cell("–" if pm is None else f"{pm}p", num_key(pm), MAXRANK_COLOR if pm is not None else DIM_COLOR)
                 if r["ranked"] else Cell("", (0, 0))),
                Cell("–" if r["value"] is None else f"{r['value']}p", num_key(r["value"]),
                     PRICE_COLOR if r["value"] is not None else DIM_COLOR),
                Cell("" if not r.get("ducats") else str(r["ducats"]), r.get("ducats") or 0),
                Cell("–" if v is None else str(v), num_key(v), volume_color(v) if v is not None else DIM_COLOR),
                Cell(f"{o['qty']}× @ {o['price']}p" if o else "", o["t"] if o else 0),
                Cell(age_text(r["updated"]), r["updated"] or 0),
            ]
            cells[C_NAME].setData(Qt.ItemDataRole.UserRole, r["slug"])
            if r.get("ducats"):
                cells[C_DUCAT].setToolTip(t("inv.ducats.tip", each=r["ducats"], total=r["ducats"] * r["n"]))
            if o:
                cells[C_LISTED].setToolTip(t("inv.listed.tip", when=age_text(o["t"])))
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

        unpriced = sum(1 for r in rows if r["value"] is None)
        text = t("inv.summary", n=len(rows), copies=sum(r["n"] + r["m"] for r in rows), value=total)
        if unpriced:
            text += " " + t("inv.unpriced", n=unpriced)
        if self.inv.imported:
            text += " " + t("inv.source", src=self.inv.source or "–", when=age_text(self.inv.imported))
        if not self.inv.items:
            text = t("inv.empty")
        self.summary.setText(text)

    def _selected_slugs(self):
        tb = self.table
        return [tb.item(r, 0).data(Qt.ItemDataRole.UserRole)
                for r in sorted({i.row() for i in tb.selectedIndexes()}) if tb.item(r, 0)]

    # ---------- importing / editing ----------
    def _report(self, res, replaced):
        msg = t("inv.import.done", matched=res.matched, lines=res.lines, unmatched=len(res.unmatched))
        box = QMessageBox(self)
        box.setWindowTitle(t("inv.import"))
        box.setText(msg)
        if res.unmatched:
            box.setDetailedText(t("inv.import.unmatched") + "\n" + "\n".join(
                f"{q}× {n}" for n, q in res.unmatched[:200]))
        box.exec()

    def _apply_import(self, res, confirm=True):
        if confirm and self.inv.items:
            ans = QMessageBox.question(self, t("inv.import"), t("inv.import.replace", n=len(self.inv.items)))
            if ans != QMessageBox.StandardButton.Yes:
                return
        self.inv.replace_with(res, res.path)
        self._report(res, True)
        self.refresh(force=True)

    def import_file(self):
        start = os.path.dirname(self.inv.path) if self.inv.path else ""
        if not start:
            aleca = os.path.join(os.environ.get("LOCALAPPDATA", ""), "AlecaFrame")
            start = aleca if os.path.isdir(aleca) else ""
        path, _ = QFileDialog.getOpenFileName(self, t("inv.import"), start, t("inv.import.filter"))
        if not path:
            return
        try:
            res = parse_file(path, self.market)
        except Exception as e:
            QMessageBox.warning(self, t("inv.import"), t("inv.import.failed", err=e))
            return
        if not res.matched:
            self._report(res, False)
            return
        self._apply_import(res)

    def reload_file(self):
        """Re-reads the file of the last import (e.g. after another tool refreshed it)."""
        path = self.inv.path
        if not path or not os.path.exists(path):
            QMessageBox.information(self, t("inv.reload"), t("inv.reload.missing", path=path or "–"))
            return
        try:
            res = parse_file(path, self.market)
        except Exception as e:
            QMessageBox.warning(self, t("inv.import"), t("inv.import.failed", err=e))
            return
        if not res.matched:
            self._report(res, False)
            return
        self._apply_import(res, confirm=False)

    # ---------- the shared game-file reader (app/game/gamefile.py) ----------
    def work_file(self, path, data):
        """Background thread: the parsed game file -> an ImportResult (names matched to the market catalog)."""
        from app.game.inventory import ImportResult, parse_json
        res = ImportResult(source=os.path.basename(path))
        res.path = path
        return parse_json(data, self.market, res)

    def apply_file(self, res):
        """Window thread: the new inventory replaces the old one (only cheap work here)."""
        if not res.matched:
            return
        self.inv.replace_with(res, res.path)
        from app.core import logbus
        logbus.add("inventory", f"{os.path.basename(res.path)} changed: inventory read again ({res.matched} items)", "ok")
        if self.isVisible():
            self.refresh(force=True)

    def auto_reload(self):
        """Silently re-reads the imported file when it changed on disk (AlecaFrame rewrites it every time you enter
        or leave a mission). Only the modification time is checked each time."""
        path = self.inv.path
        if (not path or not os.path.exists(path)) and not self.inv.items:
            path = aleca.find_data_file()          # empty inventory: take AlecaFrame's file by itself
        if not path or not os.path.exists(path):
            return
        try:
            st = os.stat(path)
            key = (st.st_mtime_ns, st.st_size)
            if key == getattr(self, "_file_stat", None):
                return                              # not touched since the last look: no need to read it again
            self._file_stat = key
            with open(path, "rb") as f:
                sig = hashlib.md5(f.read()).hexdigest()
            first = getattr(self, "_file_sig", None) is None
            old = getattr(self, "_file_sig", None)
            self._file_sig = sig
            if sig == old:
                return
            if first and os.path.getmtime(path) <= (self.inv.imported or 0):
                return                              # first look: same file we imported
            res = parse_file(path, self.market)
            from app.core import logbus
            logbus.add("inventory", f"{os.path.basename(path)} changed: inventory read again", "ok")
        except Exception as e:
            from app.core import logbus
            logbus.error("inventory", f"cannot read {os.path.basename(path)}: {e}")
            return
        if res.matched:
            self.inv.replace_with(res, res.path)
            self.refresh(force=True)

    def paste_list(self):
        text, ok = QInputDialog.getMultiLineText(self, t("inv.paste"), t("inv.paste.prompt"))
        if not ok or not text.strip():
            return
        res = parse_text(text, self.market)
        res.source = t("inv.paste.source")
        if not res.matched:
            self._report(res, False)
            return
        self._apply_import(res)

    def add_item(self):
        dlg = ItemDialog(self.market, self)
        if dlg.exec():
            cur = self.inv.items.get(dlg.slug, {"n": 0, "m": 0})
            self.inv.set(dlg.slug, cur["n"] + dlg.n.value(), cur["m"] + dlg.m.value())
            self.refresh(force=True)

    def edit_item(self):
        slugs = self._selected_slugs()
        if len(slugs) != 1:
            return
        cur = self.inv.items.get(slugs[0])
        if not cur:
            return
        dlg = ItemDialog(self.market, self, slug=slugs[0], n=cur["n"], m=cur["m"])
        if dlg.exec():
            self.inv.set(slugs[0], dlg.n.value(), dlg.m.value())
            self.refresh(force=True)

    def remove_items(self):
        slugs = self._selected_slugs()
        if not slugs:
            return
        if QMessageBox.question(self, t("inv.remove"), t("inv.remove.confirm", n=len(slugs))) \
                == QMessageBox.StandardButton.Yes:
            self.inv.remove(slugs)
            self.refresh(force=True)

    def update_prices(self):
        rows, _ = self._rows()
        self.refresher.start([r["slug"] for r in rows], CFG["refresh_skip_age"])

    # ---------- warframe.market account and sell orders ----------
    def _account_text(self):
        self.btn_account.setText(t("inv.signout", user=self.account.user or "") if self.account.logged_in
                                 else t("inv.signin"))

    def toggle_account(self):
        if self.account.logged_in:
            self.account.logout()
            self._account_text()
            return
        self.sign_in()

    def sign_in(self) -> bool:
        dlg = LoginDialog(self)
        if not dlg.exec():
            return False
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.account.login(dlg.email.text().strip(), dlg.password.text())
        except MarketError as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, t("inv.login.title"), t("inv.login.failed", err=e))
            return False
        finally:
            QApplication.restoreOverrideCursor()
            dlg.password.clear()
        self._account_text()
        return True

    def send_to_quantframe(self):
        """The selected rows (or all the rows shown, if none is selected) -> Quantframe's stock, after a check window."""
        from app.ui.quantframe_dialog import SendDialog, entries_from_rows
        slugs = self._selected_slugs()
        rows = self._rows()[0]
        if slugs:
            want = set(slugs)
            rows = [r for r in rows if r["slug"] in want]
        entries = entries_from_rows(rows)
        if not entries:
            QMessageBox.information(self, t("qf.btn"), t("qf.empty"))
            return
        SendDialog("stock", entries, self).exec()

    def send_rivens(self):
        """Revealed rivens (already on a weapon) of the inventory file -> Quantframe's riven stock, after a check window."""
        from app.game import rivens
        from app.ui.riven_dialog import RivenDialog
        path = self.inv.path
        if not path or not os.path.exists(path):
            path = aleca.find_data_file()
        if not path or not os.path.exists(path):
            QMessageBox.information(self, t("riv.btn"), t("riv.nofile"))
            return
        try:
            items, skipped = rivens.read_file(path)
        except (ValueError, OSError) as e:
            QMessageBox.warning(self, t("riv.btn"), t("riv.readfail", err=e))
            return
        if not items:
            QMessageBox.information(self, t("riv.btn"), t("riv.none"))
            return
        RivenDialog(items, skipped, self, market=self.market).exec()

    def sell_selected(self):
        slugs = self._selected_slugs()
        if not slugs:
            QMessageBox.information(self, t("inv.sell"), t("inv.sell.select"))
            return
        if not self.account.logged_in and not self.sign_in():
            return
        rows = {r["slug"]: r for r in self._rows()[0]}
        placed = failed = 0
        for slug in slugs:
            r = rows.get(slug)
            if not r:
                continue
            info = self.market.info(slug)
            row = dict(r, id=info.get("id", ""))
            if not row["id"]:
                QMessageBox.warning(self, t("inv.sell"), t("inv.sell.noid", name=r["name"]))
                failed += 1
                continue
            off = int(CFG["sell_price_offset"])
            sug = {"0": (r["price"] + off) if r["price"] else None,
                   "max": (r["pmax"] + off) if r["pmax"] else None}
            dlg = SellDialog(row, self.account, sug, {"0": r["n"], "max": r["m"] if r["ranked"] else 0}, self)
            dlg.exec()
            if dlg.result_code == "cancel":
                break
            if dlg.result_code != "place":
                continue
            v = dlg.values()
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                oid = self.account.create_order(row["id"], v["price"], v["qty"], v["rank"], v["visible"])
            except MarketError as e:
                QApplication.restoreOverrideCursor()
                QMessageBox.warning(self, t("inv.sell"), t("inv.sell.failed", name=r["name"], err=e))
                failed += 1
                self._account_text()
                if e.status == 401:
                    break
                continue
            finally:
                QApplication.restoreOverrideCursor()
            self.inv.record_order(slug, oid, v["price"], v["qty"], v["rank"] or 0)
            placed += 1
        self._account_text()
        self.refresh(force=True)
        if placed or failed:
            QMessageBox.information(self, t("inv.sell"), t("inv.sell.summary", placed=placed, failed=failed))
