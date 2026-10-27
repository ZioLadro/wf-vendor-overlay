"""Colour themes (inspired by Warframe's factions) and the font, applied to the whole program at once.

A theme is a small palette; build_style() turns it into the Qt style sheet. apply() sets it on the application, so
every window and dialog changes immediately (no restart). All themes are dark: the semantic colours used in the
tables (green = good, amber = warning, red = bad) are tuned for dark backgrounds.
"""
from config import CFG

DEFAULT_FONT = "Segoe UI"

# id -> palette. bg: window; panel: inputs and buttons; alt: alternate table rows; border; text; muted/hint: secondary
# text; accent: prices, progress bar, selected tab line; select: selected rows and hovered buttons.
# ally = friendly faction, enemy = enemy faction (only used to label the choice).
PRESETS = {
    "classic": dict(kind="", bg="#161a22", panel="#1f2430", alt="#1a1f29", head="#232938", border="#343b4d",
                    text="#e6e6e6", muted="#9aa4bd", hint="#7d869e", accent="#78c8ff", select="#2d3650",
                    maxrank="#ffcd6e", standing="#bea0ff"),
    "tenno": dict(kind="ally", bg="#10151d", panel="#19212e", alt="#141b26", head="#1f2a3b", border="#2f4058",
                  text="#e8eef7", muted="#a3b3c9", hint="#7d8ea6", accent="#5ec8f2", select="#27405e",
                  maxrank="#e8c25a", standing="#b3a3ff"),
    "ostron": dict(kind="ally", bg="#111917", panel="#192622", alt="#141f1c", head="#1f332d", border="#31504a",
                   text="#e9f1ec", muted="#a2bdb2", hint="#7f998f", accent="#4fd1b0", select="#27493f",
                   maxrank="#e6c36a", standing="#c4a6f5"),
    "entrati": dict(kind="ally", bg="#16111d", panel="#221a2e", alt="#1b1425", head="#2b2139", border="#473761",
                    text="#efe8f6", muted="#b8a6cc", hint="#9482aa", accent="#c08af0", select="#3d2c5a",
                    maxrank="#f0c978", standing="#8fe0d6"),
    "steel_meridian": dict(kind="ally", bg="#16171a", panel="#212328", alt="#1b1d21", head="#2a2d33", border="#44484f",
                           text="#ececec", muted="#adb1b8", hint="#8a8f97", accent="#e0cf8a", select="#383c44",
                           maxrank="#f0d98c", standing="#a9b8ff"),
    "red_veil": dict(kind="ally", bg="#1a1112", panel="#291a1c", alt="#211517", head="#331f22", border="#573438",
                     text="#f3e8e8", muted="#c9a8aa", hint="#a38487", accent="#ff7b72", select="#4a2a2e",
                     maxrank="#ffcf7a", standing="#d9a8ff"),
    "new_loka": dict(kind="ally", bg="#121a14", panel="#1a2a1e", alt="#15211a", head="#213526", border="#355a3d",
                     text="#ebf4ec", muted="#a6c4ab", hint="#83a089", accent="#7ee08f", select="#2a4a31",
                     maxrank="#e9d27a", standing="#b5b0ff"),
    "grineer": dict(kind="enemy", bg="#1b1711", panel="#2a2318", alt="#211c14", head="#352c1d", border="#5a4a30",
                    text="#eee4d3", muted="#c1b190", hint="#9c8e72", accent="#e8892c", select="#4d3c22",
                    maxrank="#f2c76a", standing="#c9b0ff"),
    "corpus": dict(kind="enemy", bg="#0e1822", panel="#162838", alt="#112030", head="#1b3247", border="#2c5272",
                   text="#e6f3fc", muted="#9fc0d8", hint="#7a9bb3", accent="#42c6ff", select="#22476a",
                   maxrank="#ffd27a", standing="#b8a8ff"),
    "infested": dict(kind="enemy", bg="#11170f", panel="#1a2517", alt="#151e13", head="#223020", border="#3b5434",
                     text="#e9f2e3", muted="#a9c19d", hint="#869d7b", accent="#a6e35a", select="#2e4a28",
                     maxrank="#e8d56a", standing="#d58bf0"),
    "orokin": dict(kind="enemy", bg="#14120c", panel="#201c12", alt="#1a170f", head="#2b2616", border="#554a26",
                   text="#f4ecd4", muted="#c9bc94", hint="#a39870", accent="#e8bd4a", select="#463c1e",
                   maxrank="#fff0a8", standing="#d0b8ff"),
    "sentient": dict(kind="enemy", bg="#0c0f1f", panel="#151a35", alt="#10142a", head="#1c2347", border="#323b78",
                     text="#e7e9ff", muted="#a5abdb", hint="#8189bd", accent="#8393ff", select="#283370",
                     maxrank="#ffd98a", standing="#e0a8ff"),
    "narmer": dict(kind="enemy", bg="#1a1112", panel="#291a1b", alt="#201415", head="#331f20", border="#5c3a36",
                   text="#f3e6e1", muted="#cfaaa0", hint="#a98881", accent="#ef6a4c", select="#4d2d29",
                   maxrank="#ffd47a", standing="#d6adff"),
}
ORDER = ["classic", "tenno", "ostron", "entrati", "steel_meridian", "red_veil", "new_loka",
         "grineer", "corpus", "infested", "orokin", "sentient", "narmer"]


def palette(theme_id: str) -> dict:
    return PRESETS.get(theme_id) or PRESETS["classic"]


def build_style(theme_id="classic", font=None, size=13) -> str:
    p = palette(theme_id)
    fam = (font or DEFAULT_FONT).replace('"', "")
    size = max(9, min(24, int(size)))
    return f"""
QWidget {{ background: {p['bg']}; color: {p['text']}; font-family: "{fam}"; font-size: {size}px; }}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit {{ background: {p['panel']}; border: 1px solid {p['border']};
                                                 border-radius: 4px; padding: 4px 8px; }}
QComboBox QAbstractItemView {{ background: {p['panel']}; selection-background-color: {p['select']}; }}
QListWidget {{ background: {p['panel']}; border: 1px solid {p['border']}; }}
QListWidget::item:selected {{ background: {p['select']}; color: #ffffff; }}
QTableWidget {{ background: {p['bg']}; alternate-background-color: {p['alt']}; border: 1px solid {p['border']};
               selection-background-color: {p['select']}; selection-color: #ffffff; }}
QHeaderView::section {{ background: {p['head']}; color: {p['muted']}; border: none; border-right: 1px solid {p['border']};
                       padding: 5px 8px; font-weight: bold; }}
QPushButton {{ background: {p['head']}; border: 1px solid {p['border']}; border-radius: 4px; padding: 5px 12px; }}
QPushButton:hover {{ background: {p['select']}; }}
QPushButton:disabled {{ color: {p['hint']}; background: {p['alt']}; }}
QProgressBar {{ background: {p['panel']}; border: 1px solid {p['border']}; border-radius: 4px; text-align: center; height: 14px; }}
QProgressBar::chunk {{ background: {p['accent']}; }}
QTabWidget::pane {{ border: 1px solid {p['border']}; top: -1px; }}
QTabBar::tab {{ background: {p['alt']}; border: 1px solid {p['border']}; padding: 7px 18px; margin-right: 2px; }}
QTabBar::tab:selected {{ background: {p['head']}; color: #ffffff; font-weight: bold; border-bottom: 2px solid {p['accent']}; }}
QGroupBox {{ border: 1px solid {p['border']}; border-radius: 6px; margin-top: 14px; padding-top: 8px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 6px; color: {p['muted']}; }}
QCheckBox {{ spacing: 8px; }}
QScrollBar:vertical {{ background: {p['bg']}; width: 12px; }}
QScrollBar::handle:vertical {{ background: {p['border']}; border-radius: 5px; min-height: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QToolTip {{ background: {p['panel']}; color: {p['text']}; border: 1px solid {p['border']}; }}
QLabel[role="muted"] {{ color: {p['muted']}; }}
QLabel[role="hint"] {{ color: {p['hint']}; font-size: {max(9, size - 2)}px; }}
QLabel[role="small"] {{ color: {p['muted']}; font-size: {max(8, size - 3)}px; }}
"""


BACKDROP_TILE = 560


def make_backdrop(p: dict, strength: int) -> str:
    """Draws the window's background tile (an original pattern in the spirit of Warframe's Orokin / Tenno art: thin gilded
    lattice lines, diamonds and arcs) in the theme's colours, kept faint so text stays easy to read. Returns the PNG path."""
    from PyQt6.QtCore import QPointF, QRectF, Qt
    from PyQt6.QtGui import QColor, QImage, QPainter, QPen
    from config import APP_DIR
    strength = max(0, min(100, int(strength)))
    out = APP_DIR / "backdrop" / f"{p['bg'][1:]}_{p['accent'][1:]}_{p['border'][1:]}_{strength}.png"
    if out.exists():
        return out.as_posix()
    out.parent.mkdir(parents=True, exist_ok=True)
    n = BACKDROP_TILE
    img = QImage(n, n, QImage.Format.Format_RGB32)
    img.fill(QColor(p["bg"]))
    k = strength / 100.0

    def col(c, a):
        q = QColor(c)
        q.setAlpha(int(a * k))
        return q
    g = QPainter(img)
    g.setRenderHint(QPainter.RenderHint.Antialiasing)
    # diagonal lattice
    g.setPen(QPen(col(p["border"], 120), 1))
    step = n // 4
    for i in range(-4, 9):
        g.drawLine(QPointF(i * step, 0), QPointF(i * step + n, n))
        g.drawLine(QPointF(i * step, n), QPointF(i * step + n, 0))
    # small diamonds where the lines cross
    g.setPen(Qt.PenStyle.NoPen)
    g.setBrush(col(p["accent"], 70))
    for x in range(0, n + 1, step):
        for y in range(0, n + 1, step):
            cx, cy = x + (step / 2 if (y // step) % 2 else 0), y
            d = 3.5
            g.drawPolygon([QPointF(cx, cy - d), QPointF(cx + d, cy), QPointF(cx, cy + d), QPointF(cx - d, cy)])
    # gilded arcs and rings (centred on the tile corners, so they join across tiles)
    g.setBrush(Qt.BrushStyle.NoBrush)
    for r, a, w in ((n * 0.42, 80, 1.6), (n * 0.36, 55, 1.0), (n * 0.18, 60, 1.2)):
        g.setPen(QPen(col(p["accent"], a), w))
        for cx, cy in ((0, 0), (n, 0), (0, n), (n, n)):
            g.drawEllipse(QPointF(cx, cy), r, r)
    g.setPen(QPen(col(p["accent"], 70), 1.2))
    c = QPointF(n / 2, n / 2)
    g.drawEllipse(c, n * 0.11, n * 0.11)
    g.drawArc(QRectF(n / 2 - n * 0.16, n / 2 - n * 0.16, n * 0.32, n * 0.32), 30 * 16, 120 * 16)
    g.drawArc(QRectF(n / 2 - n * 0.16, n / 2 - n * 0.16, n * 0.32, n * 0.32), 210 * 16, 120 * 16)
    g.end()
    img.save(str(out), "PNG")
    return out.as_posix()


def backdrop_style(p: dict, path: str) -> str:
    """The main window shows the background tile; containers and labels inside it become see-through, while tables, lists,
    inputs, buttons and dialogs keep their solid colours (so text never sits on the pattern where it would be hard to read)."""
    return f"""
#mainwin {{ background-color: {p['bg']}; background-image: url("{path}"); background-repeat: repeat-xy; }}
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
    style = build_style(theme_id, font, size)
    p = palette(theme_id)
    if CFG.get("backdrop", True):
        try:
            style += backdrop_style(p, make_backdrop(p, CFG.get("backdrop_strength", 45)))
        except Exception:
            pass                                    # no picture: plain background
    app.setStyleSheet(style)
    import uiutil
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
