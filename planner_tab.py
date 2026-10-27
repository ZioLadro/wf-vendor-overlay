"""Build planner (Builds > Build planner): pick a Warframe or weapon, put mods in the slots, change slot polarities (Forma) and see
capacity, drain and the stat recap. Plans are saved in build_plans.json; a plan can start as a copy of one of your own loadouts."""
import json

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget,
    QMessageBox, QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)

import buildcalc as BC
import loadouts as LO
from buildcards import Scaler, cards_widget, stats_panel
from config import APP_DIR
from i18n import t
from uiutil import role

PLANS_FILE = APP_DIR / "build_plans.json"
KINDS = ("warframe", "primary", "secondary", "melee")
INNATE = "__innate__"                                 # slot polarity as the game has it (no Forma change)


def arcane_max(name: str) -> int:
    for n, mx in LO.data().get("arcanes", {}).values():
        if n == name:
            return mx or 5
    return 5


class SlotDialog(QDialog):
    """Choose the mod (or Arcane), its rank and the slot polarity for one slot."""

    def __init__(self, parent, title, names, cur, can_pol, cur_pol, arcane=False):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.arcane = arcane
        self.resize(380, 480)
        lay = QVBoxLayout(self)
        self.filter = QLineEdit()
        self.filter.setPlaceholderText(t("plan.filter"))
        self.list = QListWidget()
        # a Riven copied from your loadout stays selectable (its stats belong to it: its rank cannot be changed here)
        self.riven = cur[2] if cur and len(cur) > 2 and cur[2] else None
        self.names = ([cur[0]] if self.riven and cur[0] not in names else []) + list(names)
        lay.addWidget(self.filter)
        lay.addWidget(self.list, 1)
        form = QFormLayout()
        self.rank = QSpinBox()
        form.addRow(t("plan.rank"), self.rank)
        self.pol = QComboBox()
        if can_pol:
            self.pol.addItem("—", INNATE)
            self.pol.addItem(t("pol.none"), "")
            for p in BC.POLARITIES:
                self.pol.addItem(t("pol." + p), p)
            i = self.pol.findData(cur_pol if cur_pol is not None else INNATE)
            self.pol.setCurrentIndex(max(0, i))
            form.addRow(t("plan.forma"), self.pol)
        lay.addLayout(form)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self._fill(cur[0] if cur else "")
        self.filter.textChanged.connect(lambda _t: self._fill(self._current()))
        self.list.currentRowChanged.connect(lambda _r: self._sync_rank())
        self.list.itemDoubleClicked.connect(lambda _i: self.accept())
        if cur and cur[0]:
            self._sync_rank(cur[1])
        else:
            self._sync_rank()

    def _current(self) -> str:
        it = self.list.currentItem()
        return it.data(Qt.ItemDataRole.UserRole) if it else ""

    def _fill(self, keep=""):
        text = self.filter.text().strip().lower()
        self.list.blockSignals(True)
        self.list.clear()
        self.list.addItem(t("plan.empty"))
        self.list.item(0).setData(Qt.ItemDataRole.UserRole, "")
        sel = 0
        for n in self.names:
            if text and text not in n.lower():
                continue
            self.list.addItem(n)
            self.list.item(self.list.count() - 1).setData(Qt.ItemDataRole.UserRole, n)
            if n == keep:
                sel = self.list.count() - 1
        self.list.setCurrentRow(sel)
        self.list.blockSignals(False)
        self._sync_rank()

    def _max(self, name):
        if not name:
            return 0
        if self.riven and name == self.riven_name():
            return 0
        if self.arcane:
            return arcane_max(name)
        info = BC.mod_info(name)
        return info[2] if info else 0

    def _sync_rank(self, rank=None):
        mx = self._max(self._current())
        self.rank.setRange(0, mx)
        self.rank.setEnabled(mx > 0)
        self.rank.setValue(mx if rank is None else min(mx, rank))

    def riven_name(self):
        return self.names[0] if self.riven else None

    def result_value(self):
        name = self._current()
        if self.riven and name == self.riven_name():
            return (name, self.riven.get("rank", 0), self.riven)
        return (name, self.rank.value()) if name else None

    def polarity(self):
        return self.pol.currentData() if self.pol.count() else INNATE


class PlannerView(QWidget):
    def __init__(self, get_loadouts):
        super().__init__()
        self.get_loadouts = get_loadouts
        self.kind, self.item = "warframe", ""
        self.mods, self.forma = [], {}
        self.roles = []
        self.reactor, self.level = True, 30
        self.plans = self._read_plans()
        self.scaler = Scaler(self, self._draw)

        self.kind_box = QComboBox()
        for k in KINDS:
            self.kind_box.addItem(t("builds.kind." + k), k)
        self.item_box = QComboBox()
        self.item_box.setEditable(True)
        self.item_box.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.item_box.setMinimumWidth(220)
        self.item_box.completer().setFilterMode(Qt.MatchFlag.MatchContains)          # type part of the name
        self.item_box.completer().setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.chk_reactor = QCheckBox(t("plan.reactor"))
        self.chk_reactor.setChecked(True)
        self.spin_level = QSpinBox()
        self.spin_level.setRange(0, 30)
        self.spin_level.setValue(30)
        self.btn_copy = QPushButton(t("plan.copy"))
        self.btn_clear = QPushButton(t("plan.new"))
        top = QHBoxLayout()
        for w in (QLabel(t("plan.kind")), self.kind_box, QLabel(t("plan.item")), self.item_box, QLabel(t("plan.level")),
                  self.spin_level, self.chk_reactor, self.btn_copy, self.btn_clear):
            top.addWidget(w)
        top.addStretch(1)

        self.name = QLineEdit()
        self.name.setPlaceholderText(t("plan.name"))
        self.saved = QComboBox()
        self.saved.setMinimumWidth(180)
        self.btn_save = QPushButton(t("plan.save"))
        self.btn_del = QPushButton(t("plan.delete"))
        bar = QHBoxLayout()
        bar.addWidget(self.name, 1)
        bar.addWidget(self.btn_save)
        bar.addWidget(QLabel(t("plan.load")))
        bar.addWidget(self.saved)
        bar.addWidget(self.btn_del)

        self.hint = QLabel(t("plan.pick"))
        role(self.hint, "hint")
        self.body = QVBoxLayout()
        self.body.setAlignment(Qt.AlignmentFlag.AlignTop)
        host = QWidget()
        host.setLayout(self.body)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(host)
        self.scaler.area = scroll
        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addLayout(bar)
        lay.addWidget(self.hint)
        lay.addWidget(scroll, 1)

        self.kind_box.currentIndexChanged.connect(lambda _i: self._kind_changed())
        self.item_box.currentIndexChanged.connect(lambda _i: self._item_changed())
        self.item_box.lineEdit().editingFinished.connect(self._item_typed)
        self.chk_reactor.toggled.connect(self._opts_changed)
        self.spin_level.valueChanged.connect(self._opts_changed)
        self.btn_copy.clicked.connect(self._copy)
        self.btn_clear.clicked.connect(self._clear)
        self.btn_save.clicked.connect(self._save)
        self.btn_del.clicked.connect(self._delete)
        self.saved.activated.connect(lambda _i: self._load())
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
        i = self.saved.findData(select)
        self.saved.setCurrentIndex(max(0, i))
        self.saved.blockSignals(False)

    # ---------- state ----------
    def _kind_changed(self):
        self.kind = self.kind_box.currentData()
        self.item_box.blockSignals(True)
        self.item_box.clear()
        for n in BC.items(self.kind):
            self.item_box.addItem(n)
        self.item_box.setCurrentIndex(-1)
        self.item_box.blockSignals(False)
        self.item = ""
        self._reset_slots()
        self._draw()

    def _item_changed(self):
        name = self.item_box.currentText().strip()
        if name == self.item:
            return                                     # same item (e.g. Enter pressed again): keep the mods
        if name not in BC.items(self.kind):
            return                                     # half-typed or unknown name: nothing to plan for
        self.item = name
        self._reset_slots()
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

    def _reset_slots(self):
        cap = LO.max_rank(self.item or "", self.kind)          # Kuva / Tenet / Coda weapons: rank 40
        if self.spin_level.maximum() != cap:
            self.spin_level.blockSignals(True)
            self.spin_level.setRange(0, cap)
            self.spin_level.setValue(cap)
            self.spin_level.blockSignals(False)
            self.level = cap
        self.roles = LO.LAYOUT.get(self.kind) or ["general"] * 8
        self.mods = [None] * len(self.roles)
        self.forma = {}

    def _opts_changed(self, *_a):
        self.reactor, self.level = self.chk_reactor.isChecked(), self.spin_level.value()
        self._draw()

    def _clear(self):
        self._reset_slots()
        self._draw()

    def _set_item(self, kind, item):
        self.kind_box.blockSignals(True)
        self.kind_box.setCurrentIndex(max(0, self.kind_box.findData(kind)))
        self.kind_box.blockSignals(False)
        self.kind = kind
        self.item_box.blockSignals(True)
        self.item_box.clear()
        for n in BC.items(kind):
            self.item_box.addItem(n)
        self.item_box.setCurrentIndex(max(-1, self.item_box.findText(item)))
        self.item_box.setEditText(item)                 # also an item the planner's data does not list
        self.item_box.blockSignals(False)
        self.item = item
        self._reset_slots()

    def _copy(self):
        los = [lo for lo in self.get_loadouts() if lo["kind"] in KINDS]
        if not los:
            QMessageBox.information(self, t("tab.builds"), t("plan.copy.none"))
            return
        labels = [f"{lo['item']} · {lo.get('cfg_name') or lo['config']}" for lo in los]
        label, ok = QInputDialog.getItem(self, t("plan.copy.title"), t("plan.copy.prompt"), labels, 0, False)
        if not ok:
            return
        lo = los[labels.index(label)]
        self._set_item(lo["kind"], lo["item"])
        for i, s in enumerate(lo["slots"][:len(self.mods)]):
            self.mods[i] = ((s["name"], s["rank"], s["riven"]) if s.get("riven") and s["riven"].get("attributes")
                            else (s["name"], s["rank"])) if s["name"] else None
            if s.get("pol") is not None:
                self.forma[i] = s["pol"]
        self.reactor, self.level = bool(lo.get("reactor", True)), int(lo.get("level", 30))
        self.chk_reactor.blockSignals(True)
        self.spin_level.blockSignals(True)
        self.chk_reactor.setChecked(self.reactor)
        self.spin_level.setValue(self.level)
        self.chk_reactor.blockSignals(False)
        self.spin_level.blockSignals(False)
        self.name.setText(label)
        self._draw()

    def _save(self):
        name = self.name.text().strip()
        if not name:
            QMessageBox.information(self, t("tab.builds"), t("plan.noname"))
            return
        self.plans[name] = {"kind": self.kind, "item": self.item, "mods": self.mods, "forma": {str(k): v for k, v in self.forma.items()},
                            "reactor": self.reactor, "level": self.level}
        self._write_plans()
        self._fill_saved(name)
        QMessageBox.information(self, t("tab.builds"), t("plan.saved", name=name))

    def _load(self):
        name = self.saved.currentData()
        p = self.plans.get(name) if name else None
        if not p:
            return
        self._set_item(p.get("kind", "warframe"), p.get("item", ""))
        mods = p.get("mods") or []
        self.mods = [tuple(m) if m else None for m in mods[:len(self.roles)]] + [None] * max(0, len(self.roles) - len(mods))
        self.forma = {int(k): v for k, v in (p.get("forma") or {}).items()}
        self.reactor, self.level = bool(p.get("reactor", True)), int(p.get("level", 30))
        self.chk_reactor.blockSignals(True)
        self.spin_level.blockSignals(True)
        self.chk_reactor.setChecked(self.reactor)
        self.spin_level.setValue(self.level)
        self.chk_reactor.blockSignals(False)
        self.spin_level.blockSignals(False)
        self.name.setText(name)
        self._draw()

    def _delete(self):
        name = self.saved.currentData()
        if name and QMessageBox.question(self, t("tab.builds"), t("plan.confirm.delete", name=name)) == QMessageBox.StandardButton.Yes:
            self.plans.pop(name, None)
            self._write_plans()
            self._fill_saved()

    # ---------- showing ----------
    def evaluate(self):
        pols = BC.slot_polarities(self.kind, self.item, self.roles, self.forma)
        return BC.evaluate(self.kind, self.item, self.roles, self.mods, pols, self.reactor, self.level), pols

    def slots(self):
        calc, pols = self.evaluate()
        out = []
        for i, r in enumerate(self.roles):
            m = self.mods[i]
            name = m[0] if m else ""
            info = BC.mod_info(name) if name and r != "arcane" else None
            rv = m[2] if m and len(m) > 2 else None
            mx = 8 if rv else (info[2] if info else (arcane_max(name) if name else None))
            c = calc["slots"][i]
            out.append({"role": r, "name": name, "rank": m[1] if m else None, "max": mx, "pol": pols[i], "mpol": c["mpol"],
                        "drain": c["drain"], "state": c["state"], "riven": rv})
        return out, calc

    def _draw(self):
        self.setUpdatesEnabled(False)                  # rebuilt in one go: no flashing
        try:
            self._draw_body()
        finally:
            self.setUpdatesEnabled(True)

    def _draw_body(self):
        while self.body.count():
            it = self.body.takeAt(0)
            w = it.widget()
            if w:
                w.setParent(None)
                w.deleteLater()
            elif it.layout():
                self._wipe(it.layout())
        if not LO.data().get("mst"):
            lab = QLabel(t("plan.nodata"))
            lab.setWordWrap(True)
            self.body.addWidget(lab)
            return
        if not self.item:
            return
        slots, calc = self.slots()
        row = QHBoxLayout()
        row.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        row.addWidget(cards_widget(slots, on_click=self._edit, cw=self.scaler.cw))
        col = QVBoxLayout()
        col.setAlignment(Qt.AlignmentFlag.AlignTop)
        col.addWidget(stats_panel({k: calc[k] for k in ("total", "used", "free")}, calc["stats"], self.level, self.reactor, calc.get("bonus")))
        note = QLabel(t("plan.compat"))
        note.setWordWrap(True)
        role(note, "hint")
        col.addWidget(note)
        row.addSpacing(12)
        row.addLayout(col)
        wrap = QWidget()
        wrap.setLayout(row)
        self.body.addWidget(wrap)

    def _wipe(self, layout):
        while layout.count():
            it = layout.takeAt(0)
            w = it.widget()
            if w:
                w.setParent(None)
                w.deleteLater()
            elif it.layout():
                self._wipe(it.layout())

    def _edit(self, i):
        r = self.roles[i]
        arcane = r == "arcane"
        names = BC.arcane_candidates(self.kind) if arcane else BC.candidates(self.kind, self.item, r)
        dlg = SlotDialog(self, t("plan.slot.title", n=i + 1, role=t("builds.slot." + r) if r != "general" else t("builds.sec.mods")),
                         names, self.mods[i], not arcane, self.forma.get(i), arcane=arcane)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self.mods[i] = dlg.result_value()
        if not arcane:
            pol = dlg.polarity()
            if pol == INNATE:
                self.forma.pop(i, None)
            else:
                self.forma[i] = pol
        self._draw()
