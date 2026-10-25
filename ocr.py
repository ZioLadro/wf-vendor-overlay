"""Screen capture + OCR + item detection."""
import os
from dataclasses import dataclass

import mss
import numpy as np

from winrect import capture_region


@dataclass
class Line:
    text: str
    x: float
    y: float
    w: float
    h: float
    score: float = 1.0


def capture():
    """Screenshot of monitor 1 (BGR) + monitor info."""
    with mss.mss() as sct:
        mon = sct.monitors[1]
        shot = sct.grab(mon)
    return np.ascontiguousarray(np.array(shot)[:, :, :3]), mon


class Grabber:
    """Reusable capture for monitoring (always use it from the same thread).
    Returns a BGRA view without copies: always use [..., :3] for the colour channels."""

    def __init__(self, only_warframe=False):
        self._sct = None
        self.only_warframe = only_warframe
        self._pids = (os.getpid(),)

    def grab(self):
        """BGRA image of the game window (or of the monitor), None if the game is not the active window."""
        try:
            if self._sct is None:
                self._sct = mss.mss()
            reg = capture_region(self._sct.monitors[1], self.only_warframe, self._pids)
            if reg is None:
                return None
            shot = self._sct.grab(reg[0])
        except Exception:
            self._sct = None
            raise
        return np.asarray(shot)


def make_engine(threads: int = 0):
    """OCR engine with limited threads and without the orientation classifier (useless here)."""
    from rapidocr import RapidOCR
    n = threads or max(1, min(3, (os.cpu_count() or 4) // 4))
    return RapidOCR(params={
        "Global.use_cls": False,
        "EngineConfig.onnxruntime.intra_op_num_threads": n,
        "EngineConfig.onnxruntime.inter_op_num_threads": 1,
    })


def read_lines(img, engine) -> list:
    res = engine(img)
    out = []
    if res is None or res.boxes is None or res.txts is None:
        return out
    for box, text, score in zip(res.boxes, res.txts, res.scores):
        xs = [pt[0] for pt in box]
        ys = [pt[1] for pt in box]
        out.append(Line(text, float(min(xs)), float(min(ys)),
                        float(max(xs) - min(xs)), float(max(ys) - min(ys)), float(score)))
    return out


def candidates(lines):
    """Single lines + pairs of vertically adjacent lines (names split over two lines)."""
    cands = list(lines)
    for a in lines:
        for b in lines:
            if a is b:
                continue
            gap = b.y - (a.y + a.h)
            if 0 <= gap < a.h * 0.8 and abs(a.x - b.x) < a.h * 1.5:
                cands.append(Line(
                    a.text + " " + b.text,
                    min(a.x, b.x), a.y,
                    max(a.x + a.w, b.x + b.w) - min(a.x, b.x),
                    (b.y + b.h) - a.y,
                ))
    return cands


def _overlap(a, b) -> bool:
    return not (a.x + a.w <= b.x or b.x + b.w <= a.x or a.y + a.h <= b.y or b.y + b.h <= a.y)


def find_items(market, lines, threshold: int = 90):
    """Returns [(Line, Match)] with no overlapping boxes, preferring the best matches."""
    hits = []
    for c in candidates(lines):
        m = market.match(c.text, threshold)
        if m:
            hits.append((m.score, len(c.text), c, m))
    hits.sort(key=lambda h: (-h[0], -h[1]))
    kept = []
    for _, _, c, m in hits:
        if not any(_overlap(c, k[0]) for k in kept):
            kept.append((c, m))
    return kept


def gray_patch(img, box):
    """Greyscale crop of a box (x, y, w, h) in captured pixels."""
    x, y, w, h = [int(round(v)) for v in box]
    H, W = img.shape[:2]
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if x1 - x0 < 4 or y1 - y0 < 4:
        return None
    return img[y0:y1, x0:x1, :3].mean(axis=2).astype(np.int16)


def _ncc(a, b) -> float:
    """Normalised correlation between two crops (1 = same structure, ~0 = different content)."""
    a = a.astype(np.float32) - a.mean()
    b = b.astype(np.float32) - b.mean()
    den = float(np.sqrt((a * a).mean() * (b * b).mean()))
    return float((a * b).mean() / den) if den > 1e-6 else 0.0


def screen_changed(img, boxes, refs, min_corr=0.6, min_std=8.0, flat_std=3.0, min_boxes=0.34):
    """True if the content under at least 1/3 of the names has changed (scroll, vendor closed, other page).

    It compares the *structure* of the text (correlation), not the brightness: a glare or a highlighted
    row does not count, while text disappearing or another scene appearing does.
    """
    changed = total = 0
    for box, ref in zip(boxes, refs):
        if ref is None or float(ref.std()) < min_std:
            continue                         # reference without text: not informative
        total += 1
        cur = gray_patch(img, box)
        if cur is None or cur.shape != ref.shape or float(cur.std()) < flat_std:
            changed += 1                     # off screen, or the area became uniform
        elif _ncc(ref, cur) < min_corr:
            changed += 1
    return total > 0 and changed / total >= min_boxes
