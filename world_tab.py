"""World tab: fissures, invasions, sortie, cycles and Baro's current stock with platinum prices."""
import threading
import time

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, QHeaderView, QTabWidget

from config import CFG
from i18n import t
from uiutil import role
from uiutil import HINT_STYLE
from world import fetch_world, parse_baro, parse_world


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
                self.bus.done.emit(fetch_world(CFG["language"]), "")
            except Exception as e:
                import logbus
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

    def show_world(self, ws):
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
