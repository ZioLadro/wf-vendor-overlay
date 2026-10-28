"""Player strip shown above every tab: name, mastery rank, trades left and a badge per syndicate with your rank.

Badges are the syndicate logos taken from the Warframe wiki (see logos.py), saved as <SyndicateTag>.png in the 'icons'
folder of the program's data folder (%LOCALAPPDATA%\\WFVendorOverlay\\icons; your own PNG files there are used as they
are). Until a logo is there, a badge is drawn from the syndicate colours in the game data."""
import time

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap
from PyQt6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QInputDialog, QLabel, QVBoxLayout, QWidget

from app.core.config import APP_DIR, CFG, save_config
from app.core.i18n import t
from app.game.inventory import game_names
from app.game.standing import get_store, is_hidden, is_nightwave, syndicate_name, trades_stale
from app.core.uiutil import role
from app.core.uiutil import MUTED_STYLE, thousands

ICON_DIR = APP_DIR / "icons"
AVATAR, EMBLEM = 52, 36
SIZE = 28
PER_COL = 4
_cache = {}


def badge(tag: str) -> QPixmap:
    if tag in _cache:
        return _cache[tag]
    pm = QPixmap(str(ICON_DIR / f"{tag}.png"))
    if pm.isNull():
        from app.ui import logos
        logos.want(tag, syndicate_name(tag))         # asks the wiki in the background; drawn badge meanwhile
        fg, bg = (game_names().get("syn_colors", {}).get(tag) or ["#DDDDDD", "#445066"])
        pm = QPixmap(SIZE * 2, SIZE * 2)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(bg))
        p.setPen(QColor(fg))
        p.drawEllipse(QRectF(3, 3, SIZE * 2 - 6, SIZE * 2 - 6))
        words = [w for w in syndicate_name(tag).replace("'", "").split() if w[0].isalpha()]
        initials = "".join(w[0] for w in words[:2]).upper() or "?"
        f = QFont("Segoe UI", 20, QFont.Weight.Bold)
        p.setFont(f)
        p.drawText(QRectF(0, 0, SIZE * 2, SIZE * 2), Qt.AlignmentFlag.AlignCenter, initials)
        p.end()
    pm = pm.scaled(SIZE, SIZE, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    _cache[tag] = pm
    return pm


def compact(n) -> str:
    """1234 -> 1.2k, 3000 -> 3k, 30500 -> 30.5k, 1250000 -> 1.2M."""
    n = int(n)
    for div, suf in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "k")):
        if abs(n) >= div:
            v = n / div
            s = f"{v:.1f}" if abs(v) < 100 else f"{v:.0f}"
            return s.rstrip("0").rstrip(".") + suf
    return str(n)


class PlayerBar(QFrame):
    def __init__(self, market):
        super().__init__()
        self.market, self.store = market, get_store()
        self._shown = None
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.info = QLabel("")
        self.info.setToolTip(t("bar.name.tip"))
        self.info.setCursor(Qt.CursorShape.PointingHandCursor)
        self.info.mousePressEvent = lambda e: self.ask_name()
        self.grid_w = QWidget()
        self.grid = QGridLayout(self.grid_w)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(14)
        self.grid.setVerticalSpacing(2)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(18)
        self.wallet_w = QWidget()
        self.wallet_g = QGridLayout(self.wallet_w)
        self.wallet_g.setContentsMargins(0, 0, 0, 0)
        self.wallet_g.setHorizontalSpacing(14)
        self.wallet_g.setVerticalSpacing(2)
        self.avatar = QLabel()                       # the profile glyph chosen in the game
        self.avatar.setFixedSize(AVATAR, AVATAR)
        self.avatar.setToolTip(t("bar.avatar.tip"))
        self.emblem = QLabel()                       # the Mastery Rank emblem
        self.emblem.setFixedSize(EMBLEM, EMBLEM)
        lay.addWidget(self.avatar, 0, Qt.AlignmentFlag.AlignTop)
        lay.addWidget(self.emblem, 0, Qt.AlignmentFlag.AlignTop)
        col = QVBoxLayout()                          # name / MR / trades, and the currencies under them
        col.setSpacing(4)
        col.addWidget(self.info)
        col.addWidget(self.wallet_w)
        col.addStretch(1)
        lay.addLayout(col)
        lay.addWidget(self.grid_w, 1)
        self.refresh()

    def ask_name(self):
        name, ok = QInputDialog.getText(self, t("bar.name.title"), t("bar.name.prompt"), text=CFG["player_name"])
        if ok:
            save_config({"player_name": name.strip()})
            self.refresh(force=True)

    def _tags(self):
        tags = {k for k in self.store.factions if not is_hidden(k)}
        tags.update(e["t"] for r in self.market.snapshot() for e in r["standing"] if e.get("t") and not is_hidden(e["t"]))
        return sorted(tags, key=lambda x: syndicate_name(x).lower())

    WALLET = (("plat", "bar.plat"), ("endo", "bar.endo"), ("ducats", "bar.ducats"), ("aya", "bar.aya"), ("regal", "bar.regal"),
              ("steel", "bar.steel"), ("pathos", "bar.pathos"), ("sliver", "bar.sliver"), ("heartcell", "bar.heartcell"),
              ("kuva", "bar.kuva"), ("vitus", "bar.vitus"))
    GAME_NAME = {"steel": "Steel Essence", "pathos": "Pathos Clamp", "sliver": "Riven Sliver", "heartcell": "Live Heartcell",
                 "vitus": "Vitus Essence", "kuva": "Kuva"}

    def _wallet(self):
        """Endo, platinum, ducats and Aya you hold (from the AlecaFrame file), compact (3k, 30k, 1.2M), with the icons of the
        icons folder when it is set."""
        from app.ui import icons
        while self.wallet_g.count():
            it = self.wallet_g.takeAt(0)
            w = it.widget()
            if w:
                w.hide()
                w.deleteLater()
        w = dict(self.store.wallet or {})
        if not w.get("aya") and CFG.get("aya_manual"):         # the game file does not always carry Aya: the number typed in Settings
            w["aya"] = int(CFG["aya_manual"])
        elif not w.get("aya"):
            w.pop("aya", None)
        shown = [(k, lab) for k, lab in self.WALLET if w.get(k) is not None and (k != "regal" or w[k])]
        for n, (k, lab) in enumerate(shown):
            cell = QWidget()
            h = QHBoxLayout(cell)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(4)
            pm = icons.wallet(k)                     # AlecaFrame's icons folder first…
            if pm is None and k in self.GAME_NAME:   # …else the game's own icon (browse.wf), downloaded once
                from app.ui import playericons
                pm = playericons.currency_pixmap(self.GAME_NAME[k], 20)
            if pm:
                ic = QLabel()
                ic.setPixmap(pm)
                h.addWidget(ic)
            txt = QLabel(compact(w[k]) if pm else f"{t(lab)} {compact(w[k])}")
            txt.setToolTip(f"{t(lab)}: {w[k]:,}")
            h.addWidget(txt)
            cell.setToolTip(f"{t(lab)}: {w[k]:,}")
            self.wallet_g.addWidget(cell, n // 5, n % 5)        # five a row, under the name and Mastery Rank
        self.wallet_w.setVisible(bool(shown))

    def _pictures(self):
        """The profile glyph and the Mastery Rank emblem (hidden until their picture is there)."""
        from app.ui import playericons as P
        s = self.store
        for lab, icon, size, tip in ((self.avatar, P.avatar_icon(getattr(s, "avatar", "")), AVATAR, None),
                                     (self.emblem, P.mastery_icon(s.mr), EMBLEM, f"MR {s.mr}" if s.mr is not None else None)):
            f = P.path_for(icon)
            pm = QPixmap(f) if f else QPixmap()
            if pm.isNull():
                lab.clear()
                lab.setVisible(False)
                continue
            lab.setPixmap(pm.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            lab.setVisible(True)
            if tip:
                lab.setToolTip(tip)

    def refresh(self, force=False):
        from app.ui import logos
        if logos.done_count != getattr(self, "_logos_seen", 0):     # new logos arrived from the wiki: redraw the badges
            self._logos_seen = logos.done_count
            _cache.clear()
            force = True
        from app.ui import playericons
        if playericons.done_count != getattr(self, "_pics_seen", 0):  # the glyph / emblem arrived: draw them
            self._pics_seen = playericons.done_count
            force = True
        key = (CFG.get("assets_dir"), CFG.get("assets_auto"), CFG.get("aya_manual"), repr(self.store.wallet), self.store.version, int(time.time() // 600), CFG["player_name"], self.store.fetched, CFG["hide_negative_ranks"])
        if not force and key == self._shown:
            return
        self._shown = key
        s = self.store
        name = CFG["player_name"] or t("bar.noname")
        parts = [f"<b>{name}</b>", f"MR {s.mr}" if s.mr is not None else "MR –",
                 t("bar.trades", n=s.trades if s.trades is not None else "–")
                 + (" ⚠" if trades_stale(s.synced) else "")]
        self.info.setText("<br>".join(parts))
        self._pictures()
        self._wallet()
        self.info.setToolTip(t("bar.trades.tip", when=time.strftime("%d/%m %H:%M", time.localtime(s.synced)) if s.synced else "–")
                             + (" " + t("bar.trades.stale") if trades_stale(s.synced) else ""))
        while self.grid.count():
            it = self.grid.takeAt(0)
            w = it.widget()
            if w:
                w.hide()                    # off the window now (deleteLater alone left it drawn for a moment)
                w.deleteLater()
        shown = [tg for tg in self._tags() if not (CFG["hide_negative_ranks"] and (s.get(tg) or {}).get("rank") is not None
                                                   and s.get(tg)["rank"] < 0)]
        for i, tag in enumerate(shown):
            f = s.get(tag)
            w = QWidget()
            h = QHBoxLayout(w)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(4)
            ic = QLabel()
            ic.setPixmap(badge(tag))
            txt = QLabel(syndicate_name(tag) + "\n" + (f"R{f['rank']}" if f and f.get("rank") is not None else "R–")
                         + " · " + (thousands(f["standing"]) if f else "–"))
            role(txt, "small")
            txt.setMinimumWidth(130)
            h.addWidget(ic)
            h.addWidget(txt)
            w.setFixedSize(SIZE + 4 + 134, SIZE + 4)
            left = f.get("daily") if f else None
            w.setToolTip(syndicate_name(tag) + "\n" + (
                t("bar.syn.tip", rank=f.get("rank", "–"), standing=thousands(f["standing"])) if f else t("bar.syn.none"))
                + (("\n" + t("bar.syn.daily", n=thousands(left))) if left is not None else ""))
            self.grid.addWidget(w, i % PER_COL, i // PER_COL)      # columns of 4, filled top to bottom
        self.grid.setColumnStretch(self.grid.columnCount(), 1)
