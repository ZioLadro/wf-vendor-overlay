"""Overlay prezzi platino + volume per i vendor di Warframe (OCR + warframe.market).

Parte attivo: rileva da solo l'apertura di un vendor e aggiorna i dati ogni 3 minuti.
F7  = listino prezzi (tutti i dati raccolti)  |  F8 = scansiona subito (riprende se in pausa)
F9  = pausa (nasconde i prezzi)  |  F10 = esci
Le stesse azioni sono nel menu dell'icona vicino all'orologio.
"""
import multiprocessing
import sys

if __name__ == "__main__":
    multiprocessing.freeze_support()     # necessario per l'exe: il processo OCR riavvia lo stesso file

from config import APP_DIR, CFG

# con --noconsole (exe) stdout/stderr non esistono: li giriamo su un file di log
if sys.stdout is None or sys.stderr is None:
    _log = open(APP_DIR / "overlay.log", "a", buffering=1, encoding="utf-8")
    sys.stdout = sys.stdout or _log
    sys.stderr = sys.stderr or _log


def _k(name: str) -> str:
    return name.strip("<>").upper()


def main():
    # import pesanti qui dentro: il processo OCR (che rilegge questo file) non li carica
    from pynput import keyboard, mouse
    from PyQt6.QtCore import QObject, pyqtSignal
    from PyQt6.QtGui import QAction
    from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

    from market import Market
    from ocr_worker import OcrClient
    from menu import PriceList, make_icon
    from overlay import Overlay
    from scanner import Scanner

    class Bridge(QObject):
        menu = pyqtSignal()
        clear = pyqtSignal()
        quit = pyqtSignal()
        results = pyqtSignal(list)
        status = pyqtSignal(str)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)     # chiudere il listino non deve chiudere il programma
    icon = make_icon()
    app.setWindowIcon(icon)
    overlay = Overlay()
    overlay.show()
    overlay.show_status("Caricamento catalogo…", 60000)
    app.processEvents()

    market = Market()
    ocr = OcrClient(market.pairs(), {
        "threads": CFG["ocr_threads"],
        "priority": CFG["ocr_priority"],
        "threshold": CFG["match_threshold"],
    })
    overlay.show_status(
        f"Pronto: apri un vendor ({_k(CFG['key_menu'])} listino, {_k(CFG['key_scan'])} scansiona, "
        f"{_k(CFG['key_clear'])} pausa, {_k(CFG['key_quit'])} esci)", 6000)

    bridge = Bridge()
    bridge.results.connect(overlay.set_items)
    bridge.status.connect(overlay.show_status)
    bridge.clear.connect(lambda: overlay.set_items([]))
    bridge.quit.connect(app.quit)

    scanner = Scanner(market, bridge, overlay.geometry().width(), ocr)

    # listino prezzi: mentre e' aperto le scansioni sono sospese (non deve leggere i nomi del listino)
    pricelist = PriceList(market)
    pricelist.setWindowIcon(icon)
    pricelist.visibility.connect(scanner.set_suspended)
    bridge.menu.connect(pricelist.toggle)

    # elenco di Baro: se vecchio (o mai scaricato) lo riscarica in background, senza bloccare nulla
    def _baro_startup():
        try:
            if market.vendors and market.vendors.baro_is_stale():
                market.vendors.refresh_baro()
        except Exception:
            pass
    import threading
    threading.Thread(target=_baro_startup, daemon=True).start()

    # icona vicino all'orologio, con le stesse azioni dei tasti
    tray = None
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray = QSystemTrayIcon(icon, app)
        tray.setToolTip("WF Vendor Overlay")
        tray_menu = QMenu()
        for text, fn in (
            (f"Listino prezzi ({_k(CFG['key_menu'])})", pricelist.toggle),
            (f"Scansiona ora ({_k(CFG['key_scan'])})", scanner.scan_now),
            (f"Pausa ({_k(CFG['key_clear'])})", scanner.stop),
            (f"Esci ({_k(CFG['key_quit'])})", app.quit),
        ):
            act = QAction(text, tray_menu)
            act.triggered.connect(lambda _checked=False, f=fn: f())
            tray_menu.addAction(act)
        tray.setContextMenu(tray_menu)
        tray.activated.connect(
            lambda reason: pricelist.toggle() if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
        tray.show()

    hotkeys = keyboard.GlobalHotKeys({
        CFG["key_menu"]: bridge.menu.emit,
        CFG["key_scan"]: scanner.scan_now,
        CFG["key_clear"]: scanner.stop,
        CFG["key_quit"]: bridge.quit.emit,
    })
    hotkeys.start()
    wheel = mouse.Listener(on_scroll=lambda x, y, dx, dy: scanner.on_scroll())
    wheel.start()

    code = app.exec()
    if tray:
        tray.hide()
    hotkeys.stop()
    wheel.stop()
    ocr.close()
    market.flush()
    sys.exit(code)


if __name__ == "__main__":
    main()
