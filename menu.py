"""Finestra "Listino prezzi": tutti i dati raccolti dall'overlay, ordinabili e filtrabili."""
import threading
import time

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView, QComboBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
    QProgressBar, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from config import CFG
from overlay import volume_color

COLUMNS = ["Oggetto", "Vendor", "Tipo", "Prezzo", "Prezzo max rank", "Volume 24h", "Aggiornato"]
C_NAME, C_VENDOR, C_KIND, C_PRICE, C_PMAX, C_VOL, C_UPD = range(7)
KIND_LABEL = {"mod": "Mod", "arcane": "Arcane", "altro": "Altro"}
PRICE_COLOR = QColor(120, 200, 255)
MAXRANK_COLOR = QColor(255, 205, 110)
DIM_COLOR = QColor(130, 130, 130)

STYLE = """
QWidget { background: #161a22; color: #e6e6e6; font-size: 13px; }
QLineEdit, QComboBox { background: #1f2430; border: 1px solid #343b4d; border-radius: 4px; padding: 4px 8px; }
QComboBox QAbstractItemView { background: #1f2430; selection-background-color: #2d3650; }
QTableWidget { background: #161a22; alternate-background-color: #1a1f29; border: 1px solid #343b4d;
               selection-background-color: #2d3650; selection-color: #ffffff; }
QHeaderView::section { background: #232938; color: #c9d1e3; border: none; border-right: 1px solid #343b4d;
                       padding: 5px 8px; font-weight: bold; }
QPushButton { background: #232938; border: 1px solid #343b4d; border-radius: 4px; padding: 5px 12px; }
QPushButton:hover { background: #2d3650; }
QPushButton:disabled { color: #6b738a; background: #1a1f29; }
QProgressBar { background: #1f2430; border: 1px solid #343b4d; border-radius: 4px; text-align: center; height: 14px; }
QProgressBar::chunk { background: #3b6ea8; }
QScrollBar:vertical { background: #161a22; width: 12px; }
QScrollBar::handle:vertical { background: #343b4d; border-radius: 5px; min-height: 24px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
"""


def make_icon() -> QIcon:
    """Icona (moneta con una 'p' di platino) disegnata al volo: nessun file da includere nell'exe."""
    pm = QPixmap(64, 64)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(30, 36, 50))
    p.setPen(QColor(120, 200, 255))
    p.drawEllipse(3, 3, 58, 58)
    p.setPen(QColor(255, 255, 255))
    p.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
    p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, "p")
    p.end()
    return QIcon(pm)


def age_text(ts) -> str:
    if not ts:
        return "mai"
    s = max(0, time.time() - ts)
    if s < 60:
        return "ora"
    if s < 3600:
        return f"{int(s // 60)} min fa"
    if s < 86400:
        return f"{int(s // 3600)} h fa"
    return f"{int(s // 86400)} g fa"


class Cell(QTableWidgetItem):
    """Cella con chiave di ordinamento propria (numeri veri, valori mancanti in fondo/inizio)."""

    def __init__(self, text: str, key, color=None, center=True):
        super().__init__(text)
        self.key = key
        self.setFlags(self.flags() & ~Qt.ItemFlag.ItemIsEditable)
        if color is not None:
            self.setForeground(QBrush(color))
        if center:
            self.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

    def __lt__(self, other):
        if isinstance(other, Cell):
            return self.key < other.key
        return super().__lt__(other)


def _num(v):
    """Chiave numerica: i valori mancanti vengono prima di tutti (in fondo con ordine decrescente)."""
    return (0, 0) if v is None else (1, v)


class PriceList(QWidget):
    visibility = pyqtSignal(bool)        # True quando la finestra si apre, False quando si chiude
    progress = pyqtSignal(int, int, int)  # fatti, totale, errori   (dal thread di aggiornamento)
    job_done = pyqtSignal(str)           # messaggio finale dell'aggiornamento prezzi
    baro_done = pyqtSignal(str)          # messaggio finale dell'aggiornamento di Baro

    def __init__(self, market):
        super().__init__()
        self.market = market
        self._cancel = threading.Event()
        self._job = None                 # thread di aggiornamento prezzi in corso
        self._baro = None
        self._sig = None                 # impronta dei dati mostrati (evita ricostruzioni inutili)
        self._built = 0.0
        self.setWindowTitle("WF Vendor Overlay · Listino prezzi")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self.resize(1000, 620)
        self.setStyleSheet(STYLE)

        self.search = QLineEdit(placeholderText="Cerca oggetto…", clearButtonEnabled=True)
        self.vendor = QComboBox()
        self.kind = QComboBox()
        self.kind.addItem("Tutti i tipi", None)
        for k in ("mod", "arcane", "altro"):
            self.kind.addItem(KIND_LABEL[k], k)
        self.count = QLabel("")
        self.count.setStyleSheet("color: #9aa4bd;")
        self._fill_vendors()

        top = QHBoxLayout()
        top.addWidget(self.search, 1)
        top.addWidget(self.vendor)
        top.addWidget(self.kind)
        top.addWidget(self.count)

        self.btn_vis = QPushButton("Aggiorna elenco mostrato")
        self.btn_vis.setToolTip("Aggiorna prezzo e volume degli oggetti che vedi nella tabella (filtri compresi). "
                                "Salta i dati piu' recenti di pochi minuti.")
        self.btn_sel = QPushButton("Aggiorna selezionati")
        self.btn_sel.setToolTip("Aggiorna sempre gli oggetti selezionati (Ctrl/Maiusc per piu' righe)")
        self.btn_stop = QPushButton("Ferma")
        self.btn_stop.setEnabled(False)
        self.btn_baro = QPushButton("Aggiorna elenco Baro")
        self.btn_baro.setToolTip("Scarica dalla wiki l'elenco degli oggetti di Baro Ki'Teer")
        self.bar = QProgressBar()
        self.bar.setVisible(False)
        self.status = QLabel("")
        self.status.setStyleSheet("color: #9aa4bd;")

        actions = QHBoxLayout()
        for b in (self.btn_vis, self.btn_sel, self.btn_stop):
            actions.addWidget(b)
        actions.addWidget(self.bar, 1)
        actions.addWidget(self.status, 2)
        actions.addWidget(self.btn_baro)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(C_NAME, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(C_VENDOR, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(C_VENDOR, 190)
        for c in range(C_KIND, len(COLUMNS)):
            hdr.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSortIndicator(C_NAME, Qt.SortOrder.AscendingOrder)

        hint = QLabel("Prezzo = mediana dei 3 venditori online più bassi (mod e arcane: a rank 0; "
                      "«max rank» a rank massimo). Volume = scambi chiusi nelle ultime 24 ore. "
                      "«–» = nessun venditore online; «mai» = dato non ancora raccolto.")
        hint.setStyleSheet("color: #7d869e; font-size: 11px;")
        hint.setWordWrap(True)

        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addLayout(actions)
        lay.addWidget(self.table, 1)
        lay.addWidget(hint)

        self._timer = QTimer(self, timeout=self.refresh)
        self.search.textChanged.connect(lambda _: self.refresh(force=True))
        self.kind.currentIndexChanged.connect(lambda _: self.refresh(force=True))
        self.vendor.currentIndexChanged.connect(lambda _: self.refresh(force=True))
        self.btn_vis.clicked.connect(self.update_shown)
        self.btn_sel.clicked.connect(self.update_selected)
        self.btn_stop.clicked.connect(self._cancel.set)
        self.btn_baro.clicked.connect(self.update_baro)
        self.progress.connect(self._on_progress)
        self.job_done.connect(self._on_job_done)
        self.baro_done.connect(self._on_baro_done)

    def _fill_vendors(self):
        cur = self.vendor.currentData()
        self.vendor.blockSignals(True)
        self.vendor.clear()
        self.vendor.addItem("Tutti i vendor", None)
        for v in self.market.vendor_names():
            self.vendor.addItem(v, v)
        i = self.vendor.findData(cur)
        self.vendor.setCurrentIndex(max(0, i))
        self.vendor.blockSignals(False)

    # ---------- dati ----------
    def refresh(self, force=False):
        rows = self.market.snapshot()
        q = self.search.text().strip().lower()
        kind = self.kind.currentData()
        vendor = self.vendor.currentData()
        total = len(rows)
        rows = [r for r in rows if (kind is None or r["kind"] == kind) and q in r["name"].lower()
                and (vendor is None or vendor in r["vendors"])]

        # ricostruisce solo se i dati sono cambiati (o ogni 30 s per far avanzare "x min fa")
        sig = hash(tuple((r["slug"], r["price"], r["pmax"], r["vol"], r["updated"]) for r in rows))
        now = time.monotonic()
        if not force and sig == self._sig and now - self._built < 30:
            return
        self._sig, self._built = sig, now

        t = self.table
        hdr = t.horizontalHeader()
        sec, order = hdr.sortIndicatorSection(), hdr.sortIndicatorOrder()
        vpos = t.verticalScrollBar().value()
        selected = {t.item(i.row(), 0).data(Qt.ItemDataRole.UserRole) for i in t.selectedIndexes()
                    if t.item(i.row(), 0)}
        t.setUpdatesEnabled(False)
        t.setSortingEnabled(False)
        t.setRowCount(0)                 # ricostruzione da zero: molto piu' veloce che sostituire 1200 righe
        t.setRowCount(len(rows))
        for i, r in enumerate(rows):
            p, pm, v = r["price"], r["pmax"], r["vol"]
            vend = ", ".join(r["vendors"])
            cells = [
                Cell(r["name"], r["name"].lower(), center=False),
                Cell(vend, vend.lower(), center=False),
                Cell(KIND_LABEL.get(r["kind"], r["kind"]), r["kind"]),
                Cell("–" if p is None else f"{p}p", _num(p), PRICE_COLOR if p is not None else DIM_COLOR),
                (Cell("–" if pm is None else f"{pm}p", _num(pm), MAXRANK_COLOR if pm is not None else DIM_COLOR)
                 if r["ranked"] else Cell("", (0, 0))),
                Cell("–" if v is None else str(v), _num(v), volume_color(v) if v is not None else DIM_COLOR),
                Cell(age_text(r["updated"]), r["updated"] or 0),
            ]
            cells[0].setData(Qt.ItemDataRole.UserRole, r["slug"])
            cells[1].setToolTip("\n".join(r["vendors"]))
            if r["ranked"]:
                cells[C_PMAX].setToolTip(f"Prezzo a rank {r['max_rank']}")
            for c, cell in enumerate(cells):
                t.setItem(i, c, cell)
        t.setSortingEnabled(True)
        t.sortByColumn(sec, order)
        if selected:
            sm = t.selectionModel()
            for i in range(t.rowCount()):
                if t.item(i, 0).data(Qt.ItemDataRole.UserRole) in selected:
                    sm.select(t.model().index(i, 0), sm.SelectionFlag.Select | sm.SelectionFlag.Rows)
        t.verticalScrollBar().setValue(vpos)
        t.setUpdatesEnabled(True)
        self.count.setText(f"{len(rows)} di {total} oggetti" if len(rows) != total else f"{total} oggetti")

    # ---------- aggiornamento prezzi / volumi ----------
    def _slugs(self, selected_only: bool) -> list:
        t = self.table
        if selected_only:
            rows = sorted({i.row() for i in t.selectedIndexes()})
        else:
            rows = range(t.rowCount())
        return [t.item(r, 0).data(Qt.ItemDataRole.UserRole) for r in rows if t.item(r, 0)]

    def update_shown(self):
        self._start_job(self._slugs(False), CFG["refresh_skip_age"])

    def update_selected(self):
        self._start_job(self._slugs(True), 0)

    def _start_job(self, slugs, max_age):
        if self._job and self._job.is_alive():
            return
        if not slugs:
            self.status.setText("Nessun oggetto da aggiornare")
            return
        eta = int(len(slugs) * 2 * 0.35)           # 2 richieste per oggetto, ~3 al secondo
        if len(slugs) > int(CFG["refresh_confirm_over"]):
            ans = QMessageBox.question(
                self, "Aggiornamento lungo",
                f"Aggiornare {len(slugs)} oggetti richiede circa {eta // 60 + 1} minuti "
                f"({len(slugs) * 2} richieste a warframe.market, limite 3 al secondo).\n\n"
                "Puoi continuare a usare il listino e fermare quando vuoi. Procedere?")
            if ans != QMessageBox.StandardButton.Yes:
                return
        self._cancel.clear()
        self._set_busy(True)
        self.bar.setRange(0, len(slugs))
        self.bar.setValue(0)
        self.status.setText(f"0 / {len(slugs)}")
        market, cancel = self.market, self._cancel

        def run():
            try:
                done, errors, stopped = market.refresh_many(
                    slugs, cancel, lambda d, n, e: self.progress.emit(d, n, e), max_age)
                msg = (f"Fermato: {done} / {len(slugs)} aggiornati" if cancel.is_set()
                       else f"Aggiornati {done} oggetti" if not stopped
                       else f"Interrotto dopo {done} / {len(slugs)}: warframe.market non risponde")
                if errors:
                    msg += f" · {errors} con errori"
            except Exception as e:
                msg = f"Errore: {e}"
            self.job_done.emit(msg)

        self._job = threading.Thread(target=run, daemon=True)
        self._job.start()

    def _set_busy(self, busy: bool):
        self.bar.setVisible(busy)
        self.btn_stop.setEnabled(busy)
        for b in (self.btn_vis, self.btn_sel):
            b.setEnabled(not busy)

    def _on_progress(self, done, total, errors):
        self.bar.setMaximum(total)
        self.bar.setValue(done)
        self.status.setText(f"{done} / {total}" + (f" · {errors} errori" if errors else ""))

    def _on_job_done(self, msg):
        self._set_busy(False)
        self.status.setText(msg)
        self.refresh(force=True)

    def update_baro(self):
        if self._baro and self._baro.is_alive():
            return
        self.btn_baro.setEnabled(False)
        self.status.setText("Baro: download in corso…")
        vendors = self.market.vendors

        def run():
            try:
                _ok, msg = vendors.refresh_baro()
            except Exception as e:
                msg = f"Baro: errore ({e})"
            self.baro_done.emit(msg)

        self._baro = threading.Thread(target=run, daemon=True)
        self._baro.start()

    def _on_baro_done(self, msg):
        self.btn_baro.setEnabled(True)
        self.status.setText(msg)
        self._fill_vendors()
        self.refresh(force=True)

    # ---------- finestra ----------
    def toggle(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow()

    def showEvent(self, e):
        super().showEvent(e)
        self.refresh(force=True)
        self._timer.start(int(CFG["menu_refresh_ms"]))
        self.visibility.emit(True)

    def hideEvent(self, e):
        super().hideEvent(e)
        self._cancel.set()               # chiudendo il listino l'aggiornamento in corso si ferma
        self._timer.stop()
        self.visibility.emit(False)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(e)
