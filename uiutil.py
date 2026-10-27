"""Shared pieces of the price-list window: style, colours, sortable cells, tray icon."""
import re
import time
from urllib.parse import quote

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QBrush, QColor, QDesktopServices, QFont, QGuiApplication, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QMenu, QTableWidgetItem

from i18n import t
from standing import afford_text

PRICE_COLOR = QColor(120, 200, 255)
MAXRANK_COLOR = QColor(255, 205, 110)
DIM_COLOR = QColor(130, 130, 130)
STANDING_COLOR = QColor(190, 160, 255)

import theme

STYLE = theme.build_style("classic")        # kept for code that still imports it; the program applies the chosen theme
HINT_STYLE = "color: #7d869e; font-size: 11px;"      # fixed-colour versions (prefer role(widget, "hint"))
MUTED_STYLE = "color: #9aa4bd;"


def role(widget, name: str):
    """Marks a label as "muted" / "hint" / "small": the colour then comes from the current theme (and follows it
    when the theme changes), instead of being written into the label."""
    widget.setProperty("role", name)



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
        f"{e['v']}: {thousands(e['s'])}" + (t("tip.rank", n=e["r"]) if e.get("r") else "") for e in entries)
                    + "\n\n" + afford_text(entries))
    return cell


# ---------- links and right-click menu on item names ----------
def market_url(slug: str) -> str:
    return "https://warframe.market/items/" + quote(slug)


def wiki_url(name: str) -> str:
    """Wiki page of an item. Market names of sets end in " Set" (the wiki page is the item itself).
    Special:Search with "go" opens the page directly when the title exists, and a search otherwise."""
    title = re.sub(r"\s+Set$", "", name).strip()
    return "https://wiki.warframe.com/w/Special:Search?go=Go&search=" + quote(title)


def attach_item_menu(table, name_col: int):
    """Right-click on a row: open the item on warframe.market / on the wiki, or copy its name.
    The name cell of each row must carry the market slug in Qt.UserRole."""
    table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    def show(pos):
        row = table.rowAt(pos.y())
        cell = table.item(row, name_col) if row >= 0 else None
        slug = cell.data(Qt.ItemDataRole.UserRole) if cell else None
        if not slug:
            return
        name = cell.text()
        menu = QMenu(table)
        a_market = menu.addAction(t("menu.market"))
        a_wiki = menu.addAction(t("menu.wiki"))
        a_copy = menu.addAction(t("menu.copy"))
        chosen = menu.exec(table.viewport().mapToGlobal(pos))
        if chosen is a_market:
            QDesktopServices.openUrl(QUrl(market_url(slug)))
        elif chosen is a_wiki:
            QDesktopServices.openUrl(QUrl(wiki_url(name)))
        elif chosen is a_copy:
            QGuiApplication.clipboard().setText(name)

    table.customContextMenuRequested.connect(show)
