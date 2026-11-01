"""Riven calculator tab (the grading and the roll planner of RivenLens, github.com/remesis/RivenLens, written again on
the program's own Riven data: see app/game/rivencalc.py).

Left: grade a Riven. Pick the weapon and the rank, type the stats as the game shows them (or read them from a picture of
the card): every stat gets its grade (S best … F worst), its distance from the average roll and the range it can roll.
Under it, every stat the weapon can roll with its range for the chosen layout.
Right: the odds of a Kuva cycle. Up to three wanted positives (each slot accepts one or more stats), what the negative
may be, and optionally a stat kept by locking it: the chance per cycle, the cycles and Kuva expected, and how many
cycles give a 50 % / 90 % chance."""
import math

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QAbstractItemView, QComboBox, QCompleter, QDoubleSpinBox, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
    QMenu, QPushButton, QSpinBox, QSplitter, QTableWidget, QTableWidgetItem, QToolButton, QVBoxLayout, QWidget,
)

from app.core.config import CFG, save_config
from app.core.i18n import t
from app.core.uiutil import role, thousands
from app.game import rivencalc as RC

ROWS = 4                                   # a Riven has 2 or 3 positives and maybe one negative
NEG_MODES = ("any", "none", "good", "must")
REVERSED = {"WeaponRecoilReductionMod"}    # the game shows its bonus with a minus ("-90% Weapon Recoil")


def _layout_text(lay) -> str:
    return t("rcalc.layout", pos=lay[0], neg=lay[1])


def _fmt(v, pct=True) -> str:
    if v is None:
        return "–"
    return f"{v:.1f}%" if pct else f"{v:.1f}"


class MultiPick(QToolButton):
    """A button with a menu of checkable stats: a wanted slot accepting one or more of them ("Any" when none)."""

    def __init__(self, empty_text: str, on_change):
        super().__init__()
        self.empty_text, self.on_change = empty_text, on_change
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.setMinimumWidth(220)
        self.menu_ = QMenu(self)
        self.setMenu(self.menu_)
        self.labels = {}
        self.chosen = set()
        self._refresh_text()

    def set_items(self, items: list, keep=True):
        """items: [(tag, label)]."""
        self.labels = dict(items)
        self.chosen = {x for x in self.chosen if x in self.labels} if keep else set()
        self.menu_.clear()
        for tag, label in items:
            a = self.menu_.addAction(label)
            a.setCheckable(True)
            a.setChecked(tag in self.chosen)
            a.toggled.connect(lambda on, tg=tag: self._toggle(tg, on))
        self.menu_.addSeparator()
        self.menu_.addAction(t("rcalc.any"), self.clear)
        self._refresh_text()

    def _toggle(self, tag, on):
        (self.chosen.add if on else self.chosen.discard)(tag)
        self._refresh_text()
        self.on_change()

    def clear(self):
        self.chosen = set()
        for a in self.menu_.actions():
            if a.isCheckable():
                a.blockSignals(True)
                a.setChecked(False)
                a.blockSignals(False)
        self._refresh_text()
        self.on_change()

    def _refresh_text(self):
        names = [self.labels[x] for x in self.labels if x in self.chosen]
        self.setText(" / ".join(names) if names else self.empty_text)
        self.setToolTip("\n".join(names))


class RivenCalcTab(QWidget):
    def __init__(self):
        super().__init__()
        self._weapons = []
        self.weapon = QComboBox()
        self.weapon.setEditable(True)
        self.weapon.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.weapon.setMinimumWidth(240)
        self.weapon.lineEdit().setPlaceholderText(t("rcalc.weapon.ph"))
        self.rtype = QLabel("")
        role(self.rtype, "muted")
        self.rank = QSpinBox()
        self.rank.setRange(0, 8)
        self.rank.setValue(int(CFG.get("rcalc_rank", 8) or 8))
        self.rank.setPrefix(t("rcalc.rank") + " ")
        self.btn_pic = QPushButton(t("rcalc.picture"))
        self.btn_pic.setToolTip(t("rcalc.picture.tip"))
        top = QHBoxLayout()
        top.addWidget(QLabel(t("rcalc.weapon")))
        top.addWidget(self.weapon)
        top.addWidget(self.rtype)
        top.addWidget(self.rank)
        top.addStretch(1)
        top.addWidget(self.btn_pic)

        # ---- grading ----
        grade_box = QGroupBox(t("rcalc.box.grade"))
        g = QGridLayout(grade_box)
        for c, h in enumerate((t("rcalc.col.stat"), t("rcalc.col.value"), t("rcalc.col.grade"), t("rcalc.col.quality"),
                               t("rcalc.col.range"))):
            lab = QLabel(h)
            role(lab, "muted")
            g.addWidget(lab, 0, c)
        self.rows = []
        for i in range(ROWS):
            stat = QComboBox()
            stat.setMinimumWidth(200)
            val = QDoubleSpinBox()
            val.setRange(-999.9, 999.9)
            val.setDecimals(1)
            val.setSingleStep(0.1)
            val.setKeyboardTracking(False)
            val.setToolTip(t("rcalc.value.tip"))
            gl, ql, rl = QLabel("–"), QLabel(""), QLabel("")
            gl.setMinimumWidth(36)
            gl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            for w in (ql, rl):
                role(w, "muted")
            g.addWidget(stat, i + 1, 0)
            g.addWidget(val, i + 1, 1)
            g.addWidget(gl, i + 1, 2)
            g.addWidget(ql, i + 1, 3)
            g.addWidget(rl, i + 1, 4)
            stat.currentIndexChanged.connect(lambda _i: self.grade())
            val.valueChanged.connect(lambda _v: self.grade())
            self.rows.append((stat, val, gl, ql, rl))
        self.layout_info = QLabel("")
        role(self.layout_info, "hint")
        self.layout_info.setWordWrap(True)
        g.addWidget(self.layout_info, ROWS + 1, 0, 1, 5)
        btn_clear = QPushButton(t("rcalc.clear"))
        btn_clear.clicked.connect(self.clear_stats)
        g.addWidget(btn_clear, ROWS + 2, 4, alignment=Qt.AlignmentFlag.AlignRight)
        g.setColumnStretch(4, 1)

        # ---- ranges of every stat ----
        range_box = QGroupBox(t("rcalc.box.ranges"))
        rl_ = QVBoxLayout(range_box)
        self.range_layout = QComboBox()
        for lay in RC.LAYOUTS:
            self.range_layout.addItem(_layout_text(lay), lay)
        self.range_layout.setCurrentIndex(1)
        h = QHBoxLayout()
        h.addWidget(QLabel(t("rcalc.layout.pick")))
        h.addWidget(self.range_layout)
        h.addStretch(1)
        rl_.addLayout(h)
        self.ranges = QTableWidget(0, 3)
        self.ranges.setHorizontalHeaderLabels([t("rcalc.col.stat"), t("rcalc.col.pos"), t("rcalc.col.neg")])
        self.ranges.verticalHeader().setVisible(False)
        self.ranges.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.ranges.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.ranges.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        rl_.addWidget(self.ranges, 1)

        left = QSplitter(Qt.Orientation.Vertical)
        left.addWidget(grade_box)
        left.addWidget(range_box)
        left.setStretchFactor(1, 1)

        # ---- cycling odds ----
        odds_box = QGroupBox(t("rcalc.box.odds"))
        o = QGridLayout(odds_box)
        hint = QLabel(t("rcalc.odds.hint"))
        hint.setWordWrap(True)
        role(hint, "hint")
        o.addWidget(hint, 0, 0, 1, 2)
        self.want = []
        for i in range(3):
            o.addWidget(QLabel(t("rcalc.want", n=i + 1)), i + 1, 0)
            mp = MultiPick(t("rcalc.any"), self.compute_odds)
            o.addWidget(mp, i + 1, 1)
            self.want.append(mp)
        o.addWidget(QLabel(t("rcalc.neg")), 4, 0)
        self.neg_mode = QComboBox()
        for m in NEG_MODES:
            self.neg_mode.addItem(t("rcalc.neg." + m), m)
        o.addWidget(self.neg_mode, 4, 1)
        o.addWidget(QLabel(t("rcalc.neg.ok")), 5, 0)
        self.neg_ok = MultiPick(t("rcalc.neg.ok.none"), self.compute_odds)
        o.addWidget(self.neg_ok, 5, 1)
        o.addWidget(QLabel(t("rcalc.lock")), 6, 0)
        self.lock = QComboBox()
        self.lock.setToolTip(t("rcalc.lock.tip"))
        o.addWidget(self.lock, 6, 1)
        o.addWidget(QLabel(t("rcalc.lock.layout")), 7, 0)
        self.lock_layout = QComboBox()
        for lay in RC.LAYOUTS:
            self.lock_layout.addItem(_layout_text(lay), lay)
        self.lock_layout.setCurrentIndex(3)
        o.addWidget(self.lock_layout, 7, 1)
        self.odds_out = QLabel("")
        self.odds_out.setWordWrap(True)
        self.odds_out.setTextFormat(Qt.TextFormat.RichText)
        self.odds_out.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        o.addWidget(self.odds_out, 8, 0, 1, 2)
        o.setRowStretch(9, 1)
        o.setColumnStretch(1, 1)
        for w in (self.neg_mode, self.lock, self.lock_layout):
            w.currentIndexChanged.connect(lambda _i: self.compute_odds())

        split = QSplitter()
        split.addWidget(left)
        split.addWidget(odds_box)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        note = QLabel(t("rcalc.note"))
        note.setWordWrap(True)
        role(note, "hint")
        self.status = QLabel("")
        role(self.status, "muted")
        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(split, 1)
        lay.addWidget(self.status)
        lay.addWidget(note)

        self.weapon.activated.connect(lambda _i: self.set_weapon(self.weapon.currentText()))
        self.weapon.lineEdit().editingFinished.connect(lambda: self.set_weapon(self.weapon.currentText()))
        self.rank.valueChanged.connect(self._rank_changed)
        self.range_layout.currentIndexChanged.connect(lambda _i: self.fill_ranges())
        self.btn_pic.clicked.connect(self._picture_menu)
        self._wname, self._rtype, self._pos, self._neg = "", "", [], []
        self._loaded = False

    # ---------- weapon ----------
    def showEvent(self, e):
        super().showEvent(e)
        if not self._loaded:
            self._loaded = True
            self.reload_weapons()

    def refresh(self, force=False):
        if force and self._loaded:
            self.reload_weapons()

    def reload_weapons(self):
        """The weapons a Riven exists for (the game data, plus warframe.market's list once the Riven flip scanned)."""
        cur = self._wname or str(CFG.get("rcalc_weapon") or "")
        self._weapons = RC.weapons()
        self.weapon.blockSignals(True)
        self.weapon.clear()
        for name, ty in self._weapons:
            self.weapon.addItem(name, ty)
        comp = QCompleter([n for n, _ty in self._weapons], self.weapon)
        comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        comp.setFilterMode(Qt.MatchFlag.MatchContains)
        self.weapon.setCompleter(comp)
        self.weapon.blockSignals(False)
        self.set_weapon(cur or (self._weapons[0][0] if self._weapons else ""), force=True)

    def set_weapon(self, name: str, force=False):
        name = name.strip()
        hit = next((n for n, _ty in self._weapons if n.lower() == name.lower()), None)
        if not hit:
            hit = next((n for n, _ty in self._weapons if name.lower() and name.lower() in n.lower()), None)
        if not hit:
            self.status.setText(t("rcalc.weapon.unknown", name=name) if name else "")
            return
        if hit == self._wname and not force:
            return
        self._wname = hit
        self.weapon.blockSignals(True)
        self.weapon.setCurrentIndex(self.weapon.findText(hit))
        self.weapon.blockSignals(False)
        self._rtype = RC.type_of(hit) or "Rifle"
        self._stats = RC.stats(self._rtype)
        try:
            self._pos, self._neg = RC.pools(hit, self._rtype)
        except Exception:
            self._pos = [k for k, s in self._stats.items() if s["pos"]]
            self._neg = [k for k, s in self._stats.items() if s["neg"]]
        self.rtype.setText(t("rcalc.type", type=t("rcalc.t." + self._rtype.lower()), pos=len(self._pos),
                             neg=len(self._neg)))
        self.status.setText("")
        save_config({"rcalc_weapon": hit})
        self._fill_stat_choices()
        self.fill_ranges()
        self._fill_odds_choices()
        self.grade()
        self.compute_odds()

    def _label(self, tag) -> str:
        return (self._stats.get(tag) or {}).get("label", tag)

    def _rank_changed(self, v):
        save_config({"rcalc_rank": int(v)})
        self.fill_ranges()
        self.grade()

    # ---------- grading ----------
    def _fill_stat_choices(self):
        tags = sorted(set(self._pos) | set(self._neg), key=lambda tg: self._label(tg).lower())
        for stat, *_rest in self.rows:
            keep = stat.currentData()
            stat.blockSignals(True)
            stat.clear()
            stat.addItem("—", "")
            for tg in tags:
                stat.addItem(self._label(tg), tg)
            stat.setCurrentIndex(max(0, stat.findData(keep)))
            stat.blockSignals(False)

    def clear_stats(self):
        for stat, val, *_r in self.rows:
            stat.blockSignals(True)
            val.blockSignals(True)
            stat.setCurrentIndex(0)
            val.setValue(0)
            stat.blockSignals(False)
            val.blockSignals(False)
        self.grade()

    def _entered(self) -> list:
        out = []
        for i, (stat, val, *_r) in enumerate(self.rows):
            if stat.currentData() and val.value() != 0:
                out.append((i, stat.currentData(), val.value()))
        return out

    def grade(self):
        entered = self._entered()
        for _stat, _val, gl, ql, rl in self.rows:
            gl.setText("–")
            gl.setStyleSheet("")
            ql.setText("")
            rl.setText("")
        if not entered or not self._rtype:
            self.layout_info.setText(t("rcalc.grade.howto"))
            return
        attrs = []
        for _i, tg, v in entered:
            if self._stats.get(tg, {}).get("faction") and 0 < v < 3:
                positive = v >= 1                        # typed as the game's multiplier: x1.25 / x0.62
            elif tg in REVERSED:
                positive = v < 0                         # recoil: the game shows the bonus as "-x %"
            else:
                positive = v > 0
            attrs.append({"tag": tg, "value": -v if tg in REVERSED else v, "positive": positive})
        npos = sum(1 for a in attrs if a["positive"])
        layout = (npos, len(attrs) - npos)
        res = RC.grade_riven(self._wname, attrs, self.rank.value())
        for (i, _tg, _v), r in zip(entered, res):
            _stat, _val, gl, ql, rl = self.rows[i]
            gr = r["grade"]
            gl.setText(gr + ("/" + r["edge"] if r.get("edge") else ""))
            col = RC.GRADE_COLORS.get(gr, "#9aa4b2")
            gl.setStyleSheet(f"font-weight: 700; color: {col};")
            if r["quality"] is not None:
                ql.setText(f"{r['quality']:+.1f}%" if r["ok"] else t("rcalc.out", q=f"{r['quality']:+.0f}"))
            if r["low"] is not None:
                rl.setText(f"{r['low']:.1f} – {r['high']:.1f}")
        valid = layout in RC.LAYOUTS
        txt = t("rcalc.layout.is", layout=_layout_text(layout)) if valid else t("rcalc.layout.bad")
        if any(not r["ok"] for r in res) and valid:
            txt += " " + t("rcalc.grade.off")
        self.layout_info.setText(txt)
        if valid:
            self.range_layout.blockSignals(True)
            self.range_layout.setCurrentIndex(RC.LAYOUTS.index(layout))
            self.range_layout.blockSignals(False)
            self.fill_ranges()

    def fill_ranges(self):
        lay = self.range_layout.currentData() or (2, 1)
        rank = self.rank.value()
        tags = sorted(set(self._pos) | set(self._neg), key=lambda tg: self._label(tg).lower())
        self.ranges.setRowCount(len(tags))
        for r, tg in enumerate(tags):
            pos = RC.value_range(tg, self._rtype, lay, True, rank) if tg in self._pos else None
            neg = RC.value_range(tg, self._rtype, lay, False, rank) if tg in self._neg and lay[1] else None
            cells = (self._label(tg),
                     f"+{pos[0]:.1f} – +{pos[1]:.1f}" if pos else "–",
                     f"-{abs(neg[0]):.1f} – -{abs(neg[1]):.1f}" if neg else "–")
            for c, text in enumerate(cells):
                it = QTableWidgetItem(text)
                if c:
                    it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.ranges.setItem(r, c, it)
        self.ranges.resizeColumnsToContents()
        self.ranges.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)

    # ---------- picture of a Riven ----------
    def _picture_menu(self):
        m = QMenu(self)
        m.addAction(t("bs.riven.image"), lambda: self._picture(False))
        a = m.addAction(t("bs.riven.clip"), lambda: self._picture(True))
        a.setEnabled(not QGuiApplication.clipboard().image().isNull())
        m.exec(self.btn_pic.mapToGlobal(self.btn_pic.rect().bottomLeft()))

    def _picture(self, from_clipboard: bool):
        from app.ui.planner_tab import ocr_picture

        def done(res):
            from app.game import rivenocr
            if isinstance(res, str):
                self.status.setText(t("share.image.bad", err=res))
                return
            try:
                rv = rivenocr.parse(res[0], "")
            except ValueError as e:
                self.status.setText(t("share.image.bad", err=str(e)))
                return
            self.apply_riven(rv)
        ocr_picture(self, from_clipboard, t("rcalc.picture"), done, self.status.setText)

    def apply_riven(self, rv: dict):
        """A Riven read from a picture (rivenocr.parse) or the planner: its weapon and stats in the grading rows."""
        if rv.get("weapon"):
            self.set_weapon(rv["weapon"])
        if rv.get("rank") is not None:
            self.rank.setValue(int(rv["rank"]))
        from app.game import rivens as R
        by_label = {R._norm(s["label"]).split(" (")[0]: tg for tg, s in self._stats.items()}
        by_label.update({R._norm(s["label"]): tg for tg, s in self._stats.items()})
        attrs = list(rv.get("attributes") or [])[:ROWS]
        missing = []
        for i, (stat, val, *_r) in enumerate(self.rows):
            stat.blockSignals(True)
            val.blockSignals(True)
            if i < len(attrs):
                a = attrs[i]
                tg = a.get("tag") or by_label.get(R._norm(str(a.get("label", ""))))
                if tg is None:
                    tg = by_label.get(R._norm(str(a.get("label", "")).split(" (")[0]))
                stat.setCurrentIndex(max(0, stat.findData(tg)))
                val.setValue(float(a.get("value") or 0))
                if not tg:
                    missing.append(str(a.get("label", "?")))
            else:
                stat.setCurrentIndex(0)
                val.setValue(0)
            stat.blockSignals(False)
            val.blockSignals(False)
        self.grade()
        self.status.setText(t("rcalc.picture.done", weapon=self._wname, n=len(attrs))
                            + (" " + t("rcalc.picture.missing", names=", ".join(missing)) if missing else ""))

    # ---------- cycling odds ----------
    def _fill_odds_choices(self):
        pos = sorted(self._pos, key=lambda tg: self._label(tg).lower())
        neg = sorted(self._neg, key=lambda tg: self._label(tg).lower())
        for mp in self.want:
            mp.set_items([(tg, self._label(tg)) for tg in pos])
        self.neg_ok.set_items([(tg, self._label(tg)) for tg in neg])
        keep = self.lock.currentData()
        self.lock.blockSignals(True)
        self.lock.clear()
        self.lock.addItem(t("rcalc.lock.none"), "")
        for tg in pos:
            self.lock.addItem(self._label(tg), tg)
        self.lock.setCurrentIndex(max(0, self.lock.findData(keep)))
        self.lock.blockSignals(False)

    def compute_odds(self):
        if not self._pos:
            self.odds_out.setText("")
            return
        wanted = [mp.chosen for mp in self.want if mp.chosen]
        mode = self.neg_mode.currentData() or "any"
        lock = self.lock.currentData() or ""
        self.lock_layout.setEnabled(bool(lock))
        if mode in ("good", "must") and not self.neg_ok.chosen:
            self.odds_out.setText(t("rcalc.odds.pickneg"))
            return
        if not wanted and mode == "any" and not lock:
            self.odds_out.setText(t("rcalc.odds.howto"))
            return
        if lock and lock_layout_bad(self.lock_layout.currentData(), wanted, lock):
            self.odds_out.setText(t("rcalc.odds.toomany"))
            return
        try:
            r = RC.odds(self._pos, self._neg, wanted, mode, self.neg_ok.chosen, lock=lock,
                        lock_layout=self.lock_layout.currentData())
        except Exception as e:                           # never let a combination stop the tab
            self.odds_out.setText(str(e))
            return
        if r["p"] <= 0:
            self.odds_out.setText(t("rcalc.odds.never"))
            return
        lines = [t("rcalc.odds.p", p=_pct(r["p"]), one=thousands(round(1 / r["p"]))),
                 t("rcalc.odds.rolls", n=thousands(math.ceil(r["rolls"])), kuva=thousands(round(r["kuva"]))),
                 t("rcalc.odds.q", p50=thousands(r["p50"]), p90=thousands(r["p90"]),
                   k50=thousands(r["p50"] * r["cost"]), k90=thousands(r["p90"] * r["cost"]))]
        by = r.get("by_layout") or {}
        if by and not lock:
            lines.append(t("rcalc.odds.by") + " " + " · ".join(f"{_layout_text(k)}: {_pct(v)}" for k, v in sorted(by.items())))
        if lock:
            lines.append(t("rcalc.odds.locked", cost=thousands(r["cost"])))
        self.odds_out.setText("<br>".join(lines))


def lock_layout_bad(layout, wanted, lock) -> bool:
    """More wanted positives than the locked layout has room for."""
    k = (layout or (3, 1))[0]
    others = [w for w in wanted if lock not in w]
    return len(others) > k - 1


def _pct(p: float) -> str:
    if p >= 0.1:
        return f"{p * 100:.1f}%"
    if p >= 0.001:
        return f"{p * 100:.2f}%"
    return f"{p * 100:.4f}%"
