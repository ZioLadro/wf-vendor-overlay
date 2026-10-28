"""Settings → Updates: version, check now, install (with the user's consent)."""
import threading

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import (QApplication, QDialog, QDialogButtonBox, QGroupBox, QHBoxLayout, QLabel, QMessageBox,
                             QProgressBar, QPushButton, QTextBrowser, QVBoxLayout)

from app.core import updater
from app.core.config import CFG, save_config
from app.core.i18n import t
from app.core.uiutil import role
from app.core.uiutil import HINT_STYLE
from app.core.version import __version__


class _Bus(QObject):
    checked = pyqtSignal(object, str)
    progress = pyqtSignal(int, int)
    staged = pyqtSignal(object, str)


class ChangesDialog(QDialog):
    """The update window: the new version, what changed since the installed one (scrollable) and the choices."""

    def __init__(self, parent, info, question, buttons):
        super().__init__(parent)
        self.setWindowTitle(t("update.title"))
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)      # also visible over the game
        self.clicked = None
        head = QLabel(t("update.head", v=info["version"], cur=__version__))
        head.setStyleSheet("font-weight: bold; font-size: 11pt;")
        sub = QLabel(t("update.changes"))
        role(sub, "muted")
        view = QTextBrowser()
        view.setOpenExternalLinks(True)
        view.setMarkdown(info.get("changes") or info.get("notes") or t("update.nochanges"))
        q = QLabel(question)
        q.setWordWrap(True)
        bb = QDialogButtonBox()
        for key, text, r in buttons:
            b = bb.addButton(text, r)
            b.clicked.connect(lambda _c=False, k=key: (setattr(self, "clicked", k), self.accept()))
        lay = QVBoxLayout(self)
        lay.addWidget(head)
        lay.addWidget(sub)
        lay.addWidget(view, 1)
        lay.addWidget(q)
        lay.addWidget(bb)
        self.resize(640, 520)


class UpdateBox(QGroupBox):
    def __init__(self):
        super().__init__(t("group.updates"))
        self.bus = _Bus()
        self.bus.checked.connect(self._checked)
        self.bus.progress.connect(self._progress)
        self.bus.staged.connect(self._staged)
        self.info = QLabel(t("update.version", v=__version__))
        self.status = QLabel("")
        role(self.status, "hint")
        self.status.setWordWrap(True)
        self.btn = QPushButton(t("update.check"))
        self.btn.clicked.connect(self.check)
        self.bar = QProgressBar()
        self.bar.setVisible(False)
        row = QHBoxLayout()
        row.addWidget(self.info)
        row.addStretch(1)
        row.addWidget(self.btn)
        lay = QVBoxLayout(self)
        lay.addLayout(row)
        lay.addWidget(self.status)
        lay.addWidget(self.bar)
        self._info = None

    def check(self):
        self.btn.setEnabled(False)
        self.status.setText(t("update.checking"))

        def run():
            try:
                self.bus.checked.emit(updater.check(), "")
            except updater.UpdateError as e:
                self.bus.checked.emit(None, str(e))
            except Exception as e:
                self.bus.checked.emit(None, type(e).__name__)
        threading.Thread(target=run, daemon=True).start()

    def _checked(self, info, err):
        self.btn.setEnabled(True)
        if info is None:
            self.status.setText(t("update.error", err=err))
            return
        if not info["newer"]:
            self.status.setText(t("update.latest", v=__version__))
            return
        self.offer(info, manual=True)

    def offer(self, info, manual=False):
        """A newer version exists: say what is possible and, if the user agrees, install it."""
        self._info = info
        self.status.setText(t("update.available", v=info["version"]))
        if not manual and str(CFG["skip_update_version"]) == info["version"]:
            return
        if not info.get("installable"):
            # the release exists but has no package yet (the build may be running, or it failed)
            QMessageBox.information(self, t("update.title"), t("update.nopackage", v=info["version"]))
            return
        R = QDialogButtonBox.ButtonRole
        if not updater.can_install():
            box = ChangesDialog(self, info, t("update.manual.q"),
                                [("page", t("update.openpage"), R.AcceptRole), ("later", t("update.later"), R.RejectRole)])
            box.exec()
            if box.clicked == "page":
                QDesktopServices.openUrl(QUrl(info["page"]))
            return
        box = ChangesDialog(self, info, t("update.ask.q"),
                            [("yes", t("update.install"), R.AcceptRole), ("later", t("update.later"), R.RejectRole),
                             ("skip", t("update.skip"), R.DestructiveRole)])
        box.exec()
        if box.clicked == "skip":
            save_config({"skip_update_version": info["version"]})
            return
        if box.clicked != "yes":
            return
        self.btn.setEnabled(False)
        self.bar.setVisible(True)
        self.bar.setRange(0, 0)
        self.status.setText(t("update.downloading"))

        def run():
            try:
                self.bus.staged.emit(updater.download(info, progress=self.bus.progress.emit), "")
            except updater.UpdateError as e:
                self.bus.staged.emit(None, str(e))
            except Exception as e:
                self.bus.staged.emit(None, type(e).__name__)
        threading.Thread(target=run, daemon=True).start()

    def _progress(self, done, total):
        if total:
            self.bar.setRange(0, total)
            self.bar.setValue(done)

    def _staged(self, staging, err):
        self.bar.setVisible(False)
        self.btn.setEnabled(True)
        if staging is None:
            self.status.setText(t("update.error", err=err))
            QMessageBox.warning(self, t("update.title"), t("update.error", err=err))
            return
        self.status.setText(t("update.installing"))
        try:
            updater.launch_installer(staging)
        except OSError as e:
            self.status.setText(t("update.error", err=e))
            QMessageBox.warning(self, t("update.title"), t("update.error", err=e))
            return
        QApplication.quit()
