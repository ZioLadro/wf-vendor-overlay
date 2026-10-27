"""Profile tab: your standing per syndicate (imported from lastData.dat / companion JSON, or typed by hand)."""
import os
import time

import aleca

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (QFileDialog, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton, QSpinBox,
                             QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from config import CFG
from i18n import t
from standing import (ProfileError, get_store, is_nightwave, parse_bytes, read_raw, signature,
                      syndicate_name)
from uiutil import role
from uiutil import HINT_STYLE


class ProfileTab(QWidget):
    def __init__(self, market):
        super().__init__()
        self.market = market
        self.store = get_store()
        self.btn = QPushButton(t("profile.import"))
        self.btn.clicked.connect(self.import_file)
        self.btn_reload = QPushButton(t("profile.reload"))
        self.btn_reload.setToolTip(t("profile.reload.tip"))
        self.btn_reload.clicked.connect(self.reload_file)
        self.info = QLabel("")
        role(self.info, "hint")
        self.info.setWordWrap(True)
        self.check = QLabel("")
        role(self.check, "hint")
        top = QHBoxLayout()
        top.addWidget(self.btn)
        top.addWidget(self.btn_reload)
        top.addStretch(1)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels([t("profile.col.syn"), t("profile.col.standing"),
                                              t("profile.col.rank"), t("profile.col.daily"), t("profile.col.source")])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        hint = QLabel(t("profile.hint"))
        role(hint, "hint")
        hint.setWordWrap(True)
        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(self.info)
        lay.addWidget(self.check)
        lay.addWidget(self.table, 1)
        lay.addWidget(hint)
        self._shown = -1
        self.refresh()
        # re-read the file by itself when it changed (cheap check: only the modification time)
        self._timer = QTimer(self, timeout=self.auto_reload)
        every = int(CFG["profile_reload_s"])
        if every > 0:
            self._timer.start(every * 1000)
            QTimer.singleShot(1500, self.auto_reload)

    def auto_reload(self):
        """Looks at the imported file; re-reads it only if its content changed. The result is shown below."""
        path = self.store.path
        if not path or not os.path.exists(path):
            path = aleca.find_data_file()          # AlecaFrame's file, found by itself: nothing to import by hand
            if not path:
                return
        try:
            aleca.sync_player_name(path)
        except Exception:
            pass
        now = time.strftime("%H:%M:%S")
        try:
            raw = read_raw(path)
            sig = signature(raw)
            if sig == self.store.sig:
                self.check.setText(t("profile.check.same", time=now))
                return
            self.store.apply_profile(path, parse_bytes(raw, path))
            self.store.sig = sig
        except ProfileError as e:
            self.check.setText(t("profile.check.error", time=now, err=e))
            return
        self.check.setText(t("profile.check.updated", time=now))
        self.refresh(force=True)

    # ---------- table ----------
    def _tags(self):
        tags = {k for k in self.store.factions if not is_nightwave(k)}
        if CFG["hide_negative_ranks"]:
            tags = {k for k in tags if (self.store.get(k) or {}).get("rank") is None or self.store.get(k)["rank"] >= 0}
        tags.update(e["t"] for r in self.market.snapshot() for e in r["standing"] if e.get("t"))
        return sorted(tags, key=lambda x: syndicate_name(x).lower())

    def refresh(self, force=False):
        if not force and self._shown == self.store.version:
            return
        self._shown = self.store.version
        tags = self._tags()
        self.table.setRowCount(len(tags))
        for r, tag in enumerate(tags):
            f = self.store.get(tag)
            name = QTableWidgetItem(syndicate_name(tag))
            name.setData(Qt.ItemDataRole.UserRole, tag)
            self.table.setItem(r, 0, name)
            sp = QSpinBox(minimum=-100_000_000, maximum=100_000_000, value=f["standing"] if f else 0)
            sp.setGroupSeparatorShown(True)
            sp.editingFinished.connect(lambda tg=tag, w=sp: self._edited(tg, w))
            self.table.setCellWidget(r, 1, sp)
            rk = QSpinBox(minimum=-2, maximum=40, value=(f.get("rank") if f and f.get("rank") is not None else 0))
            rk.editingFinished.connect(lambda tg=tag, w=sp, rw=rk: self._edited(tg, w, rw))
            self.table.setCellWidget(r, 2, rk)
            src = t("profile.src.none") if not f else (t("profile.src.manual") if f.get("manual") else t("profile.src.file"))
            d = f.get("daily") if f else None
            self.table.setItem(r, 3, QTableWidgetItem("" if d is None else f"{d:,}".replace(",", " ")))
            self.table.item(r, 3).setToolTip(t("profile.daily.tip"))
            self.table.setItem(r, 4, QTableWidgetItem(src))
        self.btn_reload.setEnabled(bool(self.store.path))
        if self.store.fetched:
            mr = f"MR {self.store.mr}" if self.store.mr is not None else ""
            self.info.setText(t("profile.info", mr=mr, file=os.path.basename(self.store.path)))
        else:
            self.info.setText(t("profile.empty"))

    def _edited(self, tag, sp, rk=None):
        cur = self.store.get(tag)
        if cur and cur["standing"] == sp.value() and (rk is None or cur.get("rank") == rk.value()):
            return
        self.store.set_manual(tag, sp.value(), rk.value() if rk else None)
        self._shown = self.store.version
        for r in range(self.table.rowCount()):
            if self.table.item(r, 0).data(Qt.ItemDataRole.UserRole) == tag:
                self.table.item(r, 4).setText(t("profile.src.manual"))

    # ---------- import ----------
    def import_file(self):
        start = os.path.dirname(self.store.path) if self.store.path else ""
        if not start:
            aleca = os.path.join(os.environ.get("LOCALAPPDATA", ""), "AlecaFrame")
            start = aleca if os.path.isdir(aleca) else ""
        path, _ = QFileDialog.getOpenFileName(self, t("profile.import"), start, t("profile.filter"))
        if path:
            self._load(path)

    def reload_file(self):
        if self.store.path:
            self._load(self.store.path)

    def _load(self, path):
        try:
            raw = read_raw(path)
            prof = parse_bytes(raw, path)
        except ProfileError as e:
            QMessageBox.warning(self, t("profile.import"), t("profile.error", err=e))
            return
        self.store.apply_profile(path, prof)
        self.store.sig = signature(raw)
        self.refresh(force=True)
