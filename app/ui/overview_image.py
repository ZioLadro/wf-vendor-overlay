"""One picture of a whole planned loadout to show it around (Discord, a guide): every item with its picture, its mods
and Arcanes as small cards, Forma, capacity, Archon Shards and Helminth, in the program's colour theme.

It is an overview only: unlike the build codes, .wfbuild files and the build screen's pictures it cannot be imported.
At most 2048 pixels on its longest side."""
import time

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QPen

from app.core import theme
from app.core.i18n import t
from app.core.version import __version__
from app.game import arcanes as A
from app.game import buildcalc as BC
from app.game import loadouts as LO

MAX_SIDE = 2048
RARITY = {"C": "#c98a54", "U": "#c9cfd6", "R": "#e8c25a", "L": "#d9b3ff"}
SHARD = {"RED": "#e0533f", "BLUE": "#3f8fe0", "GREEN": "#43c46f", "YELLOW": "#e8c040", "ORANGE": "#ef8a3a",
         "PURPLE": "#a66be8"}
ORDER = ("warframe", "primary", "secondary", "melee", "archgun", "archmelee", "archwing", "companion", "compweapon")


def _font(family, px, bold=False):
    f = QFont(family)
    f.setPixelSize(int(px))
    f.setBold(bold)
    return f


def _piece_info(kind, p):
    """What the card of a piece shows: mods [(name, rank, max, rarity, riven)], arcanes, forma, capacity…"""
    roles = BC.plan_roles(kind, p["item"])
    cfgs = p.get("configs") or [{"mods": []}]
    ci = int(p.get("cfg", 0) or 0)
    cfg = cfgs[ci] if 0 <= ci < len(cfgs) else cfgs[0]
    mods = list(cfg.get("mods") or []) + [None] * len(roles)
    mods = mods[:len(roles)]
    pols = BC.slot_polarities(kind, p["item"], roles, p.get("forma") or {})
    try:
        calc = BC.evaluate(kind, p["item"], roles, mods, pols, p.get("reactor", True), p.get("level", 30))
        cap = (calc["used"], calc["total"])
    except Exception:
        cap = None
    out_mods, arcs = [], []
    for i, m in enumerate(mods):
        if not m or not m[0]:
            continue
        riven = len(m) > 2 and bool(m[2])
        if roles[i] == "arcane":
            arcs.append((m[0], m[1], A.max_rank(m[0])))
        else:
            info = BC.mod_info(m[0])
            rar = "R" if riven else LO.data().get("rarity", {}).get(m[0]) or ("L" if m[0].startswith("Primed") else "R")
            out_mods.append((m[0], m[1], 8 if riven else (info[2] if info else m[1]), rar, riven, roles[i]))
    return {"mods": out_mods, "arcanes": arcs, "forma": BC.forma_count(kind, p["item"], roles, p.get("forma") or {}),
            "cap": cap, "shards": [x for x in (p.get("shards") or []) if x] if kind == "warframe" else [],
            "helminth": p.get("helminth"), "valence": p.get("valence") if BC.valence_capable(p["item"]) else None,
            "config": cfg.get("name") or ""}


def render(name: str, pieces: dict, owned: dict | None = None) -> QImage:
    """The overview picture of a loadout ({kind: planner piece}); a null QImage when there is nothing to draw."""
    from app.ui.builds_tab import thumb
    kinds = [k for k in ORDER if (pieces.get(k) or {}).get("item")] + \
            [k for k in pieces if k not in ORDER and (pieces.get(k) or {}).get("item")]
    if not kinds:
        return QImage()
    p = theme.palette(theme.current_id())
    head_f, body_f = theme.heading_family(), theme.body_family()
    owned = owned or {}
    cols = 1 if len(kinds) == 1 else 2
    card_w = 900
    W = 40 + cols * card_w + (cols - 1) * 24 + 40
    infos = {k: _piece_info(k, pieces[k]) for k in kinds}

    def card_h(info):
        rows = (len(info["mods"]) + 1) // 2
        h = 150 + rows * 46
        if info["arcanes"]:
            h += 56
        if info["shards"] or info["helminth"]:
            h += 40
        return max(220, h + 20)
    heights = [card_h(infos[k]) for k in kinds]
    grid_rows = [heights[i:i + cols] for i in range(0, len(heights), cols)]
    H = 150 + sum(max(r) + 24 for r in grid_rows) + 60
    img = QImage(W, H, QImage.Format.Format_ARGB32)
    img.fill(QColor(p["bg"]))
    g = QPainter(img)
    g.setRenderHint(QPainter.RenderHint.Antialiasing)
    g.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    g.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    grad = QLinearGradient(0, 0, W, H)
    grad.setColorAt(0, QColor(p["bg"]))
    grad.setColorAt(1, QColor(p["glow"]))
    g.fillRect(0, 0, W, H, grad)
    # title
    title = name or pieces[kinds[0]]["item"]
    g.setPen(QColor(p["accent"]))
    g.setFont(_font(head_f, 46, True))
    g.drawText(QRectF(40, 28, W - 80, 60), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, title.upper())
    g.setPen(QColor(p["muted"]))
    g.setFont(_font(body_f, 18))
    sub = " · ".join(pieces[k]["item"] for k in kinds)
    g.drawText(QRectF(40, 88, W - 80, 30), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, sub)
    g.setPen(QPen(QColor(p["accent"]), 2))
    g.drawLine(40, 128, W - 40, 128)

    y = 150
    idx = 0
    for row in grid_rows:
        rh = max(row)
        for c in range(len(row)):
            k = kinds[idx]
            idx += 1
            x = 40 + c * (card_w + 24)
            _card(g, QRectF(x, y, card_w, rh), k, pieces[k], infos[k], p, head_f, body_f, owned, thumb)
        y += rh + 24
    g.setPen(QColor(p["hint"]))
    g.setFont(_font(body_f, 15))
    g.drawText(QRectF(40, H - 48, W - 80, 30), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
               t("overview.footer", v=__version__, date=time.strftime("%Y-%m-%d")))
    g.end()
    if max(W, H) > MAX_SIDE:
        img = img.scaled(MAX_SIDE, MAX_SIDE, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    return img


def _card(g, r, kind, piece, info, p, head_f, body_f, owned, thumb):
    g.setPen(QPen(QColor(p["border"]), 1.5))
    g.setBrush(QColor(p["panel"]))
    g.drawRoundedRect(r, 16, 16)
    pm = thumb(piece["item"], 112)
    x0, y0 = r.x() + 22, r.y() + 20
    if pm is not None:
        g.drawPixmap(int(x0), int(y0), pm)
    tx = x0 + 128
    g.setPen(QColor(p["text"]))
    g.setFont(_font(head_f, 32, True))
    g.drawText(QRectF(tx, y0 - 4, r.width() - 170, 42), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
               piece["item"])
    g.setPen(QColor(p["accent"]))
    g.setFont(_font(head_f, 18, True))
    kind_txt = t("builds.kind." + kind).upper() + (f"  ·  {info['config']}" if info["config"] else "")
    g.drawText(QRectF(tx, y0 + 38, r.width() - 170, 26), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, kind_txt)
    badges = []
    if info["cap"]:
        badges.append(t("overview.capacity", used=info["cap"][0], total=info["cap"][1]))
    badges.append(t("overview.forma", n=info["forma"]))
    if piece.get("reactor", True):
        badges.append(t("builds.catalyst") if kind != "warframe" and kind != "companion" and kind != "archwing"
                      else t("builds.reactor.name"))
    if info["valence"]:
        badges.append(f"{t('dmg.' + str(info['valence'].get('element', '')).lower())} {float(info['valence'].get('pct') or 0):.0f}%")
    g.setPen(QColor(p["muted"]))
    g.setFont(_font(body_f, 17))
    g.drawText(QRectF(tx, y0 + 68, r.width() - 170, 26), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
               "   ·   ".join(badges))
    # mods: two columns of chips
    y = r.y() + 150
    cw = (r.width() - 44 - 14) / 2
    for i, (name, rank, mx, rar, riven, role) in enumerate(info["mods"]):
        cx = r.x() + 22 + (i % 2) * (cw + 14)
        cy = y + (i // 2) * 46
        mine = riven or name in owned
        _chip(g, QRectF(cx, cy, cw, 38), name + (" ★" if role in ("aura", "exilus", "stance") else ""),
              f"{rank}/{mx}" if mx else "", RARITY.get(rar, RARITY["R"]), p, body_f, mine or not owned)
    y += ((len(info["mods"]) + 1) // 2) * 46
    if info["arcanes"]:
        y += 8
        aw = (r.width() - 44 - 14) / 2
        for i, (name, rank, mx) in enumerate(info["arcanes"][:2]):
            _chip(g, QRectF(r.x() + 22 + i * (aw + 14), y, aw, 40), "◆ " + name, f"{rank}/{mx}", p["accent2"], p,
                  body_f, name in owned or not owned, bold=True)
        y += 50
    if info["shards"] or info["helminth"]:
        x = r.x() + 26
        for s in info["shards"]:
            col = QColor(SHARD.get(str(s.get("color") or "").upper(), p["accent"]))
            g.setPen(QPen(QColor("#ffffff") if s.get("tauforged") else col.darker(140), 2))
            g.setBrush(col)
            g.drawEllipse(QRectF(x, y + 8, 22, 22))
            x += 30
        if info["helminth"] and info["helminth"].get("path"):
            g.setPen(QColor(p["muted"]))
            g.setFont(_font(body_f, 17))
            g.drawText(QRectF(x + 10, y + 4, r.right() - x - 30, 30), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       t("overview.helminth", name=_helminth_name(info["helminth"]["path"]),
                         n=int(info["helminth"].get("slot") or 0)))


def _helminth_name(path):
    try:
        from app.ui import abilitybar as AB
        for n, pth in AB.helminth_choices():
            if pth == path:
                return n
    except Exception:
        pass
    return str(path).rsplit("/", 1)[-1]


def _chip(g, r, name, rank, bar, p, body_f, mine, bold=False):
    g.setPen(QPen(QColor(p["border"]), 1))
    g.setBrush(QColor(p["alt"]))
    g.drawRoundedRect(r, 8, 8)
    g.setPen(Qt.PenStyle.NoPen)
    g.setBrush(QColor(bar))
    g.drawRoundedRect(QRectF(r.x(), r.y(), 6, r.height()), 3, 3)
    g.setPen(QColor(p["text"] if mine else p["hint"]))
    g.setFont(_font(body_f, 18, bold))
    fm = g.fontMetrics()
    text = fm.elidedText(name, Qt.TextElideMode.ElideRight, int(r.width() - 90))
    g.drawText(QRectF(r.x() + 16, r.y(), r.width() - 90, r.height()), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)
    if rank:
        g.setPen(QColor(bar))
        g.setFont(_font(body_f, 16, True))
        g.drawText(QRectF(r.right() - 76, r.y(), 66, r.height()), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, rank)
