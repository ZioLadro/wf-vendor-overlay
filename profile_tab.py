"""Profile tab: your standing per syndicate (public profile by in-game name, or typed by hand)."""
import threading

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtWidgets import (QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton, QSpinBox, QTableWidget,
                             QTableWidgetItem, QVBoxLayout, QWidget)

from config import CFG, save_config
from i18n import t
from standing import ProfileError, fetch_profile, get_store, syndicate_name
from uiutil import HINT_STYLE


class _Bus(QObject):
    done = pyqtSignal(object, str)


class ProfileTab(QWidget):
    def __init__(self, market):
        super().__init__()
        self.market = market
        self.store = get_store()
        self.bus = _Bus()
        self.bus.done.connect(self._done)
        self.name = QLineEdit(self.store.name or CFG["player_name"])
        self.name.setPlaceholderText(t("profile.name_ph"))
        self.name.setMaximumWidth(240)
        self.btn = QPushButton(t("profile.fetch"))
        self.btn.clicked.connect(self.fetch)
        self.name.returnPressed.connect(self.fetch)
        self.info = QLabel("")
        self.info.setStyleSheet(HINT_STYLE)
        self.info.setWordWrap(True)
        top = QHBoxLayout()
        top.addWidget(QLabel(t("profile.name")))
        top.addWidget(self.name)
        top.addWidget(self.btn)
        top.addStretch(1)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([t("profile.col.syn"), t("profile.col.standing"),
                                              t("profile.col.rank"), t("profile.col.source")])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        hint = QLabel(t("profile.hint"))
        hint.setStyleSheet(HINT_STYLE)
        hint.setWordWrap(True)
        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(self.info)
        lay.addWidget(self.table, 1)
        lay.addWidget(hint)
        self._shown = -1
        self.refresh()

    # ---------- table ----------
    def _tags(self):
        tags = set(self.store.factions)
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
            sp = QSpinBox(minimum=0, maximum=100_000_000, value=f["standing"] if f else 0)
            sp.setGroupSeparatorShown(True)
            sp.editingFinished.connect(lambda tg=tag, w=sp: self._edited(tg, w))
            self.table.setCellWidget(r, 1, sp)
            rk = QSpinBox(minimum=-2, maximum=10, value=(f.get("rank") if f and f.get("rank") is not None else 0))
            rk.editingFinished.connect(lambda tg=tag, w=sp, rw=rk: self._edited(tg, w, rw))
            self.table.setCellWidget(r, 2, rk)
            src = t("profile.src.none") if not f else (t("profile.src.manual") if f.get("manual") else t("profile.src.profile"))
            self.table.setItem(r, 3, QTableWidgetItem(src))
        mr = f"MR {self.store.mr}" if self.store.mr is not None else ""
        self.info.setText(t("profile.info", mr=mr) if self.store.fetched else t("profile.empty"))

    def _edited(self, tag, sp, rk=None):
        cur = self.store.get(tag)
        if cur and cur["standing"] == sp.value() and (rk is None or cur.get("rank") == rk.value()):
            return
        self.store.set_manual(tag, sp.value(), rk.value() if rk else None)
        self._shown = self.store.version
        for r in range(self.table.rowCount()):
            if self.table.item(r, 0).data(Qt.ItemDataRole.UserRole) == tag:
                self.table.item(r, 3).setText(t("profile.src.manual"))

    # ---------- fetch ----------
    def fetch(self):
        name = self.name.text().strip()
        if not name:
            self.info.setText(t("profile.need_name"))
            return
        self.btn.setEnabled(False)
        self.info.setText(t("profile.loading"))

        def run():
            try:
                self.bus.done.emit((name, fetch_profile(name)), "")
            except ProfileError as e:
                self.bus.done.emit(None, str(e))
            except Exception as e:
                self.bus.done.emit(None, type(e).__name__)
        threading.Thread(target=run, daemon=True).start()

    def _done(self, res, err):
        self.btn.setEnabled(True)
        if res is None:
            self.info.setText(t("profile.error", err=err))
            return
        name, prof = res
        self.store.apply_profile(name, prof)
        save_config({"player_name": name})
        if not prof["factions"]:
            self.refresh(force=True)
            self.info.setText(t("profile.no_syndicates"))
            return
        self.refresh(force=True)
