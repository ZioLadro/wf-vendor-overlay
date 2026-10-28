"""Console tab: what the program is doing in the background (picture and logo downloads from the wiki, price updates,
Riven scans, file reloads, overlay messages) and any error, with the jobs in progress on top. Lines come from logbus."""
import html
import time

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
                             QVBoxLayout, QWidget)

from app.core import logbus
from app.core.i18n import t
from app.core.uiutil import role

COLORS = {"info": "", "ok": "#4fbf6a", "warn": "#e0b83a", "error": "#e0584a"}


class ConsoleTab(QWidget):
    def __init__(self):
        super().__init__()
        self._seq = 0
        self._sources = set()
        self.jobs = QLabel("")
        self.jobs.setWordWrap(True)
        self.source = QComboBox()
        self.source.addItem(t("console.all"), "")
        self.errors_only = QCheckBox(t("console.errors"))
        self.btn_clear = QPushButton(t("console.clear"))
        self.btn_save = QPushButton(t("console.save"))
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setMaximumBlockCount(logbus.MAX)
        self.text.setStyleSheet("font-family: Consolas, 'Cascadia Mono', monospace;")
        hint = QLabel(t("console.hint"))
        role(hint, "hint")
        hint.setWordWrap(True)
        bar = QHBoxLayout()
        bar.addWidget(QLabel(t("console.source")))
        bar.addWidget(self.source)
        bar.addWidget(self.errors_only)
        bar.addStretch(1)
        bar.addWidget(self.btn_clear)
        bar.addWidget(self.btn_save)
        lay = QVBoxLayout(self)
        lay.addWidget(self.jobs)
        lay.addLayout(bar)
        lay.addWidget(self.text, 1)
        lay.addWidget(hint)
        self.source.currentIndexChanged.connect(lambda _i: self._redraw())
        self.errors_only.toggled.connect(lambda _c: self._redraw())
        self.btn_clear.clicked.connect(self._clear)
        self.btn_save.clicked.connect(self._save)
        self._timer = QTimer(self, interval=1000, timeout=self._poll)

    def showEvent(self, e):
        super().showEvent(e)
        self._poll()
        self._timer.start()

    def hideEvent(self, e):
        super().hideEvent(e)
        self._timer.stop()

    def _wanted(self, line) -> bool:
        _seq, _ts, src, level, _msg = line
        if self.source.currentData() and src != self.source.currentData():
            return False
        return not self.errors_only.isChecked() or level in ("warn", "error")

    @staticmethod
    def _html(line) -> str:
        _seq, ts, src, level, msg = line
        col = COLORS.get(level, "")
        body = html.escape(f"{time.strftime('%H:%M:%S', time.localtime(ts))}  [{src}]  {msg}")
        return f"<span style='color:{col}'>{body}</span>" if col else body

    def _poll(self):
        new = logbus.since(self._seq)
        if new:
            self._seq = new[-1][0]
            for line in new:
                if line[2] not in self._sources:
                    self._sources.add(line[2])
                    self.source.addItem(line[2], line[2])
            bar = self.text.verticalScrollBar()
            at_end = bar.value() >= bar.maximum() - 4
            for line in new:
                if self._wanted(line):
                    self.text.appendHtml(self._html(line))
            if at_end:
                bar.setValue(bar.maximum())
        jobs = logbus.jobs()
        self.jobs.setText("  ·  ".join(f"<b>{src}</b> {d}/{n}" + (f" ({txt})" if txt else "") for src, (d, n, txt) in jobs.items())
                          if jobs else t("console.idle"))

    def _redraw(self):
        self.text.clear()
        for line in logbus.since(0):
            if line[0] > self._cleared_at() and self._wanted(line):
                self.text.appendHtml(self._html(line))

    def _cleared_at(self) -> int:
        return getattr(self, "_cleared", 0)

    def _clear(self):
        self._cleared = logbus.last_seq()
        self.text.clear()

    def _save(self):
        path, _ = QFileDialog.getSaveFileName(self, t("console.save"), "wfvo_console.txt", "Text (*.txt)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.text.toPlainText())
