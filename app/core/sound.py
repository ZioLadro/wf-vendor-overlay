"""A short sound when a scan starts (settings: sound_vendor, sound_riven, sound_prices; sound_file = your own .wav, empty =
the system's notification sound). Windows plays it with winsound (asynchronous, never blocks); elsewhere the window
system's beep. Any thread may call play()."""
import sys
import time

from app.core.config import CFG

_last = {}


def play(kind: str):
    """kind: vendor | riven | prices. At most one sound per kind every 3 seconds."""
    if not CFG.get(f"sound_{kind}", False):
        return
    now = time.monotonic()
    if now - _last.get(kind, 0) < 3:
        return
    _last[kind] = now
    f = str(CFG.get("sound_file") or "").strip()
    try:
        if sys.platform == "win32":
            import winsound
            if f:
                winsound.PlaySound(f, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
            else:
                winsound.PlaySound("SystemNotification", winsound.SND_ALIAS | winsound.SND_ASYNC)
            return
        from PyQt6.QtWidgets import QApplication
        QApplication.beep()
    except Exception:
        pass
