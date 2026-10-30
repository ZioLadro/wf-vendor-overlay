"""Build planner (Builds > Build planner): a simulator of the game's upgrade screen.

Pick a Warframe, weapon, companion or companion weapon, then do what the game lets you do: put mods and Arcanes in the
slots (click a card of the library at the bottom, or drag it onto a slot), change a slot's polarity (Forma: right-click a
slot), set the rank, install an Orokin Reactor / Catalyst, an Exilus or Arcane adapter, an Incarnon Genesis (and choose
the perk of every evolution tier), change the bonus element of a Kuva / Tenet / Coda weapon (Valence Fusion), keep several
configurations (A, B, C…). Capacity, Forma count and the stats follow every change.

A plan is a whole loadout (Warframe, weapons, companion…) saved in build_plans.json; it can start as a copy of one of your
own in-game loadouts or items."""
import json
import re

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMenu, QMessageBox,
    QPushButton, QScrollArea, QSizePolicy, QSpinBox, QVBoxLayout, QWidget,
)

from app.game import buildcalc as BC
from app.game import incarnon as INC
from app.game import loadouts as LO
from app.ui import abilitybar as AB
from app.ui import icons
from app.ui.buildcards import Scaler
from app.ui.buildscreen import BuildScreen, ModLibrary, incarnon_model, land_width, wf_base_stats
from app.core.config import APP_DIR
from app.core.i18n import t
from app.core.uiutil import role

PLANS_FILE = APP_DIR / "build_plans.json"
KINDS = ("warframe", "primary", "secondary", "melee", "companion", "compweapon", "archwing", "archgun", "archmelee")
GUNS = ("primary", "secondary", "archgun")
WEAPONS = ("primary", "secondary", "melee", "archgun", "archmelee", "compweapon")
INNATE = "__innate__"                                 # slot polarity as the game has it (no Forma change)
LETTERS = "ABCDEFGH"
_PREFIX = re.compile(r"^(Primed|Amalgam|Umbral|Archon|Flawed|Galvanized)\s+", re.I)


def arcane_max(name: str) -> int:
    for n, mx in LO.data().get("arcanes", {}).values():
        if n == name:
            return mx or 5
    return 5


def _icon(widget, key):
    """AlecaFrame's picture of an upgrade on a switch, when the icons folder is there."""
    pm = icons.build(key, 20)
    if pm is not None:
        widget.setIcon(QIcon(pm))


def upgrade_icons(kind, reactor, exilus=None, arcane=None) -> list:
    """The upgrades shown by the title (AlecaFrame's pictures), lit when installed: [(picture key, on, tooltip)].
    exilus / arcane None: the item has no such slot."""
    weapon = kind in WEAPONS
    out = [("catalyst" if weapon else "reactor", bool(reactor),
            t("builds.catalyst") if weapon else t("builds.reactor.name"))]
    if exilus is not None:
        out.append(("exilus_adapter", bool(exilus), t("bs.opt.exilus")))
    if arcane is not None and kind in ("primary", "secondary"):
        out.append(("primary_arcane" if kind == "primary" else "secondary_arcane", bool(arcane), t("bs.opt.arcane")))
    return [(k, on, tip + " · " + t("bs.up.on" if on else "bs.up.off")) for k, on, tip in out]


def share_actions(menu, parent, get_piece, get_screen, get_title):
    """Adds the four ways to share a build to a menu: copy the code, save a .wfbuild file, save / copy the picture.
    get_piece() -> (kind, piece); get_screen() -> the build screen widget; get_title() -> (title, subtitle)."""
    from app.ui import buildshare as S

    def code():
        k, p = get_piece()
        S.copy_text(S.encode(k, p))
        QMessageBox.information(parent, t("share.code"), t("share.code.done"))

    def file():
        from PyQt6.QtWidgets import QFileDialog
        k, p = get_piece()
        path, _ = QFileDialog.getSaveFileName(parent, t("share.file"), f"{p['item']}.wfbuild", S.FILE_FILTER)
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(S.to_json(k, p), fh, ensure_ascii=False, indent=1)

    def picture(save):
        title, sub = get_title()
        img = S.image(get_screen(), title, sub)
        if not save:
            S.copy_image(img)
            QMessageBox.information(parent, t("share.image"), t("share.image.done"))
            return
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(parent, t("share.image"), f"{title}.png", "PNG (*.png)")
        if path:
            img.save(path if path.lower().endswith(".png") else path + ".png", "PNG")
    menu.addAction(t("share.code"), code)
    menu.addAction(t("share.file"), file)
    menu.addAction(t("share.image"), lambda: picture(True))
    menu.addAction(t("share.image.copy"), lambda: picture(False))


def ocr_picture(parent, from_clipboard: bool, title: str, done, say=lambda _t: None):
    """Reads a picture's text with the OCR in the background (a file chosen, or the clipboard's picture);
    done((lines, w, h, path)) or done(error text), in the GUI thread."""
    from PyQt6.QtCore import QObject, pyqtSignal as _sig
    from PyQt6.QtGui import QGuiApplication
    from PyQt6.QtWidgets import QFileDialog
    if from_clipboard:
        img = QGuiApplication.clipboard().image()
        if img.isNull():
            return
        path = str(APP_DIR / "import_picture.png")
        img.save(path, "PNG")
    else:
        path, _ = QFileDialog.getOpenFileName(parent, title, "", "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
        if not path:
            return
    say(t("share.image.reading"))

    class _Done(QObject):
        sig = _sig(object)
    holder = _Done()
    holder.sig.connect(lambda res: (done(res), setattr(parent, "_ocr_holder", None)))
    parent._ocr_holder = holder                         # kept alive until the answer arrives

    def work():
        try:
            import app.scan.ocr_worker as OW
            if OW.CLIENT is not None:
                lines, w, h = OW.CLIENT.read_image(path)
            else:
                import numpy as np
                from PIL import Image
                from app.scan.ocr import make_engine, read_lines
                im = Image.open(path).convert("RGB")
                ls = read_lines(np.array(im)[:, :, ::-1].copy(), make_engine())
                lines, w, h = [(x.text, x.x, x.y, x.w, x.h, x.score) for x in ls], im.width, im.height
            holder.sig.emit((lines, w, h, path))
        except Exception as e:
            holder.sig.emit(f"{type(e).__name__}: {e}")
    import threading
    threading.Thread(target=work, daemon=True, name="picture-ocr").start()


def loadout_share_actions(menu, parent, get_loadout, get_images):
    """A whole loadout (Warframe, weapons, companion…): code, .wfloadout file, one picture of every piece.
    get_loadout() -> (name, {kind: piece}); get_images() -> [QImage of each piece] (buildshare.image)."""
    from app.ui import buildshare as S
    from PyQt6.QtWidgets import QFileDialog

    def code():
        name, pieces = get_loadout()
        S.copy_text(S.encode_loadout(name, pieces))
        QMessageBox.information(parent, t("share.loadout"), t("share.code.done"))

    def file():
        name, pieces = get_loadout()
        path, _ = QFileDialog.getSaveFileName(parent, t("share.file"), f"{name or 'loadout'}.wfloadout", S.LOADOUT_FILTER)
        if path:
            with open(path if path.lower().endswith((".wfloadout", ".json")) else path + ".wfloadout", "w",
                      encoding="utf-8") as fh:
                json.dump(S.loadout_json(name, pieces), fh, ensure_ascii=False, indent=1)

    def picture(save):
        name, _pieces = get_loadout()
        img = S.stack(get_images())
        if img.isNull():
            return
        if not save:
            S.copy_image(img)
            QMessageBox.information(parent, t("share.image"), t("share.image.done"))
            return
        path, _ = QFileDialog.getSaveFileName(parent, t("share.image"), f"{name or 'loadout'}.png", "PNG (*.png)")
        if path:
            img.save(path if path.lower().endswith(".png") else path + ".png", "PNG")
    sub = menu.addMenu(t("share.loadout"))
    sub.setToolTipsVisible(True)
    sub.addAction(t("share.code"), code)
    sub.addAction(t("share.file.loadout"), file)
    sub.addAction(t("share.image"), lambda: picture(True))
    sub.addAction(t("share.image.copy"), lambda: picture(False))
    return sub


def mod_family(name: str) -> str:
    """Mods the game does not let you equip together share this: Vitality, Primed Vitality, Umbral / Archon Vitality."""
    return _PREFIX.sub("", name or "").strip().lower()


def new_piece(kind: str, item: str) -> dict:
    """A piece of the loadout as it comes out of the Foundry, with the usual upgrades installed."""
    roles = BC.plan_roles(kind, item)
    inc = INC.available(item) if kind in ("primary", "secondary", "melee") else None
    return {"item": item, "configs": [{"mods": [None] * len(roles)}], "cfg": 0, "forma": {}, "reactor": True,
            "level": LO.max_rank(item, kind), "exilus": True, "arcane": True,
            "incarnon": {"on": bool(inc and inc["kind"] == "builtin"), "evo": 5, "perks": [0, 0, 0, 0, 0]},
            "valence": {"element": "Toxin", "pct": 60.0} if BC.valence_capable(item) else None,
            "shards": [None] * 5 if kind == "warframe" else []}


def upgrade_piece(p: dict, kind: str) -> dict:
    """A piece saved by an older version ({"item","mods","forma","reactor","level"}) in today's form."""
    if "configs" in p:
        p = dict(p)
        p["forma"] = {int(k): v for k, v in (p.get("forma") or {}).items()}
        p["configs"] = [dict(c, mods=[tuple(m) if m else None for m in c.get("mods") or []]) for c in p["configs"]]
        return p
    q = new_piece(kind, p.get("item", ""))
    q["configs"] = [{"mods": [tuple(m) if m else None for m in p.get("mods") or []]}]
    q["forma"] = {int(k): v for k, v in (p.get("forma") or {}).items()}
    q["reactor"], q["level"] = bool(p.get("reactor", True)), int(p.get("level", q["level"]))
    return q


def piece_shards(p: dict, kind: str) -> list:
    """The piece's 5 Archon Shard slots (Warframes): [{"color","key","tauforged"} or None]."""
    if kind != "warframe":
        return []
    sh = list(p.get("shards") or [])[:5]
    sh += [None] * (5 - len(sh))
    p["shards"] = sh
    return sh


class PlannerView(QWidget):
    def __init__(self, get_loadouts, get_presets=None, get_owned=None):
        super().__init__()
        self.get_loadouts, self.get_presets = get_loadouts, get_presets
        self.get_owned = get_owned or (lambda: {})
        self.kind, self.item = "warframe", ""
        self.p = None                    # the piece shown (see new_piece)
        self.pieces = {}                 # the whole loadout: kind -> piece
        self.roles, self.selected = [], None
        self._auto = False                 # the selected slot was chosen by the planner (after installing a mod)
        self.plans = self._read_plans()
        self.scaler = Scaler(self, self._draw, fn=land_width, start=200)

        self.kind_box = QComboBox()
        for k in KINDS:
            self.kind_box.addItem(t("builds.kind." + k), k)
        self.item_box = QComboBox()
        self.item_box.setEditable(True)
        self.item_box.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.item_box.setMinimumWidth(220)
        self.item_box.completer().setFilterMode(Qt.MatchFlag.MatchContains)          # type part of the name
        self.item_box.completer().setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.btn_copy = QPushButton(t("plan.copy"))
        self.btn_clear = QPushButton(t("plan.new"))
        self.btn_share = QPushButton(t("share.btn"))
        self.btn_share.setToolTip(t("share.btn.tip"))
        top = QHBoxLayout()
        for w in (QLabel(t("plan.kind")), self.kind_box, QLabel(t("plan.item")), self.item_box, self.btn_copy, self.btn_clear,
                  self.btn_share):
            top.addWidget(w)
        top.addStretch(1)
        self.name = QLineEdit()
        self.name.setPlaceholderText(t("plan.name"))
        self.saved = QComboBox()
        self.saved.setMinimumWidth(180)
        self.btn_save = QPushButton(t("plan.save"))
        role(self.btn_save, "primary")
        self.btn_del = QPushButton(t("plan.delete"))
        top.addWidget(self.name, 1)
        top.addWidget(self.btn_save)
        top.addWidget(QLabel(t("plan.load")))
        top.addWidget(self.saved)
        top.addWidget(self.btn_del)

        self.strip = QHBoxLayout()                    # the pieces of the loadout being planned
        self.hint = QLabel(t("plan.pick"))
        role(self.hint, "hint")
        self.hint.setWordWrap(True)
        self.screen = BuildScreen(editable=True)
        host = QWidget()
        hl = QVBoxLayout(host)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.addWidget(self.screen)
        hl.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(host)
        self.scaler.area = scroll
        self.library = ModLibrary()
        self.actions = QHBoxLayout()                  # bottom bar, like the game's: ACTIONS · REMOVE ALL
        self.btn_actions = QPushButton(t("bs.actions"))
        self.btn_remove = QPushButton(t("bs.remove_all"))
        self.status = QLabel("")
        role(self.status, "muted")
        self.actions.addWidget(self.status, 1)
        self.actions.addWidget(self.btn_actions)
        self.actions.addWidget(self.btn_remove)
        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addLayout(self.strip)
        lay.addWidget(self.hint)
        lay.addWidget(scroll, 1)
        lay.addWidget(self.library)
        lay.addLayout(self.actions)

        self.kind_box.currentIndexChanged.connect(lambda _i: self._kind_changed())
        self.item_box.currentIndexChanged.connect(lambda _i: self._item_changed())
        self.item_box.lineEdit().editingFinished.connect(self._item_typed)
        self.btn_copy.clicked.connect(self._copy)
        self.btn_clear.clicked.connect(self._clear)
        self.btn_share.clicked.connect(self._share_menu)
        self.btn_save.clicked.connect(self._save)
        self.btn_del.clicked.connect(self._delete)
        self.saved.activated.connect(lambda _i: self._load())
        self.btn_remove.clicked.connect(self._remove_all)
        self.btn_actions.clicked.connect(self._actions_menu)
        self.screen.slot_clicked.connect(self._select)
        self.screen.slot_menu.connect(self._slot_menu)
        self.screen.slot_dropped.connect(lambda i, name: self._install(name, i))
        self.screen.config_selected.connect(self._config)
        self.screen.config_added.connect(self._config_add)
        self.screen.perk_picked.connect(self._perk)
        self.library.picked.connect(lambda name: self._install(name, None))
        self._fill_saved()
        self._kind_changed()

    def showEvent(self, e):
        super().showEvent(e)
        self.scaler.attach()

    # ---------- plans on disk ----------
    def _read_plans(self) -> dict:
        try:
            d = json.loads(PLANS_FILE.read_text(encoding="utf-8"))
            return d if isinstance(d, dict) else {}
        except Exception:
            return {}

    def _write_plans(self):
        try:
            PLANS_FILE.write_text(json.dumps(self.plans, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError:
            pass

    def _fill_saved(self, select=""):
        self.saved.blockSignals(True)
        self.saved.clear()
        self.saved.addItem("—", "")
        for n in sorted(self.plans, key=str.lower):
            self.saved.addItem(n, n)
        self.saved.setCurrentIndex(max(0, self.saved.findData(select)))
        self.saved.blockSignals(False)

    # ---------- the piece shown ----------
    @property
    def mods(self) -> list:
        return self.p["configs"][self.p["cfg"]]["mods"] if self.p else []

    def _store_piece(self):
        if self.p and self.p.get("item"):
            self.pieces[self.kind] = self.p
        elif self.kind in self.pieces and not (self.p and self.p.get("item")):
            self.pieces.pop(self.kind, None)

    def _show_piece(self, kind, piece):
        """Shows a piece (its item in the boxes, its slots)."""
        self._set_boxes(kind, piece["item"] if piece else "")
        self.kind, self.p = kind, piece
        self.item = piece["item"] if piece else ""
        self.roles = BC.plan_roles(kind, self.item) if piece else []
        if piece:
            for c in piece["configs"]:                 # the slot count of an older plan
                c["mods"] = (list(c["mods"]) + [None] * len(self.roles))[:len(self.roles)]
        self.selected = None
        self._draw()

    def switch_to(self, kind):
        """Shows another piece of the loadout (the current one is kept)."""
        self._store_piece()
        self._show_piece(kind, self.pieces.get(kind))

    def _set_boxes(self, kind, item):
        self.kind_box.blockSignals(True)
        self.kind_box.setCurrentIndex(max(0, self.kind_box.findData(kind)))
        self.kind_box.blockSignals(False)
        self.item_box.blockSignals(True)
        self.item_box.clear()
        for n in BC.items(kind):
            self.item_box.addItem(n)
        self.item_box.setCurrentIndex(self.item_box.findText(item) if item else -1)
        self.item_box.setEditText(item)
        self.item_box.blockSignals(False)

    def _kind_changed(self):
        kind = self.kind_box.currentData()
        if kind == self.kind and self.p is not None:
            return
        self.switch_to(kind)

    def _item_changed(self):
        name = self.item_box.currentText().strip()
        if not name or name == self.item or name not in BC.items(self.kind):
            return                                     # same item, half-typed or unknown name
        self.p = new_piece(self.kind, name)
        self.item = name
        self.roles = BC.plan_roles(self.kind, name)
        self.selected = None
        self._store_piece()
        self._draw()

    def _item_typed(self):
        """A name typed by hand: accepted when it matches an item (case does not matter), otherwise the box goes back."""
        text = self.item_box.currentText().strip().lower()
        match = next((n for n in BC.items(self.kind) if n.lower() == text), None)
        if match:
            i = self.item_box.findText(match)
            if i >= 0 and i != self.item_box.currentIndex():
                self.item_box.setCurrentIndex(i)
            else:
                self._item_changed()
        else:
            self.item_box.setEditText(self.item)

    def _clear(self):
        """A new, empty loadout."""
        self.pieces = {}
        self.p, self.item = None, ""
        self.name.clear()
        self._show_piece(self.kind, None)

    # ---------- copying from the game ----------
    def piece_from_loadout(self, lo) -> dict:
        """One of your items, with all its configurations, as a planned piece."""
        kind, item = lo["kind"], lo["item"]
        p = new_piece(kind, item)
        roles = BC.plan_roles(kind, item)
        sibs = [x for x in self.get_loadouts() if lo.get("oid") and x.get("oid") == lo.get("oid")] or [lo]
        sibs.sort(key=lambda x: x.get("idx", 0))
        p["configs"] = []
        for x in sibs:
            mods = []
            for s in x["slots"][:len(roles)]:
                if not s.get("name"):
                    mods.append(None)
                elif s.get("riven") and s["riven"].get("attributes"):
                    mods.append((s["name"], s["rank"], s["riven"]))
                else:
                    mods.append((s["name"], s["rank"]))
            mods += [None] * (len(roles) - len(mods))
            p["configs"].append({"mods": mods, "name": x.get("cfg_name") or ""})
        p["cfg"] = max(0, next((n for n, x in enumerate(sibs) if x.get("idx") == lo.get("idx")), 0))
        base = BC.innate(kind, item, roles)
        p["forma"] = {i: s["pol"] for i, s in enumerate(lo["slots"][:len(roles)])
                      if s.get("pol") is not None and s.get("pol") != base[i]}
        p["reactor"], p["level"] = bool(lo.get("reactor", True)), int(lo.get("level", p["level"]))
        ex = lo.get("extras") or {}
        if "exilus" in ex:
            p["exilus"] = bool(ex["exilus"]) or kind == "warframe" and any(
                s.get("name") for s in lo["slots"] if s["role"] == "exilus")
        if kind in WEAPONS and "arcane_slot" in ex:
            p["arcane"] = bool(ex["arcane_slot"]) or any(s.get("name") for s in lo["slots"] if s["role"] == "arcane")
        if ex.get("valence"):
            p["valence"] = {"element": ex["valence"]["element"], "pct": float(ex["valence"]["pct"])}
        inc = lo.get("incarnon")
        if inc:
            p["incarnon"] = {"on": inc["kind"] in ("genesis", "builtin"), "evo": max(inc.get("evo") or 0, len(inc.get("skill") or "")) or 5,
                             "perks": [int(c) if c.isdigit() else 0 for c in (inc.get("skill") or "")[:5]] + [0] * (5 - len((inc.get("skill") or "")[:5]))}
        if kind == "warframe":
            sh = [{"color": x.get("color"), "key": x.get("key"), "tauforged": bool(x.get("tauforged"))}
                  for x in (lo.get("shards") or [])[:5]]
            p["shards"] = sh + [None] * (5 - len(sh))
            hm = lo.get("helminth")
            if hm and hm.get("path"):
                p["helminth"] = {"slot": int(hm["slot"]), "path": hm["path"]}
        return p

    def _copy(self):
        presets = list((self.get_presets() or {}).get("presets") or []) if self.get_presets else []
        if presets:
            choice, ok = QInputDialog.getItem(self, t("plan.copy.title"), t("plan.copy.what"),
                                              [t("plan.copy.loadout"), t("plan.copy.item")], 0, False)
            if not ok:
                return
            if choice == t("plan.copy.loadout"):
                return self._copy_loadout(presets)
        los = [lo for lo in self.get_loadouts() if lo["kind"] in KINDS]
        if not los:
            QMessageBox.information(self, t("tab.builds"), t("plan.copy.none"))
            return
        labels = [f"{lo['item']} · {lo.get('cfg_name') or lo['config']}" for lo in los]
        label, ok = QInputDialog.getItem(self, t("plan.copy.title"), t("plan.copy.prompt"), labels, 0, False)
        if ok:
            self.copy_item(los[labels.index(label)], label)

    def copy_item(self, lo, label=""):
        """Plans one of your items (also used by the Builds tab's "Simulate in the planner")."""
        self._store_piece()
        piece = self.piece_from_loadout(lo)
        self.pieces[lo["kind"]] = piece
        if label:
            self.name.setText(label)
        self._show_piece(lo["kind"], piece)

    def _copy_loadout(self, presets):
        """A whole in-game loadout (Warframe, weapons, companion…) as a plan: every piece with its mods."""
        labels = [p["name"] for p in presets]
        label, ok = QInputDialog.getItem(self, t("plan.copy.title"), t("plan.copy.prompt"), labels, 0, False)
        if not ok:
            return
        p = presets[labels.index(label)]
        los = self.get_loadouts()
        self.pieces = {}
        role_kind = {"warframe": "warframe", "primary": "primary", "secondary": "secondary", "melee": "melee",
                     "companion": "companion", "companion_weapon": "compweapon", "archwing": "archwing",
                     "archgun": "archgun", "archmelee": "archmelee"}
        rows = list(p.get("warframe") or []) + list(p.get("companion") or [])
        rows += list(((self.get_presets() or {}).get("tenno") or {}).get("archwing") or [])
        for r in rows:
            kind = role_kind.get(r.get("role"))
            if not kind:
                continue
            lo = next((x for x in los if x.get("oid") == r.get("oid") and x.get("idx") == r.get("idx")), None)
            if lo and lo["kind"] in KINDS:
                self.pieces[kind] = self.piece_from_loadout(dict(lo, kind=kind))
            elif r["item"] in BC.items(kind):
                self.pieces[kind] = new_piece(kind, r["item"])
        self.name.setText(label)
        first = next((k for k in KINDS if k in self.pieces), "warframe")
        self._show_piece(first, self.pieces.get(first))

    # ---------- saving ----------
    def _save(self):
        name = self.name.text().strip()
        if not name:
            QMessageBox.information(self, t("tab.builds"), t("plan.noname"))
            return
        self._store_piece()
        pieces = {}
        for k, v in self.pieces.items():
            pieces[k] = dict(v, forma={str(i): p for i, p in v["forma"].items()},
                             configs=[dict(c, mods=[list(m) if m else None for m in c["mods"]]) for c in v["configs"]])
        self.plans[name] = {"v": 2, "kind": self.kind, "pieces": pieces}
        self._write_plans()
        self._fill_saved(name)
        QMessageBox.information(self, t("tab.builds"), t("plan.saved", name=name))

    def _load(self):
        name = self.saved.currentData()
        p = self.plans.get(name) if name else None
        if not p:
            return
        if p.get("pieces"):
            self.pieces = {k: upgrade_piece(v, k) for k, v in p["pieces"].items() if k in KINDS and v.get("item")}
        else:                                           # a single item (0.3.7 and before)
            kind = p.get("kind", "warframe")
            self.pieces = {kind: upgrade_piece(p, kind)} if p.get("item") else {}
        self.name.setText(name)
        first = p.get("kind") if p.get("kind") in self.pieces else next(iter(self.pieces), "warframe")
        self._show_piece(first, self.pieces.get(first))

    def _delete(self):
        name = self.saved.currentData()
        if name and QMessageBox.question(self, t("tab.builds"), t("plan.confirm.delete", name=name)) == QMessageBox.StandardButton.Yes:
            self.plans.pop(name, None)
            self._write_plans()
            self._fill_saved()

    # ---------- what the game lets you do ----------
    def _candidates(self, i):
        r = self.roles[i]
        return BC.arcane_candidates(self.kind) if r == "arcane" else BC.candidates(self.kind, self.item, r)

    def _locked(self, i) -> bool:
        r = self.roles[i]
        return (r == "exilus" and not self.p.get("exilus", True)) or \
               (r == "arcane" and self.kind in WEAPONS and not self.p.get("arcane", True))

    def _install(self, name, slot=None):
        """Puts a mod / Arcane in a slot: the one dropped on, else the selected one, else the first empty slot it fits."""
        if not self.p:
            return
        fits = [i for i in range(len(self.roles)) if name in self._candidates(i) and not self._locked(i)]
        if slot is None:                               # an Exilus mod goes to the free Exilus slot first
            # on screen the general slots go from the last (top left) to the first: filled in that order, as the game
            empty = sorted((i for i in fits if not self.mods[i]),
                           key=lambda i: (self.roles[i] != "exilus", -i if self.roles[i] == "general" else i))
            # a slot you picked yourself wins; one the planner moved to after the last mod does not, when the mod has a
            # better place (an Exilus mod, the Exilus slot)
            mine = self.selected in fits and not (self._auto and empty and self.roles[empty[0]] == "exilus")
            slot = self.selected if mine else next(iter(empty), None)
        if slot is None or slot not in fits:
            self._say(t("bs.nofit", name=name))
            return
        fam = mod_family(name)
        clash = next((i for i, m in enumerate(self.mods) if m and i != slot and mod_family(m[0]) == fam), None)
        if clash is not None and self.roles[slot] != "arcane":
            self._say(t("bs.clash", name=name, other=self.mods[clash][0]))
            return
        mx = arcane_max(name) if self.roles[slot] == "arcane" else (BC.mod_info(name) or [0, 0, 0])[2]
        self.mods[slot] = (name, mx)
        # the next empty slot of the same kind gets selected: clicking mods one after the other fills the build
        same = [i for i in range(len(self.roles)) if self.roles[i] == self.roles[slot] and not self.mods[i] and not self._locked(i)]
        if self.roles[slot] == "general":                  # screen order: from the last slot down
            same.sort(reverse=True)
            self.selected = next((i for i in same if i < slot), same[0] if same else slot)
        else:
            self.selected = next((i for i in same if i > slot), same[0] if same else slot)
        self._auto = True
        self._say("")
        self._draw()

    def _select(self, i):
        self.selected, self._auto = i, False
        self._draw()

    def _say(self, text):
        self.status.setText(text)

    # ---------- sharing: code, file, picture ----------
    def _share_menu(self):
        m = QMenu(self)
        m.addAction(t("share.import.code"), self._import_code)
        m.addAction(t("share.import.file"), self._import_file)
        m.addAction(t("share.import.image"), lambda: self._import_image(False))
        from PyQt6.QtGui import QGuiApplication
        a = m.addAction(t("share.import.clip"), lambda: self._import_image(True))
        a.setEnabled(not QGuiApplication.clipboard().image().isNull())
        if self.p and self.p.get("item"):
            m.addSeparator()
            share_actions(m, self, lambda: (self.kind, self.p), lambda: self.screen,
                          lambda: (self.p["item"], t("builds.kind." + self.kind) + " · " + (self.name.text() or "")))
        self._store_piece()
        if sum(1 for p in self.pieces.values() if p and p.get("item")) > 1:
            m.addSeparator()
            loadout_share_actions(m, self, lambda: (self.name.text().strip(), dict(self.pieces)), self._loadout_images)
        m.exec(self.btn_share.mapToGlobal(self.btn_share.rect().bottomLeft()))

    def _loadout_images(self) -> list:
        """A picture of every piece of the loadout, each drawn on the screen in turn (the shown one comes back)."""
        from app.ui import buildshare as S
        from PyQt6.QtWidgets import QApplication
        self._store_piece()
        back, out = self.kind, []
        for k in KINDS:
            p = self.pieces.get(k)
            if not p or not p.get("item"):
                continue
            self.switch_to(k)
            QApplication.processEvents()
            out.append(S.image(self.screen, p["item"], t("builds.kind." + k) + " · " + (self.name.text() or "")))
        self.switch_to(back)
        return out

    def import_text(self, text):
        from app.ui import buildshare as S
        try:
            what, kind, piece = S.decode_any(text)
        except (ValueError, json.JSONDecodeError) as e:
            QMessageBox.warning(self, t("share.import.code"), t("share.bad", err=str(e)))
            return False
        self._store_piece()
        if what == "loadout":                          # a whole loadout: every piece, the name as the plan's
            name, pieces = kind, piece
            self.pieces = pieces
            if name:
                self.name.setText(name)
            first = next((k for k in KINDS if k in self.pieces), "warframe")
            self._show_piece(first, self.pieces.get(first))
            self._say(t("share.imported.loadout", name=name or "—", n=len(pieces)))
            return True
        self.pieces[kind] = piece
        self._show_piece(kind, piece)
        self._say(t("share.imported", item=piece["item"]))
        return True

    def _import_code(self):
        from PyQt6.QtGui import QGuiApplication
        clip = QGuiApplication.clipboard().text() or ""
        text, ok = QInputDialog.getMultiLineText(self, t("share.import.code"), t("share.import.prompt"),
                                                 clip if "WFVO1:" in clip else "")
        if ok and text.strip():
            self.import_text(text)

    def _import_image(self, from_clipboard: bool):
        """A build read from a picture (a screenshot of the game's upgrade screen, or a picture shared by this program):
        the OCR reads it in its own process, buildocr places the mods by where they are."""
        from PyQt6.QtWidgets import QFileDialog
        from PyQt6.QtGui import QGuiApplication
        if from_clipboard:
            img = QGuiApplication.clipboard().image()
            if img.isNull():
                return
            path = str(APP_DIR / "import_build.png")
            img.save(path, "PNG")
        else:
            path, _ = QFileDialog.getOpenFileName(self, t("share.import.image"), "",
                                                  "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
            if not path:
                return
        self._say(t("share.image.reading"))

        def work():
            try:
                import app.scan.ocr_worker as OW
                if OW.CLIENT is not None:
                    lines, w, h = OW.CLIENT.read_image(path)
                else:                                      # no OCR process (tests): read it here
                    import numpy as np
                    from PIL import Image
                    from app.scan.ocr import make_engine, read_lines
                    im = Image.open(path).convert("RGB")
                    ls = read_lines(np.array(im)[:, :, ::-1].copy(), make_engine())
                    lines, w, h = [(x.text, x.x, x.y, x.w, x.h, x.score) for x in ls], im.width, im.height
                self._img_done.done.emit(("ok", lines, w, h, path))
            except Exception as e:
                self._img_done.done.emit(("err", f"{type(e).__name__}: {e}"))
        if not hasattr(self, "_img_done"):
            from PyQt6.QtCore import QObject, pyqtSignal as _sig

            class _Done(QObject):
                done = _sig(object)
            self._img_done = _Done()
            self._img_done.done.connect(self._image_read)
        import threading
        threading.Thread(target=work, daemon=True, name="build-image").start()

    def _ocr_picture(self, from_clipboard: bool, title: str, done):
        ocr_picture(self, from_clipboard, title, done, self._say)

    def _riven_image(self, i, from_clipboard: bool):
        """Slot i becomes the Riven of the picture (its name, stats, MR, rerolls); a Riven already there keeps its
        polarity and, when the picture's name is close to it, its name."""
        def done(res):
            from app.game import rivenocr
            if isinstance(res, str):
                self._say(t("share.image.bad", err=res))
                return
            cur = self.mods[i] if i < len(self.mods) else None
            old = cur[2] if cur and len(cur) > 2 and isinstance(cur[2], dict) else {}
            try:
                rv = rivenocr.parse(res[0], cur[0] if old else "")
            except ValueError as e:
                self._say(t("share.image.bad", err=str(e)))
                return
            riven = rivenocr.merge(rv, old)
            self.mods[i] = (riven["mod_name"] + " (Riven)", riven["rank"], riven)
            self._draw()
            self._say(t("bs.riven.done", name=riven["mod_name"], stats=rivenocr.summary(riven)))
        self._ocr_picture(from_clipboard, t("bs.riven.image"), done)

    def _image_read(self, res):
        from app.game import buildocr
        if res[0] != "ok":
            self._say(t("share.image.bad", err=res[1]))
            return
        try:
            from PIL import Image
            try:
                img = Image.open(res[4]).convert("RGB")       # the colours: polarities, Omni Forma
                if img.size != (res[2], res[3]):
                    img = img.resize((res[2], res[3]))
            except Exception:
                img = None
            b = buildocr.parse(res[1], res[2], res[3], image=img)
        except ValueError as e:
            self._say(t("share.image.bad", err=str(e)))
            return
        piece = new_piece(b["kind"], b["item"])
        mods = b["mods"] + [None] * (len(piece["configs"][0]["mods"]) - len(b["mods"]))
        piece["configs"][0]["mods"] = mods[:len(piece["configs"][0]["mods"])]
        piece["forma"] = {int(k): v for k, v in (b.get("pols") or {}).items()}
        self._store_piece()
        self.pieces[b["kind"]] = piece
        self._show_piece(b["kind"], piece)
        n = sum(1 for m in piece["configs"][0]["mods"] if m)
        msg = t("share.image.done", item=b["item"], n=n)
        if b["unplaced"]:
            msg += " " + t("share.image.unplaced", names=", ".join(b["unplaced"]))
        if b.get("pols"):
            msg += " " + t("share.image.pols", n=sum(1 for v in b["pols"].values() if v),
                           omni=sum(1 for v in b["pols"].values() if v == "universal"))
        if b.get("mismatch"):
            msg += " " + t("share.image.mismatch", names=", ".join(b["mismatch"]))
        rv = [m for m in piece["configs"][0]["mods"] if m and len(m) > 2]
        if rv:
            msg += " " + t("share.image.rivens", names=", ".join(m[2]["mod_name"] for m in rv))
        self._say(msg)

    def _import_file(self):
        from PyQt6.QtWidgets import QFileDialog
        from app.ui import buildshare as S
        path, _ = QFileDialog.getOpenFileName(self, t("share.import.file"), "", S.FILE_FILTER)
        if path:
            try:
                with open(path, encoding="utf-8") as fh:
                    self.import_text(fh.read())
            except OSError as e:
                QMessageBox.warning(self, t("share.import.file"), str(e))

    def _slot_menu(self, i, pos):
        m = QMenu(self)
        cur = self.mods[i]
        r = self.roles[i]
        if cur:
            name = cur[0]
            riven = len(cur) > 2 and cur[2]
            mx = 8 if riven else (arcane_max(name) if r == "arcane" else (BC.mod_info(name) or [0, 0, 0])[2])
            if mx and not riven:
                sub = m.addMenu(t("bs.menu.rank"))
                for k in range(mx + 1):
                    a = QAction(t("builds.rank", rank=k, max=mx), sub, checkable=True)
                    a.setChecked(cur[1] == k)
                    a.triggered.connect(lambda _c=False, k=k: self._set_rank(i, k))
                    sub.addAction(a)
            m.addAction(t("bs.menu.remove"), lambda: self._remove(i))
            from app.ui.buildscreen import market_link
            from PyQt6.QtGui import QDesktopServices
            from PyQt6.QtCore import QUrl
            m.addAction(t("bs.market.riven" if riven else "bs.market"),
                        lambda: QDesktopServices.openUrl(QUrl(market_link(name, riven or None))))
        if r == "general":                             # a Riven's stats from a picture of its card / tooltip
            m.addSeparator()
            m.addAction(t("bs.riven.image"), lambda: self._riven_image(i, False))
            from PyQt6.QtGui import QGuiApplication
            a = m.addAction(t("bs.riven.clip"), lambda: self._riven_image(i, True))
            a.setEnabled(not QGuiApplication.clipboard().image().isNull())
        if r != "arcane":
            sub = m.addMenu(t("bs.menu.polarity"))
            base = BC.innate(self.kind, self.item, self.roles)[i]
            here = self.p["forma"].get(i, INNATE)
            opts = [(INNATE, t("bs.pol.innate", pol=t("pol." + base) if base else t("pol.none")), base),
                    ("", t("pol.none"), "")] + [(p, t("pol." + p), p) for p in BC.POLARITIES]
            for val, label, pol in opts:
                a = QAction(label, sub, checkable=True)
                a.setChecked(here == val)
                pm = icons.polarity(pol, 16) if pol else None
                if pm is not None:
                    a.setIcon(QIcon(pm))
                a.triggered.connect(lambda _c=False, v=val: self._set_pol(i, v))
                sub.addAction(a)
        if r == "exilus":
            a = QAction(t("bs.opt.exilus"), m, checkable=True)
            a.setChecked(self.p.get("exilus", True))
            a.triggered.connect(lambda c: self._set_opt("exilus", bool(c)))
            m.addAction(a)
        if r == "arcane" and self.kind in WEAPONS:
            a = QAction(t("bs.opt.arcane"), m, checkable=True)
            a.setChecked(self.p.get("arcane", True))
            a.triggered.connect(lambda c: self._set_opt("arcane", bool(c)))
            m.addAction(a)
        m.exec(pos)

    def _set_rank(self, i, k):
        if self.mods[i]:
            self.mods[i] = (self.mods[i][0], k) + tuple(self.mods[i][2:])
            self._draw()

    def _remove(self, i):
        self.mods[i] = None
        self._draw()

    def _remove_all(self):
        if self.p:
            self.p["configs"][self.p["cfg"]]["mods"] = [None] * len(self.roles)
            self._draw()

    def _set_pol(self, i, val):
        if val == INNATE:
            self.p["forma"].pop(i, None)
        else:
            self.p["forma"][i] = val
        self._draw()

    def _set_opt(self, key, value):
        if self.p is not None:
            self.p[key] = value
            self._draw()

    def _config(self, i):
        self.p["cfg"] = i
        self.selected = None
        self._draw()

    def _config_add(self):
        if len(self.p["configs"]) >= len(LETTERS):
            return
        self.p["configs"].append({"mods": [None] * len(self.roles)})
        self.p["cfg"] = len(self.p["configs"]) - 1
        self._draw()

    def _perk(self, tier, k):
        inc = self.p["incarnon"]
        if not inc.get("on"):
            self._say(t("bs.inc.off"))
            return
        if tier >= inc.get("evo", 5):
            inc["evo"] = tier + 1                       # choosing a perk of a later tier unlocks it
        inc["perks"][tier] = k
        self._draw()

    def _actions_menu(self):
        if not self.p:
            return
        m = QMenu(self)
        m.addAction(t("bs.act.forma_reset"), lambda: (self.p.__setitem__("forma", {}), self._draw()))
        m.addAction(t("bs.act.forma_fit"), self._forma_fit)
        m.addAction(t("bs.act.copy_cfg"), self._copy_config)
        if len(self.p["configs"]) > 1:
            m.addAction(t("bs.act.del_cfg"), self._del_config)
        m.addAction(t("bs.act.rename_cfg"), self._rename_config)
        m.exec(self.btn_actions.mapToGlobal(self.btn_actions.rect().topLeft()))

    def _forma_fit(self):
        """Forma every mod's slot to the mod's own polarity (what players do to fit a build)."""
        for i, m in enumerate(self.mods):
            if m and self.roles[i] != "arcane":
                info = BC.mod_info(m[0])
                pol = (m[2] or {}).get("polarity") if len(m) > 2 and m[2] else (info[0] if info else "")
                if pol:
                    base = BC.innate(self.kind, self.item, self.roles)[i]
                    if base == pol:
                        self.p["forma"].pop(i, None)
                    else:
                        self.p["forma"][i] = pol
        self._draw()

    def _copy_config(self):
        cur = self.p["configs"][self.p["cfg"]]
        if len(self.p["configs"]) < len(LETTERS):
            self.p["configs"].append({"mods": list(cur["mods"]), "name": ""})
            self.p["cfg"] = len(self.p["configs"]) - 1
            self._draw()

    def _del_config(self):
        self.p["configs"].pop(self.p["cfg"])
        self.p["cfg"] = max(0, self.p["cfg"] - 1)
        self._draw()

    def _rename_config(self):
        c = self.p["configs"][self.p["cfg"]]
        name, ok = QInputDialog.getText(self, t("bs.act.rename_cfg"), t("bs.act.rename_cfg.prompt"), text=c.get("name") or "")
        if ok:
            c["name"] = name.strip()
            self._draw()

    # ---------- showing ----------
    def model(self) -> dict:
        """What the screen shows for the piece: slots, capacity, stats (see BuildScreen.show_model)."""
        p, kind, item, roles = self.p, self.kind, self.item, self.roles
        pols = BC.slot_polarities(kind, item, roles, p["forma"])
        has_ex = "exilus" in roles
        locked = {"exilus": has_ex and not p.get("exilus", True), "arcane": kind in WEAPONS and not p.get("arcane", True)}
        calc = BC.evaluate(kind, item, roles, self.mods, pols, p.get("reactor", True), p.get("level", 30), locked=locked,
                           shards=[x for x in piece_shards(p, kind) if x] or None)
        slots = []
        for i, r in enumerate(roles):
            m = self.mods[i]
            name = m[0] if m else ""
            info = BC.mod_info(name) if name and r != "arcane" else None
            rv = m[2] if m and len(m) > 2 else None
            mx = 8 if rv else (info[2] if info else (arcane_max(name) if name else None))
            c = calc["slots"][i]
            slots.append({"role": r, "name": name, "rank": m[1] if m else None, "max": mx, "pol": pols[i], "mpol": c["mpol"],
                          "drain": c["drain"], "state": c["state"], "riven": rv, "posture": kind == "compweapon" and r == "stance"})
        valence = p.get("valence") if BC.valence_capable(item) else None
        avail = INC.available(item) if kind in ("primary", "secondary", "melee") else None
        pk = None
        if avail and p["incarnon"].get("on"):          # the chosen evolution perks count in the stats
            top = INC.tier_count(avail["kind"], avail["page"])
            pk = INC.bonuses(avail["page"], p["incarnon"].get("perks") or [], min(int(p["incarnon"].get("evo", 5) or 5), top), item)
        weapon = BC.weapon_stats(kind, item, calc["bonus"], calc.get("elements") or [], valence,
                                  calc.get("flat"), pk) if kind in WEAPONS else None
        cfgs = [{"label": c.get("name") or t("bs.cfg", c=LETTERS[n]), "active": n == p["cfg"]} for n, c in enumerate(p["configs"])]
        out = {"kind": kind, "item": item, "title": item, "rank": p.get("level"), "configs": cfgs, "slots": slots,
               "capacity": {k: calc[k] for k in ("total", "used", "free")}, "level": p.get("level"),
               "reactor": p.get("reactor"), "forma": BC.forma_count(kind, item, roles, p["forma"]),
               "wf_stats": calc["stats"], "wf_base": wf_base_stats(item) if kind == "warframe" else
               (BC.companion_base(item) if kind == "companion" else {}),
               "abilities": AB.model(item, p.get("helminth")) if kind == "warframe" else [],
               "weapon": weapon, "bonus": calc["bonus"], "valence": valence, "locked": locked, "selected": self.selected,
               "unique": bool(valence), "upgrades": upgrade_icons(kind, p.get("reactor", True), p.get("exilus", True)
                                                                  if "exilus" in roles else None,
                                                                  p.get("arcane", True) if "arcane" in roles else None)}
        owned = self.get_owned() or {}
        if owned:                                      # what you own is known (the game file was read)
            out["owned"] = owned
        avail = INC.available(item) if kind in ("primary", "secondary", "melee") else None
        if avail:
            inc = p["incarnon"]
            on = inc.get("on")
            head = t("inc." + avail["kind"]) + ("" if on else " · " + t("bs.inc.notinstalled"))
            out["incarnon"] = incarnon_model(avail["kind"], avail["page"], inc.get("perks") or [], inc.get("evo", 5) if on else 0,
                                             head=head, note="" if on else t("bs.inc.install"))
        return out

    def _options(self) -> QWidget:
        """The planner's switches above the slots: rank, Reactor / Catalyst, adapters, Valence, Incarnon Genesis."""
        p, kind = self.p, self.kind
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(10)
        h.addWidget(QLabel(t("plan.level")))
        lvl = QSpinBox()
        lvl.setRange(0, LO.max_rank(self.item, kind))
        lvl.setValue(int(p.get("level", 30)))
        lvl.setKeyboardTracking(False)                 # typed numbers count once finished (every change redraws)
        lvl.valueChanged.connect(lambda v: self._set_opt("level", int(v)))
        h.addWidget(lvl)
        what = t("builds.catalyst") if kind in WEAPONS else t("builds.reactor.name")
        cb = QCheckBox(what)
        _icon(cb, "catalyst" if kind in WEAPONS else "reactor")
        cb.setChecked(bool(p.get("reactor", True)))
        cb.setToolTip(t("bs.opt.reactor.tip"))
        cb.toggled.connect(lambda c: self._set_opt("reactor", bool(c)))
        h.addWidget(cb)
        if "exilus" in self.roles:
            cb = QCheckBox(t("bs.opt.exilus"))
            _icon(cb, "exilus_adapter")
            cb.setChecked(bool(p.get("exilus", True)))
            cb.toggled.connect(lambda c: self._set_opt("exilus", bool(c)))
            h.addWidget(cb)
        if "arcane" in self.roles and kind in WEAPONS:
            cb = QCheckBox(t("bs.opt.arcane"))
            _icon(cb, "secondary_arcane" if kind == "secondary" else "primary_arcane")
            cb.setChecked(bool(p.get("arcane", True)))
            cb.toggled.connect(lambda c: self._set_opt("arcane", bool(c)))
            h.addWidget(cb)
        if BC.valence_capable(self.item):
            v = p.get("valence") or {"element": "Toxin", "pct": 60.0}
            p["valence"] = v
            h.addWidget(QLabel(t("bs.opt.valence")))
            el = QComboBox()
            for e in BC.VALENCE:
                el.addItem(t("dmg." + e.lower()), e)
            el.setCurrentIndex(max(0, el.findData(v["element"])))
            el.setToolTip(t("bs.opt.valence.tip"))
            el.currentIndexChanged.connect(lambda _i, b=el: (v.__setitem__("element", b.currentData()), self._draw()))
            h.addWidget(el)
            pct = QDoubleSpinBox()
            pct.setRange(25.0, 60.0)
            pct.setDecimals(1)
            pct.setSuffix("%")
            pct.setValue(float(v.get("pct") or 60))
            pct.setKeyboardTracking(False)
            pct.valueChanged.connect(lambda x: (v.__setitem__("pct", float(x)), self._draw()))
            h.addWidget(pct)
        avail = INC.available(self.item) if kind in ("primary", "secondary", "melee") else None
        if avail:
            inc = p["incarnon"]
            if avail["kind"] == "genesis":
                cb = QCheckBox(t("bs.opt.genesis"))
                cb.setChecked(bool(inc.get("on")))
                cb.setToolTip(t("bs.opt.genesis.tip", page=avail["page"]))
                cb.toggled.connect(lambda c: (inc.__setitem__("on", bool(c)), self._draw()))
                h.addWidget(cb)
            else:
                inc["on"] = True
            h.addWidget(QLabel(t("bs.opt.evo")))
            evo = QSpinBox()
            top = INC.tier_count(avail["kind"], avail["page"])        # Evolution V only on weapons that have it
            evo.setRange(1, top)
            evo.setValue(min(top, int(inc.get("evo", 5) or 5)))
            evo.setKeyboardTracking(False)
            evo.setEnabled(bool(inc.get("on")))
            evo.valueChanged.connect(lambda x: (inc.__setitem__("evo", int(x)), self._draw()))
            h.addWidget(evo)
        h.addStretch(1)
        if kind != "warframe":
            return w
        outer = QWidget()
        v = QVBoxLayout(outer)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(4)
        v.addWidget(w)
        v.addWidget(self._shard_row())
        v.addWidget(self._helminth_row())
        return outer

    def _helminth_row(self) -> QWidget:
        """The Helminth: which of the four abilities is replaced and by what (the Helminth's own abilities or another
        Warframe's). Shown in the ability row under the stats, with its tooltip."""
        hm = self.p.get("helminth") or {}
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)
        lab = QLabel(t("plan.helminth"))
        lab.setToolTip(t("plan.helminth.tip"))
        h.addWidget(lab)
        slot = QComboBox()
        slot.addItem(t("plan.helminth.none"), 0)
        own = AB.model(self.item, None)
        for a in own[1:]:
            slot.addItem(t("plan.helminth.slot", n=a["slot"], name=a["name"]), a["slot"])
        slot.setCurrentIndex(max(0, slot.findData(int(hm.get("slot") or 0))))
        ab = QComboBox()
        ab.setEditable(True)
        ab.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        ab.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        ab.completer().setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        ab.setMinimumWidth(220)
        for name, path in AB.helminth_choices():
            ab.addItem(name, path)
        ab.setCurrentIndex(max(0, ab.findData(hm.get("path"))) if hm.get("path") else 0)
        ab.setEnabled(bool(hm.get("slot")))

        def changed(_x=None):
            n = int(slot.currentData() or 0)
            ab.setEnabled(bool(n))
            path = ab.currentData() if ab.findText(ab.currentText()) >= 0 else None
            self.p["helminth"] = {"slot": n, "path": path or ab.itemData(0)} if n else None
            self._draw()
        slot.currentIndexChanged.connect(changed)
        ab.currentIndexChanged.connect(changed)
        h.addWidget(slot)
        h.addWidget(ab)
        h.addStretch(1)
        return w

    def _shard_row(self) -> QWidget:
        """The Warframe's 5 Archon Shards: a shard per slot and Tauforged or not (strength, duration, health, shields,
        armor and energy count in the stats)."""
        sh = piece_shards(self.p, self.kind)
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)
        lab = QLabel(t("plan.shards"))
        lab.setToolTip(t("plan.shards.tip"))
        h.addWidget(lab)
        for i in range(5):
            cur = sh[i] or {}
            box = QComboBox()
            box.addItem("—", None)
            known = set()
            for color, rows in BC.SHARD_CHOICES.items():
                for key, label in rows:
                    box.addItem(f"{LO.SHARD_COLORS.get(color, color.title())}: {label}", f"{color}|{key}")
                    known.add((color, key))
            if cur.get("key") and (cur.get("color"), cur.get("key")) not in known:     # a shard of your loadout not listed
                box.addItem(f"{LO.SHARD_COLORS.get(cur.get('color'), str(cur.get('color')).title())}: "
                            f"{LO.SHARD_EFFECT.get(cur['key'], cur['key'])}", f"{cur.get('color')}|{cur['key']}")
            box.setCurrentIndex(max(0, box.findData(f"{cur.get('color')}|{cur.get('key')}")) if cur.get("key") else 0)
            box.setToolTip(t("plan.shards.tip"))
            box.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            box.setMinimumContentsLength(17)
            tau = QCheckBox("τ")
            tau.setToolTip(t("plan.shards.tau"))
            tau.setChecked(bool(cur.get("tauforged")))
            tau.setEnabled(bool(cur.get("key")))

            def changed(_x=None, i=i, box=box, tau=tau):
                d = str(box.currentData() or "")
                c, _s, k = d.partition("|")
                sh[i] = {"color": c, "key": k, "tauforged": tau.isChecked()} if k else None
                self._draw()
            box.currentIndexChanged.connect(changed)
            tau.toggled.connect(changed)
            h.addWidget(box)
            h.addWidget(tau)
        h.addStretch(1)
        return w

    def _draw_strip(self):
        """The pieces of the loadout being planned: one button per kind (pressed = the one shown); a click switches to it."""
        from PyQt6.QtWidgets import QPushButton as B
        while self.strip.count():
            it = self.strip.takeAt(0)
            if it.widget():
                it.widget().hide()
                it.widget().deleteLater()
        self._store_piece()
        if not any(self.pieces.values()):
            return
        lab = QLabel(t("plan.loadout"))
        role(lab, "muted")
        self.strip.addWidget(lab)
        for k in KINDS:
            p = self.pieces.get(k)
            if not p and k != self.kind:
                continue
            b = B(f"{t('builds.kind.' + k)}: {p['item'] if p else '—'}")
            b.setCheckable(True)
            b.setChecked(k == self.kind)
            if k == self.kind:
                b.setStyleSheet("font-weight: bold; text-decoration: underline;")
            b.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
            b.clicked.connect(lambda _c=False, kk=k: self.switch_to(kk))
            self.strip.addWidget(b)
        missing = [k for k in KINDS if k not in self.pieces and k != self.kind]
        if missing:
            add = B("+ " + t("plan.loadout.addshort"))
            add.setToolTip(t("plan.loadout.add"))
            menu = QMenu(add)
            for k in missing:
                menu.addAction(t("builds.kind." + k), lambda kk=k: self.switch_to(kk))
            add.setMenu(menu)
            self.strip.addWidget(add)
        self.strip.addStretch(1)

    def _draw(self):
        self.setUpdatesEnabled(False)                  # rebuilt in one go: no flashing
        try:
            self._draw_strip()
            if not LO.data().get("mst"):
                self.hint.setText(t("plan.nodata"))
                self.hint.show()
                self.screen.clear()
                self.library.hide()
                return
            if not self.p:
                self.hint.setText(t("plan.pick"))
                self.hint.show()
                self.screen.clear()
                self.library.hide()
                for w in (self.btn_actions, self.btn_remove):
                    w.setEnabled(False)
                return
            for w in (self.btn_actions, self.btn_remove):
                w.setEnabled(True)
            self.hint.setText(t("plan.howto"))
            cw = self.scaler.cw
            self.screen.show_model(self.model(), cw, extra_top=self._options())
            sel = self.selected if self.selected is not None and self.selected < len(self.roles) else None
            r = self.roles[sel] if sel is not None else "general"
            names = BC.arcane_candidates(self.kind) if r == "arcane" else BC.candidates(self.kind, self.item, r)
            what = t("bs.lib.for", slot=t("builds.slot." + r)) if r != "general" else t("builds.sec.mods")
            self.library.set_mods(names, self.get_owned() or {}, arcane=r == "arcane", what=what, cw=max(130, int(cw * 0.8)))
            self.library.show()
        finally:
            self.setUpdatesEnabled(True)
