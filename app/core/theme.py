"""Colour themes (inspired by Warframe's factions) and the font, applied to the whole program at once.

A theme is a small palette; build_style() turns it into the Qt style sheet. apply() sets it on the application, so
every window and dialog changes immediately (no restart). All themes are dark: the semantic colours used in the
tables (green = good, amber = warning, red = bad) are tuned for dark backgrounds.
"""
import os

from app.core.config import CFG

DEFAULT_FONT = "Noto Sans"              # bundled (assets/fonts): the font of the game's own interface text
HEADING_FONT = "Rajdhani"               # bundled: titles, tabs and headers (the game's wide, technical headings)
FONT_FILES = ("NotoSans-Variable.ttf", "Rajdhani-Medium.ttf", "Rajdhani-SemiBold.ttf", "Rajdhani-Bold.ttf")
_fonts = {"loaded": None}


def load_fonts() -> set:
    """Registers the bundled fonts once; returns the families now available."""
    if _fonts["loaded"] is None:
        try:
            from PyQt6.QtGui import QGuiApplication
            if QGuiApplication.instance() is None:
                return set()                   # no application yet (a module built a style at import): Qt would crash
        except Exception:
            return set()
        fams = set()
        try:
            from PyQt6.QtGui import QFontDatabase
            from app.core.paths import ASSETS
            for name in FONT_FILES:
                fid = QFontDatabase.addApplicationFont(str(ASSETS / "fonts" / name))
                if fid >= 0:
                    fams.update(QFontDatabase.applicationFontFamilies(fid))
        except Exception:
            pass
        _fonts["loaded"] = fams
    return _fonts["loaded"]


def body_family() -> str:
    fam = str(CFG.get("ui_font") or DEFAULT_FONT)
    return fam


def heading_family() -> str:
    load_fonts()
    return HEADING_FONT if HEADING_FONT in (_fonts["loaded"] or set()) else body_family()


def current_id() -> str:
    return str(CFG.get("theme") or "classic")


def _mix(a: str, b: str, t: float) -> str:
    """The colour t of the way from a to b (#rrggbb)."""
    a, b = a.lstrip("#"), b.lstrip("#")
    ca = [int(a[i:i + 2], 16) for i in (0, 2, 4)]
    cb = [int(b[i:i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ca, cb))


def make_palette(kind, bg, surface, accent, accent2, text, maxrank="#ffcd6e", standing="#bea0ff") -> dict:
    """A full palette from five colours: the window (bg), cards and inputs (surface), the accent (prices, the selected
    tab, progress), a second accent (highlights, the build screen's gold) and the text colour."""
    return dict(kind=kind, bg=bg, panel=surface, alt=_mix(bg, surface, 0.55), head=_mix(surface, accent, 0.07),
                border=_mix(surface, text, 0.13), text=text, muted=_mix(text, bg, 0.30), hint=_mix(text, bg, 0.47),
                accent=accent, accent2=accent2, select=_mix(surface, accent, 0.30), maxrank=maxrank, standing=standing,
                glow=_mix(bg, accent, 0.18))


# id -> (kind, bg, surface, accent, second accent, text): inspired by Warframe's factions, syndicates and places.
# kind: ally / syndicate / place / enemy (only used to label the choice).
SPECS = {
    "classic": ("", "#12151c", "#1b202b", "#6ec3ff", "#ffcd6e", "#e8ecf3"),
    "tenno": ("ally", "#0f141c", "#172130", "#5ec8f2", "#e8c25a", "#e8eef7"),
    "lotus": ("ally", "#0d1615", "#15231f", "#6fe3c8", "#f2ead2", "#eaf5f2"),
    "void": ("ally", "#0a0a14", "#14142a", "#8c7bff", "#e8e4ff", "#ecebff"),
    "drifter": ("ally", "#14150f", "#212318", "#b9c46a", "#e88a3c", "#eef0e4"),
    "steel_meridian": ("syndicate", "#16171a", "#212328", "#e0cf8a", "#d0503c", "#ececec"),
    "arbiters": ("syndicate", "#14161a", "#21252b", "#e8eef4", "#8fb4d8", "#f2f4f7"),
    "suda": ("syndicate", "#0c1420", "#132236", "#4aa8ff", "#9ef0ff", "#e8f2fc"),
    "perrin": ("syndicate", "#0f1819", "#172628", "#46d6c8", "#e8c25a", "#e6f4f2"),
    "red_veil": ("syndicate", "#190f12", "#29181c", "#ff6b6b", "#c46bff", "#f5e8ea"),
    "new_loka": ("syndicate", "#101912", "#19271c", "#7ee08f", "#f2e3a0", "#ebf4ec"),
    "ostron": ("place", "#12181a", "#1b2629", "#4fd1b0", "#f0a656", "#e9f1ec"),
    "solaris": ("place", "#14161b", "#20242c", "#f0a020", "#5ac8e8", "#eceff3"),
    "entrati": ("place", "#15111d", "#211a2e", "#c08af0", "#f0c978", "#efe8f6"),
    "holdfasts": ("place", "#11141f", "#1a1f31", "#e6d6a8", "#7ad6e8", "#eef0f6"),
    "duviri": ("place", "#16110f", "#241b17", "#e7b24c", "#e0577f", "#f6ece4"),
    "hollvania": ("place", "#140e1b", "#21172d", "#ff4fa3", "#43e8ff", "#f3eaf8"),
    "grineer": ("enemy", "#1a160f", "#292217", "#e8892c", "#a9c24f", "#eee4d3"),
    "kuva": ("enemy", "#170b0d", "#261316", "#ff3d4d", "#ffb070", "#f6e6e6"),
    "corpus": ("enemy", "#0c1621", "#132636", "#42c6ff", "#ffd27a", "#e6f3fc"),
    "infested": ("enemy", "#10160e", "#192416", "#a6e35a", "#d58bf0", "#e9f2e3"),
    "orokin": ("enemy", "#14120b", "#201c11", "#e8bd4a", "#f4ecd4", "#f4ecd4"),
    "sentient": ("enemy", "#0b0e1e", "#141a35", "#8393ff", "#ff8ad8", "#e7e9ff"),
    "narmer": ("enemy", "#191012", "#28191a", "#ef6a4c", "#e6c08a", "#f3e6e1"),
    "murmur": ("enemy", "#0f0f13", "#1a1a22", "#b8b8dc", "#7a63ff", "#ececf4"),
    "scaldra": ("enemy", "#16100b", "#251b13", "#ff7a1a", "#c0c8d0", "#f2ebe4"),
    "stalker": ("enemy", "#0b0a0a", "#181313", "#e02434", "#b8b8b8", "#efe6e6"),
}
PRESETS = {k: make_palette(*v) for k, v in SPECS.items()}
ORDER = list(SPECS)


def palette(theme_id: str) -> dict:
    return PRESETS.get(theme_id) or PRESETS["classic"]


def arrow_mark(color: str, up=False) -> str:
    """A small chevron (PNG, once per colour) for the combo boxes' and spin boxes' arrows; "" when it cannot be drawn."""
    try:
        from PyQt6.QtGui import QGuiApplication
        if QGuiApplication.instance() is None:
            return ""
        from PyQt6.QtCore import QPointF, Qt
        from PyQt6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen
        from app.core.config import APP_DIR
        out = APP_DIR / "backdrop" / f"arrow{'up' if up else ''}_{color.lstrip('#')}.png"
        if not out.exists():
            out.parent.mkdir(parents=True, exist_ok=True)
            img = QImage(24, 24, QImage.Format.Format_ARGB32)
            img.fill(Qt.GlobalColor.transparent)
            g = QPainter(img)
            g.setRenderHint(QPainter.RenderHint.Antialiasing)
            pen = QPen(QColor(color), 2.6)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            g.setPen(pen)
            y0, y1 = (15, 9) if up else (9, 15)
            path = QPainterPath(QPointF(6, y0))
            path.lineTo(QPointF(12, y1))
            path.lineTo(QPointF(18, y0))
            g.drawPath(path)
            g.end()
            img.save(str(out), "PNG")
        return out.as_posix()
    except Exception:
        return ""


def check_mark(color: str) -> str:
    """A small tick (PNG, drawn once per colour) for the ticked boxes; "" when it cannot be drawn."""
    try:
        from PyQt6.QtGui import QGuiApplication
        if QGuiApplication.instance() is None:
            return ""
        from PyQt6.QtCore import QPointF, Qt
        from PyQt6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen
        from app.core.config import APP_DIR
        out = APP_DIR / "backdrop" / f"check_{color.lstrip('#')}.png"
        if not out.exists():
            out.parent.mkdir(parents=True, exist_ok=True)
            img = QImage(32, 32, QImage.Format.Format_ARGB32)
            img.fill(Qt.GlobalColor.transparent)
            g = QPainter(img)
            g.setRenderHint(QPainter.RenderHint.Antialiasing)
            pen = QPen(QColor(color), 4.2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            g.setPen(pen)
            path = QPainterPath(QPointF(8, 17))
            path.lineTo(QPointF(14, 23))
            path.lineTo(QPointF(25, 10))
            g.drawPath(path)
            g.end()
            img.save(str(out), "PNG")
        return out.as_posix()
    except Exception:
        return ""


def build_style(theme_id="classic", font=None, size=13) -> str:
    """The program's look: dark cards with rounded corners on the theme's background, a sidebar of sections (see
    menu.NavTabs), flat tabs underlined in the accent, the game's fonts (Noto Sans for text, Rajdhani for titles)."""
    load_fonts()
    p = palette(theme_id)
    fam = (font or DEFAULT_FONT).replace('"', "")
    head = heading_family().replace('"', "")
    size = max(9, min(24, int(size)))
    hs = size + 2
    tick = check_mark(p["bg"])
    arrow, arrow_up = arrow_mark(p["text"]), arrow_mark(p["text"], up=True)
    tick_rule = f'image: url("{tick}");' if tick else ""
    return f"""
QWidget {{ background: {p['bg']}; color: {p['text']}; font-family: "{fam}"; font-size: {size}px; }}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTextEdit, QFontComboBox {{
    background: {p['panel']}; border: 1px solid {p['border']}; border-radius: 7px; padding: 5px 9px;
    selection-background-color: {p['select']}; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QPlainTextEdit:focus {{ border: 1px solid {p['accent']}; }}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {{ border: 1px solid {_mix(p['border'], p['accent'], 0.5)}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
{f"QComboBox::down-arrow {{ image: url({arrow}); width: 12px; height: 12px; }}" if arrow else ""}
{f"QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{ image: url({arrow}); width: 9px; height: 9px; }}" if arrow else ""}
{f"QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{ image: url({arrow_up}); width: 9px; height: 9px; }}" if arrow_up else ""}
QComboBox QAbstractItemView {{ background: {p['panel']}; border: 1px solid {p['border']}; border-radius: 6px;
    selection-background-color: {p['select']}; outline: 0; padding: 4px; }}
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ width: 16px; border: none; }}
QListWidget, QTreeWidget {{ background: {p['panel']}; border: 1px solid {p['border']}; border-radius: 8px; outline: 0; }}
QListWidget::item, QTreeWidget::item {{ padding: 4px 6px; border-radius: 5px; }}
QListWidget::item:hover, QTreeWidget::item:hover {{ background: {p['alt']}; }}
QListWidget::item:selected, QTreeWidget::item:selected {{ background: {p['select']}; color: #ffffff; }}
QTableWidget, QTableView {{ background: {p['panel']}; alternate-background-color: {p['alt']}; border: 1px solid {p['border']};
    border-radius: 8px; gridline-color: {p['border']}; selection-background-color: {p['select']}; selection-color: #ffffff; outline: 0; }}
QTableWidget::item {{ padding: 2px 4px; }}
QHeaderView {{ background: transparent; }}
QHeaderView::section {{ background: {p['head']}; color: {p['muted']}; border: none; border-bottom: 1px solid {p['border']};
    padding: 6px 8px; font-family: "{head}"; font-size: {hs}px; font-weight: 600; }}
QTableCornerButton::section {{ background: {p['head']}; border: none; }}
QPushButton, QToolButton {{ background: {p['head']}; border: 1px solid {p['border']}; border-radius: 7px; padding: 6px 14px;
    font-family: "{head}"; font-size: {hs}px; font-weight: 600; }}
QPushButton:hover, QToolButton:hover {{ background: {p['select']}; border: 1px solid {p['accent']}; }}
QPushButton:pressed, QToolButton:pressed {{ background: {_mix(p['select'], p['accent'], 0.25)}; }}
QPushButton:checked {{ background: {p['select']}; border: 1px solid {p['accent']}; color: #ffffff; }}
QPushButton:disabled, QToolButton:disabled {{ color: {p['hint']}; background: {p['alt']}; border: 1px solid {p['alt']}; }}
QPushButton[role="primary"] {{ background: {p['accent']}; color: {p['bg']}; border: 1px solid {p['accent']}; }}
QPushButton[role="primary"]:hover {{ background: {_mix(p['accent'], '#ffffff', 0.2)}; }}
QProgressBar {{ background: {p['panel']}; border: 1px solid {p['border']}; border-radius: 6px; text-align: center; height: 12px; }}
QProgressBar::chunk {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {p['accent']}, stop:1 {p['accent2']}); border-radius: 5px; }}
QTabWidget::pane {{ border: 1px solid {p['border']}; border-radius: 10px; top: -1px; background: {p['bg']}; }}
QTabBar {{ background: transparent; }}
QTabBar::tab {{ background: transparent; color: {p['muted']}; border: none; border-bottom: 2px solid transparent;
    padding: 7px 16px; margin-right: 4px; font-family: "{head}"; font-size: {hs}px; font-weight: 600; }}
QTabBar::tab:hover {{ color: {p['text']}; border-bottom: 2px solid {p['border']}; }}
QTabBar::tab:selected {{ color: #ffffff; border-bottom: 2px solid {p['accent']}; }}
QGroupBox {{ background: {p['panel']}; border: 1px solid {p['border']}; border-radius: 10px; margin-top: 20px; padding: 12px 8px 8px 8px;
    font-family: "{head}"; font-size: {hs + 2}px; font-weight: 700; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 6px; color: {p['accent']}; font-family: "{head}";
    font-size: {hs + 1}px; font-weight: 700; }}
QCheckBox, QRadioButton {{ spacing: 8px; background: transparent; }}
QCheckBox::indicator, QTreeWidget::indicator, QTableWidget::indicator {{ width: 15px; height: 15px; border-radius: 4px;
    border: 1px solid {_mix(p['border'], p['text'], 0.25)}; background: {p['bg']}; }}
QCheckBox::indicator:hover {{ border: 1px solid {p['accent']}; }}
QCheckBox::indicator:checked, QTreeWidget::indicator:checked, QTableWidget::indicator:checked {{
    background: {p['accent']}; border: 1px solid {p['accent']}; {tick_rule} }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{ background: {p['border']}; border-radius: 4px; min-height: 28px; min-width: 28px; }}
QScrollBar::handle:hover {{ background: {p['accent']}; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ height: 0; width: 0; background: none; }}
QSplitter::handle {{ background: transparent; }}
QSplitter::handle:hover {{ background: {p['border']}; }}
QMenu {{ background: {p['panel']}; border: 1px solid {p['border']}; border-radius: 8px; padding: 5px; }}
QMenu::item {{ padding: 6px 22px 6px 14px; border-radius: 5px; }}
QMenu::item:selected {{ background: {p['select']}; }}
QMenu::separator {{ height: 1px; background: {p['border']}; margin: 4px 8px; }}
QToolTip {{ background: {p['panel']}; color: {p['text']}; border: 1px solid {p['accent']}; border-radius: 6px; padding: 6px; }}
QLabel {{ background: transparent; }}
QLabel[role="muted"] {{ color: {p['muted']}; }}
QLabel[role="hint"] {{ color: {p['hint']}; font-size: {max(9, size - 2)}px; }}
QLabel[role="small"] {{ color: {p['muted']}; font-size: {max(8, size - 3)}px; }}
QLabel[role="heading"] {{ font-family: "{head}"; font-size: {size + 6}px; font-weight: 700; color: {p['text']}; }}
QLabel[role="section"] {{ font-family: "{head}"; font-size: {hs + 1}px; font-weight: 700; color: {p['accent']}; }}
QFrame#playerbar, QFrame#worldstrip {{ background: {p['panel']}; border: 1px solid {p['border']}; border-radius: 10px; }}
QListWidget#nav {{ background: {_mix(p['bg'], p['panel'], 0.6)}; border: 1px solid {p['border']}; border-radius: 12px;
    padding: 8px 6px; font-family: "{head}"; font-size: {size + 3}px; font-weight: 600; }}
QListWidget#nav::item {{ padding: 9px 12px; margin: 2px 0; border-radius: 8px; color: {p['muted']}; border-left: 3px solid transparent; }}
QListWidget#nav::item:hover {{ background: {p['alt']}; color: {p['text']}; }}
QListWidget#nav::item:selected {{ background: {p['select']}; color: #ffffff; border-left: 3px solid {p['accent']}; }}
"""


BACKDROP_TILE = 560


# background patterns (original drawings in the spirit of each faction's look) and the one each theme uses by default
BACKDROPS = ["lattice", "curves", "plates", "circuit", "cells", "waves", "rings"]
THEME_BACKDROP = {"classic": "lattice", "tenno": "curves", "lotus": "curves", "void": "rings", "drifter": "plates",
                  "steel_meridian": "plates", "arbiters": "lattice", "suda": "circuit", "perrin": "circuit",
                  "red_veil": "curves", "new_loka": "cells", "ostron": "waves", "solaris": "plates", "entrati": "rings",
                  "holdfasts": "rings", "duviri": "waves", "hollvania": "circuit", "grineer": "plates", "kuva": "curves",
                  "corpus": "circuit", "infested": "cells", "orokin": "lattice", "sentient": "waves", "narmer": "rings",
                  "murmur": "rings", "scaldra": "plates", "stalker": "curves"}


def backdrop_for(theme_id: str) -> str:
    choice = str(CFG.get("backdrop_style") or "auto")
    return choice if choice in BACKDROPS else THEME_BACKDROP.get(theme_id, "lattice")


def make_backdrop(p: dict, strength: int, style: str = "lattice") -> str:
    """Draws the window's background tile (a seamless, faint pattern in the theme's colours, so text stays easy to read).
    Returns the PNG path (made once per theme colours, pattern and strength, then reused)."""
    import math
    import random
    from PyQt6.QtCore import QPointF, QRectF, Qt
    from PyQt6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen
    from app.core.config import APP_DIR
    strength = max(0, min(100, int(strength)))
    style = style if style in BACKDROPS else "lattice"
    out = APP_DIR / "backdrop" / f"{style}_{p['bg'][1:]}_{p['accent'][1:]}_{p['border'][1:]}_{strength}.png"
    if out.exists():
        return out.as_posix()
    out.parent.mkdir(parents=True, exist_ok=True)
    n = BACKDROP_TILE
    img = QImage(n, n, QImage.Format.Format_RGB32)
    img.fill(QColor(p["bg"]))
    k = strength / 100.0
    rnd = random.Random(style)                       # same drawing every time

    def col(c, a):
        q = QColor(c)
        q.setAlpha(int(a * k))
        return q
    g = QPainter(img)
    g.setRenderHint(QPainter.RenderHint.Antialiasing)

    def tiled(draw, x, y, r):
        """Draws a shape near (x, y) of size r, repeated across the tile's edges so the tile joins seamlessly."""
        for dx in (-n, 0, n):
            for dy in (-n, 0, n):
                if -r <= x + dx <= n + r and -r <= y + dy <= n + r:
                    draw(x + dx, y + dy)

    if style == "lattice":                           # Orokin: gilded lattice, diamonds, rings
        g.setPen(QPen(col(p["border"], 120), 1))
        step = n // 4
        for i in range(-4, 9):
            g.drawLine(QPointF(i * step, 0), QPointF(i * step + n, n))
            g.drawLine(QPointF(i * step, n), QPointF(i * step + n, 0))
        g.setPen(Qt.PenStyle.NoPen)
        g.setBrush(col(p["accent"], 70))
        for x in range(0, n + 1, step):
            for y in range(0, n + 1, step):
                cx, d = x + (step / 2 if (y // step) % 2 else 0), 3.5
                g.drawPolygon([QPointF(cx, y - d), QPointF(cx + d, y), QPointF(cx, y + d), QPointF(cx - d, y)])
        g.setBrush(Qt.BrushStyle.NoBrush)
        for r, a, w in ((n * 0.42, 80, 1.6), (n * 0.36, 55, 1.0), (n * 0.18, 60, 1.2)):
            g.setPen(QPen(col(p["accent"], a), w))
            for cx, cy in ((0, 0), (n, 0), (0, n), (n, n)):
                g.drawEllipse(QPointF(cx, cy), r, r)
        g.setPen(QPen(col(p["accent"], 70), 1.2))
        g.drawEllipse(QPointF(n / 2, n / 2), n * 0.11, n * 0.11)
    elif style == "curves":                          # Tenno: long flowing curls
        for i in range(9):
            y0 = i * n / 9
            path = QPainterPath(QPointF(-20, y0))
            for j in range(4):
                x1 = j * n / 4
                path.cubicTo(QPointF(x1 + n / 12, y0 - 40), QPointF(x1 + n / 6, y0 + 40), QPointF(x1 + n / 4, y0))
            g.setPen(QPen(col(p["accent"] if i % 3 == 0 else p["border"], 85 if i % 3 == 0 else 120), 1.3 if i % 3 == 0 else 1))
            g.drawPath(path)
        for _ in range(7):
            x, y, r = rnd.uniform(0, n), rnd.uniform(0, n), rnd.uniform(14, 34)
            g.setPen(QPen(col(p["accent"], 75), 1.2))
            tiled(lambda a, b, r=r: g.drawArc(QRectF(a - r, b - r, 2 * r, 2 * r), 20 * 16, 250 * 16), x, y, r)
    elif style == "plates":                          # Grineer / Steel Meridian: riveted armour plates
        step = n // 5
        g.setPen(QPen(col(p["border"], 140), 1.4))
        for i in range(6):
            for j in range(6):
                off = step / 2 if j % 2 else 0
                g.drawRect(QRectF(i * step + off - step, j * step, step, step))
        g.setPen(Qt.PenStyle.NoPen)
        g.setBrush(col(p["accent"], 80))
        for i in range(6):
            for j in range(6):
                off = step / 2 if j % 2 else 0
                for cx, cy in ((8, 8), (step - 8, 8), (8, step - 8), (step - 8, step - 8)):
                    g.drawEllipse(QPointF(i * step + off - step + cx, j * step + cy), 2.2, 2.2)
    elif style == "circuit":                         # Corpus: circuit traces with nodes
        grid = n // 14
        for _ in range(26):
            x, y = rnd.randrange(14) * grid, rnd.randrange(14) * grid
            pts = [QPointF(x, y)]
            for _s in range(rnd.randint(2, 5)):
                if rnd.random() < 0.5:
                    x += rnd.choice((-1, 1)) * rnd.randint(1, 4) * grid
                else:
                    y += rnd.choice((-1, 1)) * rnd.randint(1, 4) * grid
                pts.append(QPointF(x, y))
            for dx in (-n, 0, n):
                for dy in (-n, 0, n):
                    g.setPen(QPen(col(p["border"], 150), 1.2))
                    for a, b in zip(pts, pts[1:]):
                        g.drawLine(a + QPointF(dx, dy), b + QPointF(dx, dy))
                    g.setPen(QPen(col(p["accent"], 110), 1.2))
                    g.setBrush(Qt.BrushStyle.NoBrush)
                    g.drawEllipse(pts[-1] + QPointF(dx, dy), 3.5, 3.5)
    elif style == "cells":                           # Infested / New Loka: organic cells
        for _ in range(38):
            x, y, r = rnd.uniform(0, n), rnd.uniform(0, n), rnd.uniform(10, 46)
            g.setPen(QPen(col(p["border"] if r > 25 else p["accent"], 130 if r > 25 else 80), 1.1))
            g.setBrush(Qt.BrushStyle.NoBrush)
            tiled(lambda a, b, r=r: g.drawEllipse(QPointF(a, b), r, r * rnd.uniform(0.75, 1.0)), x, y, r)
            if r > 30:
                tiled(lambda a, b, r=r: g.drawEllipse(QPointF(a + r * 0.2, b - r * 0.1), r * 0.25, r * 0.25), x, y, r)
    elif style == "waves":                           # Ostron / Sentient: layered waves
        for i in range(12):
            y0 = i * n / 12
            path = QPainterPath(QPointF(0, y0))
            for x in range(0, n + 1, 8):
                path.lineTo(QPointF(x, y0 + 9 * math.sin(2 * math.pi * x / (n / 2) + i * 0.8)))
            g.setPen(QPen(col(p["accent"] if i % 4 == 0 else p["border"], 85 if i % 4 == 0 else 125), 1.2))
            g.drawPath(path)
    else:                                            # rings (Entrati / Narmer): spirals and concentric rings
        for cx, cy in ((n * 0.25, n * 0.3), (n * 0.75, n * 0.75)):
            for j in range(7):
                r = 18 + j * 20
                g.setPen(QPen(col(p["accent"] if j % 3 == 0 else p["border"], 80 if j % 3 == 0 else 120), 1.1))
                tiled(lambda a, b, r=r, j=j: g.drawArc(QRectF(a - r, b - r, 2 * r, 2 * r), (j * 40) * 16, 280 * 16), cx, cy, r)
    g.end()
    img.save(str(out), "PNG")
    return out.as_posix()


def make_picture_backdrop(p: dict, strength: int, src: str):
    """Your own picture as background: cropped to 16:9, 1920×1080, and blended into the theme's background colour (the
    visibility setting is how much of the picture shows), so text stays readable. None if the file cannot be read."""
    import hashlib
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QColor, QImage, QPainter
    from app.core.config import APP_DIR
    try:
        st = os.stat(src)
    except OSError:
        return None
    strength = max(0, min(100, int(strength)))
    key = hashlib.md5(f"{src}|{st.st_mtime_ns}|{st.st_size}|{p['bg']}|{strength}".encode()).hexdigest()[:16]
    out = APP_DIR / "backdrop" / f"picture_{key}.png"
    if out.exists():
        return out.as_posix()
    img = QImage(src)
    if img.isNull():
        return None
    W, H = 1920, 1080
    img = img.scaled(W, H, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
    img = img.copy((img.width() - W) // 2, (img.height() - H) // 2, W, H)
    canvas = QImage(W, H, QImage.Format.Format_RGB32)
    canvas.fill(QColor(p["bg"]))
    g = QPainter(canvas)
    g.setOpacity(0.06 + 0.5 * strength / 100.0)        # 45 (default) -> about a quarter of the picture
    g.drawImage(0, 0, img)
    g.end()
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(str(out), "PNG")
    return out.as_posix()


def backdrop_style(p: dict, path: str, stretch: bool = False) -> str:
    """The main window shows the background tile (or your picture, stretched to the window); containers and labels inside
    it become see-through, while tables, lists, inputs, buttons and dialogs keep their solid colours (so text never sits
    on the pattern where it would be hard to read)."""
    paint = (f'border-image: url("{path}") 0 0 0 0 stretch stretch;' if stretch
             else f'background-image: url("{path}"); background-repeat: repeat-xy;')
    return f"""
#mainwin {{ background-color: {p['bg']}; {paint} }}
#mainwin QLabel, #mainwin QCheckBox, #mainwin QRadioButton, #mainwin QGroupBox, #mainwin QStackedWidget,
#mainwin QSplitter, #mainwin QTabWidget, #mainwin QScrollArea, #mainwin QWidget#qt_scrollarea_viewport,
#mainwin .QWidget {{ background: transparent; }}
"""


def apply(app=None, theme_id=None, font=None, size=None):
    """Sets the style sheet of the application. Arguments default to the saved settings."""
    if app is None:
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
    if app is None:
        return ""
    theme_id = CFG["theme"] if theme_id is None else theme_id
    font = CFG["ui_font"] if font is None else font
    size = CFG["ui_font_size"] if size is None else size
    load_fonts()
    style = build_style(theme_id, font, size)
    p = palette(theme_id)
    if CFG.get("backdrop", True):
        try:
            kind = str(CFG.get("backdrop_style") or "auto")
            pic = make_picture_backdrop(p, CFG.get("backdrop_strength", 45), str(CFG.get("backdrop_image") or "")) \
                if kind == "image" and CFG.get("backdrop_image") else None
            if pic:
                style += backdrop_style(p, pic, stretch=True)
            elif kind != "none":
                style += backdrop_style(p, make_backdrop(p, CFG.get("backdrop_strength", 45), backdrop_for(theme_id)))
        except Exception as e:
            from app.core import logbus
            logbus.error("theme", f"background: {type(e).__name__}: {e}")    # plain background
    app.setStyleSheet(style)
    from app.core import uiutil
    uiutil.PRICE_COLOR.setNamedColor(p["accent"])
    uiutil.MAXRANK_COLOR.setNamedColor(p["maxrank"])
    uiutil.STANDING_COLOR.setNamedColor(p["standing"])
    uiutil.DIM_COLOR.setNamedColor(p["hint"])
    return style


def ensure_applied():
    """Used by windows created without main() (tests, tools): apply the saved theme if none is set yet."""
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is not None and not app.styleSheet():
        apply(app)


def contrast(a: str, b: str) -> float:
    """WCAG contrast ratio between two #rrggbb colours."""
    def lum(c):
        c = c.lstrip("#")
        v = [int(c[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        v = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in v]
        return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)
