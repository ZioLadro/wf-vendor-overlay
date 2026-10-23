"""Shared pieces of the price-list window: style, colours, sortable cells, tray icon."""
import time

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QTableWidgetItem

from i18n import t

PRICE_COLOR = QColor(120, 200, 255)
MAXRANK_COLOR = QColor(255, 205, 110)
DIM_COLOR = QColor(130, 130, 130)
STANDING_COLOR = QColor(190, 160, 255)

STYLE = """
QWidget { background: #161a22; color: #e6e6e6; font-size: 13px; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { background: #1f2430; border: 1px solid #343b4d;
                                                 border-radius: 4px; padding: 4px 8px; }
QComboBox QAbstractItemView { background: #1f2430; selection-background-color: #2d3650; }
QTableWidget { background: #161a22; alternate-background-color: #1a1f29; border: 1px solid #343b4d;
               selection-background-color: #2d3650; selection-color: #ffffff; }
QHeaderView::section { background: #232938; color: #c9d1e3; border: none; border-right: 1px solid #343b4d;
                       padding: 5px 8px; font-weight: bold; }
QPushButton { background: #232938; border: 1px solid #343b4d; border-radius: 4px; padding: 5px 12px; }
QPushButton:hover { background: #2d3650; }
QPushButton:disabled { color: #6b738a; background: #1a1f29; }
QProgressBar { background: #1f2430; border: 1px solid #343b4d; border-radius: 4px; text-align: center; height: 14px; }
QProgressBar::chunk { background: #3b6ea8; }
QTabWidget::pane { border: 1px solid #343b4d; top: -1px; }
QTabBar::tab { background: #1a1f29; border: 1px solid #343b4d; padding: 7px 18px; margin-right: 2px; }
QTabBar::tab:selected { background: #232938; color: #ffffff; font-weight: bold; }
QGroupBox { border: 1px solid #343b4d; border-radius: 6px; margin-top: 14px; padding-top: 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 6px; color: #9aa4bd; }
QCheckBox { spacing: 8px; }
QScrollBar:vertical { background: #161a22; width: 12px; }
QScrollBar::handle:vertical { background: #343b4d; border-radius: 5px; min-height: 24px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
"""
HINT_STYLE = "color: #7d869e; font-size: 11px;"
MUTED_STYLE = "color: #9aa4bd;"


def make_icon() -> QIcon:
    """Icon (a coin with a platinum 'p') drawn on the fly: no file to bundle in the exe."""
    pm = QPixmap(64, 64)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(30, 36, 50))
    p.setPen(QColor(120, 200, 255))
    p.drawEllipse(3, 3, 58, 58)
    p.setPen(QColor(255, 255, 255))
    p.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
    p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, "p")
    p.end()
    return QIcon(pm)


def age_text(ts) -> str:
    if not ts:
        return t("age.never")
    s = max(0, time.time() - ts)
    if s < 60:
        return t("age.now")
    if s < 3600:
        return t("age.min", n=int(s // 60))
    if s < 86400:
        return t("age.hour", n=int(s // 3600))
    return t("age.day", n=int(s // 86400))


def thousands(n) -> str:
    return f"{int(n):,}".replace(",", ".") if t("lang.code") == "it" else f"{int(n):,}"


class Cell(QTableWidgetItem):
    """Cell with its own sort key (real numbers, missing values at one end)."""

    def __init__(self, text: str, key, color=None, center=True):
        super().__init__(text)
        self.key = key
        self.setFlags(self.flags() & ~Qt.ItemFlag.ItemIsEditable)
        if color is not None:
            self.setForeground(QBrush(color))
        if center:
            self.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

    def __lt__(self, other):
        if isinstance(other, Cell):
            return self.key < other.key
        return super().__lt__(other)


def num_key(v):
    """Numeric key: missing values come before everything (last when sorting descending)."""
    return (0, 0) if v is None else (1, v)


def kind_label(kind: str) -> str:
    return t("kind." + kind)


def standing_cell(entries):
    """Standing cost: one value, or 'min – max' if it varies between vendors; details in the tooltip."""
    if not entries:
        return Cell("", (0, 0))
    costs = [e["s"] for e in entries]
    lo, hi = min(costs), max(costs)
    cell = Cell(thousands(lo) if lo == hi else f"{thousands(lo)} – {thousands(hi)}", (1, lo), STANDING_COLOR)
    cell.setToolTip("\n".join(
        f"{e['v']}: {thousands(e['s'])}" + (t("tip.rank", n=e["r"]) if e.get("r") else "") for e in entries))
    return cell
