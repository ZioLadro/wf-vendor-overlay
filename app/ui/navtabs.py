"""The main window's sections as a sidebar (like AlecaFrame's): an icon and a name per section on the left, the section
on the right. Has the few QTabWidget methods the window uses (addTab, currentWidget, currentChanged…)."""
from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QListWidget, QListWidgetItem, QStackedWidget, QWidget


class NavTabs(QWidget):
    currentChanged = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setFixedWidth(212)
        self.nav.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav.setIconSize(QSize(18, 18))
        self.stack = QStackedWidget()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        lay.addWidget(self.nav)
        lay.addWidget(self.stack, 1)
        self.nav.currentRowChanged.connect(self._row)

    def _row(self, i):
        if 0 <= i < self.stack.count():
            self.stack.setCurrentIndex(i)
            self.currentChanged.emit(i)

    def addTab(self, widget, text, glyph=""):
        it = QListWidgetItem(f"{glyph}   {text.upper()}" if glyph else text.upper())
        it.setToolTip(text)
        self.nav.addItem(it)
        self.stack.addWidget(widget)
        if self.nav.currentRow() < 0:
            self.nav.setCurrentRow(0)
        return self.stack.count() - 1

    def currentWidget(self):
        return self.stack.currentWidget()

    def currentIndex(self):
        return self.stack.currentIndex()

    def setCurrentIndex(self, i):
        self.nav.setCurrentRow(i)

    def setCurrentWidget(self, w):
        i = self.stack.indexOf(w)
        if i >= 0:
            self.nav.setCurrentRow(i)

    def indexOf(self, w):
        return self.stack.indexOf(w)

    def count(self):
        return self.stack.count()

    def widget(self, i):
        return self.stack.widget(i)

    def tabText(self, i):
        it = self.nav.item(i)
        return it.toolTip() if it else ""
