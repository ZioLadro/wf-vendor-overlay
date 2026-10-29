"""Weekly tab: vendor offers with a purchase limit (Teshin, Ironwake, Nightcap, Archimedean, Acrithis…), what you bought
this period, when the limits reset, and which offers you follow in the standing plan overlay. Purchases the program could
not identify are listed on top, to pick from the vendor's offers (see weekly.py)."""
import os
import time

from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMenu, QPushButton,
    QTableWidget, QTableWidgetItem, QToolButton, QVBoxLayout, QWidget,
)

from app.game import aleca
from app.game import weekly as WK
from app.core.i18n import t
from app.core.uiutil import Cell, role, thousands


def left(seconds) -> str:
    s = max(0, int(seconds))
    d, h, m = s // 86400, s % 86400 // 3600, s % 3600 // 60
    return f"{d}d {h}h" if d else (f"{h}h {m:02d}m" if h else f"{m}m")


def cost_text(cost, any_cost=None) -> str:
    """"10 Pathos Clamp"; a price drawn from a list (any_cost: [[lowest, highest, currency]]): "one of: 80 Kovnik, …"."""
    if cost:
        return " + ".join(f"{thousands(n)} {name}" for n, name in cost)
    if any_cost:
        parts = [(f"{thousands(lo)}" if lo == hi else f"{thousands(lo)}-{thousands(hi)}") + f" {name}" for lo, hi, name in any_cost]
        return t("weekly.cost.any", items=", ".join(parts[:3]) + (f", … ({len(parts)})" if len(parts) > 3 else ""))
    return "–"


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
        self.wallet = QLabel("")                    # the currencies these vendors ask for, and how many you have
        self.wallet.setWordWrap(True)
        bar = QHBoxLayout()
        bar.addWidget(QLabel(t("weekly.vendor")))
        bar.addWidget(self.vendor, 1)
        bar.addWidget(self.weekly_only)
        bar.addWidget(self.only_tracked)
        bar.addWidget(self.show_inactive)
        # offer categories (several at once) and a name filter
        from app.core.config import CFG
        self.cats = QToolButton()
        self.cats.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.cats.setToolTip(t("weekly.cat.tip"))
        menu = QMenu(self.cats)
        on = set(CFG.get("weekly_categories") or [])
        self.cat_actions = {}
        for key, _test in WK.CATEGORIES + (("other", None),):
            a = menu.addAction(t("weekly.cat." + key))
            a.setCheckable(True)
            a.setChecked(key in on)
            a.toggled.connect(lambda _c: self._cats_changed())
            self.cat_actions[key] = a
        menu.addSeparator()
        menu.addAction(t("weekly.cat.all"), self._cats_clear)
        self.cats.setMenu(menu)
        self._cats_label()
        self.search = QLineEdit()
        self.search.setPlaceholderText(t("weekly.search"))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _s: self.refresh(force=True))
        bar.insertWidget(2, self.cats)
        bar.insertWidget(3, self.search, 1)
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
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)    # several offers at once
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._menu)
        self.sel_bar = QHBoxLayout()
        self.sel_info = QLabel("")
        role(self.sel_info, "muted")
        self.btn_track = QPushButton(t("weekly.sel.track"))
        self.btn_untrack = QPushButton(t("weekly.sel.untrack"))
        self.btn_track.clicked.connect(lambda: self._track_selected(True))
        self.btn_untrack.clicked.connect(lambda: self._track_selected(False))
        self.sel_bar.addWidget(self.sel_info, 1)
        self.sel_bar.addWidget(self.btn_track)
        self.sel_bar.addWidget(self.btn_untrack)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self._selection_changed()
        hint = QLabel(t("weekly.hint"))
        hint.setWordWrap(True)
        role(hint, "hint")
        lay = QVBoxLayout(self)
        lay.addWidget(self.unknown_box)
        lay.addLayout(bar)
        lay.addWidget(self.summary)
        lay.addWidget(self.wallet)
        lay.addWidget(self.table, 1)
        lay.addLayout(self.sel_bar)
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
        cats = {k for k, a in self.cat_actions.items() if a.isChecked()}
        text = self.search.text().strip().lower()
        sig = (self.w.version, self.vendor.currentData(), self.weekly_only.isChecked(), self.only_tracked.isChecked(),
               self.show_inactive.isChecked(), tuple(sorted(cats)), text,
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
                and (self.show_inactive.isChecked() or o.get("active") is not False)
                and (not cats or o.get("cat") in cats)
                and (not text or text in o["name"].lower() or text in o["vendor_name"].lower())]
        tb = self.table
        tb.blockSignals(True)
        tb.setSortingEnabled(False)
        tb.setRowCount(len(rows))
        for r, o in enumerate(rows):
            reset = o["expiry"] or (WK.next_reset(now) if o["hours"] == 168 else
                                    (int(now // 86400) + 1) * 86400 if o["hours"] == 24 else None)
            done = o["bought"] >= o["limit"]
            vname = o["vendor_name"] + ("  " + t("weekly.ev.on") if o.get("active") else "  " + t("weekly.ev.off")
                                        if o.get("active") is False else "")
            cells = [Cell(vname, o["vendor_name"].lower(), center=False),
                     Cell(o["name"] + (f" ×{thousands(o['qty'])}" if o["qty"] > 1 else ""), o["name"].lower(), center=False),
                     Cell(cost_text(o["cost"], o.get("cost_any")), cost_text(o["cost"], o.get("cost_any")).lower(), center=False),
                     Cell(f"{o['bought']}/{o['limit']}" + ("  ✔" if done else "") + ("  " + t("weekly.ocr") if o.get("ocr") else ""),
                          o["bought"] / max(1, o["limit"])),
                     Cell(left(reset - now) if reset else "–", reset or 0)]
            if o.get("ocr"):
                cells[3].setToolTip(t("weekly.ocr.tip"))
            if o.get("cost_any"):
                cells[2].setToolTip(t("weekly.cost.any.tip") + "\n" + "\n".join(
                    (f"{lo}" if lo == hi else f"{lo}-{hi}") + f" {n}" for lo, hi, n in o["cost_any"]))
            cells[1].setToolTip(t("weekly.cat." + o.get("cat", "other")))
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
        self._draw_wallet(rows)
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

    def _draw_wallet(self, rows):
        """Each currency the shown offers cost (Steel Essence for Teshin, Riven Slivers for Ironwake, Pathos Clamps for
        Acrithis…) with how many you own (from the game file), and its icon."""
        from app.ui import playericons as P
        names = []
        for o in rows:
            for _q, n in o.get("cost") or []:
                if n not in names:
                    names.append(n)
        if not names:
            self.wallet.setText("")
            return
        path = self._path()
        inv = WK.raw_inventory(path) if path else None
        have = WK.counts(inv) if inv else {}
        parts = []
        for n in names:
            c = P.currency(n)
            if n.lower() == "credits":
                q = have.get("RegularCredits")
            else:
                q = have.get(c["path"]) if c else None
            icon = P.path_for(c["icon"]) if c and c.get("icon") else None
            img = f"<img src='{QUrl.fromLocalFile(icon).toString()}' height='16'> " if icon else ""
            parts.append(f"{img}{n.title() if n.isupper() else n}: <b>{thousands(q) if q is not None else '–'}</b>")
        self.wallet.setText(t("weekly.wallet") + " " + " &nbsp;·&nbsp; ".join(parts))

    # ---------- categories and several offers at once ----------
    def _cats_label(self):
        on = [k for k, a in self.cat_actions.items() if a.isChecked()]
        self.cats.setText((t("weekly.cat.label", n=len(on)) if on else t("weekly.cat.all")) + " ▾")

    def _cats_changed(self):
        from app.core.config import save_config
        save_config({"weekly_categories": [k for k, a in self.cat_actions.items() if a.isChecked()]})
        self._cats_label()
        self.refresh(force=True)

    def _cats_clear(self):
        for a in self.cat_actions.values():
            a.blockSignals(True)
            a.setChecked(False)
            a.blockSignals(False)
        self._cats_changed()

    def _selected_offers(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        out = []
        for r in rows:
            it = self.table.item(r, 5)
            if it is not None and it.data(Qt.ItemDataRole.UserRole) is not None:
                out.append(tuple(it.data(Qt.ItemDataRole.UserRole)))
        return out

    def _selection_changed(self):
        n = len(self._selected_offers())
        self.sel_info.setText(t("weekly.sel.n", n=n) if n else t("weekly.sel.hint"))
        self.btn_track.setEnabled(bool(n))
        self.btn_untrack.setEnabled(bool(n))

    def _track_selected(self, on):
        for vendor, offer in self._selected_offers():
            self.w.track(vendor, offer, on)
        self.refresh(force=True)

    def _menu(self, pos):
        if not self._selected_offers():
            return
        m = QMenu(self)
        m.addAction(t("weekly.sel.track"), lambda: self._track_selected(True))
        m.addAction(t("weekly.sel.untrack"), lambda: self._track_selected(False))
        m.exec(self.table.viewport().mapToGlobal(pos))

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
        region = self.w.region or "–"
        try:
            from app.game.eelog import LOCATION, PLACE_NAMES
            here = LOCATION.current()
            if here:
                region += " · " + t("weekly.unknown.eelog", place=PLACE_NAMES.get(here, here))
        except Exception:
            pass
        head = QLabel(t("weekly.unknown.head", n=len(unk), region=region))
        head.setToolTip(t("weekly.unknown.tip"))
        head.setWordWrap(True)
        head.setStyleSheet("font-weight: bold; color: #c9a227;")
        self.unknown_lay.addWidget(head)
        now = time.time()
        grouped = set()
        for g in self.w.groups():                  # "which one did you NOT buy?": one answer for a whole group
            grouped |= set(g["keys"])
            row = QHBoxLayout()
            lab = QLabel(t("weekly.group.row", vendor=g["vendor_name"], k=len(g["keys"]), n=g["n"]))
            box = QComboBox()
            for i in g["offers"]:
                box.addItem(i["name"] + (f" ×{thousands(i['qty'])}" if i["qty"] > 1 else ""), i["id"])
            box.setToolTip(t("weekly.group.tip"))
            ok = QPushButton(t("weekly.confirm"))
            ok.clicked.connect(lambda _c=False, ks=list(g["keys"]), b=box: (self.w.identify_group(ks, b.currentData()),
                                                                          self.refresh(force=True)))
            row.addWidget(lab)
            row.addWidget(box, 1)
            row.addWidget(ok)
            self.unknown_lay.addLayout(row)
        for u in unk:
            if u["key"] in grouped:
                continue
            row = QHBoxLayout()
            lab = QLabel(t("weekly.unknown.row", vendor=u["vendor_name"], n=u["n"], left=left(u["expiry"] - now)))
            box = QComboBox()
            poss = set(u.get("possible") or [])
            for i in u["items"]:
                star = "★ " if i["id"] in u["candidates"] else ("" if not poss or i["id"] in poss else "✗ ")
                box.addItem(star + i["name"] + (f" ×{thousands(i['qty'])}" if i["qty"] > 1 else ""), i["id"])
                if poss and i["id"] not in poss:
                    box.setItemData(box.count() - 1, t("weekly.unknown.impossible"), Qt.ItemDataRole.ToolTipRole)
            box.setToolTip(t("weekly.unknown.box", n=len(poss)) if poss else "")
            box.addItem(t("weekly.skip"), WK.SKIP)
            ok = QPushButton(t("weekly.confirm"))
            ok.clicked.connect(lambda _c=False, k=u["key"], b=box: (self.w.identify(k, b.currentData()), self.refresh(force=True)))
            row.addWidget(lab)
            row.addWidget(box, 1)
            row.addWidget(ok)
            self.unknown_lay.addLayout(row)
