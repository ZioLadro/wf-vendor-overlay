"""In-memory log of what the program is doing in the background (downloads, updates, scans, errors), shown by the Console
tab. Any thread may call add(); the Console reads the lines in the GUI thread. The last MAX lines are kept."""
import threading
import time
from collections import deque

MAX = 3000
_lines = deque(maxlen=MAX)
_lock = threading.Lock()
_seq = 0
_progress = {}                      # source -> (done, total, text): ongoing jobs shown at the top of the Console


def add(source: str, message: str, level: str = "info"):
    """level: info, ok, warn, error."""
    global _seq
    with _lock:
        _seq += 1
        _lines.append((_seq, time.time(), source, level, str(message)))


def error(source: str, message: str):
    add(source, message, "error")


def progress(source: str, done: int, total: int, text: str = ""):
    """An ongoing job (total 0 = finished: removed from the list)."""
    with _lock:
        if total and done < total:
            _progress[source] = (done, total, text)
        else:
            _progress.pop(source, None)


def since(seq: int) -> list:
    """Lines newer than seq: [(seq, time, source, level, message)]."""
    with _lock:
        return [x for x in _lines if x[0] > seq]


def jobs() -> dict:
    with _lock:
        return dict(_progress)


def last_seq() -> int:
    return _seq
