"""Builds tab: your own in-game loadouts, laid out like the game's screen (slots, Arcanes, Archon Shards, Helminth)."""
import json
import os
import time

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QButtonGroup, QComboBox, QFrame, QStackedWidget, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
    QPushButton, QScrollArea, QSplitter, QVBoxLayout, QWidget,
)

from app.game import aleca
from app.ui import icons
from app.ui import previews
from app.ui.buildcards import Scaler
from app.ui.buildscreen import BuildScreen, land_width
from app.ui.planner_tab import PlannerView
from app.game import loadouts as LO
from app.core.config import APP_DIR
from app.core.i18n import t
from app.core.uiutil import age_text, role

CACHE_FILE = APP_DIR / "loadouts.json"
from app.core.version import __version__
# the saved loadouts are read again from the game file after every program update (new fields, fixed calculations):
# 0.2.9 added spliced Rivens and exalted weapons but kept the old copy, so they did not show until the file changed
CACHE_VER = f"6-{__version__}"
KINDS = ["warframe", "primary", "secondary", "melee", "exalted", "archwing", "archgun", "archmelee", "necramech", "companion", "compweapon"]
SHARD_RGB = {"RED": "#c8453c", "BLUE": "#3b8fd9", "GREEN": "#3fbf6a", "YELLOW": "#e0b83a", "ORANGE": "#e08a3a",
             "PURPLE": "#a46be0"}


THUMB = 40


_thumbs = {}


def thumb(name, size=THUMB):
    """Picture of a Warframe / weapon / companion from the Warframe wiki (None until it is downloaded). Kept in memory once
    loaded, so redrawing the lists does not read and scale the files again."""
    key = (name, size)
    if key in _thumbs:
        return _thumbs[key]
    f = previews.by_name(name, wiki_only=True) if name else None
    if not f:
        return None
    pm = QPixmap(str(f))
    if pm.isNull():
        return None
    pm = pm.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    _thumbs[key] = pm
    return pm


def prefetch_names(loadouts, presets) -> list:
    """Every name the Builds tab shows a picture for: the mods of your loadouts and the items themselves (Arcanes use the
    generic pictures of the icons folder, Rivens have none)."""
    names = []
    for lo in loadouts:
        names.append(lo["item"])
        mods = [s["name"] for s in lo["slots"] if s["name"] and s["role"] != "arcane" and not s.get("riven")]
        names += mods
        for m in mods:                                   # the artwork shown inside the cards
            previews.by_name(m, kind="art")
    for p in (presets or {}).get("presets") or []:
        names += [r["item"] for r in p.get("warframe", []) + p.get("companion", [])]
    for rows in ((presets or {}).get("tenno") or {}).values():
        names += [r["item"] for r in rows]
    return names


def _perk_stats(lo):
    """The chosen Incarnon perks of a loadout's weapon, as stats (None without an installed / built-in Incarnon)."""
    from app.game import incarnon as INC
    inc = lo.get("incarnon")
    if not inc or inc.get("kind") not in ("genesis", "builtin"):
        return None
    skill = inc.get("skill") or ""
    return INC.bonuses(inc["page"], [int(c) if c.isdigit() else 0 for c in skill[:5]],
                       max(int(inc.get("evo") or 0), len(skill)), lo["item"])


class LoadoutView(QWidget):
    """The selected loadout, laid out like the game's upgrade screen (buildscreen.py), with the Archon Shards and the
    Helminth ability under it. "Simulate in the planner" opens the item in the build planner."""

    def __init__(self):
        super().__init__()
        self.lay = QVBoxLayout(self)
        self.lay.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.empty = QLabel(t("builds.pick"))
        role(self.empty, "muted")
        self.screen = BuildScreen(editable=False)
        self.screen.config_selected.connect(self._config_clicked)
        self.body = QVBoxLayout()
        self.lay.addWidget(self.empty)
        self.lay.addWidget(self.screen)
        self.lay.addLayout(self.body)
        self.lay.addStretch(1)
        self.lookup = {}                                 # (item id, config index) -> loadout, set by the owner (config buttons)
        self.on_simulate = None                          # set by the Builds tab: opens a loadout in the planner
        self._lo = None
        self.scaler = Scaler(self, lambda: self.show_loadout(self._lo), fn=land_width, start=200)
        # kept for the callers that set a text when nothing is shown
        self.sub = self.empty

    def _clear(self, layout):
        while layout.count():
            it = layout.takeAt(0)
            w = it.widget()
            if w:
                w.hide()
                w.deleteLater()
            elif it.layout():
                self._clear(it.layout())

    def _section(self, text, icon=None):
        lab = QLabel(text.upper())
        lab.setStyleSheet("font-weight: bold; letter-spacing: 1px; margin-top: 10px;")
        pm = icons.build(icon, 22) if icon else None
        if pm is None:
            self.body.addWidget(lab)
            return
        row = QHBoxLayout()                              # AlecaFrame's picture of the section (shards, Helminth)
        pic = QLabel()
        pic.setPixmap(pm)
        pic.setStyleSheet("margin-top: 10px;")
        row.addWidget(pic)
        row.addWidget(lab)
        row.addStretch(1)
        self.body.addLayout(row)

    def _copy_data(self, lo):
        """The item as the game file has it and as the program reads it, to the clipboard (to report a capacity that
        differs from the game's)."""
        from PyQt6.QtWidgets import QApplication
        out = {"item": lo["item"], "kind": lo["kind"], "config": lo.get("cfg_name") or lo["config"], "level": lo.get("level"),
               "reactor": lo.get("reactor"), "reactor_src": lo.get("reactor_src"), "capacity": lo.get("capacity"),
               "slots": [{k: s.get(k) for k in ("role", "name", "rank", "max", "pol", "pol_src", "mpol", "drain")}
                         for s in lo["slots"]], "file": lo.get("raw")}
        QApplication.clipboard().setText(json.dumps(out, ensure_ascii=False, indent=1))
        self.empty.setText(t("bs.copydata.done"))
        self.empty.show()

    def _config_clicked(self, i):
        lo = self._lo
        cfgs = (lo or {}).get("configs") or []
        if lo and 0 <= i < len(cfgs):
            self._switch(lo, cfgs[i]["idx"])

    def _switch(self, lo, idx):
        target = self.lookup.get((lo.get("oid"), idx))
        if target:
            self.show_loadout(target)

    def showEvent(self, e):
        super().showEvent(e)
        self.scaler.attach()

    def show_loadout(self, lo):
        self.setUpdatesEnabled(False)                  # rebuilt in one go: no flashing half-drawn cards
        try:
            self._show(lo)
        finally:
            self.setUpdatesEnabled(True)

    @staticmethod
    def model(lo) -> dict:
        """A loadout read from the game file as the screen's model."""
        from app.game import buildcalc as BC
        from app.game import incarnon as INC
        from app.ui.buildscreen import incarnon_model, wf_base_stats
        ex = lo.get("extras") or {}
        what = t("builds.catalyst") if lo["kind"] in ("primary", "secondary", "melee", "archgun", "archmelee", "compweapon") else t("builds.reactor.name")
        if lo.get("reactor"):
            pot = t("builds.pot.yes" if lo.get("reactor_src") != "guess" else "builds.pot.guess", what=what)
        elif lo.get("reactor_src") == "unknown":
            pot = t("builds.pot.unknown", what=what)
        else:
            pot = t("builds.pot.no", what=what)
        kind_txt = t("builds.kind." + lo["kind"]) + (f" ({lo['owner']})" if lo.get("owner") else "")
        sub = (kind_txt + ("" if lo["kind"] == "exalted" else "  ·  " + pot)
               + (f"  ·  {t('builds.valence', el=ex['valence']['element'], pct=ex['valence']['pct'])}" if ex.get("valence") else "")
               + (f"  ·  ◈ {ex['lens']}" if ex.get("lens") else "")
               + ("  ·  " + t("builds.gilded") if ex.get("gilded") else ""))
        unlocked = [t(k) for k, on in (("builds.exilus_on", ex.get("exilus")), ("builds.arcane_on", ex.get("arcane_slot")),
                                       ("builds.valence_swap", ex.get("valence_swap"))) if on]
        cfgs = [{"label": c.get("name") or t("builds.cfg.default", c=c["config"]), "active": c["idx"] == lo["idx"],
                 "tip": t("builds.config", c=c["config"])} for c in lo.get("configs") or []]
        weapons = ("primary", "secondary", "melee", "archgun", "archmelee", "compweapon")
        m = {"kind": lo["kind"], "item": lo["item"], "title": lo["item"] + (f"  “{ex['custom']}”" if ex.get("custom") else ""),
             "rank": lo.get("level"), "forma": lo.get("forma"), "configs": cfgs if len(cfgs) > 1 else
             [{"label": lo.get("cfg_name") or t("builds.cfg.default", c=lo["config"]), "active": True}],
             "slots": lo["slots"], "capacity": lo.get("capacity"), "capacity_none": lo.get("capacity") is None,
             "level": lo.get("level", 30), "reactor": lo.get("reactor", True), "wf_stats": lo.get("stats") or {},
             "wf_base": wf_base_stats(lo["item"]) if lo["kind"] == "warframe" else {},
             "weapon": BC.weapon_stats(lo["kind"], lo["item"], lo.get("bonus") or {}, lo.get("elements") or [], ex.get("valence"),
                             lo.get("flat"), _perk_stats(lo))
             if lo["kind"] in weapons else None,
             "bonus": lo.get("bonus") or {}, "valence": ex.get("valence"), "unique": bool(ex.get("valence")),
             "subtitle": sub, "subtitle_tip": t("builds.pot.tip") + ("\n" + ", ".join(unlocked) if unlocked else ""),
             "pic": thumb(lo["item"], 48),
             "upgrades": __import__("app.ui.planner_tab", fromlist=["x"]).upgrade_icons(
                 lo["kind"], lo.get("reactor"),
                 bool(ex.get("exilus")) or any(s_.get("name") for s_ in lo["slots"] if s_["role"] == "exilus")
                 if any(s_["role"] == "exilus" for s_ in lo["slots"]) and "exilus" in ex else None,
                 bool(ex.get("arcane_slot")) or any(s_.get("name") for s_ in lo["slots"] if s_["role"] == "arcane")
                 if any(s_["role"] == "arcane" for s_ in lo["slots"]) and "arcane_slot" in ex else None),
             # an empty Arcane slot of a weapon without its Arcane adapter (game file) is drawn locked
             "locked": {"arcane": lo["kind"] in weapons and "arcane_slot" in ex and not ex["arcane_slot"]
                        and not any(s_.get("name") for s_ in lo["slots"] if s_["role"] == "arcane")}}
        inc = lo.get("incarnon")
        if inc:
            head, _lines = INC.describe(inc, t)
            if inc["kind"] == "available":
                m["incarnon"] = {"head": head, "note": t("bs.inc.elsewhere"), "show_path": False}
            else:
                skill = inc.get("skill") or ""
                m["incarnon"] = incarnon_model(inc["kind"], inc["page"], [int(c) if c.isdigit() else 0 for c in skill[:5]],
                                               max(inc.get("evo") or 0, len(skill)), head=head)
        return m

    def _show(self, lo):
        self._lo = lo
        self._clear(self.body)
        if not lo:
            self.screen.clear()
            self.empty.setText(t("builds.pick"))
            self.empty.show()
            return
        self.empty.hide()
        self.screen.show_model(self.model(lo), self.scaler.cw)
        if self.on_simulate and lo["kind"] in ("warframe", "primary", "secondary", "melee", "companion", "archwing",
                                               "archgun", "archmelee", "compweapon"):
            row = QHBoxLayout()
            b = QPushButton("⚙ " + t("bs.simulate"))
            b.setToolTip(t("bs.simulate.tip"))
            b.clicked.connect(lambda: self.on_simulate(lo))
            row.addWidget(b)
            c = QPushButton("⧉ " + t("bs.copydata"))
            c.setToolTip(t("bs.copydata.tip"))
            c.clicked.connect(lambda: self._copy_data(lo))
            row.addWidget(c)
            row.addStretch(1)
            self.body.addLayout(row)
        if lo["kind"] == "warframe":
            self._section(t("builds.sec.shards"), "shards")
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
            self._section(t("builds.sec.helminth"), "helminth")
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
                    w.hide()
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
        lo = self._lookup.get((r["oid"], r["idx"]))
        if lo:
            sub += "  ·  " + (lo.get("cfg_name") or t("builds.config", c=lo["config"]))
        btn = QPushButton(f"{title.upper()}\n{sub}")
        pm = thumb(r["item"])
        if pm is not None:                                   # the item's picture (Warframe wiki)
            btn.setIcon(QIcon(pm))
            btn.setIconSize(pm.size())
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
        if getattr(self, "group", None) is not None:
            self.group.setParent(None)
            self.group.deleteLater()
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
        self.owned = {}                               # mods and Arcanes you own (the planner's library)
        self._mtime = 0
        self._shown = None
        self._tried_auto = False
        self._load_cache()
        QTimer.singleShot(4000, self._startup_pictures)

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
        self.mode.addItem(t("builds.mode.plan"), "plan")
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
        self.planner = PlannerView(lambda: self.loadouts, lambda: self.presets, lambda: self.owned)
        self.view.on_simulate = self.simulate
        self.pview.detail.on_simulate = self.simulate
        self.stack.addWidget(self.planner)
        lay = QVBoxLayout(self)
        lay.addLayout(bar)
        lay.addWidget(self.summary)
        lay.addWidget(self.stack, 1)
        self.mode.currentIndexChanged.connect(self._mode_changed)
        self.plist.currentItemChanged.connect(lambda cur, _p: self._show_preset(cur))

        self.btn_reload.clicked.connect(self.reload_file)
        self.filter.textChanged.connect(lambda _t: self._fill())
        self.kind.currentIndexChanged.connect(lambda _i: self._fill())
        self.list.currentItemChanged.connect(self._list_pick)
        self._mode_changed()
        self._fill()
        # pictures arrive a little later: redraw the shown loadout while some are still on their way
        self._pic_timer = QTimer(self, interval=2500, timeout=self._pictures)
        self._pic_timer.start()

    def showEvent(self, e):
        super().showEvent(e)
        self._pic_timer.start()

    def hideEvent(self, e):
        super().hideEvent(e)
        self._pic_timer.stop()                         # nothing to redraw while the tab is not on screen

    def _mode_changed(self):
        mode = self.mode.currentData()
        self.stack.setCurrentIndex({"game": 0, "items": 1, "plan": 2}[mode])
        self.filter.setVisible(mode == "items")
        self.kind.setVisible(mode == "items")
        self.btn_reload.setVisible(mode != "plan")
        self._summary()

    def simulate(self, lo):
        """Opens one of your items in the build planner (all its configurations), to try changes on it."""
        self.planner.copy_item(lo, f"{lo['item']} · {lo.get('cfg_name') or lo['config']}")
        self.mode.setCurrentIndex(self.mode.findData("plan"))

    def _startup_pictures(self):
        """At start: reads the game file if nothing is saved yet, then asks the wiki for the pictures still missing (the mods
        of your loadouts and the items), in the background, one at a time."""
        if not self.loadouts:
            self._tried_auto = True
            self.reload_file(silent=True)
        previews.prefetch(prefetch_names(self.loadouts, self.presets))

    def _list_pick(self, cur, _prev=None):
        idx = cur.data(Qt.ItemDataRole.UserRole) if cur is not None else None
        self._lookup()
        self.view.show_loadout(self.loadouts[idx] if idx is not None and 0 <= idx < len(self.loadouts) else None)

    def _lookup(self):
        d = {(lo.get("oid"), lo.get("idx")): lo for lo in self.loadouts if lo.get("oid")}
        self.view.lookup = d
        self.pview.detail.lookup = d
        return d

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
        if self.mode.currentData() == "plan":
            self.summary.setText("")
        elif not self.loadouts:
            self.summary.setText(t("builds.empty"))
        elif self.mode.currentData() == "game":
            self.summary.setText(t("builds.summary.game", n=len(self.presets.get("presets") or []),
                                   src=os.path.basename(self.source) or "–", when=age_text(self.when)))
        else:
            self.summary.setText(t("builds.summary", n=len(self.loadouts), shown=sum(1 for i in range(self.list.count()) if self.list.item(i).data(Qt.ItemDataRole.UserRole) is not None),
                                   src=os.path.basename(self.source) or "–", when=age_text(self.when)))

    def _pictures(self):
        """Pictures arrive from the wiki in the background: when some came in, put them where they are missing, without
        rebuilding the lists (rebuilding everything every few seconds made the window flash)."""
        n = previews.pending()
        now = time.monotonic()
        if n == getattr(self, "_pending_seen", 0) or not self.isVisible() or now - getattr(self, "_pics_at", 0) < 5:
            return
        self._pending_seen, self._pics_at = n, now
        self.setUpdatesEnabled(False)
        try:
            mode = self.mode.currentData()
            if mode == "items":
                for i in range(self.list.count()):
                    it = self.list.item(i)
                    idx = it.data(Qt.ItemDataRole.UserRole)
                    if idx is not None and it.icon().isNull():
                        pm = thumb(self.loadouts[idx]["item"], 28)
                        if pm is not None:
                            it.setIcon(QIcon(pm))
                self.view.show_loadout(self.view._lo)
            elif mode == "game":
                for btn, r in self.pview._buttons:
                    if btn.icon().isNull():
                        pm = thumb(r["item"])
                        if pm is not None:
                            btn.setIcon(QIcon(pm))
                            btn.setIconSize(pm.size())
                self.pview.detail.show_loadout(self.pview.detail._lo)
            else:
                self.planner._draw()
        finally:
            self.setUpdatesEnabled(True)

    # ---------- data ----------
    def _load_cache(self):
        try:
            d = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            if d.get("ver") == CACHE_VER and isinstance(d.get("loadouts"), list) and isinstance(d.get("presets"), dict):
                self.loadouts, self.presets = d["loadouts"], d["presets"]
                self.owned = d.get("owned") or {}
                self.source, self.when = d.get("source", ""), d.get("time", 0)
        except Exception:
            pass

    def _save_cache(self):
        try:
            CACHE_FILE.write_text(json.dumps({"ver": CACHE_VER, "time": self.when, "source": self.source, "loadouts": self.loadouts,
                                                         "presets": self.presets, "owned": self.owned},
                                             ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    def _find_file(self):
        path = self.inventory.path
        if not path or not os.path.exists(path):
            path = aleca.find_data_file()
        return path if path and os.path.exists(path) else ""

    @staticmethod
    def work_file(path, data):
        """Background thread: loadouts and presets from the parsed game file."""
        return {"path": path, "loadouts": LO.read(data), "presets": LO.presets(data), "owned": LO.owned_mods(data)}

    def apply_file(self, d):
        self.loadouts, self.presets = d["loadouts"], d["presets"]
        self.owned = d.get("owned") or self.owned
        self.source, self.when = d["path"], int(time.time())
        try:
            self._mtime = os.path.getmtime(d["path"])
        except OSError:
            pass
        self._tried_auto = True
        self._save_cache()
        from app.core import logbus
        logbus.add("builds", f"{len(self.loadouts)} loadouts read from {os.path.basename(d['path'])}", "ok")
        if self.isVisible():
            self._fill(keep=True)
        else:
            self._stale = True
        previews.prefetch(prefetch_names(self.loadouts, self.presets))

    def reload_file(self, silent=False):
        path = self._find_file()
        if not path:
            if not silent:
                QMessageBox.information(self, t("tab.builds"), t("builds.nofile"))
            return False
        from app.core import logbus
        try:
            data = LO.read_all_file(path)
            logbus.add("builds", f"{len(data['loadouts'])} loadouts read from {os.path.basename(path)}", "ok")
        except (ValueError, OSError) as e:
            logbus.error("builds", f"cannot read {os.path.basename(path)}: {e}")
            if not silent:
                QMessageBox.warning(self, t("tab.builds"), t("builds.fail", err=e))
            return False
        self.loadouts, self.presets = data["loadouts"], data["presets"]
        self.owned = data.get("owned") or {}
        self.source, self.when = path, int(time.time())
        self._mtime = os.path.getmtime(path)
        self._save_cache()
        self._fill(keep=True)
        previews.prefetch(prefetch_names(self.loadouts, self.presets))
        return True

    # ---------- showing ----------
    def _fill(self, keep=False):
        """The list on the left, grouped by kind (Warframes, primaries, secondaries, melee, companions…) with a header per
        group and the item's picture when it is there."""
        cur = None
        if keep and self.list.currentItem() is not None and self.list.currentItem().data(Qt.ItemDataRole.UserRole) is not None:
            lo = self.loadouts[self.list.currentItem().data(Qt.ItemDataRole.UserRole)]
            cur = (lo.get("oid"), lo.get("idx"), lo["item"], lo["config"])
        text, kind = self.filter.text().strip().lower(), self.kind.currentData()
        self.list.blockSignals(True)
        self.list.clear()
        sel_row = first = -1
        order = {k: n for n, k in enumerate(KINDS)}
        shown = sorted((i for i, lo in enumerate(self.loadouts)
                        if (not kind or lo["kind"] == kind) and (not text or text in lo["item"].lower())),
                       key=lambda i: (order.get(self.loadouts[i]["kind"], 99), self.loadouts[i]["item"].lower(),
                                      self.loadouts[i]["config"]))
        last_kind = None
        for i in shown:
            lo = self.loadouts[i]
            if lo["kind"] != last_kind:                 # group header (not selectable)
                last_kind = lo["kind"]
                head = QListWidgetItem(t("builds.kind." + lo["kind"]).upper())
                head.setFlags(Qt.ItemFlag.NoItemFlags)
                f = head.font()
                f.setBold(True)
                head.setFont(f)
                self.list.addItem(head)
            it = QListWidgetItem(f"{lo['item']}  ·  {lo.get('cfg_name') or lo['config']}")
            it.setData(Qt.ItemDataRole.UserRole, i)
            pm = thumb(lo["item"], 28)
            if pm is not None:
                it.setIcon(QIcon(pm))
            self.list.addItem(it)
            row = self.list.count() - 1
            if first < 0:
                first = row
            if cur and (cur[:2] == (lo.get("oid"), lo.get("idx")) if cur[0] else cur[2:] == (lo["item"], lo["config"])):
                sel_row = row
        self.list.blockSignals(False)
        if first >= 0:
            self.list.setCurrentRow(sel_row if sel_row >= 0 else first)
        else:
            self.view.show_loadout(None)
        self._fill_presets()
        self._summary()

    def set_busy(self, busy: bool):
        pass

    def refresh(self, force=False, select=None):
        """Called by the window's timer: first time, loads the game file by itself; later, only when it changed."""
        from app.game import incarnon as INC
        if INC.done_count != getattr(self, "_inc_seen", 0) and self.isVisible():   # Incarnon perk names arrived
            self._inc_seen = INC.done_count
            if self.mode.currentData() == "items":
                self.view.show_loadout(self.view._lo)
            elif self.mode.currentData() == "game":
                self.pview.detail.show_loadout(self.pview.detail._lo)
        # the game file is watched and read in the background (app/game/gamefile.py -> apply_file); here only what was
        # read while the tab was hidden is shown
        if getattr(self, "_stale", False):
            self._stale = False
            self._fill(keep=True)
