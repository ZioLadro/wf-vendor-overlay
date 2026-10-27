"""Settings tab: edits config.json from inside the program."""
import re

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFontComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

from config import CFG, DEFAULTS, save_config
from i18n import LANGUAGES, t
from uiutil import role
from uiutil import HINT_STYLE, MUTED_STYLE

# (key, widget, options, restart)   widget: bool | int:(min,max) | float:(min,max,decimals) | choice | text
GROUPS = [
    ("general", [
        ("language", "choice", LANGUAGES, True),
        ("start_active", "bool", None, True),
        ("player_name", "text", None, False),
        ("hide_negative_ranks", "bool", None, False),
        ("check_updates", "bool", None, False),
        ("vendor_check", "bool", None, False),
        ("vendor_header", "bool", None, False),
        ("vendor_header_top", "int", (5, 70), False),
        ("vendor_header_required", "bool", None, False),
        ("vendor_min_items", "int", (1, 20), False),
        ("only_warframe", "bool", None, True),
        ("rec_overlay", "bool", None, False),
        ("rec_overlay_top", "int", (1, 50), False),
        ("auto_detect", "bool", None, False),
        ("show_volume", "bool", None, False),
        ("hide_zero_volume", "bool", None, False),
        ("open_list_on_start", "bool", None, False),
        ("window_on_top", "bool", None, True),
        ("profile_reload_s", "int", (0, 3600), True),
        ("world_refresh_s", "int", (15, 3600), False),
    ]),
    ("hotkeys", [
        ("key_menu", "text", None, True),
        ("key_scan", "text", None, True),
        ("key_clear", "text", None, True),
        ("key_quit", "text", None, True),
    ]),
    ("detection", [
        ("watch_interval", "float", (0.1, 10, 2), False),
        ("watch_interval_moving", "float", (0.1, 20, 2), False),
        ("auto_settle_polls", "int", (1, 20), False),
        ("auto_motion_frac", "float", (0.001, 0.5, 3), False),
        ("auto_min_gap", "float", (0, 60, 1), False),
        ("scroll_debounce", "float", (0.1, 5, 2), False),
        ("match_threshold", "int", (50, 100), True),
    ]),
    ("data", [
        ("refresh_interval", "int", (30, 3600), False),
        ("open_max_age", "int", (0, 3600), False),
        ("show_cached_max_age", "int", (0, 86400), False),
        ("refresh_skip_age", "int", (0, 86400), False),
        ("refresh_confirm_over", "int", (1, 5000), False),
        ("baro_refresh_days", "int", (1, 90), False),
    ]),
    ("theme", [
        ("theme", "choice", "themes", False),
        ("ui_font", "font", None, False),
        ("ui_font_size", "int", (9, 24), False),
    ]),
    ("appearance", [
        ("volume_low", "int", (1, 10000), False),
        ("volume_high", "int", (2, 100000), False),
        ("volume_offset_y", "int", (-20, 40), False),
        ("menu_refresh_ms", "int", (500, 30000), False),
    ]),
    ("performance", [
        ("ocr_threads", "int", (0, 16), True),
        ("ocr_width", "int", (0, 3840), True),
        ("ocr_mask_panel", "bool", None, True),
        ("ocr_priority", "choice", [("normal", "normal"), ("below_normal", "below_normal"), ("idle", "idle")], True),
        ("publish_throttle", "float", (0.0, 2, 2), False),
    ]),
    ("inventory", [
        ("inv_exclude_maxed", "bool", None, False),
        ("inv_exclude_installed", "bool", None, False),
        ("item_previews", "bool", None, False),
        ("assets_auto", "bool", None, False),
        ("assets_dir", "text", None, False),
        ("aya_manual", "int", (0, 1000000), False),
        ("rankup_min_gain", "int", (0, 10000), False),
        ("sell_price_offset", "int", (-100, 100), False),
    ]),
    ("quantframe", [
        ("quantframe_url", "text", None, False),
    ]),
    ("riven", [
        ("riven_rpm", "int", (1, 20), False),
        ("riven_scan_weapons", "int", (1, 500), False),
        ("riven_weapon_filter", "text", None, False),
        ("riven_sell_factor", "int", (30, 100), False),
        ("riven_online_only", "bool", None, False),
        ("riven_min_margin", "int", (0, 100000), False),
        ("riven_min_score", "int", (0, 100), False),
        ("riven_max_price", "int", (0, 1000000), False),
        ("riven_min_sales", "int", (0, 1000), False),
    ]),
    ("recommendations", [
        ("rec_min_volume", "int", (0, 100000), False),
        ("rec_min_price", "int", (0, 100000), False),
        ("rec_top", "int", (10, 2000), False),
        ("ducat_min_ratio", "int", (1, 500), False),
        ("advice_liquid_volume", "int", (1, 1000), False),
        ("advice_trend_weight", "int", (0, 100), False),
        ("sell_min_price", "int", (0, 100000), False),
    ]),
]


_KEY_TOKEN = re.compile(r"^(<[a-z0-9_]+>|[^<>+\s])$")


def _valid_hotkey(s: str) -> bool:
    """pynput format: tokens joined by '+', each a <special_key> or a single character."""
    tokens = s.strip().lower().split("+")
    if not s.strip() or not all(_KEY_TOKEN.match(tok) for tok in tokens):
        return False
    if not any(tok.startswith("<") for tok in tokens):
        return False                         # a bare letter would fire while typing anywhere
    try:
        from pynput import keyboard
        keyboard.HotKey.parse(s.strip().lower())
    except ImportError:
        pass                                 # pynput unavailable here: the pattern check is enough
    except Exception:
        return False
    return True


class SettingsTab(QWidget):
    restart_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.widgets = {}                   # key -> (widget, kind, restart)

        self.subtabs = QTabWidget()
        for gname, fields in GROUPS:
            page = QWidget()
            col = QVBoxLayout(page)
            box = QGroupBox(t("group." + gname))
            form = QFormLayout(box)
            for key, kind, opt, restart in fields:
                w = self._make(kind, opt)
                w.setToolTip(t("set." + key + ".tip"))
                label = QLabel(t("set." + key) + (" ⟳" if restart else ""))
                label.setToolTip(t("set." + key + ".tip"))
                form.addRow(label, w)
                self.widgets[key] = (w, kind, restart)
            col.addWidget(box)
            if gname == "general":
                from update_box import UpdateBox
                self.update_box = UpdateBox()
                col.addWidget(self.update_box)
            if gname == "theme":
                self.theme_note = QLabel(t("settings.theme.note"))
                self.theme_note.setWordWrap(True)
                role(self.theme_note, "hint")
                col.addWidget(self.theme_note)
            col.addStretch(1)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(page)
            self.subtabs.addTab(scroll, t("group." + gname))
        for key in ("theme", "ui_font", "ui_font_size"):
            w = self.widgets[key][0]
            (w.currentIndexChanged if key == "theme" else w.currentFontChanged if key == "ui_font"
             else w.valueChanged).connect(self._preview)

        self.btn_save = QPushButton(t("settings.save"))
        self.btn_restart = QPushButton(t("settings.save_restart"))
        self.btn_defaults = QPushButton(t("settings.defaults"))
        self.msg = QLabel("")
        self.msg.setWordWrap(True)
        role(self.msg, "muted")
        hint = QLabel(t("settings.hint", file=str(_config_path())))
        role(hint, "hint")
        hint.setWordWrap(True)

        buttons = QHBoxLayout()
        buttons.addWidget(self.btn_defaults)
        buttons.addStretch(1)
        buttons.addWidget(self.btn_save)
        buttons.addWidget(self.btn_restart)

        lay = QVBoxLayout(self)
        lay.addWidget(self.subtabs, 1)
        lay.addWidget(self.msg)
        lay.addLayout(buttons)
        lay.addWidget(hint)

        self.btn_save.clicked.connect(lambda: self.save(False))
        self.btn_restart.clicked.connect(lambda: self.save(True))
        self.btn_defaults.clicked.connect(self.restore_defaults)
        self.load()

    @staticmethod
    def _make(kind, opt):
        if kind == "bool":
            return QCheckBox()
        if kind == "int":
            w = QSpinBox(minimum=opt[0], maximum=opt[1])
        elif kind == "float":
            w = QDoubleSpinBox(minimum=opt[0], maximum=opt[1], decimals=opt[2], singleStep=0.1 if opt[1] > 1 else 0.01)
        elif kind == "choice":
            w = QComboBox()
            if opt == "themes":
                import theme
                for tid in theme.ORDER:
                    kind_txt = theme.PRESETS[tid]["kind"]
                    w.addItem(t("theme." + tid) + (f"  ({t('theme.' + kind_txt)})" if kind_txt else ""), tid)
                return w
            for value, label in opt:
                w.addItem(label, value)
            return w
        elif kind == "font":
            w = QFontComboBox()
            w.setMaximumWidth(260)
            return w
        else:
            w = QLineEdit()
            w.setMaximumWidth(220)
            return w
        w.setMaximumWidth(140)
        return w

    # ---------- values <-> widgets ----------
    def _set(self, key, value):
        w, kind, _ = self.widgets[key]
        if kind == "bool":
            w.setChecked(bool(value))
        elif kind in ("int", "float"):
            w.setValue(value)
        elif kind == "choice":
            w.setCurrentIndex(max(0, w.findData(value)))
        elif kind == "font":
            w.setCurrentFont(QFont(str(value)))
        else:
            w.setText(str(value))

    def _get(self, key):
        w, kind, _ = self.widgets[key]
        if kind == "bool":
            return w.isChecked()
        if kind == "int":
            return int(w.value())
        if kind == "float":
            return float(w.value())
        if kind == "choice":
            return w.currentData()
        if kind == "font":
            return w.currentFont().family()
        return w.text().strip()

    def load(self, source=None):
        source = CFG if source is None else source
        for key in self.widgets:
            self._set(key, source[key])

    def _preview(self, *_):
        """Shows the chosen theme / font at once; it is kept only if saved (leaving the tab restores the saved one)."""
        import theme
        theme.apply(None, self._get("theme"), self._get("ui_font"), self._get("ui_font_size"))

    def hideEvent(self, e):
        super().hideEvent(e)
        import theme
        theme.apply()

    def showEvent(self, e):
        super().showEvent(e)
        self.load()                          # picks up values changed elsewhere (e.g. the Recommendations tab)

    def restore_defaults(self):
        self.load(DEFAULTS)
        self.msg.setText(t("settings.defaults_loaded"))

    def save(self, restart: bool):
        new = {k: self._get(k) for k in self.widgets}
        for k in ("key_menu", "key_scan", "key_clear", "key_quit"):
            new[k] = new[k].lower()
        for k in ("key_menu", "key_scan", "key_clear", "key_quit"):
            if not _valid_hotkey(new[k]):
                self.msg.setText(t("settings.bad_key", key=new[k] or "∅"))
                return
        if new["volume_high"] <= new["volume_low"]:
            self.msg.setText(t("settings.bad_volume"))
            return
        changed_restart = [t("set." + k) for k, (_, _, r) in self.widgets.items() if r and new[k] != CFG[k]]
        if not save_config(new):
            self.msg.setText(t("settings.save_failed"))
            return
        text = t("settings.saved")
        if changed_restart:
            text += " " + t("settings.needs_restart", items=", ".join(changed_restart))
        self.msg.setText(text)
        import theme
        theme.apply()
        if restart:
            self.restart_requested.emit()


def _config_path():
    from config import CONFIG_FILE
    return CONFIG_FILE
