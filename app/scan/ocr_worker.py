"""Separate process for capture + OCR + name matching.

The heavy work runs here, at low priority and with few threads, so the main process
(overlay, keyboard, mouse wheel) is never slowed down and the game stays smooth.
The main process uses OcrClient; it never imports rapidocr/onnxruntime.
"""
import multiprocessing as mp
import os
import sys
import threading


def _set_priority(level: str):
    try:
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes
            flag = {"idle": 0x40, "below_normal": 0x4000, "normal": 0x20}.get(level)
            if flag:
                k = ctypes.windll.kernel32
                k.GetCurrentProcess.restype = wintypes.HANDLE
                k.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
                k.SetPriorityClass(k.GetCurrentProcess(), flag)
        else:
            os.nice({"idle": 19, "below_normal": 10}.get(level, 0))
    except Exception:
        pass


def dbg_img_active(cfg):
    return bool(cfg.get("debug_image"))


def serve(conn, pairs, cfg):
    """Process loop: receives ("scan",) / ("catalog", pairs) / ("quit",)."""
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")
    _set_priority(cfg.get("priority", "below_normal"))
    threads = cfg.get("threads") or max(1, min(3, (os.cpu_count() or 4) // 4))
    os.environ["OMP_NUM_THREADS"] = str(threads)
    try:
        import cv2
        cv2.setNumThreads(threads)
    except Exception:
        pass

    import numpy as np
    from app.scan.matcher import Matcher
    from app.scan.winrect import capture_region
    from app.scan.ocr import find_items, gray_patch, make_engine, read_lines

    engine = make_engine(threads)
    matcher = Matcher(pairs)
    threshold = cfg.get("threshold", 90)
    sct = None
    origin = [0, 0, 0]          # offset of the captured region in the monitor, monitor width
    last_fp = last_hits = last_patches = None
    last_texts = []
    conn.send(("ready",))

    def grab():
        nonlocal sct
        dbg = cfg.get("debug_image")           # tests only: an image instead of the screen
        if dbg:
            from PIL import Image
            return np.array(Image.open(dbg).convert("RGB"))[:, :, ::-1].copy()
        import mss
        try:
            if sct is None:
                sct = mss.mss()
            mon = sct.monitors[1]
            reg = capture_region(mon, cfg.get("only_warframe", False), (cfg.get("main_pid", 0),))
            if reg is None:
                return None
            shot = sct.grab(reg[0])
        except Exception:
            sct = None
            raise
        origin[:] = [reg[1], reg[2], mon["width"]]
        return np.ascontiguousarray(np.asarray(shot)[:, :, :3])

    while True:
        try:
            msg = conn.recv()
        except (EOFError, OSError):
            return
        cmd = msg[0]
        exclude = msg[1] if cmd == "scan" and len(msg) > 1 else None
        if cmd == "quit":
            return
        if cmd == "catalog":
            matcher, last_hits, last_patches = Matcher(msg[1]), None, None
            continue
        if cmd != "scan":
            continue
        try:
            bgr = grab()
            if bgr is None:                       # the game is not the active window: nothing to read
                last_fp = last_hits = last_patches = None
                conn.send(("ok", [], 1, [], (0, 0), "nowindow", [], 0))
                continue
            w = origin[2] or bgr.shape[1]
            for (ex, ey, ew, eh) in exclude or ():      # areas of this program's own windows: not read
                x0, y0 = max(0, int(ex) - origin[0]), max(0, int(ey) - origin[1])
                bgr[y0:max(y0, int(ey + eh) - origin[1]), x0:max(x0, int(ex + ew) - origin[0])] = 0
            if dbg_img_active(cfg):
                origin[:] = [0, 0, bgr.shape[1]]
                w = bgr.shape[1]
            fp = bgr[::16, ::16].mean(axis=2)
            if (last_hits is not None and last_fp is not None and fp.shape == last_fp.shape
                    and (np.abs(fp - last_fp) > 20).mean() < 0.001):
                conn.send(("ok", last_hits, w, last_patches, tuple(origin[:2]), "", last_texts, bgr.shape[0]))   # identical screen: reuse the result
                continue
            small, k = bgr, 1.0
            tw = int(cfg.get("ocr_width") or 0)
            if 0 < tw < small.shape[1]:           # shrunk: much faster, same items read (a new, smaller image)
                import cv2
                k = tw / small.shape[1]
                small = cv2.resize(small, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
            if cfg.get("mask_panel"):             # the vendor's left info panel (below the title) is not read
                if small is bgr:                  # the full-size capture is still needed for the crops: copy it
                    small = bgr.copy()
                hh, ww = small.shape[:2]
                small[int(hh * 0.2):int(hh * 0.93), :int(ww * 0.31)] = 0
            lines = read_lines(small, engine)
            if k != 1.0:                          # back to the coordinates of the real image
                for ln in lines:
                    ln.x, ln.y, ln.w, ln.h = ln.x / k, ln.y / k, ln.w / k, ln.h / k
            hits = [(c.x, c.y, c.w, c.h, m.slug, m.score) for c, m in find_items(matcher, lines, threshold)]
            # all the text read (the vendor's name is somewhere in it): (text, x, y, w, h)
            texts = [(ln.text, ln.x, ln.y, ln.w, ln.h) for ln in lines if len(ln.text) >= 4 and ln.score >= 0.5][:200]
            # crops under the names, taken from THIS screenshot (no labels): used to detect
            # when the vendor is closed or the list changes
            patches = [gray_patch(bgr, h[:4]) for h in hits]
            last_fp, last_hits, last_patches, last_texts = fp, hits, patches, texts
            conn.send(("ok", hits, w, patches, tuple(origin[:2]), "", texts, bgr.shape[0]))
        except Exception as e:
            last_fp = last_hits = last_patches = None
            conn.send(("err", f"{type(e).__name__}: {e}"))


class OcrClient:
    """Main-process side: starts the worker and requests scans."""

    def __init__(self, pairs, cfg):
        self._pairs, self._cfg = list(pairs), dict(cfg)
        self._lock = threading.Lock()
        self._proc = self._conn = None
        self._ready = False
        self.skipped = ""
        self.img_h = 0             # height of the captured image (to tell what is at the top)
        self.texts = []            # all the text read on the last scan: (text, x, y, w, h)
        self.origin = (0, 0)       # offset of the last captured region inside the monitor
        self._start()

    def _start(self):
        """Starts the worker as a plain program (no multiprocessing handle duplication, which Windows can refuse with
        "WinError 5") and talks to it over a private localhost connection protected by a random key."""
        import subprocess
        from multiprocessing.connection import Listener
        key = os.urandom(16)
        lis = Listener(("127.0.0.1", 0), authkey=key)
        try:
            frozen = getattr(sys, "frozen", False)
            from app.core.paths import ROOT
            main = str(ROOT / "main.py")
            args = [sys.executable] + ([] if frozen else [main]) + ["--ocr-worker", str(lis.address[1]), key.hex()]
            env = {k: v for k, v in os.environ.items() if k != "PYINSTALLER_RESET_ENVIRONMENT"}
            flags = 0x08000000 if sys.platform == "win32" else 0          # CREATE_NO_WINDOW
            proc = subprocess.Popen(args, env=env, close_fds=True, creationflags=flags)
            lis._listener._socket.settimeout(60)
            conn = lis.accept()
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
            raise
        finally:
            lis.close()
        conn.send(("init", self._pairs, self._cfg))
        self._proc, self._conn, self._ready = proc, conn, False

    def _restart(self):
        self.close()
        self._start()

    def scan(self, timeout: float = 120.0, exclude=None):
        """Returns ([(x, y, w, h, slug, score)], screen_width_in_pixels, reference_crops)."""
        with self._lock:
            if self._proc.poll() is not None:
                self._start()
            try:
                if not self._ready:
                    if not self._conn.poll(timeout):
                        self._restart()
                        raise TimeoutError("OCR did not start")
                    self._conn.recv()
                    self._ready = True
                self._conn.send(("scan", list(exclude or ())))
                if not self._conn.poll(timeout):
                    self._restart()
                    raise TimeoutError("OCR too slow")
                msg = self._conn.recv()
            except (EOFError, OSError, BrokenPipeError):
                self._restart()
                raise RuntimeError("OCR process died, restarting")
            if msg[0] == "err":
                raise RuntimeError(msg[1])
            self.origin = tuple(msg[4]) if len(msg) > 4 else (0, 0)
            self.skipped = msg[5] if len(msg) > 5 else ""
            self.texts = msg[6] if len(msg) > 6 else []
            self.img_h = msg[7] if len(msg) > 7 else 0
            return msg[1], msg[2], msg[3]

    def close(self):
        try:
            self._conn.send(("quit",))
        except Exception:
            pass
        try:
            self._proc.wait(1.0)
        except Exception:
            try:
                self._proc.terminate()
            except Exception:
                pass


def worker_main(port: int, key_hex: str):
    """Entry point of the worker program (started by OcrClient with --ocr-worker PORT KEY)."""
    from multiprocessing.connection import Client
    conn = Client(("127.0.0.1", port), authkey=bytes.fromhex(key_hex))
    msg = conn.recv()
    if msg[0] != "init":
        return
    serve(conn, msg[1], msg[2])
