"""Platinum price + volume overlay for Warframe vendors (OCR + warframe.market).

Starts active: it detects a vendor being opened by itself and refreshes the data every 3 minutes.
F7  = price list (prices, recommendations, settings)  |  F8 = scan now (resumes if paused)
F9  = pause (hides the prices)  |  F10 = quit
The same actions are in the tray icon menu.
"""
import multiprocessing
import sys

if __name__ == "__main__":
    multiprocessing.freeze_support()     # needed by the exe: the OCR process restarts this same file

from config import APP_DIR, CFG
from i18n import t

# with --noconsole (exe) stdout/stderr do not exist: redirect them to a log file
if sys.stdout is None or sys.stderr is None:
    _log = open(APP_DIR / "overlay.log", "a", buffering=1, encoding="utf-8")
    sys.stdout = sys.stdout or _log
    sys.stderr = sys.stderr or _log


def _k(name: str) -> str:
    return name.strip("<>").upper()


def main():
    # heavy imports in here: the OCR process (which re-reads this file) does not load them
    from pynput import keyboard, mouse
    from PyQt6.QtCore import QObject, QTimer, pyqtSignal
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
    app.setQuitOnLastWindowClosed(False)     # closing the price list must not quit the program
    icon = make_icon()
    app.setWindowIcon(icon)
    overlay = Overlay()
    overlay.show()
    overlay.show_status(t("status.loading"), 60000)
    app.processEvents()

    market = Market()
    ocr = OcrClient(market.pairs(), {
        "threads": CFG["ocr_threads"],
        "priority": CFG["ocr_priority"],
        "threshold": CFG["match_threshold"],
        "only_warframe": CFG["only_warframe"],
        "main_pid": __import__("os").getpid(),
    })
    overlay.show_status(t("status.ready", menu=_k(CFG["key_menu"]), scan=_k(CFG["key_scan"]),
                          pause=_k(CFG["key_clear"]), quit=_k(CFG["key_quit"])), 6000)

    bridge = Bridge()
    bridge.results.connect(overlay.set_items)
    bridge.status.connect(overlay.show_status)
    bridge.clear.connect(lambda: overlay.set_items([]))
    bridge.quit.connect(app.quit)

    scanner = Scanner(market, bridge, overlay.geometry().width(), ocr)

    # price list: stays usable while it is open; its own area is blanked before the OCR (it must not read its own names)
    pricelist = PriceList(market)
    pricelist.setWindowIcon(icon)
    scanner.exclude_provider = pricelist.screen_rect_px
    pricelist.visibility.connect(lambda _v: scanner.list_changed())
    bridge.menu.connect(pricelist.toggle)
    if CFG["open_list_on_start"]:
        QTimer.singleShot(800, pricelist.toggle)      # open the price list when the program starts

    def restart():
        """Starts a new instance and quits this one (used by Settings → Save and restart)."""
        import os
        import subprocess
        frozen = getattr(sys, "frozen", False)
        args = [sys.executable] + ([] if frozen else [sys.argv[0]]) + sys.argv[1:]
        env = dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1")    # onefile exe: do not reuse this temp dir
        subprocess.Popen(args, env=env, close_fds=True)
        app.quit()

    pricelist.restart_requested.connect(restart)

    # Baro's list: if old (or never downloaded) re-download it in the background without blocking
    def _baro_startup():
        try:
            if market.vendors and market.vendors.baro_is_stale():
                market.vendors.refresh_baro()
        except Exception:
            pass
    import threading
    threading.Thread(target=_baro_startup, daemon=True).start()

    # tray icon, with the same actions as the keys
    tray = None
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray = QSystemTrayIcon(icon, app)
        tray.setToolTip("WF Vendor Overlay")
        tray_menu = QMenu()
        for text, fn in (
            (t("tray.pricelist", key=_k(CFG["key_menu"])), pricelist.toggle),
            (t("tray.scan", key=_k(CFG["key_scan"])), scanner.scan_now),
            (t("tray.pause", key=_k(CFG["key_clear"])), scanner.stop),
            (t("tray.quit", key=_k(CFG["key_quit"])), app.quit),
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
