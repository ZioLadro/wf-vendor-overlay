"""Settings → Updates: version, check now, install (with the user's consent)."""
import threading

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import (QApplication, QGroupBox, QHBoxLayout, QLabel, QMessageBox, QProgressBar, QPushButton,
                             QVBoxLayout)

import updater
from i18n import t
from uiutil import HINT_STYLE
from version import __version__


class _Bus(QObject):
    checked = pyqtSignal(object, str)
    progress = pyqtSignal(int, int)
    staged = pyqtSignal(object, str)


class UpdateBox(QGroupBox):
    def __init__(self):
        super().__init__(t("group.updates"))
        self.bus = _Bus()
        self.bus.checked.connect(self._checked)
        self.bus.progress.connect(self._progress)
        self.bus.staged.connect(self._staged)
        self.info = QLabel(t("update.version", v=__version__))
        self.status = QLabel("")
        self.status.setStyleSheet(HINT_STYLE)
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
        self._info = info
        self.status.setText(t("update.available", v=info["version"]))
        if not updater.can_install():
            if QMessageBox.question(self, t("update.title"), t("update.manual", v=info["version"], notes=info["notes"])) \
                    == QMessageBox.StandardButton.Yes:
                QDesktopServices.openUrl(QUrl(info["page"]))
            return
        ans = QMessageBox.question(self, t("update.title"), t("update.ask", v=info["version"], notes=info["notes"]))
        if ans != QMessageBox.StandardButton.Yes:
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
            return
        self.status.setText(t("update.installing"))
        try:
            updater.launch_installer(staging)
        except OSError as e:
            self.status.setText(t("update.error", err=e))
            return
        QApplication.quit()
