"""Vosfor tab: what your Arcanes dissolve into, which Arcanes are best turned into Vosfor, which of Loid's collections are
worth the Vosfor (see app/game/vosfor.py for the maths)."""
import time

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QPushButton, QSplitter, QTableWidget,
    QVBoxLayout, QWidget,
)

from app.core.i18n import t
from app.core.uiutil import DIM_COLOR, PRICE_COLOR, Cell, attach_item_menu, num_key, role, thousands
from app.game import arcanes as A
from app.game import vosfor as V

GOOD, BAD, AMBER = QColor("#4fbf6a"), QColor("#e0584a"), QColor("#e0b83a")


def _table(headers, stretch=0):
    tb = QTableWidget(0, len(headers))
    tb.setHorizontalHeaderLabels(headers)
    tb.verticalHeader().hide()
    tb.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    tb.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    tb.setAlternatingRowColors(True)
    tb.setShowGrid(False)
    hdr = tb.horizontalHeader()
    for c in range(len(headers)):
        hdr.setSectionResizeMode(c, QHeaderView.ResizeMode.Stretch if c == stretch else
                                 QHeaderView.ResizeMode.ResizeToContents)
    return tb


def _p(v, dec=0):
    return "–" if v is None else (f"{v:.{dec}f}p" if dec else f"{round(v)}p")


class VosforTab(QWidget):
    def __init__(self, market, refresher, get_owned, get_installed=lambda: set()):
        super().__init__()
        self.market, self.refresher = market, refresher
        self.get_owned, self.get_installed = get_owned, get_installed
        self._sig = None
        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.TextFormat.RichText)
        self.btn_prices = QPushButton(t("vos.prices"))
        self.btn_prices.setToolTip(t("vos.prices.tip"))
        self.only_mine = QCheckBox(t("vos.only_dissolve"))
        self.only_mine.setToolTip(t("vos.only_dissolve.tip"))
        bar = QHBoxLayout()
        bar.addWidget(self.summary, 1)
        bar.addWidget(self.only_mine)
        bar.addWidget(self.btn_prices)

        self.mine = _table([t("vos.col.arcane"), t("vos.col.copies"), t("vos.col.yield"), t("vos.col.vosfor"),
                            t("vos.col.price"), t("vos.col.value"), t("vos.col.plat100"), t("vos.col.advice")])
        self.cheap = _table([t("vos.col.arcane"), t("vos.col.yield"), t("vos.col.price"), t("vos.col.perplat"),
                             t("vos.col.plat100")])
        self.packs = _table([t("vos.col.pack"), t("vos.col.ev"), t("vos.col.per100"), t("vos.col.best"),
                             t("vos.col.legendary"), t("vos.col.back"), t("vos.col.known")], stretch=3)
        self.pack_detail = _table([t("vos.col.arcane"), t("vos.col.chance"), t("vos.col.price"), t("vos.col.yield")])
        for tb in (self.mine, self.cheap, self.pack_detail):
            attach_item_menu(tb, 0)

        def box(title, w, hint=None):
            g = QGroupBox(title)
            lay = QVBoxLayout(g)
            if hint:
                lab = QLabel(hint)
                lab.setWordWrap(True)
                role(lab, "hint")
                lay.addWidget(lab)
            lay.addWidget(w, 1)
            return g
        right = QSplitter(Qt.Orientation.Vertical)
        right.addWidget(box(t("vos.box.packs"), self.packs, t("vos.box.packs.hint", cost=V.pack_cost(), n=V.pack_size())))
        right.addWidget(box(t("vos.box.pack"), self.pack_detail))
        left = QSplitter(Qt.Orientation.Vertical)
        left.addWidget(box(t("vos.box.mine"), self.mine, t("vos.box.mine.hint")))
        left.addWidget(box(t("vos.box.cheap"), self.cheap, t("vos.box.cheap.hint")))
        split = QSplitter()
        split.addWidget(left)
        split.addWidget(right)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 1)
        note = QLabel(t("vos.note"))
        note.setWordWrap(True)
        role(note, "hint")
        lay = QVBoxLayout(self)
        lay.addLayout(bar)
        lay.addWidget(split, 1)
        lay.addWidget(note)
        self.btn_prices.clicked.connect(self.update_prices)
        self.only_mine.toggled.connect(lambda _c: self.refresh(force=True))
        self.packs.currentCellChanged.connect(lambda *_a: self._show_pack())
        self._packs = []

    # ---------- data ----------
    def _slug(self, name):
        try:
            return self.market.slug_for_name(name)
        except Exception:
            return None

    def prices(self) -> dict:
        """{Arcane name: rank 0 price} of every Arcane that can be dissolved, from the saved market data."""
        out = {}
        for name in (A.vosfor_data().get("yield") or {}):
            s = self._slug(name)
            c = self.market.cached(s) if s else None
            if c and c.get("price") is not None:
                out[name] = c["price"]
        return out

    def update_prices(self):
        slugs = [s for s in (self._slug(n) for n in (A.vosfor_data().get("yield") or {})) if s]
        self.refresher.start(slugs, 3600)

    def set_busy(self, busy: bool):
        self.btn_prices.setEnabled(not busy)

    # ---------- showing ----------
    def refresh(self, force=False):
        prices = self.prices()
        owned = self.get_owned() or {}
        sig = (tuple(sorted(prices.items())), len(owned), sum(int(e.get("c", e.get("n", 0)) or 0) for e in owned.values()),
               self.only_mine.isChecked(), int(time.time() // 300))
        if not force and sig == self._sig:
            return
        self._sig = sig
        rows = V.mine(owned, prices, self.get_installed() or set())
        if self.only_mine.isChecked():
            rows = [r for r in rows if r["advice"] == "dissolve"]
        tot = V.totals(V.mine(owned, prices, self.get_installed() or set()))
        rate = V.best_rate(prices)
        self._fill_mine(rows)
        self._fill_cheap(V.cheapest(prices), rate)
        self._packs = V.packs(prices)
        self._fill_packs(self._packs)
        if not owned:
            text = t("vos.summary.noinv")
        else:
            text = t("vos.summary", all=thousands(tot["all"]), packs=tot["packs_all"], dis=thousands(tot["dissolve"]),
                     dpacks=tot["packs_dissolve"], lost=round(tot["plat_lost"]))
        if rate:
            text += " " + t("vos.summary.rate", p=f"{rate:.1f}")
        if len(prices) < 20:
            text += " " + t("vos.summary.noprices")
        self.summary.setText(text)

    def _fill(self, tb, rows):
        tb.setSortingEnabled(False)
        tb.setRowCount(0)
        tb.setRowCount(len(rows))
        for i, cells in enumerate(rows):
            for c, cell in enumerate(cells):
                tb.setItem(i, c, cell)
        tb.setSortingEnabled(True)

    def _fill_mine(self, rows):
        col = {"dissolve": GOOD, "sell": PRICE_COLOR, "keep": DIM_COLOR, "unknown": DIM_COLOR}
        out = []
        for r in rows:
            adv = Cell(t("vos.adv." + r["advice"]), r["advice"], col.get(r["advice"]))
            adv.setToolTip(t("vos.adv." + r["advice"] + ".tip"))
            name = Cell(r["name"], r["name"].lower(), center=False)
            name.setToolTip(A.describe(r["name"], r["rank"]))
            out.append([name, Cell(f"{r['copies']}" + (f" (R{r['rank']})" if r["rank"] else ""), r["copies"]),
                        Cell(str(r["yield"]), r["yield"]), Cell(thousands(r["vosfor"]), r["vosfor"]),
                        Cell(_p(r["price"]), num_key(r["price"]), PRICE_COLOR if r["price"] is not None else DIM_COLOR),
                        Cell(_p(r["value"]), num_key(r["value"])),
                        Cell(_p(r["plat100"], 1), num_key(r["plat100"])), adv])
        self._fill(self.mine, out)

    def _fill_cheap(self, rows, rate):
        out = []
        for r in rows:
            good = rate and r["plat100"] <= rate
            out.append([Cell(r["name"], r["name"].lower(), center=False), Cell(str(r["yield"]), r["yield"]),
                        Cell(_p(r["price"]), r["price"], PRICE_COLOR), Cell(f"{r['per_plat']:.1f}", r["per_plat"],
                                                                             GOOD if good else None),
                        Cell(_p(r["plat100"], 1), r["plat100"])])
        self._fill(self.cheap, out)
        self.cheap.sortByColumn(3, Qt.SortOrder.DescendingOrder)

    def _fill_packs(self, packs):
        out = []
        for p in packs:
            best = p["best"]
            name = Cell(p["name"], p["name"].lower(), center=False)
            name.setData(Qt.ItemDataRole.UserRole, p["id"])
            low = p["known"] < 0.5
            none = p["known"] <= 0                      # no price at all yet: nothing to estimate
            out.append([name, Cell("–" if none else ("~" if low else "") + _p(p["ev"], 1), p["ev"],
                                   DIM_COLOR if none else AMBER if low else PRICE_COLOR),
                        Cell("–" if none else f"{p['per100']:.1f}p", p["per100"]),
                        Cell(f"{best[0]} ({best[2]:.0f}p · {best[1] * 100:.1f}%)" if best else "–", best[2] if best else 0),
                        Cell(f"{p['legendary'] * 100:.1f}%", p["legendary"]),
                        Cell(f"{p['ev_vosfor']:.0f}", p["ev_vosfor"]),
                        Cell(f"{p['known'] * 100:.0f}%", p["known"], AMBER if low else DIM_COLOR)])
            out[-1][1].setToolTip(t("vos.ev.tip", n=V.pack_size()) + ("\n" + t("vos.ev.low") if low else ""))
        self._fill(self.packs, out)
        self.packs.sortByColumn(1, Qt.SortOrder.DescendingOrder)
        if self.packs.rowCount() and self.packs.currentRow() < 0:
            self.packs.selectRow(0)
        self._show_pack()

    def _show_pack(self):
        row = self.packs.currentRow()
        it = self.packs.item(row, 0) if row >= 0 else None
        pid = it.data(Qt.ItemDataRole.UserRole) if it else None
        p = next((x for x in self._packs if x["id"] == pid), None)
        rows = []
        for name, ch, pr, y in (p["rows"] if p else []):
            rows.append([Cell(name, name.lower(), center=False), Cell(f"{ch * 100:.2f}%", ch),
                         Cell(_p(pr), num_key(pr), PRICE_COLOR if pr is not None else DIM_COLOR),
                         Cell(str(y) if y else "–", y or 0)])
        self._fill(self.pack_detail, rows)
        self.pack_detail.sortByColumn(2, Qt.SortOrder.DescendingOrder)
