"""Transparent, always-on-top, click-through overlay (PyQt6).

For every item: the price to the right of the name; the volume (red = low, green = high)
below it, centred under the name.
"""
import math

from PyQt6.QtCore import Qt, QRectF, QTimer
from PyQt6.QtGui import QColor, QFont, QGuiApplication, QPainter
from PyQt6.QtWidgets import QWidget

from app.core.config import CFG
from app.core.i18n import t


def volume_color(v: float) -> QColor:
    """Red up to volume_low, green from volume_high up, logarithmic blend in between."""
    lo = max(1.0, float(CFG["volume_low"]))
    hi = max(lo + 1.0, float(CFG["volume_high"]))
    if v <= lo:
        t = 0.0
    elif v >= hi:
        t = 1.0
    else:
        t = math.log(v / lo) / math.log(hi / lo)
    return QColor.fromHsv(int(120 * t), 235, 255)     # 0 = red, 60 = yellow, 120 = green


class Overlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setGeometry(QGuiApplication.primaryScreen().geometry())
        self.items = []
        self.status = ""
        self._timer = QTimer(self, singleShot=True, timeout=self._clear_status)

    def set_items(self, items):
        self.items = items
        self.update()

    def show_status(self, text, ms=3000):
        self.status = text
        self._timer.start(ms)
        self.update()

    def _clear_status(self):
        self.status = ""
        self.update()

    def _pill(self, p, rect, text, color):
        p.setBrush(QColor(20, 20, 20, int(255 * max(0, min(100, int(CFG.get("ov_bg_opacity", 88)))) / 100)))
        p.setPen(color)
        p.drawRoundedRect(rect, 6, 6)
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        price_font = QFont("Segoe UI", int(CFG.get("ov_price_font", 11)), QFont.Weight.Bold)
        vol_font = QFont("Segoe UI", int(CFG.get("ov_vol_font", 9)), QFont.Weight.Bold)
        price_color, star = QColor(CFG.get("ov_price_color") or "#78c8ff"), QColor(CFG.get("ov_star_color") or "#ffd228")

        rec_font = QFont("Segoe UI", 7, QFont.Weight.Bold)
        rec_text = "★ " + t("overlay.recommended") + " ★"
        best_text = "★ " + t("overlay.best") + " ★"
        for it in self.items:
            if it.get("rec"):           # small yellow stars above the name (does not cover it)
                p.setFont(rec_font)
                rec_text_it = best_text if it["rec"] == 1 else rec_text
                fm = p.fontMetrics()
                w, h = fm.horizontalAdvance(rec_text_it) + 8, fm.height() + 1
                x = max(2, min(it["x"], self.width() - w - 2))
                y = max(2, it["y"] - h - 1)
                p.setBrush(QColor(60, 45, 0, 215) if it["rec"] == 1 else QColor(20, 20, 20, 190))
                p.setPen(star.lighter(115) if it["rec"] == 1 else star)
                p.drawRoundedRect(QRectF(x, y, w, h), 4, 4)
                p.drawText(QRectF(x, y, w, h), Qt.AlignmentFlag.AlignCenter, rec_text_it)
            # price: to the right of the name
            p.setFont(price_font)
            fm = p.fontMetrics()
            text = it["label"]
            w, h = fm.horizontalAdvance(text) + 14, fm.height() + 6
            x = min(it["x"] + it["w"] + 6, self.width() - w - 2)
            y = it["y"] + (it["h"] - h) / 2
            ok = it.get("price") is not None or it.get("pmax") is not None
            self._pill(p, QRectF(x, y, w, h), text,
                       price_color if ok else QColor(150, 150, 150))

            # volume: below the name, centred, coloured by value
            v = it.get("vol")
            if CFG["show_volume"] and v is not None:
                p.setFont(vol_font)
                fm = p.fontMetrics()
                vtext = f"vol {v}"
                w, h = fm.horizontalAdvance(vtext) + 12, fm.height() + 4
                x = it["x"] + it["w"] / 2 - w / 2
                x = max(2, min(x, self.width() - w - 2))
                y = min(it["y"] + it["h"] + CFG["volume_offset_y"], self.height() - h - 2)
                self._pill(p, QRectF(x, y, w, h), vtext, volume_color(v))

        if self.status:
            p.setFont(price_font)
            fm = p.fontMetrics()
            p.setPen(QColor(255, 255, 255))
            p.setBrush(QColor(0, 0, 0, 160))
            w = fm.horizontalAdvance(self.status) + 20
            p.drawRoundedRect(QRectF(10, 10, w, fm.height() + 10), 6, 6)
            p.drawText(QRectF(10, 10, w, fm.height() + 10), Qt.AlignmentFlag.AlignCenter, self.status)
