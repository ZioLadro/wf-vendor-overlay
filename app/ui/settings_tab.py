"""Settings tab: edits config.json from inside the program."""
import re

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFontComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

from app.core.config import CFG, DEFAULTS, save_config
from app.core.i18n import LANGUAGES, t
from app.core.uiutil import role
from app.core.uiutil import HINT_STYLE, MUTED_STYLE

# tab -> [(box, [(key, widget, options, restart)])]   widget: bool | int:(min,max) | float:(min,max,decimals) | choice | text
# | color | font | activities | wallet
GROUPS = [
    ("general", [
        ("general", [
            ("language", "choice", LANGUAGES, True),
            ("player_name", "text", None, False),
            ("start_active", "bool", None, True),
            ("open_list_on_start", "bool", None, False),
            ("window_on_top", "bool", None, True),
            ("check_updates", "bool", None, False),
            ("profile_reload_s", "int", (0, 3600), True),
        ]),
        ("player", [
            ("wallet_shown", "wallet", None, False),
            ("hide_negative_ranks", "bool", None, False),
            ("world_strip", "bool", None, True),
            ("world_refresh_s", "int", (15, 3600), False),
        ]),
    ]),
    ("hotkeys", [
        ("hotkeys", [
            ("key_menu", "text", None, True),
            ("key_scan", "text", None, True),
            ("key_clear", "text", None, True),
            ("key_quit", "text", None, True),
            ("key_goals", "text", None, True),
            ("key_goals_interact", "text", None, True),
        ]),
    ]),
    ("sounds", [
        ("sounds", [
            ("sound_vendor", "bool", None, False),
            ("sound_riven", "bool", None, False),
            ("sound_deal", "bool", None, False),
            ("sound_prices", "bool", None, False),
            ("sound_file", "text", "sound", False),
        ]),
    ]),
    ("detection", [
        ("vendor", [                                     # is the screen read a vendor's, and which one
            ("auto_detect", "bool", None, False),
            ("vendor_check", "bool", None, False),
            ("vendor_min_items", "int", (1, 20), False),
            ("vendor_min_share", "float", (0.3, 1, 2), False),
            ("vendor_header", "bool", None, False),
            ("vendor_header_top", "int", (5, 70), False),
            ("vendor_header_required", "bool", None, False),
            ("weekly_ocr", "bool", None, False),
        ]),
        ("eelog", [                                      # the game's own log: where you are
            ("ee_log", "bool", None, False),
            ("ee_log_skip_missions", "bool", None, False),
            ("ee_log_path", "text", "eelog", False),
        ]),
        ("screen", [
            ("only_warframe", "bool", None, True),
            ("watch_interval", "float", (0.1, 10, 2), False),
            ("watch_interval_moving", "float", (0.1, 20, 2), False),
            ("auto_settle_polls", "int", (1, 20), False),
            ("auto_motion_frac", "float", (0.001, 0.5, 3), False),
            ("auto_min_gap", "float", (0, 60, 1), False),
            ("scroll_debounce", "float", (0.1, 5, 2), False),
            ("match_threshold", "int", (50, 100), True),
        ]),
    ]),
    ("data", [
        ("data", [
            ("refresh_interval", "int", (30, 3600), False),
            ("open_max_age", "int", (0, 3600), False),
            ("show_cached_max_age", "int", (0, 86400), False),
            ("refresh_skip_age", "int", (0, 86400), False),
            ("refresh_confirm_over", "int", (1, 5000), False),
            ("baro_refresh_days", "int", (1, 90), False),
        ]),
    ]),
    ("theme", [
        ("theme", [
            ("theme", "choice", "themes", False),
            ("backdrop", "bool", None, False),
            ("backdrop_style", "choice", "backdrops", False),
            ("backdrop_image", "text", "picture", False),
            ("backdrop_strength", "int", (0, 100), False),
            ("ui_font", "font", None, False),
            ("ui_font_size", "int", (9, 24), False),
            ("mod_frames", "bool", None, False),
            ("build_figure", "bool", None, False),
        ]),
    ]),
    ("performance", [
        ("performance", [
            ("ocr_threads", "int", (0, 16), True),
            ("ocr_width", "int", (0, 3840), True),
            ("ocr_mask_panel", "bool", None, True),
            ("ocr_priority", "choice", [("normal", "normal"), ("below_normal", "below_normal"), ("idle", "idle")], True),
            ("publish_throttle", "float", (0.0, 2, 2), False),
            ("menu_refresh_ms", "int", (500, 30000), False),
        ]),
    ]),
    ("inventory", [
        ("inventory", [
            ("inv_exclude_maxed", "bool", None, False),
            ("inv_exclude_installed", "bool", None, False),
            ("rankup_min_gain", "int", (0, 10000), False),
            ("sell_price_offset", "int", (-100, 100), False),
            ("aya_manual", "int", (0, 1000000), False),
        ]),
        ("pictures", [
            ("item_previews", "bool", None, False),
            ("assets_auto", "bool", None, False),
            ("assets_dir", "text", None, False),
        ]),
    ]),
    ("quantframe", [
        ("quantframe", [
            ("quantframe_url", "text", None, False),
        ]),
    ]),
    ("riven", [
        ("riven_scan", [
            ("riven_rpm", "int", (1, 20), False),
            ("riven_scan_weapons", "int", (1, 500), False),
            ("riven_auto_hours", "int", (0, 168), False),
            ("riven_weapon_filter", "text", None, False),
        ]),
        ("riven_deals", [
            ("riven_sell_factor", "int", (30, 100), False),
            ("riven_min_margin", "int", (0, 100000), False),
            ("riven_min_score", "int", (0, 100), False),
            ("riven_max_price", "int", (0, 1000000), False),
            ("riven_min_sales", "int", (0, 1000), False),
            ("riven_max_age_days", "int", (0, 365), False),
            ("riven_online_only", "bool", None, False),
            ("riven_bids", "bool", None, False),
            ("riven_whisper", "text", "wide", False),
        ]),
        ("riven_live", [
            ("riven_live_top", "int", (0, 50), False),
            ("riven_live_minutes", "int", (1, 120), False),
            ("riven_live_rpm", "int", (1, 10), False),
            ("riven_alert_margin", "int", (0, 100000), False),
        ]),
    ]),
    ("recommendations", [
        ("recommendations", [
            ("rec_min_volume", "int", (0, 100000), False),
            ("rec_min_price", "int", (0, 100000), False),
            ("rec_top", "int", (10, 2000), False),
            ("pmax_min_volume", "float", (0, 50, 1), False),
            ("stale_refresh_h", "float", (0, 48, 1), False),
            ("ducat_min_ratio", "int", (1, 500), False),
            ("advice_liquid_volume", "int", (1, 1000), False),
            ("advice_trend_weight", "int", (0, 100), False),
            ("sell_min_price", "int", (0, 100000), False),
        ]),
    ]),
]


# the Overlay tab (its own section of the main window since 0.7.0): the prices on the vendor screen and the Activities
# overlay, one page each
OVERLAY_GROUPS = [
    ("ov_prices", [
        ("ov_prices", [                                  # prices over the vendor screen
            ("show_volume", "bool", None, False),
            ("volume_offset_y", "int", (-20, 40), False),
            ("volume_low", "int", (1, 10000), False),
            ("volume_high", "int", (2, 100000), False),
            ("hide_zero_volume", "bool", None, False),
            ("hide_operational_supply", "bool", None, False),
            ("rec_overlay", "bool", None, False),
            ("rec_overlay_top", "int", (1, 50), False),
            ("ov_theme", "choice", "ov_themes", False),
            ("ov_price_font", "int", (7, 24), False),
            ("ov_vol_font", "int", (6, 20), False),
            ("ov_bg_opacity", "int", (0, 100), False),
            ("ov_price_color", "color", None, False),
            ("ov_star_color", "color", None, False),
        ]),
    ]),
    ("ov_goals_look", [
        ("ov_goals_look", [                              # the Activities overlay: how it looks
            ("goals_theme", "choice", "goals_themes", False),
            ("goals_opacity", "int", (0, 100), False),
            ("goals_font", "int", (8, 24), False),
            ("goals_font_family", "font", "empty", False),
            ("goals_title_color", "color", None, False),
            ("goals_text_color", "color", None, False),
            ("goals_ready_color", "color", None, False),
            ("goals_hint_color", "color", None, False),
            ("goals_soon_color", "color", None, False),
            ("goals_interact", "choice", "goals_interact", False),
            ("goals_unlock_s", "int", (2, 120), False),
            ("goals_track_interact", "bool", None, False),
        ]),
    ]),
    ("ov_goals_content", [
        ("ov_goals_content", [                           # … and what it lists
            ("goals_untracked", "activities", None, False),
            ("goals_items", "int", (1, 40), False),
            ("goals_per_vendor", "bool", None, False),
            ("goals_repeat", "bool", None, False),
            ("goals_by_reset", "bool", None, False),
            ("goals_activities", "bool", None, False),
            ("goals_only_short", "bool", None, False),
            ("goals_where", "bool", None, False),
            ("goals_weekly", "bool", None, False),
            ("goals_quests", "bool", None, False),
            ("goals_cal_rows", "int", (0, 20), False),
            ("goals_routine", "bool", None, False),
        ]),
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


HOTKEYS = ("key_menu", "key_scan", "key_clear", "key_quit", "key_goals", "key_goals_interact")


class SettingsTab(QWidget):
    """A page of settings (sub-tabs of boxes of fields). The Settings section uses GROUPS; the Overlay section is the
    same page with OVERLAY_GROUPS (and a preview of the overlays' colours)."""
    restart_requested = pyqtSignal()

    def __init__(self, groups=None, overlay=False):
        super().__init__()
        self.widgets = {}                   # key -> (widget, kind, restart)
        self.overlay = overlay
        groups = GROUPS if groups is None else groups
        self.update_box = None

        self.subtabs = QTabWidget()
        for gname, boxes in groups:
            page = QWidget()
            col = QVBoxLayout(page)
            for bname, fields in boxes:
                box = QGroupBox(t("box." + bname))
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
                from app.ui.update_box import UpdateBox
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
        if overlay:                          # previews of the overlays with the values on the page (redrawn twice a second)
            self.preview = OverlayPreview(self)
            col = self.subtabs.widget(0).widget().layout()
            col.insertWidget(0, self.preview)
            self.goals_preview = GoalsPreview(self)
            gl = self.subtabs.widget(1).widget().layout()
            gl.insertWidget(0, self.goals_preview)
            from PyQt6.QtCore import QTimer
            self._prev_timer = QTimer(self, interval=500,
                                      timeout=lambda: (self.preview.update(), self.goals_preview.update()))
        for key in ("theme", "ui_font", "ui_font_size"):
            if key not in self.widgets:
                continue
            w = self.widgets[key][0]
            (w.currentIndexChanged if key == "theme" else w.currentFontChanged if key == "ui_font"
             else w.valueChanged).connect(self._preview)

        self.btn_save = QPushButton(t("settings.save"))
        role(self.btn_save, "primary")
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

    def _make(self, kind, opt):
        if kind == "activities":                      # a button opening the list of the Activities overlay
            w = QPushButton(t("set.goals_untracked.button"))
            w.value = []
            w.clicked.connect(lambda _c=False, b=w: SettingsTab._edit_activities(b))
            w.setMaximumWidth(260)
            return w
        if kind == "bool":
            return QCheckBox()
        if kind == "wallet":                          # one tick per currency the player strip can show
            from PyQt6.QtWidgets import QGridLayout
            from app.ui.player_bar import PlayerBar
            w = QWidget()
            g = QGridLayout(w)
            g.setContentsMargins(0, 0, 0, 0)
            g.setHorizontalSpacing(14)
            w.boxes = {}
            for n, (k, lab) in enumerate(PlayerBar.WALLET):
                cb = QCheckBox(t(lab))
                w.boxes[k] = cb
                g.addWidget(cb, n // 4, n % 4)
            return w
        if kind == "color":                           # a button showing the colour; a click opens the colour picker
            w = QPushButton()
            w.value = "#ffffff"
            w.setMaximumWidth(140)

            def pick(_c=False, b=w):
                from PyQt6.QtGui import QColor
                from PyQt6.QtWidgets import QColorDialog
                c = QColorDialog.getColor(QColor(b.value), b)
                if c.isValid():
                    SettingsTab._paint_color(b, c.name())
            w.clicked.connect(pick)
            return w
        if kind == "int":
            w = QSpinBox(minimum=opt[0], maximum=opt[1])
        elif kind == "float":
            w = QDoubleSpinBox(minimum=opt[0], maximum=opt[1], decimals=opt[2], singleStep=0.1 if opt[1] > 1 else 0.01)
        elif kind == "choice":
            w = QComboBox()
            if opt == "backdrops":
                from app.core import theme
                w.addItem(t("backdrop.auto"), "auto")
                for b in theme.BACKDROPS:
                    w.addItem(t("backdrop." + b), b)
                w.addItem(t("backdrop.image"), "image")
                w.addItem(t("backdrop.none"), "none")
                return w
            if opt == "themes":
                from app.core import theme
                for tid in theme.ORDER:
                    kind_txt = theme.PRESETS[tid]["kind"]
                    w.addItem(t("theme." + tid) + (f"  ({t('theme.' + kind_txt)})" if kind_txt else ""), tid)
                return w
            if opt in ("goals_themes", "ov_themes"):     # the overlays: the program's theme, your colours, or any theme
                from app.core import theme
                w.addItem(t("ovtheme.program"), "program")
                w.addItem(t("ovtheme.custom"), "custom")
                if opt == "goals_themes":
                    w.addItem(t("ovtheme.game"), "game")
                for tid in theme.ORDER:
                    w.addItem(t("theme." + tid), tid)
                return w
            if opt == "goals_interact":
                for v in ("hotkey", "cursor", "always"):
                    w.addItem(t("goals.interact." + v), v)
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
            if opt == "wide":
                w.setMaximumWidth(560)
                w.setMinimumWidth(420)
            if opt == "sound":                         # a .wav of yours, with a button to choose it and one to hear it
                from PyQt6.QtWidgets import QFileDialog, QStyle
                act = w.addAction(w.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon),
                                  QLineEdit.ActionPosition.TrailingPosition)
                act.triggered.connect(lambda _c=False, box=w: box.setText(
                    QFileDialog.getOpenFileName(box, t("set.sound_file"), box.text(), "WAV (*.wav)")[0] or box.text()))
                test = w.addAction(w.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay),
                                   QLineEdit.ActionPosition.TrailingPosition)

                def hear(_c=False, box=w):
                    from app.core import sound
                    from app.core.config import CFG as C
                    old = (C.get("sound_file"), C.get("sound_vendor"))
                    C["sound_file"], C["sound_vendor"] = box.text().strip(), True
                    sound._last.pop("vendor", None)
                    sound.play("vendor")
                    C["sound_file"], C["sound_vendor"] = old
                test.triggered.connect(hear)
                w.setMaximumWidth(320)
            if opt == "eelog":                         # the game's log: empty = where the game keeps it
                from PyQt6.QtWidgets import QFileDialog, QStyle
                w.setPlaceholderText(t("set.ee_log_path.auto"))
                act = w.addAction(w.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon),
                                  QLineEdit.ActionPosition.TrailingPosition)
                act.triggered.connect(lambda _c=False, box=w: box.setText(
                    QFileDialog.getOpenFileName(box, t("set.ee_log_path"), box.text(), "EE.log (*.log)")[0] or box.text()))
                w.setMaximumWidth(420)
                w.setMinimumWidth(300)
            if opt == "picture":                       # a file of yours: a button in the box opens the file chooser
                from PyQt6.QtWidgets import QFileDialog, QStyle
                act = w.addAction(w.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon),
                                  QLineEdit.ActionPosition.TrailingPosition)

                def pick(_c=False, box=w):
                    path, _ = QFileDialog.getOpenFileName(box, t("set.backdrop_image"), box.text(),
                                                          "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
                    if path:
                        box.setText(path)
                act.triggered.connect(pick)
                # a wallpaper from the Warframe wiki: chosen in a gallery, set at once
                wall = w.addAction(w.style().standardIcon(QStyle.StandardPixmap.SP_DesktopIcon),
                                   QLineEdit.ActionPosition.TrailingPosition)
                wall.setToolTip(t("wall.button"))

                def wiki(_c=False, box=w):
                    from app.ui import wallpapers
                    path = wallpapers.choose(self)
                    if path:
                        box.setText(path)
                        style = self.widgets.get("backdrop_style")
                        if style is not None and hasattr(style[0], "findData"):
                            style[0].setCurrentIndex(max(0, style[0].findData("image")))
                        on = self.widgets.get("backdrop")
                        if on is not None and hasattr(on[0], "setChecked"):
                            on[0].setChecked(True)
                wall.triggered.connect(wiki)
                w.setMaximumWidth(360)
            return w
        w.setMaximumWidth(140)
        return w

    @staticmethod
    def _paint_color(b, value):
        b.value = str(value or "#ffffff")
        b.setText(b.value)
        b.setStyleSheet(f"QPushButton {{ background: {b.value}; color: {'#000' if _light(b.value) else '#fff'}; }}")

    # ---------- values <-> widgets ----------
    def _set(self, key, value):
        w, kind, _ = self.widgets[key]
        if kind == "color":
            self._paint_color(w, value)
            return
        if kind == "wallet":
            on = set(value) if isinstance(value, list) else set(w.boxes)
            for k, cb in w.boxes.items():
                cb.setChecked(k in on)
            return
        if kind == "activities":
            w.value = list(value or [])
            w.setText(t("set.goals_untracked.button") + (f" ({len(w.value)} ✘)" if w.value else ""))
            return
        if kind == "bool":
            w.setChecked(bool(value))
        elif kind in ("int", "float"):
            w.setValue(value)
        elif kind == "choice":
            w.setCurrentIndex(max(0, w.findData(value)))
        elif kind == "font":
            w.setCurrentFont(QFont(str(value) or "Segoe UI"))
        else:
            w.setText(str(value))

    @staticmethod
    def _edit_activities(button):
        """Which activities the Activities overlay shows, syndicate by syndicate (unticked = left out)."""
        from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QTreeWidget, QTreeWidgetItem
        from app.game import goals as G
        from app.game.standing import syndicate_name
        dlg = QDialog(button.window())
        dlg.setWindowTitle(t("set.goals_untracked"))
        dlg.resize(520, 520)
        tree = QTreeWidget()
        tree.setHeaderHidden(True)
        off = set(button.value or [])
        lang = "it" if str(CFG.get("language", "en")).startswith("it") else "en"
        tags = list(G.RELAY) + [k for k in G.ACTIVITIES[lang] if not k.startswith("_")]
        for tag in tags:
            name = syndicate_name(tag)
            top = QTreeWidgetItem([name])
            top.setFlags(top.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsAutoTristate)
            for n, a in enumerate(G.activities(tag, name)):
                ch = QTreeWidgetItem([a])
                ch.setFlags(ch.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                ch.setData(0, Qt.ItemDataRole.UserRole, f"{tag}|{n}")
                ch.setCheckState(0, Qt.CheckState.Unchecked if (f"{tag}|{n}" in off or f"{tag}|*" in off)
                                 else Qt.CheckState.Checked)
                top.addChild(ch)
            tree.addTopLevelItem(top)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        hint = QLabel(t("set.goals_untracked.tip"))
        hint.setWordWrap(True)
        lay = QVBoxLayout(dlg)
        lay.addWidget(hint)
        lay.addWidget(tree, 1)
        lay.addWidget(bb)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            out = []
            for i in range(tree.topLevelItemCount()):
                top = tree.topLevelItem(i)
                for j in range(top.childCount()):
                    ch = top.child(j)
                    if ch.checkState(0) != Qt.CheckState.Checked:
                        out.append(ch.data(0, Qt.ItemDataRole.UserRole))
            button.value = out
            button.setText(t("set.goals_untracked.button") + (f" ({len(out)} ✘)" if out else ""))

    def _get(self, key):
        w, kind, _ = self.widgets[key]
        if kind == "activities":
            return list(w.value or [])
        if kind == "wallet":
            return [k for k, cb in w.boxes.items() if cb.isChecked()]
        if kind == "color":
            return w.value
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
        from app.core import theme
        theme.apply(None, self._get("theme"), self._get("ui_font"), self._get("ui_font_size"))

    def hideEvent(self, e):
        super().hideEvent(e)
        if self.overlay:
            self._prev_timer.stop()
        if "theme" in self.widgets:
            from app.core import theme
            theme.apply()

    def showEvent(self, e):
        super().showEvent(e)
        self.load()                          # picks up values changed elsewhere (e.g. the Recommendations tab)
        if self.overlay:
            self._prev_timer.start()

    def values(self) -> dict:
        """What the page shows now (saved or not): the overlay previews draw these."""
        return {k: self._get(k) for k in self.widgets}

    def restore_defaults(self):
        self.load(DEFAULTS)
        self.msg.setText(t("settings.defaults_loaded"))

    def save(self, restart: bool):
        new = {k: self._get(k) for k in self.widgets}
        keys = tuple(k for k in HOTKEYS if k in new)
        for k in keys:
            new[k] = new[k].lower()
        for k in keys:
            if not _valid_hotkey(new[k]):
                self.msg.setText(t("settings.bad_key", key=new[k] or "∅"))
                return
        sets = {k: set(new[k].split("+")) for k in keys}
        for a in keys:                       # pynput fires a hotkey whose keys are all held, extra keys or not
            for b in keys:
                if a != b and sets[b] <= sets[a]:
                    self.msg.setText(t("settings.key_overlap", a=new[a], b=new[b]))
                    return
        if "volume_high" in new and new["volume_high"] <= new["volume_low"]:
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
        if "theme" in self.widgets:
            from app.core import theme
            theme.apply()
        if restart:
            self.restart_requested.emit()


def _light(hexcolor: str) -> bool:
    try:
        h = hexcolor.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return r * 0.3 + g * 0.59 + b * 0.11 > 150
    except (ValueError, IndexError):
        return True


def _config_path():
    from app.core.config import CONFIG_FILE
    return CONFIG_FILE


def overlay_colors(values=None) -> dict:
    """The price labels' look on the vendor screen: {"price", "star", "bg"} from the overlay theme (ov_theme): the
    program's theme, one of the themes, or your own colours (ov_price_color / ov_star_color)."""
    v = values or CFG
    which = str(v.get("ov_theme") or "custom")
    if which == "custom":
        return {"price": v.get("ov_price_color") or "#78c8ff", "star": v.get("ov_star_color") or "#ffd228",
                "bg": "#141414"}
    from app.core import theme
    p = theme.palette(str(CFG.get("theme") or "classic") if which == "program" else which)
    return {"price": p["accent"], "star": p["accent2"], "bg": p["bg"]}


class OverlayPreview(QWidget):
    """How the prices will look over a vendor's screen with the values on the page (saved or not)."""

    def __init__(self, page):
        super().__init__()
        self.page = page
        self.setMinimumHeight(96)

    def paintEvent(self, _e):
        from PyQt6.QtGui import QColor, QFont, QPainter
        v = dict(CFG)
        try:
            v.update(self.page.values())
        except Exception:
            pass
        c = overlay_colors(v)
        g = QPainter(self)
        g.setRenderHint(QPainter.RenderHint.Antialiasing)
        g.fillRect(self.rect(), QColor("#2a2f38"))
        g.setPen(QColor("#9aa4b2"))
        g.drawText(12, 22, t("ovprev.title"))
        x = 14
        for name, price, vol, star in (("Primed Continuity", 48, 63, True), ("Arcane Energize", 31, 9, False),
                                      ("Vitality", 2, 140, False)):
            g.setPen(QColor("#dfe6ee"))
            g.setFont(QFont(self.font().family(), 10))
            g.drawText(x, 48, name)
            bg = QColor(c["bg"])
            bg.setAlpha(int(255 * int(v.get("ov_bg_opacity", 88)) / 100))
            f = QFont(self.font().family(), int(v.get("ov_price_font", 11)))
            f.setBold(True)
            g.setFont(f)
            txt = ("★ " if star and v.get("rec_overlay", True) else "") + f"{price}p"
            w = g.fontMetrics().horizontalAdvance(txt) + 10
            g.fillRect(x, 54, w, g.fontMetrics().height() + 2, bg)
            g.setPen(QColor(c["star"] if star else c["price"]))
            g.drawText(x + 5, 54 + g.fontMetrics().ascent() + 1, txt)
            if v.get("show_volume", True):
                g.setFont(QFont(self.font().family(), int(v.get("ov_vol_font", 9))))
                lo, hi = int(v.get("volume_low", 10)), int(v.get("volume_high", 50))
                g.setPen(QColor("#e05a4f" if vol <= lo else "#4fbf6a" if vol >= hi else "#e0b83a"))
                g.drawText(x + 5, 54 + 22 + int(v.get("volume_offset_y", 2)) + g.fontMetrics().ascent(), f"{vol}/24h")
            x += 190
        g.end()


class GoalsPreview(QWidget):
    """A few lines of the Activities overlay with the look on the page (theme, colours, font, opacity)."""

    def __init__(self, page):
        super().__init__()
        self.page = page
        self.setMinimumHeight(150)

    def paintEvent(self, _e):
        from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter
        from app.ui.goals_overlay import goals_colors
        v = dict(CFG)
        try:
            v.update(self.page.values())
        except Exception:
            pass
        c = goals_colors(v)
        g = QPainter(self)
        g.setRenderHint(QPainter.RenderHint.Antialiasing)
        g.fillRect(self.rect(), QColor("#39404b"))
        alpha = int(255 * max(0, min(100, int(v.get("goals_opacity", 45)))) / 100)
        band = QLinearGradient(0, 0, 340, 0)
        bc = QColor(c["band"])
        for pos, k in ((0.0, 1.0), (0.75, 0.7), (1.0, 0.15)):
            q = QColor(bc)
            q.setAlpha(int(alpha * k))
            band.setColorAt(pos, q)
        g.setBrush(band)
        g.setPen(QColor(0, 0, 0, 0))
        g.drawRoundedRect(8, 8, 340, self.height() - 16, 6, 6)
        fs = int(v.get("goals_font", 12))
        fam = v.get("goals_font_family") or self.font().family()
        y = 8 + fs + 8
        for text, key, bold in ((t("goals.title").upper(), "title", True), ("Cephalon Suda · 8,250 / 22,000", "title", True),
                                ("Vaykor Marelok — 25,000", "text", False), ("✔ Rakta Cernos — " + t("ovprev.ready"), "ready", False),
                                (t("ovprev.hint"), "hint", False), (t("ovprev.soon"), "soon", False)):
            f = QFont(fam)
            f.setPixelSize(fs + (1 if bold else 0))
            f.setBold(bold)
            g.setFont(f)
            g.setPen(QColor(0, 0, 0))
            g.drawText(19, y + 1, text)
            g.setPen(QColor(c[key]))
            g.drawText(18, y, text)
            y += fs + 9
        g.end()
