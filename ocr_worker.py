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
    from matcher import Matcher
    from winrect import capture_region
    from ocr import find_items, gray_patch, make_engine, read_lines

    engine = make_engine(threads)
    matcher = Matcher(pairs)
    threshold = cfg.get("threshold", 90)
    sct = None
    origin = [0, 0, 0]          # offset of the captured region in the monitor, monitor width
    last_fp = last_hits = last_patches = None
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
            reg = capture_region(mon, cfg.get("only_warframe", False))
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
                conn.send(("ok", [], 1, [], (0, 0)))
                continue
            w = origin[2] or bgr.shape[1]
            if dbg_img_active(cfg):
                origin[:] = [0, 0, bgr.shape[1]]
                w = bgr.shape[1]
            fp = bgr[::16, ::16].mean(axis=2)
            if (last_hits is not None and last_fp is not None and fp.shape == last_fp.shape
                    and (np.abs(fp - last_fp) > 20).mean() < 0.001):
                conn.send(("ok", last_hits, w, last_patches, tuple(origin[:2])))   # identical screen: reuse the result
                continue
            hits = [(c.x, c.y, c.w, c.h, m.slug, m.score)
                    for c, m in find_items(matcher, read_lines(bgr, engine), threshold)]
            # crops under the names, taken from THIS screenshot (no labels): used to detect
            # when the vendor is closed or the list changes
            patches = [gray_patch(bgr, h[:4]) for h in hits]
            last_fp, last_hits, last_patches = fp, hits, patches
            conn.send(("ok", hits, w, patches, tuple(origin[:2])))
        except Exception as e:
            last_fp = last_hits = last_patches = None
            conn.send(("err", f"{type(e).__name__}: {e}"))


class OcrClient:
    """Main-process side: starts the worker and requests scans."""

    def __init__(self, pairs, cfg):
        self._ctx = mp.get_context("spawn")
        self._pairs, self._cfg = list(pairs), dict(cfg)
        self._lock = threading.Lock()
        self._proc = self._conn = None
        self._ready = False
        self.origin = (0, 0)       # offset of the last captured region inside the monitor
        self._start()

    def _start(self):
        parent, child = self._ctx.Pipe()
        proc = self._ctx.Process(target=serve, args=(child, self._pairs, self._cfg), daemon=True)
        proc.start()
        child.close()
        self._proc, self._conn, self._ready = proc, parent, False

    def _restart(self):
        self.close()
        self._start()

    def scan(self, timeout: float = 120.0):
        """Returns ([(x, y, w, h, slug, score)], screen_width_in_pixels, reference_crops)."""
        with self._lock:
            if not self._proc.is_alive():
                self._start()
            try:
                if not self._ready:
                    if not self._conn.poll(timeout):
                        self._restart()
                        raise TimeoutError("OCR did not start")
                    self._conn.recv()
                    self._ready = True
                self._conn.send(("scan",))
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
            return msg[1], msg[2], msg[3]

    def close(self):
        try:
            self._conn.send(("quit",))
        except Exception:
            pass
        try:
            self._proc.join(1.0)
            if self._proc.is_alive():
                self._proc.terminate()
        except Exception:
            pass
