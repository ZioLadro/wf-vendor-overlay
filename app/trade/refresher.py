"""Background refresh of prices/volumes shared by all the tabs of the price-list window."""
import threading

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QMessageBox

from app.core.config import CFG
from app.core.i18n import t


class Refresher(QObject):
    started = pyqtSignal(int)             # total number of items
    progress = pyqtSignal(int, int, int)  # done, total, errors   (emitted from the worker thread)
    finished = pyqtSignal(str)            # final message
    queue_start = pyqtSignal(object, object)   # a click that waited for the Riven scan: start it now (window's thread)

    def __init__(self, market, parent_widget):
        super().__init__(parent_widget)
        self.market, self.parent_widget = market, parent_widget
        self._cancel = threading.Event()
        self._thread = None
        self.queue_start.connect(lambda slugs, age: self.start(slugs, age, confirm=False))

    @property
    def busy(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def cancel(self):
        self._cancel.set()

    def start(self, slugs, max_age, confirm=True) -> bool:
        """Starts the update. Asks for confirmation first when the batch is large (unless confirm=False: the automatic
        refresh of old data, which sends small batches)."""
        slugs = list(dict.fromkeys(slugs))
        if self.busy:
            return False
        if not slugs:
            self.finished.emit(t("job.nothing"))
            return False
        if confirm and len(slugs) > int(CFG["refresh_confirm_over"]):
            eta = int(len(slugs) * 2 * 0.35)           # 2 requests per item, ~3 per second
            ans = QMessageBox.question(
                self.parent_widget, t("job.confirm.title"),
                t("job.confirm.text", n=len(slugs), minutes=eta // 60 + 1, requests=len(slugs) * 2))
            if ans != QMessageBox.StandardButton.Yes:
                return False
        from app.trade import netguard
        if not netguard.claim("prices"):                # a Riven scan is talking to the site: wait for it
            from app.core import logbus
            if confirm:                                  # a click: starts by itself when the scan ends
                logbus.add("prices", "a Riven scan is running: the price update starts when it ends", "warn")
                self.finished.emit(t("job.queued"))
                netguard.when_free(lambda s=slugs, a=max_age: self.queue_start.emit(s, a))
            return False
        self._cancel.clear()
        from app.core import sound
        sound.play("prices")
        self.started.emit(len(slugs))
        market, cancel = self.market, self._cancel

        from app.core import logbus
        logbus.add("prices", f"updating {len(slugs)} items")

        def prog(d, n, e):
            self.progress.emit(d, n, e)
            logbus.progress("prices", d, n, f"{e} errors" if e else "")

        def run():
            try:
                done, errors, stopped = market.refresh_many(slugs, cancel, prog, max_age)
                if cancel.is_set():
                    msg = t("job.stopped", done=done, total=len(slugs))
                elif stopped:
                    msg = t("job.aborted", done=done, total=len(slugs))
                else:
                    msg = t("job.done", n=done)
                if errors:
                    msg += t("job.errors", n=errors)
            except Exception as e:
                msg = t("status.error", err=e)
                logbus.error("prices", f"{type(e).__name__}: {e}")
            logbus.progress("prices", 0, 0)
            from app.trade import netguard
            netguard.release("prices")
            logbus.add("prices", msg, "warn" if "error" in msg.lower() or "errori" in msg.lower() else "ok")
            self.finished.emit(msg)

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()
        return True
