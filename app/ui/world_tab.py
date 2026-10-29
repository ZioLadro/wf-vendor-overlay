"""World tab: fissures, invasions, sortie, cycles, the Arbitration schedule (hour by hour, with the arbi.guide tier) and
Baro's current stock with platinum prices."""
import threading
import time

from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
                             QHeaderView, QTabWidget)

from app.core.config import CFG
from app.core.i18n import t
from app.core.uiutil import role
from app.core.uiutil import HINT_STYLE
from app.game.world import fetch_world, parse_baro, parse_world


class _Bus(QObject):
    done = pyqtSignal(object, str)


def _table(headers):
    tb = QTableWidget(0, len(headers))
    tb.setHorizontalHeaderLabels(headers)
    tb.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    tb.verticalHeader().setVisible(False)
    tb.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    return tb


class WorldTab(QWidget):
    HEADERS = {
        "cycles": ("world.col.area", "world.col.state", "world.col.left"),
        "sortie": ("world.col.mission", "world.col.node", "world.col.mod"),
        "fissures": ("world.col.tier", "world.col.mission", "world.col.node", "world.col.left"),
        "invasions": ("world.col.node", "world.col.desc", "world.col.reward", "world.col.progress"),
    }

    def __init__(self, market):
        super().__init__()
        self.market = market
        self._last = 0.0
        self._busy = False
        self.bus = _Bus()
        self.bus.done.connect(self._done)
        self.status = QLabel(t("world.never"))
        role(self.status, "hint")
        self.btn = QPushButton(t("world.refresh"))
        self.btn.clicked.connect(lambda: self.refresh(force=True))
        top = QHBoxLayout()
        top.addWidget(self.status, 1)
        top.addWidget(self.btn)
        self.sub = QTabWidget()
        self.tables = {}
        for key in ("fissures", "invasions", "sortie", "cycles"):
            tb = _table([t(h) for h in self.HEADERS[key]])
            self.tables[key] = tb
            self.sub.addTab(tb, t("world.sec." + key))
        self.baro_head = QLabel("")
        self.baro = _table([t("world.col.item"), t("world.col.ducats"), t("world.col.credits"), t("world.col.plat")])
        bw = QWidget()
        bl = QVBoxLayout(bw)
        bl.addWidget(self.baro_head)
        bl.addWidget(self.baro, 1)
        self.sub.addTab(bw, "Baro Ki'Teer")
        # the Arbitrations to come (browse.wf's schedule, arbi.guide's tiers)
        self.arbi_rows, self.arbi_tiers = [], None
        self.arbi_filter = QComboBox()
        for key, label in (("", "world.arbi.all"), ("S", "world.arbi.s"), ("A", "world.arbi.a"), ("B", "world.arbi.b"),
                           ("C", "world.arbi.c")):
            self.arbi_filter.addItem(t(label), key)
        self.arbi_filter.setCurrentIndex(max(0, self.arbi_filter.findData(CFG.get("world_arbi_min", ""))))
        self.arbi_filter.currentIndexChanged.connect(self._arbi_filter_changed)
        self.arbi_note = QLabel(t("world.arbi.note"))
        self.arbi_note.setWordWrap(True)
        self.arbi_note.setOpenExternalLinks(True)
        role(self.arbi_note, "hint")
        self.arbi = _table([t("world.col.when"), t("world.col.in"), t("world.col.node"), t("world.col.mission"),
                            t("world.col.faction"), t("world.col.arbitier")])
        aw = QWidget()
        al = QVBoxLayout(aw)
        ah = QHBoxLayout()
        ah.addWidget(QLabel(t("world.arbi.show")))
        ah.addWidget(self.arbi_filter)
        ah.addStretch(1)
        al.addLayout(ah)
        al.addWidget(self.arbi, 1)
        al.addWidget(self.arbi_note)
        self.sub.insertTab(3, aw, t("world.sec.arbi"))
        self._arbi_timer = QTimer(self, interval=30_000, timeout=lambda: self.show_arbitrations() if aw.isVisible() else None)
        self._arbi_timer.start()
        # every activity of the world that can be followed in the Activities overlay
        self.follow = QTableWidget(0, 3)
        self.follow.setHorizontalHeaderLabels([t("wt.col.follow"), t("wt.col.what"), t("wt.col.now")])
        self.follow.verticalHeader().setVisible(False)
        self.follow.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.follow.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.follow.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.follow.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.follow.itemChanged.connect(self._follow_changed)
        fw = QWidget()
        fl = QVBoxLayout(fw)
        fnote = QLabel(t("wt.note"))
        fnote.setWordWrap(True)
        role(fnote, "hint")
        fl.addWidget(fnote)
        fl.addWidget(self.follow, 1)
        self.sub.insertTab(0, fw, t("wt.tab"))
        self.sub.setCurrentIndex(1)
        self._follow_rows = []
        self._follow_timer = QTimer(self, interval=1000, timeout=lambda: self._tick_follow() if fw.isVisible() else None)
        self._follow_timer.start()
        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(self.sub, 1)

    def refresh(self, force=False):
        """Called by the window timer: downloads only if world_refresh_s passed (or forced)."""
        if self._busy or (not force and time.monotonic() - self._last < float(CFG["world_refresh_s"])):
            return
        self._busy = True
        self.btn.setEnabled(False)
        self.status.setText(t("world.loading"))

        def run():
            try:
                from app.game import arbi
                self.arbi_tiers = arbi.tierlist()
                self.arbi_rows = arbi.schedule()
            except Exception as e:
                from app.core import logbus
                logbus.error("arbitration", f"{type(e).__name__}: {e}")
            try:
                self.bus.done.emit(fetch_world(CFG["language"]), "")
            except Exception as e:
                from app.core import logbus
                logbus.error("world", f"{type(e).__name__}: {e}")
                self.bus.done.emit(None, type(e).__name__)
        threading.Thread(target=run, daemon=True).start()

    def _done(self, ws, err):
        self._busy = False
        self.btn.setEnabled(True)
        self._last = time.monotonic()
        if ws is None:
            self.status.setText(t("world.error", err=err))
            return
        self.show_world(ws)
        self.status.setText(t("world.updated", time=time.strftime("%H:%M:%S")))

    def _arbi_filter_changed(self, _i):
        from app.core.config import save_config
        save_config({"world_arbi_min": self.arbi_filter.currentData() or ""})
        self.show_arbitrations()

    def show_arbitrations(self, hours=72):
        """The Arbitrations of the next hours: start, countdown, node, mission, faction and arbi.guide tier."""
        from app.game import arbi
        from app.ui.world_strip import TIER_COLOR, left
        order = {"S": 0, "A": 1, "B": 2, "C": 3, "D": 4, "F": 5}
        least = self.arbi_filter.currentData() or ""
        now = time.time()
        rows = []
        for i, (start, node) in enumerate(self.arbi_rows or []):
            end = self.arbi_rows[i + 1][0] if i + 1 < len(self.arbi_rows) else start + 3600
            if end <= now or start > now + hours * 3600:
                continue
            info = arbi.node_info(node) or [node, "", "", ""]
            tier, saryn, _n = arbi.tier_of(self.arbi_tiers, node, f"{info[0]} ({info[1]})")
            if least and order.get(tier, 9) > order[least]:
                continue
            rows.append((start, end, info, tier, saryn))
        self.arbi.setRowCount(len(rows))
        for r, (start, end, info, tier, saryn) in enumerate(rows):
            when = time.strftime("%d/%m %H:%M", time.localtime(start))
            cnt = t("world.arbi.now", left=left(end - now)) if start <= now else left(start - now)
            vals = (when, cnt, f"{info[0]} ({info[1]})" if info[1] else info[0], info[2], info[3],
                    (tier + (" *" if saryn else "")) if self.arbi_tiers else "–")
            for c, val in enumerate(vals):
                it = QTableWidgetItem(val)
                if c in (1, 5):
                    it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if c == 5 and tier:
                    it.setForeground(QBrush(QColor(TIER_COLOR.get(tier, "#9aa4b2"))))
                    it.setToolTip(t("strip.arbi.tip.ve", tier=tier, ve=arbi.TIER_INFO[tier]) if tier in arbi.TIER_INFO
                                  else t("strip.arbi.tip." + ("special" if tier == "Special" else "f")))
                if start <= now:
                    f = it.font()
                    f.setBold(True)
                    it.setFont(f)
                self.arbi.setItem(r, c, it)
        if not rows:
            self.arbi.setRowCount(1)
            self.arbi.setItem(0, 0, QTableWidgetItem(t("world.arbi.none")))

    def show_follow(self, ws):
        """Every activity that can be followed, the followed ones first (ticked)."""
        from app.game import worldtrack as WT
        followed = WT.tracked()
        rows = WT.items(ws)
        have = {e["key"] for e in rows}
        rows += [{"key": k, "missing": True} for k in followed if k not in have]
        rows.sort(key=lambda e: (e["key"] not in followed, {"events": 0, "cycles": 1, "fissures": 2, "invasions": 3}
                                 .get(e.get("group"), 4), WT.title(e)))
        self._follow_rows = rows
        tb = self.follow
        tb.blockSignals(True)
        tb.setRowCount(len(rows))
        for r, e in enumerate(rows):
            cb = QTableWidgetItem("")
            cb.setFlags(cb.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            cb.setCheckState(Qt.CheckState.Checked if e["key"] in followed else Qt.CheckState.Unchecked)
            cb.setData(Qt.ItemDataRole.UserRole, e["key"])
            tb.setItem(r, 0, cb)
            tb.setItem(r, 1, QTableWidgetItem(WT.title(e)))
            tb.setItem(r, 2, QTableWidgetItem(WT.text(e)[len(WT.title(e)) + 2:]))
        tb.blockSignals(False)

    def _tick_follow(self):
        from app.game import worldtrack as WT
        now = time.time()
        for r, e in enumerate(self._follow_rows):
            it = self.follow.item(r, 2)
            if it is not None:
                txt = WT.text(e, now)[len(WT.title(e)) + 2:]
                if it.text() != txt:
                    it.setText(txt)

    def _follow_changed(self, item):
        if item.column() != 0 or item.data(Qt.ItemDataRole.UserRole) is None:
            return
        from app.game import worldtrack as WT
        WT.set_tracked(item.data(Qt.ItemDataRole.UserRole), item.checkState() == Qt.CheckState.Checked)

    def show_world(self, ws):
        self.show_follow(ws)
        self.show_arbitrations()
        for key, rows in parse_world(ws):
            tb = self.tables[key]
            tb.setRowCount(len(rows))
            for r, row in enumerate(rows):
                for c, val in enumerate(row):
                    tb.setItem(r, c, QTableWidgetItem(val))
        head, items = parse_baro(ws)
        self.baro_head.setText(head or t("world.baro_none"))
        self.baro.setRowCount(len(items))
        for r, (name, du, cr) in enumerate(items):
            slug = self.market.slug_for_name(name)
            c = self.market.cached(slug) if slug else None
            plat = f"{c['price']}p" if c and c.get("price") is not None else "–"
            for col, val in enumerate((name, "" if du is None else str(du), "" if cr is None else f"{cr:,}".replace(",", " "), plat)):
                it = QTableWidgetItem(val)
                if col:
                    it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.baro.setItem(r, col, it)
