"""Sharing builds: a short code to paste (chat, Discord), a .wfbuild file, and a picture of the build screen.

Code: "WFVO1:" + the planned piece (planner_tab's format: item, configurations with their mods and ranks, Forma, Reactor /
Catalyst, rank, adapters, Incarnon, bonus element, Archon Shards) as JSON, compressed (zlib) and base64url-encoded.
The same JSON, readable, is the .wfbuild file. Both come back into the planner (Import), from the Builds tab or the planner.
Picture: the build screen as it is shown (mods, capacity, stats recap, Incarnon path) with a title bar, saved as PNG or
copied to the clipboard."""
import base64
import json
import zlib

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter

PREFIX = "WFVO1:"
FILE_FILTER = "WF Vendor Overlay build (*.wfbuild *.json)"


def _plain(piece: dict) -> dict:
    """The piece as plain JSON (tuples to lists, slot keys of the Forma as text)."""
    return json.loads(json.dumps(piece, default=list))


def to_json(kind: str, piece: dict) -> dict:
    from app.core.version import __version__
    return {"format": "wfvo-build", "v": 1, "app": __version__, "kind": kind, "piece": _plain(piece)}


def encode(kind: str, piece: dict) -> str:
    raw = json.dumps(to_json(kind, piece), separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return PREFIX + base64.urlsafe_b64encode(zlib.compress(raw, 9)).decode("ascii").rstrip("=")


def decode(text: str) -> tuple:
    """(kind, piece) from a code or the JSON of a file. Raises ValueError with a short reason."""
    s = (text or "").strip()
    if s.startswith("{"):
        d = json.loads(s)
    else:
        i = s.find(PREFIX)
        if i < 0:
            raise ValueError("not a build code (it starts with WFVO1:)")
        body = "".join(s[i + len(PREFIX):].split())
        body += "=" * (-len(body) % 4)
        try:
            d = json.loads(zlib.decompress(base64.urlsafe_b64decode(body)).decode("utf-8"))
        except Exception as e:
            raise ValueError(f"the code is damaged ({type(e).__name__})")
    if not isinstance(d, dict) or d.get("format") != "wfvo-build" or not isinstance(d.get("piece"), dict):
        raise ValueError("not a build of this program")
    kind, piece = str(d.get("kind") or ""), d["piece"]
    if not piece.get("item"):
        raise ValueError("the build has no item")
    from app.ui.planner_tab import KINDS, upgrade_piece
    if kind not in KINDS:
        raise ValueError(f"unknown kind of item: {kind}")
    return kind, upgrade_piece(piece, kind)


def image(widget, title: str, subtitle: str = "") -> QImage:
    """The widget (the build screen) as a picture with a title bar on top and the program's name at the bottom."""
    from app.core import theme
    from app.core.version import __version__
    p = theme.palette(theme.current_id())
    from PyQt6.QtWidgets import QApplication, QWidget
    hidden = [w for w in widget.findChildren(QWidget, "bs_extra") if w.isVisible()]
    for w in hidden:                                    # the planner's switches are not part of the build
        w.hide()
    QApplication.processEvents()
    shot = widget.grab()
    for w in hidden:
        w.show()
    dpr = shot.devicePixelRatio() or 1.0
    w, h = int(shot.width() / dpr), int(shot.height() / dpr)
    head, foot, pad = 58, 26, 14
    img = QImage(int((w + 2 * pad) * dpr), int((h + head + foot) * dpr), QImage.Format.Format_ARGB32)
    img.setDevicePixelRatio(dpr)
    img.fill(QColor(p["bg"]))
    g = QPainter(img)
    g.setRenderHint(QPainter.RenderHint.Antialiasing)
    g.fillRect(QRectF(0, 0, w + 2 * pad, head), QColor(p["head"]))
    g.fillRect(QRectF(0, head - 3, w + 2 * pad, 3), QColor(p["accent"]))
    f = QFont(theme.heading_family())
    f.setPixelSize(24)
    f.setBold(True)
    f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 108)
    g.setFont(f)
    g.setPen(QColor(p["text"]))
    g.drawText(QRectF(pad, 4, w, 30), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, title.upper())
    f2 = QFont(theme.body_family())
    f2.setPixelSize(12)
    g.setFont(f2)
    g.setPen(QColor(p["muted"]))
    g.drawText(QRectF(pad, 32, w, 18), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, subtitle)
    g.drawPixmap(pad, head, shot)
    g.setPen(QColor(p["hint"]))
    g.drawText(QRectF(pad, head + h + 4, w, foot - 8), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
               f"WF Vendor Overlay {__version__}")
    g.end()
    return img


def copy_image(img: QImage):
    QGuiApplication.clipboard().setImage(img)


def copy_text(text: str):
    QGuiApplication.clipboard().setText(text)
