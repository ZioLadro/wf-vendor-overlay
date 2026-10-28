"""AlecaFrame's lastData.dat, read ONCE per change and off the window's thread, for everybody who needs it.

Before, the Inventory, Profile, Builds and Weekly tabs and the Activities overlay each watched the file, read it,
decrypted it and parsed its ~1 MB of JSON on their own, on the window's thread: every time AlecaFrame rewrote it (each
mission) the program froze for a moment several times over. Now:

  - one watcher looks at the file's date and size every few seconds (no read while nothing changed);
  - after a change it waits until the file has stopped changing (AlecaFrame may still be writing it);
  - a background thread reads it, compares its fingerprint (identical content: nothing to do), decrypts it, parses the
    JSON once, and runs every consumer's own (slow) work on the parsed data in that same thread: matching the inventory
    to the market catalog, reading standing, loadouts…;
  - the results reach the window's thread through a Qt signal, where each consumer only applies them (fast).

Consumers register with get().register(name, work, apply): work(path, data) runs in the background thread and returns a
result; apply(result) runs on the window's thread. Anyone can also ask for the last parsed data: get().data(path)."""
import hashlib
import json
import os
import threading
import time

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

STABLE_S = 1.5          # the file must keep the same date and size this long before it is read
FIND_EVERY_S = 30.0     # how often the AlecaFrame folders are searched again for the newest lastData.dat


def decode(raw: bytes, path: str) -> dict:
    """The inventory dict of a lastData.dat (decrypted) or of a plain JSON file, parsed once (the wrapped
    {"InventoryJson": "…"} form is unwrapped without parsing anything twice). Raises ValueError."""
    from app.game import inventory as I
    if str(path).lower().endswith(".dat"):
        try:
            from cryptography.hazmat.primitives import padding
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        except ImportError:
            raise ValueError("the 'cryptography' package is needed: pip install cryptography")
        if not raw or len(raw) % 16:
            raise ValueError("not an AlecaFrame file (wrong size)")
        dec = Cipher(algorithms.AES(I.DAT_KEY), modes.CBC(I.DAT_IV)).decryptor()
        unpad = padding.PKCS7(128).unpadder()
        text = (unpad.update(dec.update(raw) + dec.finalize()) + unpad.finalize()).decode("utf-8")
    else:
        text = raw.decode("utf-8-sig")
    data = json.loads(text)
    for _ in range(2):
        inner = data.get("InventoryJson") if isinstance(data, dict) else None
        if isinstance(inner, str):
            data = json.loads(inner)
        elif isinstance(inner, dict):
            data = inner
        else:
            break
    if not isinstance(data, dict):
        raise ValueError("the file holds no inventory")
    return data


class GameFile(QObject):
    loaded = pyqtSignal(object)           # {"path","sig","data","results": {name: result}, "errors": {name: text}}

    def __init__(self):
        super().__init__()
        self._consumers = {}              # name -> (work, apply)
        self._lock = threading.Lock()
        self._busy = False
        self._last = {"path": "", "key": None, "sig": "", "data": None, "t": 0.0}
        self._seen = (None, 0.0)          # (stat key, since when)
        self._path, self._found_at = "", 0.0
        self.preferred = lambda: ""       # the path the Inventory tab imported (set by the window)
        self.loaded.connect(self._dispatch)
        self.timer = QTimer(self, timeout=self.poll)

    # ---------- consumers ----------
    def register(self, name, work, apply):
        self._consumers[name] = (work, apply)

    def start(self, every_s):
        if every_s > 0:
            self.timer.start(int(max(1, min(every_s, 5)) * 1000))   # stat only: cheap, so at least every 5 s
            QTimer.singleShot(1200, self.poll)

    def path(self) -> str:
        p = self.preferred() or ""
        if p and os.path.exists(p):
            return p
        now = time.monotonic()
        if not self._path or now - self._found_at > FIND_EVERY_S or not os.path.exists(self._path):
            from app.game import aleca
            self._path, self._found_at = aleca.find_data_file(), now
        return self._path

    def data(self, path=None):
        """The last parsed inventory dict (None until the first read). Never reads the file itself."""
        with self._lock:
            if path and self._last["path"] and os.path.normcase(path) != os.path.normcase(self._last["path"]):
                return None
            return self._last["data"]

    def key(self):
        return self._last["key"]

    # ---------- watching ----------
    def poll(self, force=False):
        """Looks at the file's date and size; starts a background read when it changed and has settled."""
        if self._busy:
            return
        path = self.path()
        if not path:
            return
        try:
            st = os.stat(path)
        except OSError:
            return
        key = (path, st.st_mtime_ns, st.st_size)
        if key == self._last["key"] and not force:
            return
        now = time.monotonic()
        if key != self._seen[0]:
            self._seen = (key, now)
            if self._last["key"] is not None and not force:
                return                    # just changed: wait until AlecaFrame has finished writing it
        elif now - self._seen[1] < STABLE_S and not force:
            return
        self._busy = True
        threading.Thread(target=self._work, args=(path, key, force), daemon=True, name="gamefile").start()

    def read_now(self):
        """Reads the file again at the next chance even if it did not change (the Reload buttons)."""
        self._busy = False
        self.poll(force=True)

    def _work(self, path, key, force):
        from app.core import logbus
        out = {"path": path, "key": key, "sig": "", "data": None, "results": {}, "errors": {}, "same": False}
        try:
            raw = None
            for _ in range(3):            # AlecaFrame may hold it for a moment
                try:
                    with open(path, "rb") as f:
                        raw = f.read()
                    break
                except OSError:
                    time.sleep(0.3)
            if raw is None:
                raise OSError("the file is busy")
            sig = hashlib.md5(raw).hexdigest()
            out["sig"] = sig
            if sig == self._last["sig"] and not force:
                out["same"], out["data"] = True, self._last["data"]
            else:
                t0 = time.perf_counter()
                data = decode(raw, path)
                out["data"] = data
                t1 = time.perf_counter()
                for name, (work, _apply) in list(self._consumers.items()):
                    try:
                        out["results"][name] = work(path, data)
                    except Exception as e:      # one consumer failing must not stop the others
                        out["errors"][name] = f"{type(e).__name__}: {e}"
                logbus.add("gamefile", f"{os.path.basename(path)} read: decrypted and parsed in "
                                       f"{(t1 - t0) * 1000:.0f} ms, processed in {(time.perf_counter() - t1) * 1000:.0f} ms "
                                       f"(in the background)", "ok")
        except Exception as e:
            out["errors"]["*"] = f"{type(e).__name__}: {e}"
        self.loaded.emit(out)

    def _dispatch(self, out):
        """On the window's thread: keeps the data and lets every consumer apply its result."""
        from app.core import logbus
        self._busy = False
        if "*" in out["errors"]:
            logbus.error("gamefile", f"cannot read {os.path.basename(out['path'])}: {out['errors']['*']}")
            with self._lock:
                self._last["key"] = out["key"]      # do not retry the same broken file every few seconds
            return
        with self._lock:
            self._last.update(path=out["path"], key=out["key"], sig=out["sig"], data=out["data"], t=time.time())
        if out["same"]:
            return
        for name, err in out["errors"].items():
            logbus.error(name, err)
        for name, (_work, apply) in list(self._consumers.items()):
            if name in out["results"]:
                try:
                    apply(out["results"][name])
                except Exception as e:
                    logbus.error(name, f"{type(e).__name__}: {e}")


_gf = None


def get() -> GameFile:
    global _gf
    if _gf is None:
        _gf = GameFile()
    return _gf
