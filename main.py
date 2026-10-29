"""Platinum price + volume overlay for Warframe vendors (OCR + warframe.market).

Starts active: it detects a vendor being opened by itself and refreshes the data every 3 minutes.
F7  = price list (prices, recommendations, settings)  |  F8 = scan now (resumes if paused)
F9  = pause (hides the prices)  |  F10 = quit
The same actions are in the tray icon menu.
"""
import multiprocessing
import os
import sys

# Restart and update launch this program with PYINSTALLER_RESET_ENVIRONMENT=1 (so the new exe does not reuse the old
# temp folder). The bootloader has already read it: remove it, or the OCR process we start would inherit it, behave
# like a brand-new program and fail with "OSError: [WinError 87]" in multiprocessing's spawn_main.
os.environ.pop("PYINSTALLER_RESET_ENVIRONMENT", None)

if __name__ == "__main__":
    multiprocessing.freeze_support()
    if len(sys.argv) >= 4 and sys.argv[1] == "--ocr-worker":     # the OCR process: this same program, started by OcrClient
        from app.scan.ocr_worker import worker_main
        worker_main(int(sys.argv[2]), sys.argv[3])
        sys.exit(0)

from app.core.config import APP_DIR, CFG
from app.core.i18n import t
from app.core.version import __version__

# with --noconsole (exe) stdout/stderr do not exist: redirect them to a log file
if sys.stdout is None or sys.stderr is None:
    _log = open(APP_DIR / "overlay.log", "a", buffering=1, encoding="utf-8")
    sys.stdout = sys.stdout or _log
    sys.stderr = sys.stderr or _log


def _k(name: str) -> str:
    return name.strip("<>").upper()


def main():
    # heavy imports in here: the OCR process (which re-reads this file) does not load them
    from pynput import keyboard
    from app.scan.wheel import WheelListener
    from PyQt6.QtCore import QObject, QTimer, pyqtSignal
    from PyQt6.QtGui import QAction
    from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

    from app.trade.market import Market
    from app.scan.ocr_worker import OcrClient
    from app.ui.menu import PriceList, make_icon
    from app.scan.overlay import Overlay
    from app.scan.scanner import Scanner

    class Bridge(QObject):
        menu = pyqtSignal()
        clear = pyqtSignal()
        quit = pyqtSignal()
        results = pyqtSignal(list)
        update_found = pyqtSignal(object)
        status = pyqtSignal(str)
        goals = pyqtSignal()
        goals_interact = pyqtSignal()

    if sys.platform == "win32":                  # own taskbar identity: the taskbar shows our icon, not python's
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ZioLadro.WFVendorOverlay")
        except Exception:
            pass
    app = QApplication(sys.argv)
    from app.core import theme
    theme.apply(app)
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
        "ocr_width": CFG["ocr_width"],
        "mask_panel": CFG["ocr_mask_panel"],
        "threshold": CFG["match_threshold"],
        "only_warframe": CFG["only_warframe"],
        "main_pid": __import__("os").getpid(),
    })
    overlay.show_status(t("status.ready", menu=_k(CFG["key_menu"]), scan=_k(CFG["key_scan"]),
                          pause=_k(CFG["key_clear"]), quit=_k(CFG["key_quit"])), 6000)

    bridge = Bridge()
    bridge.results.connect(overlay.set_items)
    bridge.status.connect(overlay.show_status)
    from app.core import logbus
    bridge.status.connect(lambda text: logbus.add("overlay", text))
    bridge.clear.connect(lambda: overlay.set_items([]))
    bridge.quit.connect(app.quit)

    scanner = Scanner(market, bridge, overlay.geometry().width(), ocr)

    # price list: stays usable while it is open; its own area is blanked before the OCR (it must not read its own names)
    pricelist = PriceList(market)
    pricelist.setWindowIcon(icon)
    # in-game Activities overlay (hotkey key_goals): what to buy with standing and how to earn it
    from app.ui.goals_overlay import GoalsOverlay
    from app.game.standing import get_store
    goals = GoalsOverlay(market, pricelist.inventory, get_store())
    bridge.goals.connect(goals.toggle)
    bridge.goals_interact.connect(goals.toggle_interact)
    bridge.results.connect(lambda items: goals.vendor_shown(bool(items)))     # a vendor recognised: the plan switches off
    QTimer.singleShot(1500, goals.start)
    from app.game import weekly as WK
    scanner.on_texts = lambda texts: WK.get().ocr_scan(texts)       # limited offers on the vendor screen (Weekly)
    scanner.exclude_provider = lambda: [r for r in (pricelist.screen_rect_px(), goals.screen_rect_px()) if r]
    pricelist.visibility.connect(lambda _v: scanner.list_changed())
    bridge.menu.connect(pricelist.toggle)
    bridge.update_found.connect(pricelist.offer_update)
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

    # update check at start (in the background; it only tells you, installing is up to you in Settings)
    def _update_startup():
        if not CFG["check_updates"]:
            return
        try:
            from app.core import updater
            info = updater.check()
            if info["newer"]:
                bridge.status.emit(t("update.notice", v=info["version"]))
                bridge.update_found.emit(info)
        except Exception:
            pass
    threading.Thread(target=_update_startup, daemon=True).start()

    # tray icon, with the same actions as the keys
    tray = None
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray = QSystemTrayIcon(icon, app)
        tray.setToolTip("WF Vendor Overlay " + __version__)
        tray_menu = QMenu()
        for text, fn in (
            (t("tray.pricelist", key=_k(CFG["key_menu"])), pricelist.toggle),
            (t("tray.goals", key=_k(CFG["key_goals"])), goals.toggle),
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
        CFG["key_goals"]: bridge.goals.emit,
        **({CFG["key_goals_interact"]: bridge.goals_interact.emit}
           if CFG.get("key_goals_interact") and CFG["key_goals_interact"] not in
           (CFG["key_menu"], CFG["key_scan"], CFG["key_clear"], CFG["key_quit"], CFG["key_goals"]) else {}),
    })
    hotkeys.start()
    wheel = WheelListener(scanner.on_scroll)
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
