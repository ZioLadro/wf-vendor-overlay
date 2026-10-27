"""Builds tab: your own in-game loadouts, laid out like the game's screen (slots, Arcanes, Archon Shards, Helminth)."""
import json
import os
import time

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QButtonGroup, QComboBox, QFrame, QStackedWidget, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
    QPushButton, QScrollArea, QSplitter, QVBoxLayout, QWidget,
)

import aleca
import icons
import previews
import loadouts as LO
from config import APP_DIR
from i18n import t
from uiutil import age_text, role

CACHE_FILE = APP_DIR / "loadouts.json"
KINDS = ["warframe", "primary", "secondary", "melee", "archwing", "archgun", "necramech", "companion"]
SHARD_RGB = {"RED": "#c8453c", "BLUE": "#3b8fd9", "GREEN": "#3fbf6a", "YELLOW": "#e0b83a", "ORANGE": "#e08a3a",
             "PURPLE": "#a46be0"}


def _card(name, rank, mx, kind_role):
    """One slot: its name and rank. kind_role: general | aura | exilus | stance | arcane."""
    f = QFrame()
    f.setProperty("card", "empty" if not name else ("special" if kind_role != "general" else "slot"))
    f.setMinimumSize(120, 58)
    outer = QHBoxLayout(f)
    outer.setContentsMargins(8, 5, 8, 5)
    pm = None
    if name and kind_role == "arcane":                    # Arcanes: the generic picture of their rarity (icons folder only)
        pm = icons.arcane(name)
    elif name:                                            # mods: the card picture (warframe.market, else the wiki)
        pic = previews.by_name(name)
        if pic:
            pm = QPixmap(str(pic))
            if not pm.isNull():
                pm = pm.scaledToHeight(52, Qt.TransformationMode.SmoothTransformation)
    if pm is not None and not pm.isNull():
        img = QLabel()
        img.setPixmap(pm)
        outer.addWidget(img)
    lay = QVBoxLayout()
    outer.addLayout(lay, 1)
    lay.setSpacing(1)
    top = QLabel(t("builds.slot." + kind_role) if kind_role != "general" else "")
    role(top, "small")
    top.setVisible(kind_role != "general")
    main = QLabel(name or "—")
    main.setWordWrap(True)
    if not name:
        role(main, "hint")
    lay.addWidget(top)
    lay.addWidget(main, 1)
    if name and rank is not None and mx:
        sub = QLabel(t("builds.rank", rank=rank, max=mx))
        role(sub, "muted" if rank >= mx else "hint")
        lay.addWidget(sub)
    return f


class LoadoutView(QWidget):
    """The selected loadout, laid out like in the game."""

    def __init__(self):
        super().__init__()
        self.lay = QVBoxLayout(self)
        self.lay.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.title = QLabel("")
        self.title.setStyleSheet("font-size: 17px; font-weight: bold;")
        self.sub = QLabel("")
        role(self.sub, "muted")
        self.body = QVBoxLayout()
        self.lay.addWidget(self.title)
        self.lay.addWidget(self.sub)
        self.lay.addLayout(self.body)
        self.lay.addStretch(1)

    def _clear(self, layout):
        while layout.count():
            it = layout.takeAt(0)
            w = it.widget()
            if w:
                w.setParent(None)
                w.deleteLater()
            elif it.layout():
                self._clear(it.layout())

    def _section(self, text):
        lab = QLabel(text)
        role(lab, "muted")
        lab.setStyleSheet("font-weight: bold; margin-top: 8px;")
        self.body.addWidget(lab)

    def _grid(self, slots, cols=4):
        g = QGridLayout()
        g.setSpacing(6)
        for n, s in enumerate(slots):
            g.addWidget(_card(s["name"], s["rank"], s["max"], s["role"]), n // cols, n % cols)
        for c in range(cols):
            g.setColumnStretch(c, 1)
        self.body.addLayout(g)

    def show_loadout(self, lo):
        self._clear(self.body)
        if not lo:
            self.title.setText("")
            self.sub.setText(t("builds.pick"))
            return
        self.title.setText(f"{lo['item']}  ·  {t('builds.config', c=lo['config'])}")
        self.sub.setText(t("builds.kind." + lo["kind"]) + "  ·  " + t("builds.forma", n=lo["forma"]))
        slots = lo["slots"]
        special = [s for s in slots if s["role"] in ("aura", "exilus", "stance")]
        general = [s for s in slots if s["role"] == "general"]
        arcanes = [s for s in slots if s["role"] == "arcane"]
        if special:
            self._section(t("builds.sec.special"))
            self._grid(special, cols=3)
        self._section(t("builds.sec.mods"))
        self._grid(general)
        if arcanes:
            self._section(t("builds.sec.arcanes"))
            self._grid(arcanes, cols=2)
        if lo["kind"] == "warframe":
            self._section(t("builds.sec.shards"))
            row = QHBoxLayout()
            if lo["shards"]:
                for s in lo["shards"]:
                    pm = icons.shard(s["color"], s["tauforged"])
                    if pm:                                   # the picture already says colour and tauforged: effect only
                        icon = QLabel()
                        icon.setPixmap(pm)
                        row.addWidget(icon)
                        chip = QLabel(s["effect"])
                        rgb = None
                    else:
                        chip = QLabel(f"{t('builds.tau') + ' ' if s['tauforged'] else ''}{s['color_name']}\n{s['effect']}")
                        rgb = SHARD_RGB.get(s["color"], "#888888")
                    chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    if rgb:
                        chip.setStyleSheet(f"background: {rgb}; color: #101010; border-radius: 6px; padding: 5px 8px;"
                                           + (" border: 2px solid #ffd966;" if s["tauforged"] else ""))
                    row.addWidget(chip)
                row.addStretch(1)
            else:
                none = QLabel(t("builds.none"))
                role(none, "hint")
                row.addWidget(none)
            self.body.addLayout(row)
            self._section(t("builds.sec.helminth"))
            h = lo["helminth"]
            lab = QLabel(t("builds.helminth", slot=h["slot"], replaced=h["replaced"] or "?", ability=h["ability"])
                         if h else t("builds.none"))
            if not h:
                role(lab, "hint")
            self.body.addWidget(lab)


class PresetView(QWidget):
    """A game loadout as the in-game screen: Warframe and weapons, companion, Archwing and Necramech as big rows; click a row
    to see the mods, Arcanes, Archon Shards and Helminth of that item below."""

    def __init__(self):
        super().__init__()
        self.lay = QVBoxLayout(self)
        self.lay.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.title = QLabel("")
        self.title.setStyleSheet("font-size: 17px; font-weight: bold;")
        self.rows = QHBoxLayout()                       # three columns: Warframe + weapons | companion + Archwing | Necramech
        self.rows.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.detail = LoadoutView()
        self.lay.addWidget(self.title)
        self.lay.addLayout(self.rows)
        self.lay.addWidget(self.detail, 1)
        self._lookup, self._buttons = {}, []

    def _clear(self):
        def wipe(layout):
            while layout.count():
                it = layout.takeAt(0)
                w = it.widget()
                if w:
                    w.setParent(None)
                    w.deleteLater()
                elif it.layout():
                    wipe(it.layout())
        wipe(self.rows)
        self._buttons = []
        self.cols = []
        for _ in range(3):
            c = QVBoxLayout()
            c.setAlignment(Qt.AlignmentFlag.AlignTop)
            self.rows.addLayout(c, 1)
            self.cols.append(c)
        self.col = self.cols[0]

    def _head(self, text, col=None):
        if col is not None:
            self.col = self.cols[col]
        lab = QLabel(text)
        role(lab, "muted")
        lab.setStyleSheet("font-weight: bold; margin-top: 4px;")
        self.col.addWidget(lab)

    def _button(self, r, group):
        title = ((r.get("custom") + " ") if r.get("custom") and r["role"] not in ("companion",) else "") + r["item"]
        if r["role"] == "companion" and r.get("custom"):
            title = r["custom"]
        sub = t("builds.maxrank") if r["maxed"] else t("builds.rank1", n=r["rank"])
        if r["role"] == "companion" and r.get("custom"):
            sub = r["item"] + " · " + sub
        if (r["oid"], r["idx"]) in self._lookup:
            sub += "  ·  " + t("builds.config", c=LO.LETTERS[r["idx"]] if r["idx"] < 8 else r["idx"] + 1)
        btn = QPushButton(f"{title.upper()}\n{sub}")
        btn.setCheckable(True)
        btn.setStyleSheet("QPushButton { text-align: left; padding: 8px 12px; }")
        btn.setToolTip(t("builds.role." + r["role"]))
        btn.clicked.connect(lambda _c=False, rr=r: self._pick(rr))
        group.addButton(btn)
        self.col.addWidget(btn)
        self._buttons.append((btn, r))
        return btn

    def _pick(self, r):
        lo = self._lookup.get((r["oid"], r["idx"]))
        if lo:
            self.detail.show_loadout(lo)
        else:
            self.detail.show_loadout(None)
            self.detail.sub.setText(t("builds.nomods", item=r["item"]))

    def show_preset(self, preset, tenno, lookup):
        self._lookup = lookup
        self._clear()
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        if not preset:
            self.title.setText("")
            self.detail.show_loadout(None)
            return
        self.title.setText(("★ " if preset["favorite"] else "") + preset["name"])
        self._head(t("builds.tab.warframe"), 0)
        for r in preset["warframe"]:
            self._button(r, self.group)
        if preset["companion"]:
            self._head(t("builds.tab.companion"), 1)
            for r in preset["companion"]:
                self._button(r, self.group)
        for key, colno in (("archwing", 1), ("necramech", 2)):
            if tenno.get(key):
                self._head(t("builds.tab." + key), colno)
                for r in tenno[key]:
                    self._button(r, self.group)
        if self._buttons:
            self._buttons[0][0].setChecked(True)
            self._pick(self._buttons[0][1])


class BuildsTab(QWidget):
    def __init__(self, market, refresher, inventory):
        super().__init__()
        self.market, self.refresher, self.inventory = market, refresher, inventory
        self.loadouts, self.presets, self.source, self.when = [], {"presets": [], "tenno": {}}, "", 0
        self._mtime = 0
        self._shown = None
        self._tried_auto = False
        self._load_cache()

        self.btn_reload = QPushButton(t("builds.reload"))
        self.btn_reload.setToolTip(t("builds.reload.tip"))
        self.filter = QLineEdit()
        self.filter.setPlaceholderText(t("builds.filter"))
        self.kind = QComboBox()
        self.kind.addItem(t("builds.kind.all"), "")
        for k in KINDS:
            self.kind.addItem(t("builds.kind." + k), k)
        self.mode = QComboBox()
        self.mode.addItem(t("builds.mode.game"), "game")
        self.mode.addItem(t("builds.mode.items"), "items")
        bar = QHBoxLayout()
        bar.addWidget(self.mode)
        bar.addWidget(self.filter, 1)
        bar.addWidget(self.kind)
        bar.addWidget(self.btn_reload)
        self.summary = QLabel("")
        role(self.summary, "muted")
        self.summary.setWordWrap(True)

        self.list = QListWidget()
        self.list.setMinimumWidth(230)
        self.view = LoadoutView()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.view)
        split = QSplitter()
        split.addWidget(self.list)
        split.addWidget(scroll)
        split.setStretchFactor(1, 1)
        # the game's own loadouts (named, with Warframe, weapons, companion, Archwing, Necramech)
        self.plist = QListWidget()
        self.plist.setMinimumWidth(230)
        self.pview = PresetView()
        pscroll = QScrollArea()
        pscroll.setWidgetResizable(True)
        pscroll.setWidget(self.pview)
        psplit = QSplitter()
        psplit.addWidget(self.plist)
        psplit.addWidget(pscroll)
        psplit.setStretchFactor(1, 1)
        self.stack = QStackedWidget()
        self.stack.addWidget(psplit)
        self.stack.addWidget(split)
        lay = QVBoxLayout(self)
        lay.addLayout(bar)
        lay.addWidget(self.summary)
        lay.addWidget(self.stack, 1)
        self.mode.currentIndexChanged.connect(self._mode_changed)
        self.plist.currentItemChanged.connect(lambda cur, _p: self._show_preset(cur))

        self.btn_reload.clicked.connect(self.reload_file)
        self.filter.textChanged.connect(lambda _t: self._fill())
        self.kind.currentIndexChanged.connect(lambda _i: self._fill())
        self.list.currentItemChanged.connect(lambda cur, _p: self.view.show_loadout(
            self.loadouts[cur.data(Qt.ItemDataRole.UserRole)] if cur else None))
        self._mode_changed()
        self._fill()
        # pictures arrive a little later: redraw the shown loadout while some are still on their way
        self._pic_timer = QTimer(self, interval=2500, timeout=self._pictures)
        self._pic_timer.start()

    def _mode_changed(self):
        game = self.mode.currentData() == "game"
        self.stack.setCurrentIndex(0 if game else 1)
        self.filter.setVisible(not game)
        self.kind.setVisible(not game)
        self._summary()

    def _lookup(self):
        return {(lo.get("oid"), lo.get("idx")): lo for lo in self.loadouts if lo.get("oid")}

    def _fill_presets(self):
        cur = self.plist.currentRow()
        self.plist.blockSignals(True)
        self.plist.clear()
        for i, p in enumerate(self.presets.get("presets") or []):
            it = QListWidgetItem(("★ " if p["favorite"] else "") + p["name"])
            it.setData(Qt.ItemDataRole.UserRole, i)
            self.plist.addItem(it)
        self.plist.blockSignals(False)
        if self.plist.count():
            self.plist.setCurrentRow(max(0, min(cur, self.plist.count() - 1)))
        else:
            self.pview.show_preset(None, {}, {})

    def _show_preset(self, cur):
        if not cur:
            return
        self.pview.show_preset(self.presets["presets"][cur.data(Qt.ItemDataRole.UserRole)],
                               self.presets.get("tenno") or {}, self._lookup())

    def _summary(self):
        if not self.loadouts:
            self.summary.setText(t("builds.empty"))
        elif self.mode.currentData() == "game":
            self.summary.setText(t("builds.summary.game", n=len(self.presets.get("presets") or []),
                                   src=os.path.basename(self.source) or "–", when=age_text(self.when)))
        else:
            self.summary.setText(t("builds.summary", n=len(self.loadouts), shown=self.list.count(),
                                   src=os.path.basename(self.source) or "–", when=age_text(self.when)))

    def _pictures(self):
        n = previews.pending()
        if n != getattr(self, "_pending_seen", 0) and self.isVisible():
            cur = self.list.currentItem()
            if cur:
                self.view.show_loadout(self.loadouts[cur.data(Qt.ItemDataRole.UserRole)])
            if self.plist.currentItem():
                cur = self.plist.currentItem()
                b = self.pview.group.checkedButton() if hasattr(self.pview, "group") else None
                self._show_preset(cur)
                if b is not None:                       # keep the same row selected
                    for btn, r in self.pview._buttons:
                        if btn.text() == b.text():
                            btn.setChecked(True)
                            self.pview._pick(r)
        self._pending_seen = n

    # ---------- data ----------
    def _load_cache(self):
        try:
            d = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            if isinstance(d.get("loadouts"), list) and isinstance(d.get("presets"), dict):     # an older cache has no presets
                self.loadouts, self.presets = d["loadouts"], d["presets"]
                self.source, self.when = d.get("source", ""), d.get("time", 0)
        except Exception:
            pass

    def _save_cache(self):
        try:
            CACHE_FILE.write_text(json.dumps({"time": self.when, "source": self.source, "loadouts": self.loadouts,
                                                         "presets": self.presets},
                                             ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    def _find_file(self):
        path = self.inventory.path
        if not path or not os.path.exists(path):
            path = aleca.find_data_file()
        return path if path and os.path.exists(path) else ""

    def reload_file(self, silent=False):
        path = self._find_file()
        if not path:
            if not silent:
                QMessageBox.information(self, t("tab.builds"), t("builds.nofile"))
            return False
        try:
            data = LO.read_all_file(path)
        except (ValueError, OSError) as e:
            if not silent:
                QMessageBox.warning(self, t("tab.builds"), t("builds.fail", err=e))
            return False
        self.loadouts, self.presets = data["loadouts"], data["presets"]
        self.source, self.when = path, int(time.time())
        self._mtime = os.path.getmtime(path)
        self._save_cache()
        self._fill(keep=True)
        return True

    # ---------- showing ----------
    def _fill(self, keep=False):
        cur = None
        if keep and self.list.currentItem():
            lo = self.loadouts[self.list.currentItem().data(Qt.ItemDataRole.UserRole)] if self.list.currentItem() else None
            cur = (lo["item"], lo["config"]) if lo else None
        text, kind = self.filter.text().strip().lower(), self.kind.currentData()
        self.list.blockSignals(True)
        self.list.clear()
        sel_row = -1
        for i, lo in enumerate(self.loadouts):
            if kind and lo["kind"] != kind:
                continue
            if text and text not in lo["item"].lower():
                continue
            it = QListWidgetItem(f"{lo['item']}  ·  {lo['config']}")
            it.setData(Qt.ItemDataRole.UserRole, i)
            self.list.addItem(it)
            if cur == (lo["item"], lo["config"]):
                sel_row = self.list.count() - 1
        self.list.blockSignals(False)
        if self.list.count():
            self.list.setCurrentRow(sel_row if sel_row >= 0 else 0)
        else:
            self.view.show_loadout(None)
        self._fill_presets()
        self._summary()

    def set_busy(self, busy: bool):
        pass

    def refresh(self, force=False, select=None):
        """Called by the window's timer: first time, loads the game file by itself; later, only when it changed."""
        if not self._tried_auto and not (self.loadouts and self.presets.get("presets")):
            self._tried_auto = True
            self.reload_file(silent=True)
            return
        path = self.source if self.source and os.path.exists(self.source) else ""
        if path:
            try:
                m = os.path.getmtime(path)
            except OSError:
                return
            if self._mtime and m > self._mtime + 1 and force:
                self.reload_file(silent=True)
            elif not self._mtime:
                self._mtime = m
