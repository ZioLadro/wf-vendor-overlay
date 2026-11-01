"""Build planner ▸ Cost: what the planned loadout needs that you do not have (Endo, credits, platinum), mod by mod, with
the buttons to update those prices and to put want-to-buy orders for the missing ones in Quantframe."""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QDialog, QHBoxLayout, QHeaderView, QLabel, QPushButton, QTableWidget, QVBoxLayout,
)

from app.core.i18n import t
from app.core.uiutil import DIM_COLOR, PRICE_COLOR, Cell, attach_item_menu, num_key, role, thousands

GOOD, AMBER = QColor("#4fbf6a"), QColor("#e0b83a")
COLS = ("item", "type", "rank", "owned", "status", "endo", "credits", "plat", "platmax", "used")


class CostDialog(QDialog):
    def __init__(self, planner):
        super().__init__(planner)
        self.planner = planner
        self.setWindowTitle(t("cost.title", name=planner.name.text().strip() or t("plan.untitled")))
        self.resize(980, 600)
        self.all_cfg = QCheckBox(t("cost.allcfg"))
        self.all_cfg.setToolTip(t("cost.allcfg.tip"))
        self.only_missing = QCheckBox(t("cost.onlymissing"))
        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.TextFormat.RichText)
        self.table = QTableWidget(0, len(COLS))
        self.table.setHorizontalHeaderLabels([t("cost.col." + c) for c in COLS])
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        hdr = self.table.horizontalHeader()
        for c in range(len(COLS)):
            hdr.setSectionResizeMode(c, QHeaderView.ResizeMode.Stretch if c in (0, len(COLS) - 1)
                                     else QHeaderView.ResizeMode.ResizeToContents)
        attach_item_menu(self.table, 0)
        note = QLabel(t("cost.note"))
        note.setWordWrap(True)
        role(note, "hint")
        self.btn_prices = QPushButton(t("cost.prices"))
        self.btn_prices.setToolTip(t("cost.prices.tip"))
        self.btn_qf = QPushButton(t("cost.qf"))
        self.btn_qf.setToolTip(t("cost.qf.tip"))
        self.btn_copy = QPushButton(t("cost.copy"))
        close = QPushButton(t("cost.close"))
        top = QHBoxLayout()
        top.addWidget(self.all_cfg)
        top.addWidget(self.only_missing)
        top.addStretch(1)
        bottom = QHBoxLayout()
        bottom.addWidget(self.btn_prices)
        bottom.addWidget(self.btn_copy)
        bottom.addStretch(1)
        bottom.addWidget(self.btn_qf)
        bottom.addWidget(close)
        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(self.summary)
        lay.addWidget(self.table, 1)
        lay.addWidget(note)
        lay.addLayout(bottom)
        self.all_cfg.toggled.connect(lambda _c: self.fill())
        self.only_missing.toggled.connect(lambda _c: self.fill())
        self.btn_prices.clicked.connect(self.update_prices)
        self.btn_qf.clicked.connect(self.to_quantframe)
        self.btn_copy.clicked.connect(self.copy_list)
        close.clicked.connect(self.accept)
        rf = getattr(planner, "refresher", None)
        if rf is not None:
            rf.finished.connect(lambda _m: self.fill() if self.isVisible() else None)
        self.fill()

    def _cost(self):
        return self.planner.cost(self.all_cfg.isChecked())

    def _slug(self, name):
        mk = self.planner.market
        try:
            return mk.slug_for_name(name) if mk is not None else None
        except Exception:
            return None

    def fill(self):
        c = self._cost()
        self._rows = c["rows"]
        rows = [r for r in c["rows"] if not self.only_missing.isChecked() or r["status"] != "ok"]
        tb = self.table
        tb.setSortingEnabled(False)
        tb.setRowCount(0)
        tb.setRowCount(len(rows))
        st_col = {"ok": GOOD, "rank": AMBER, "buy": PRICE_COLOR}
        for i, r in enumerate(rows):
            own = (t("cost.own.arc", c=r["have_n"], r=r["have_rank"]) if r["arcane"] else
                   t("cost.own.mod", r=r["have_rank"])) if r["have_n"] else "–"
            if r["arcane"] and r["buy_copies"]:
                status = t("cost.st.copies", n=r["buy_copies"])
            else:
                status = t("cost.st." + r["status"])
            plat = r["plat"]
            plat_txt = "–" if plat is None else f"{plat:.0f}p"
            if r["status"] != "ok" and plat is None and r["plat_max"] is None:
                plat_txt = t("cost.noprice")
            pm = r["plat_max"]
            cells = [Cell(r["name"], r["name"].lower(), center=False),
                     Cell(t("kind.arcane") if r["arcane"] else t("kind.mod"), r["arcane"]),
                     Cell(f"{r['rank']}/{r['max']}", r["rank"]),
                     Cell(own, r["have_n"], None if r["have_n"] else DIM_COLOR),
                     Cell(status, r["status"], st_col.get(r["status"])),
                     Cell(thousands(r["endo"]) if r["endo"] else "–", r["endo"]),
                     Cell(thousands(r["credits"]) if r["credits"] else "–", r["credits"]),
                     Cell(plat_txt, num_key(plat), PRICE_COLOR if plat is not None and r["choice"] != "maxed" else DIM_COLOR),
                     Cell("–" if pm is None else f"{pm:.0f}p", num_key(pm), PRICE_COLOR if r["choice"] == "maxed" else DIM_COLOR),
                     Cell(", ".join(r["items"]), ", ".join(r["items"]).lower(), center=False)]
            if r["choice"] == "maxed":
                cells[8].setToolTip(t("cost.maxed.tip"))
            for col, cell in enumerate(cells):
                tb.setItem(i, col, cell)
        tb.setSortingEnabled(True)
        own_note = "" if self.planner.get_owned() else "<br>" + t("cost.noinv")
        self.summary.setText(t("cost.summary", endo=thousands(c["endo"]), credits=thousands(c["credits"]),
                               plat=round(c["plat"]), platmax=round(c["plat_max"]), missing=c["missing"],
                               owned=c["owned"], n=len(c["rows"]))
                             + (" " + t("cost.unpriced", n=c["unpriced"]) if c["unpriced"] else "") + own_note)
        missing = [r for r in c["rows"] if r["status"] == "buy" or (r["arcane"] and r["buy_copies"])]
        self.btn_qf.setEnabled(bool(missing))
        self.btn_prices.setEnabled(self.planner.refresher is not None and bool(c["rows"]))

    def update_prices(self):
        slugs = [s for s in (self._slug(r["name"]) for r in self._rows if r["status"] != "ok") if s]
        if self.planner.refresher is not None and slugs:
            self.planner.refresher.start(slugs, 600)

    def to_quantframe(self):
        """The missing mods / Arcanes -> Quantframe's wish list: its Live Scraper places want-to-buy orders for them on
        warframe.market (Quantframe ▸ Settings ▸ Advanced ▸ HTTP server must be on)."""
        from app.game import buildcost as BCOST
        from app.ui.quantframe_dialog import SendDialog
        entries = BCOST.wish_entries(self._rows, self._slug)
        if not entries:
            return
        SendDialog("wish", entries, self, all_checked=True).exec()

    def copy_list(self):
        from PyQt6.QtGui import QGuiApplication
        lines = []
        for r in self._rows:
            if r["status"] == "ok":
                continue
            what = (t("cost.st.copies", n=r["buy_copies"]) if r["arcane"] and r["buy_copies"] else t("cost.st." + r["status"]))
            lines.append(f"{r['name']} R{r['rank']}: {what}" + (f" ~{r['plat']:.0f}p" if r["plat"] is not None else "")
                         + (f", {r['endo']} Endo" if r["endo"] else ""))
        QGuiApplication.clipboard().setText("\n".join(lines))
        self.summary.setText(self.summary.text() + "<br>" + t("cost.copied", n=len(lines)))
