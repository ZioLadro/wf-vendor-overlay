"""Processo separato per cattura + OCR + riconoscimento nomi.

Il lavoro pesante gira qui, a priorita' bassa e con pochi thread, cosi' il processo principale
(che gestisce overlay, tastiera e rotellina) non viene mai rallentato e il gioco resta fluido.
Il processo principale usa OcrClient; non importa mai rapidocr/onnxruntime.
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


def serve(conn, pairs, cfg):
    """Ciclo del processo: riceve ("scan",) / ("catalog", pairs) / ("quit",)."""
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
    from ocr import find_items, gray_patch, make_engine, read_lines

    engine = make_engine(threads)
    matcher = Matcher(pairs)
    threshold = cfg.get("threshold", 90)
    sct = None
    last_fp = last_hits = last_patches = None
    conn.send(("ready",))

    def grab():
        nonlocal sct
        dbg = cfg.get("debug_image")           # solo per i test: immagine al posto dello schermo
        if dbg:
            from PIL import Image
            return np.array(Image.open(dbg).convert("RGB"))[:, :, ::-1].copy()
        import mss
        try:
            if sct is None:
                sct = mss.mss()
            shot = sct.grab(sct.monitors[1])
        except Exception:
            sct = None
            raise
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
            w = bgr.shape[1]
            fp = bgr[::16, ::16].mean(axis=2)
            if (last_hits is not None and last_fp is not None and fp.shape == last_fp.shape
                    and (np.abs(fp - last_fp) > 20).mean() < 0.001):
                conn.send(("ok", last_hits, w, last_patches))   # schermo identico: riusa il risultato
                continue
            hits = [(c.x, c.y, c.w, c.h, m.slug, m.score)
                    for c, m in find_items(matcher, read_lines(bgr, engine), threshold)]
            # ritagli sotto i nomi, presi da QUESTO screenshot (senza etichette): servono a capire
            # quando il vendor viene chiuso o la lista cambia
            patches = [gray_patch(bgr, h[:4]) for h in hits]
            last_fp, last_hits, last_patches = fp, hits, patches
            conn.send(("ok", hits, w, patches))
        except Exception as e:
            last_fp = last_hits = last_patches = None
            conn.send(("err", f"{type(e).__name__}: {e}"))


class OcrClient:
    """Lato processo principale: avvia il worker e chiede le scansioni."""

    def __init__(self, pairs, cfg):
        self._ctx = mp.get_context("spawn")
        self._pairs, self._cfg = list(pairs), dict(cfg)
        self._lock = threading.Lock()
        self._proc = self._conn = None
        self._ready = False
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
        """Ritorna ([(x, y, w, h, slug, score)], larghezza_schermo_in_pixel, ritagli_di_riferimento)."""
        with self._lock:
            if not self._proc.is_alive():
                self._start()
            try:
                if not self._ready:
                    if not self._conn.poll(timeout):
                        self._restart()
                        raise TimeoutError("OCR non avviato")
                    self._conn.recv()
                    self._ready = True
                self._conn.send(("scan",))
                if not self._conn.poll(timeout):
                    self._restart()
                    raise TimeoutError("OCR troppo lento")
                msg = self._conn.recv()
            except (EOFError, OSError, BrokenPipeError):
                self._restart()
                raise RuntimeError("Processo OCR terminato, riavvio")
            if msg[0] == "err":
                raise RuntimeError(msg[1])
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
