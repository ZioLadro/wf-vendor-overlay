"""The two long jobs that talk to warframe.market, the price update (Refresher: hundreds of item requests) and the Riven
scan (auction searches, which the site wants slow), never run at the same time: together they would go past the site's
limits and get "too many requests". Each job claims its name here before it starts; the other one waits for its turn
(automatic runs simply try again later, a click is queued and starts when the other job ends)."""
import threading

_lock = threading.Lock()
_running = set()
_queued = []            # callbacks waiting for the market to be free (run on the window's thread by the caller)


def claim(name: str) -> bool:
    """True (and the job is marked running) when no OTHER market job runs."""
    with _lock:
        if any(n != name for n in _running):
            return False
        _running.add(name)
        return True


def release(name: str):
    with _lock:
        _running.discard(name)
        waiting = list(_queued)
        _queued.clear()
    for fn in waiting:
        try:
            fn()
        except Exception:
            pass


def busy_other(name: str) -> str:
    """The name of the other job running, or ""."""
    with _lock:
        return next((n for n in _running if n != name), "")


def when_free(fn):
    """Runs fn when the running job ends (fn must be safe to call from that job's thread: use a Qt signal or QTimer)."""
    with _lock:
        _queued.append(fn)
