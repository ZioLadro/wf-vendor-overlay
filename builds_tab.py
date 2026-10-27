"""Builds tab: your own in-game loadouts, laid out like the game's screen (slots, Arcanes, Archon Shards, Helminth)."""
import json
import os
import time

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
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
    pic = previews.by_name(name) if name else None
    if pic:                                               # the mod/Arcane card picture (warframe.market, else the wiki)
        img = QLabel()
        pm = QPixmap(str(pic))
        if not pm.isNull():
            img.setPixmap(pm.scaledToHeight(52, Qt.TransformationMode.SmoothTransformation))
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
            if it.widget():
                it.widget().deleteLater()
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
                    chip = QLabel(f"{t('builds.tau') + ' ' if s['tauforged'] else ''}{s['color_name']}\n{s['effect']}")
                    chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    pm = icons.shard(s["color"], s["tauforged"])
                    if pm:
                        icon = QLabel()
                        icon.setPixmap(pm)
                        row.addWidget(icon)
                    rgb = SHARD_RGB.get(s["color"], "#888888")
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


class BuildsTab(QWidget):
    def __init__(self, market, refresher, inventory):
        super().__init__()
        self.market, self.refresher, self.inventory = market, refresher, inventory
        self.loadouts, self.source, self.when = [], "", 0
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
        bar = QHBoxLayout()
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
        lay = QVBoxLayout(self)
        lay.addLayout(bar)
        lay.addWidget(self.summary)
        lay.addWidget(split, 1)

        self.btn_reload.clicked.connect(self.reload_file)
        self.filter.textChanged.connect(lambda _t: self._fill())
        self.kind.currentIndexChanged.connect(lambda _i: self._fill())
        self.list.currentItemChanged.connect(lambda cur, _p: self.view.show_loadout(
            self.loadouts[cur.data(Qt.ItemDataRole.UserRole)] if cur else None))
        self._fill()
        # pictures arrive a little later: redraw the shown loadout while some are still on their way
        self._pic_timer = QTimer(self, interval=2500, timeout=self._pictures)
        self._pic_timer.start()

    def _pictures(self):
        n = previews.pending()
        if n != getattr(self, "_pending_seen", 0) and self.isVisible():
            cur = self.list.currentItem()
            if cur:
                self.view.show_loadout(self.loadouts[cur.data(Qt.ItemDataRole.UserRole)])
        self._pending_seen = n

    # ---------- data ----------
    def _load_cache(self):
        try:
            d = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            if isinstance(d.get("loadouts"), list):
                self.loadouts, self.source, self.when = d["loadouts"], d.get("source", ""), d.get("time", 0)
        except Exception:
            pass

    def _save_cache(self):
        try:
            CACHE_FILE.write_text(json.dumps({"time": self.when, "source": self.source, "loadouts": self.loadouts},
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
            los = LO.read_file(path)
        except (ValueError, OSError) as e:
            if not silent:
                QMessageBox.warning(self, t("tab.builds"), t("builds.fail", err=e))
            return False
        self.loadouts, self.source, self.when = los, path, int(time.time())
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
        self.summary.setText(
            t("builds.summary", n=len(self.loadouts), shown=self.list.count(), src=os.path.basename(self.source) or "–",
              when=age_text(self.when)) if self.loadouts else t("builds.empty"))

    def set_busy(self, busy: bool):
        pass

    def refresh(self, force=False, select=None):
        """Called by the window's timer: first time, loads the game file by itself; later, only when it changed."""
        if not self._tried_auto and not self.loadouts:
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
