"""
settings_ui.py — PyQt6 settings window for Voxel voice dictation app.
No CustomTkinter dependency; pure PyQt6 + pynput for hotkey capture.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
from typing import Callable

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject, QSize
from PyQt6.QtGui import QFont, QIcon, QFontDatabase, QPainter, QPen, QColor, QPainterPath
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QCheckBox,
    QFrame,
    QSizePolicy,
    QApplication,
)
from pynput import keyboard as pynput_keyboard

# One source for colour and chrome. settings_ui used to carry its own copy of
# the palette, the stylesheet and these widgets; two copies is what let the
# scrollbars and dropdowns drift apart.
from src.ui_pyqt6.theme import ArrowComboBox, IOSSwitch, current_palette
from src.ui_pyqt6.flags import flag_icon

logger = logging.getLogger(__name__)


# Dictation Mode subtitle, and what it says when Offline mode makes it inert.
_MODE_SUBTITLE = "How your speech is cleaned up"
_MODE_SUBTITLE_OFFLINE = "Not used in Offline mode — transcription only"


def _is_modifier_only_hotkey(hotkey: str) -> bool:
    """True when the combo is modifiers alone, with no ordinary trigger key."""
    from src.hotkey_listener import HotkeyListener
    try:
        return HotkeyListener(
            hotkey_str=hotkey, on_press=lambda: None, on_release=lambda: None
        ).is_modifier_only
    except Exception:
        return False



# ---------------------------------------------------------------------------
# Background worker for API key validation
# ---------------------------------------------------------------------------
class _ValidateWorker(QObject):
    """Runs the API key validation callback in a thread and emits a result signal."""

    result = pyqtSignal(bool, str)  # (success, message)

    def __init__(self, callback: Callable, key: str) -> None:
        super().__init__()
        self._callback = callback
        self._key = key

    def run(self) -> None:
        try:
            ok = self._callback(self._key)
            if ok:
                self.result.emit(True, "Valid API key")
            else:
                self.result.emit(False, "Invalid API key")
        except Exception as exc:  # noqa: BLE001
            self.result.emit(False, str(exc))


# ---------------------------------------------------------------------------
# Main settings window
# ---------------------------------------------------------------------------
class SettingsWindow(QWidget):
    """PyQt6 settings window for Voxel."""

    # Signal used to marshal hotkey capture results back to the GUI thread.
    _hotkey_captured = pyqtSignal(str)
    # Signal to update status label from worker thread.
    _validate_result = pyqtSignal(bool, str)

    def __init__(
        self,
        config,
        on_save: Callable,
        on_validate_key: Callable | None = None,
        on_quit: Callable | None = None,
        on_history: Callable | None = None,
        on_stats: Callable | None = None,
    ) -> None:
        super().__init__()

        self._config = config
        self._on_save = on_save
        self._on_validate_key = on_validate_key
        self._on_quit = on_quit
        self._on_history = on_history
        self._on_stats = on_stats

        # Hotkey capture state
        self._capturing = False
        self._captured_keys: set[str] = set()
        self._capture_listener: pynput_keyboard.Listener | None = None

        # Worker thread references (kept alive)
        self._validate_thread: QThread | None = None
        self._validate_worker: _ValidateWorker | None = None

        self._build_ui()

        # Connect internal signals
        self._hotkey_captured.connect(self._finish_capture)
        self._validate_result.connect(self._on_validate_result)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show(self, _root=None) -> None:  # noqa: ANN001
        """Show (or raise) the settings window. _root is accepted for API compat but ignored."""
        # The window is built once and reused, so the device list would otherwise
        # be frozen at startup and a newly plugged-in mic could never be chosen.
        try:
            self._populate_mics()
        except Exception as e:
            logger.warning("Could not refresh microphone list: %s", e)

        if self.isMinimized():
            self.showNormal()
            self.raise_()
            self.activateWindow()
            return
        if self.isVisible():
            self.raise_()
            self.activateWindow()
            return
        # Centre on screen
        screen = QApplication.primaryScreen()
        if screen is not None:
            geom = screen.availableGeometry()
            self.move(
                geom.center().x() - self.width() // 2,
                geom.center().y() - self.height() // 2,
            )
        super().show()
        self.raise_()
        self.activateWindow()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.setWindowTitle("Voxel")
        self.setFixedSize(540, 820)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowMinimizeButtonHint
        )

        # Window icon
        icon_path = self._resolve_asset("icon.ico")
        if icon_path and os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(28, 28, 28, 24)
        root_layout.setSpacing(0)

        # ── Header ──────────────────────────────────────────────────────
        header_row = QHBoxLayout()

        header_text = QVBoxLayout()
        title_lbl = QLabel("Voxel")
        title_lbl.setObjectName("app_title")
        header_text.addWidget(title_lbl)

        sub_lbl = QLabel("Voice dictation settings")
        sub_lbl.setObjectName("subtitle")
        header_text.addWidget(sub_lbl)
        header_row.addLayout(header_text, stretch=1)

        # Header buttons
        _small_btn = (
            f"background-color: {current_palette()['separator']}; color: {current_palette()['secondary']}; "
            f"border-radius: 4px; font-size: 11px; "
            f"padding: 3px 10px; min-height: 0; min-width: 0;"
        )
        _small_btn_hover = f"background-color: #333; color: {current_palette()['text']};"

        history_btn = QPushButton("History")
        history_btn.setStyleSheet(f"QPushButton {{ {_small_btn} }} QPushButton:hover {{ {_small_btn_hover} }}")
        history_btn.clicked.connect(self._open_history)
        header_row.addWidget(history_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        header_row.addSpacing(4)

        stats_btn = QPushButton("Stats")
        stats_btn.setStyleSheet(f"QPushButton {{ {_small_btn} }} QPushButton:hover {{ {_small_btn_hover} }}")
        stats_btn.clicked.connect(self._open_stats)
        header_row.addWidget(stats_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        header_row.addSpacing(4)

        help_btn = QLabel("?")
        help_btn.setFixedSize(24, 24)
        help_btn.setAlignment(Qt.AlignmentFlag.AlignCenter)
        help_btn.setToolTip("Help & FAQ")
        help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        help_btn.setStyleSheet(
            f"QLabel {{ background-color: transparent; color: {current_palette()['accent']}; "
            f"border: 1.5px solid {current_palette()['accent']}; border-radius: 12px; "
            f"font-size: 13px; font-weight: bold; }}"
            f"QLabel:hover {{ background-color: #1e1e3e; }}"
        )
        help_btn.mousePressEvent = lambda e: self._show_help()
        header_row.addWidget(help_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        root_layout.addLayout(header_row)

        root_layout.addSpacing(16)

        # Divider
        divider = QFrame()
        divider.setObjectName("divider")
        divider.setFrameShape(QFrame.Shape.HLine)
        root_layout.addWidget(divider)

        root_layout.addSpacing(8)

        # ── API Key ──────────────────────────────────────────────────────
        self._add_section(root_layout, "API Key", "Your Groq API key for transcription")

        key_row = QHBoxLayout()
        key_row.setSpacing(8)

        self._api_key_edit = QLineEdit()
        self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_edit.setText(self._config.get("api_key", ""))
        self._api_key_edit.setPlaceholderText("gsk_…")
        self._api_key_edit.setFixedHeight(36)
        key_row.addWidget(self._api_key_edit, stretch=1)

        if self._on_validate_key:
            verify_btn = QPushButton("Verify")
            verify_btn.setFixedSize(72, 36)
            verify_btn.clicked.connect(self._validate_key)
            key_row.addWidget(verify_btn)

        root_layout.addLayout(key_row)

        self._status_label = QLabel("")
        self._status_label.setObjectName("status_label")
        root_layout.addWidget(self._status_label)

        root_layout.addSpacing(4)

        # ── Hotkey ───────────────────────────────────────────────────────
        self._add_section(root_layout, "Hotkey", "Click Record, then press your desired combo")

        hotkey_row = QHBoxLayout()
        hotkey_row.setSpacing(8)

        self._hotkey_edit = QLineEdit()
        self._hotkey_edit.setReadOnly(True)
        self._hotkey_edit.setText(self._config.get("hotkey", "<ctrl>+<shift>+space"))
        self._hotkey_edit.setFixedHeight(36)
        hotkey_row.addWidget(self._hotkey_edit, stretch=1)

        self._capture_btn = QPushButton("Record")
        self._capture_btn.setFixedSize(80, 36)
        self._capture_btn.clicked.connect(self._toggle_hotkey_capture)
        hotkey_row.addWidget(self._capture_btn)

        root_layout.addLayout(hotkey_row)

        root_layout.addSpacing(4)

        # ── Activation mode ──────────────────────────────────────────────
        activation_sub = QLabel("Activation")
        activation_sub.setObjectName("section_sub")
        root_layout.addWidget(activation_sub)
        root_layout.addSpacing(2)

        self._activation_combo = ArrowComboBox()
        self._activation_combo.setFixedHeight(36)
        for label, value in (
            ("Hold to talk", "hold"),
            ("Press to start, press to stop", "toggle"),
        ):
            self._activation_combo.addItem(label, userData=value)
        current_activation = self._config.get("activation_mode", "hold")
        for i in range(self._activation_combo.count()):
            if self._activation_combo.itemData(i) == current_activation:
                self._activation_combo.setCurrentIndex(i)
                break
        self._activation_combo.setToolTip(
            "Hold to talk: record while the hotkey is held.\n"
            "Press to start, press to stop: tap once to begin, tap again to finish."
        )
        root_layout.addWidget(self._activation_combo)

        root_layout.addSpacing(8)

        # ── Dictation Mode ───────────────────────────────────────────────
        self._profile_sub = self._add_section(
            root_layout, "Dictation Mode", _MODE_SUBTITLE
        )

        profile_row = QHBoxLayout()
        profile_row.setSpacing(8)

        self._profile_combo = ArrowComboBox()
        self._profile_combo.setFixedHeight(36)
        self._populate_profiles()
        profile_row.addWidget(self._profile_combo, stretch=1)

        voice_cmd_btn = QPushButton("Voice Commands")
        voice_cmd_btn.setFixedSize(130, 36)
        voice_cmd_btn.clicked.connect(self._show_voice_commands)
        profile_row.addWidget(voice_cmd_btn)

        root_layout.addLayout(profile_row)

        root_layout.addSpacing(8)

        # ── Microphone ────────────────────────────────────────────────────
        self._add_section(root_layout, "Microphone", "Select your recording device")

        self._mic_combo = ArrowComboBox()
        self._mic_combo.setFixedHeight(36)
        self._populate_mics()
        root_layout.addWidget(self._mic_combo)

        root_layout.addSpacing(8)

        # ── Language + checkboxes row ────────────────────────────────────
        options_row = QHBoxLayout()
        options_row.setSpacing(16)

        # Language column
        lang_col = QVBoxLayout()
        lang_col.setSpacing(4)
        lang_title = QLabel("Language")
        lang_title.setObjectName("section_title")
        lang_col.addWidget(lang_title)

        self._lang_combo = ArrowComboBox()
        _LANGUAGES = [
            ("auto", "Auto-detect"),
            ("en", "English"),
            ("es", "Spanish"),
            ("fr", "French"),
            ("de", "German"),
            ("it", "Italian"),
            ("pt", "Portuguese"),
            ("ja", "Japanese"),
            ("ko", "Korean"),
            ("zh", "Chinese"),
        ]
        # Flags are images: Windows renders flag emoji as letter pairs. A
        # language with no flag (Auto-detect) or a missing asset still gets its
        # row, just without a picture.
        flag_assets = self._resolve_assets_root()
        self._lang_combo.setIconSize(QSize(20, 15))
        for code, label in _LANGUAGES:
            icon = flag_icon(code, flag_assets) if flag_assets else None
            if icon is not None:
                self._lang_combo.addItem(icon, label, userData=code)
            else:
                self._lang_combo.addItem(label, userData=code)
        # Select current language
        current_lang = self._config.get("language", "en")
        for i in range(self._lang_combo.count()):
            if self._lang_combo.itemData(i) == current_lang:
                self._lang_combo.setCurrentIndex(i)
                break
        self._lang_combo.setFixedHeight(36)
        lang_col.addWidget(self._lang_combo)

        options_row.addLayout(lang_col, stretch=1)

        # Checkboxes column
        check_col = QVBoxLayout()
        check_col.setSpacing(10)
        check_col.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._mute_check = IOSSwitch("Mute sounds")
        self._mute_check.setChecked(self._config.get("mute_sound", False))
        self._mute_check.setToolTip("Disable the chime sound that plays after you stop recording")
        check_col.addWidget(self._mute_check)

        self._autostart_check = IOSSwitch("Run at login")
        self._autostart_check.setChecked(self._config.get("auto_start", False))
        self._autostart_check.setToolTip("Automatically launch Voxel when Windows starts")
        check_col.addWidget(self._autostart_check)

        self._always_copy_check = IOSSwitch("Always copy to clipboard")
        self._always_copy_check.setChecked(self._config.get("always_copy", False))
        self._always_copy_check.setToolTip("Keep transcribed text on your clipboard after pasting\n(instead of restoring your previous clipboard)")
        check_col.addWidget(self._always_copy_check)

        self._clipboard_notice_check = IOSSwitch("Show clipboard notice")
        self._clipboard_notice_check.setChecked(self._config.get("clipboard_notice", True))
        self._clipboard_notice_check.setToolTip("Show a notification when text is copied to clipboard\ninstead of pasted (e.g. when desktop is focused)")
        check_col.addWidget(self._clipboard_notice_check)

        self._auto_profile_check = IOSSwitch("Auto-switch profile per app")
        self._auto_profile_check.setChecked(self._config.get("auto_profile", False))
        self._auto_profile_check.setToolTip("Automatically switch dictation mode based on the focused app.\nConfigure app mappings in the config file.")
        check_col.addWidget(self._auto_profile_check)

        self._offline_check = IOSSwitch("Offline mode")
        self._offline_check.setChecked(self._config.get("offline_mode", False))
        self._offline_check.setToolTip("Use local Whisper model instead of Groq API.\nNo internet needed, but slower and no AI text cleanup.\nModel downloads on first use (~145MB for base).")
        # Offline transcription skips LLM cleanup entirely, so Dictation Mode has
        # no effect. Say so instead of leaving a control that quietly does nothing.
        self._offline_check.stateChanged.connect(self._sync_offline_state)
        check_col.addWidget(self._offline_check)
        self._sync_offline_state()


        options_row.addLayout(check_col, stretch=1)

        root_layout.addLayout(options_row)

        # ── Spacer ───────────────────────────────────────────────────────
        root_layout.addStretch(1)

        # ── Save button ──────────────────────────────────────────────────
        self._save_btn = QPushButton("Save Settings")
        self._save_btn.setObjectName("save_btn")
        self._save_btn.clicked.connect(self._save)
        root_layout.addWidget(self._save_btn)

        # ── Footer: support link + version ───────────────────────────────
        root_layout.addSpacing(8)
        footer_row = QHBoxLayout()

        coffee_label = QLabel('<a href="https://paypal.me/draxctrl" style="color: #777777; font-size: 11px; text-decoration: none;">Support this project ☕</a>')
        coffee_label.setOpenExternalLinks(True)
        footer_row.addWidget(coffee_label, 0, Qt.AlignmentFlag.AlignLeft)

        footer_row.addStretch(1)

        version_label = QLabel("v2.0")
        version_label.setStyleSheet(f"color: {current_palette()['secondary']}; font-size: 11px;")
        footer_row.addWidget(version_label, 0, Qt.AlignmentFlag.AlignRight)

        root_layout.addLayout(footer_row)


    # ------------------------------------------------------------------
    # Helper: section header
    # ------------------------------------------------------------------

    def _add_section(self, layout: QVBoxLayout, title: str, subtitle: str) -> QLabel:
        """Add a section header. Returns the subtitle label so callers can update it."""
        t = QLabel(title)
        t.setObjectName("section_title")
        layout.addWidget(t)

        s = QLabel(subtitle)
        s.setObjectName("section_sub")
        layout.addWidget(s)

        layout.addSpacing(4)
        return s

    # ------------------------------------------------------------------
    # Microphone enumeration
    # ------------------------------------------------------------------

    def _populate_mics(self) -> None:
        """List available input devices using PyAudio. Prefer WASAPI for full names.

        Safe to call repeatedly — the list is rebuilt, so newly plugged-in mics
        appear when Settings is reopened.

        ``_mic_names`` maps each combo row to the *real* device name, kept apart
        from the display text so a disconnected device can be shown as
        "X (not connected)" while still saving as "X", and so the error
        placeholder never gets written to the config as if it were a device.
        """
        self._mic_combo.clear()
        self._mic_names: dict[int, str] = {}
        try:
            import pyaudio
            pa = pyaudio.PyAudio()
            saved_device = self._config.get("mic_device", None)
            saved_name = self._config.get("mic_device_name", None)
            default_idx = pa.get_default_input_device_info().get("index", 0)
            selected = 0
            matched_by_name = False
            seen_names: set[str] = set()

            # Same helper the recorder resolves names with, so the list the user
            # picks from and the device actually opened cannot disagree.
            from src.mic_recorder import find_preferred_host_api
            wasapi_idx = find_preferred_host_api(pa)
            target_host = wasapi_idx if wasapi_idx is not None else pa.get_default_host_api_info().get("index", 0)

            for i in range(pa.get_device_count()):
                info = pa.get_device_info_by_index(i)
                if info.get("maxInputChannels", 0) <= 0:
                    continue
                if info.get("hostApi", -1) != target_host:
                    continue
                name = info.get("name", f"Device {i}")
                if name in seen_names:
                    continue
                seen_names.add(name)
                idx = info.get("index", i)
                self._mic_combo.addItem(name, userData=idx)
                self._mic_names[self._mic_combo.count() - 1] = name
                # Name wins over the index, which may now point elsewhere.
                if saved_name and name == saved_name:
                    selected = self._mic_combo.count() - 1
                    matched_by_name = True
                elif not matched_by_name and not saved_name and saved_device is not None \
                        and idx == saved_device:
                    selected = self._mic_combo.count() - 1
                elif not matched_by_name and saved_name is None and saved_device is None \
                        and idx == default_idx:
                    selected = self._mic_combo.count() - 1

            # A saved device that isn't currently present stays in the list and
            # stays selected. Otherwise opening Settings and pressing Save for an
            # unrelated reason would silently rewrite the user's choice to
            # whatever happened to be listed first.
            if saved_name and not matched_by_name:
                self._mic_combo.addItem(f"{saved_name} (not connected)", userData=None)
                row = self._mic_combo.count() - 1
                self._mic_names[row] = saved_name
                selected = row

            if self._mic_combo.count() > 0:
                self._mic_combo.setCurrentIndex(selected)
            pa.terminate()
        except Exception as e:
            # Enumeration failed. Show a placeholder, but record no name for it
            # so saving can't persist "Default Microphone" as a device name that
            # will never resolve again.
            logger.warning("Could not list input devices: %s", e)
            self._mic_combo.addItem("Default Microphone", userData=None)

    # ------------------------------------------------------------------
    # Profile enumeration
    # ------------------------------------------------------------------

    def _populate_profiles(self) -> None:
        from src.profiles import ProfileManager
        pm = ProfileManager(self._config)
        active = self._config.get("active_profile", "default")
        selected = 0
        for i, (pid, prof) in enumerate(pm.list_profiles().items()):
            self._profile_combo.addItem(prof["name"], userData=pid)
            if pid == active:
                selected = i
        self._profile_combo.setCurrentIndex(selected)

    # ------------------------------------------------------------------
    # Voice Commands dialog
    # ------------------------------------------------------------------

    def _show_voice_commands(self) -> None:
        from PyQt6.QtWidgets import QDialog, QScrollArea, QTextEdit

        commands = dict(self._config.get("voice_commands", {}))

        dlg = QDialog(self)
        dlg.setWindowTitle("Voice Commands")
        dlg.setFixedSize(500, 450)

        icon_path = self._resolve_asset("icon.ico")
        if icon_path and os.path.exists(icon_path):
            dlg.setWindowIcon(QIcon(icon_path))

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        info = QLabel("Say a trigger phrase and Voxel will insert the template instead of cleaning up your speech.")
        info.setObjectName("section_sub")
        info.setWordWrap(True)
        layout.addWidget(info)

        # Scrollable list of commands
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        layout.addWidget(scroll, stretch=1)

        scroll_content = QWidget()
        scroll.setWidget(scroll_content)
        self._cmd_layout = QVBoxLayout(scroll_content)
        self._cmd_layout.setContentsMargins(0, 0, 0, 0)
        self._cmd_layout.setSpacing(8)

        self._cmd_entries: list[tuple[QLineEdit, QLineEdit]] = []

        def add_cmd_row(trigger: str = "", expansion: str = ""):
            row = QHBoxLayout()
            row.setSpacing(8)
            t = QLineEdit(trigger)
            t.setPlaceholderText("Trigger phrase")
            t.setFixedHeight(32)
            row.addWidget(t, stretch=1)

            arrow = QLabel("->")
            arrow.setStyleSheet(f"color: {current_palette()['secondary']}; font-size: 14px;")
            arrow.setFixedWidth(24)
            arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
            row.addWidget(arrow)

            e = QLineEdit(expansion)
            e.setPlaceholderText("Expands to...")
            e.setFixedHeight(32)
            row.addWidget(e, stretch=2)

            del_btn = QPushButton("X")
            del_btn.setFixedSize(32, 32)
            del_btn.setStyleSheet(f"background-color: {current_palette()['separator']}; font-size: 12px; min-height: 0;")
            entry_pair = (t, e)
            self._cmd_entries.append(entry_pair)
            del_btn.clicked.connect(lambda: self._remove_cmd_row(entry_pair, row_widget))
            row.addWidget(del_btn)

            row_widget = QWidget()
            row_widget.setLayout(row)
            self._cmd_layout.addWidget(row_widget)

        for trigger, expansion in commands.items():
            add_cmd_row(trigger, expansion)

        # Add + Save buttons
        btn_row = QHBoxLayout()
        add_btn = QPushButton("+ Add Command")
        add_btn.setFixedHeight(36)
        add_btn.setStyleSheet(f"background-color: {current_palette()['separator']}; font-size: 12px;")
        add_btn.clicked.connect(lambda: add_cmd_row())
        btn_row.addWidget(add_btn)

        save_btn = QPushButton("Save Commands")
        save_btn.setFixedHeight(36)
        save_btn.clicked.connect(lambda: self._save_voice_commands(dlg))
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

        # Placeholder hint
        hint = QLabel("Placeholders: {{date}}, {{time}}, {{datetime}}, {{clipboard}}")
        hint.setObjectName("section_sub")
        layout.addWidget(hint)

        dlg.exec()

    def _remove_cmd_row(self, entry_pair, row_widget):
        if entry_pair in self._cmd_entries:
            self._cmd_entries.remove(entry_pair)
        row_widget.setParent(None)
        row_widget.deleteLater()

    def _save_voice_commands(self, dlg):
        commands = {}
        for trigger_edit, expansion_edit in self._cmd_entries:
            trigger = trigger_edit.text().strip()
            expansion = expansion_edit.text().strip()
            if trigger and expansion:
                commands[trigger] = expansion
        self._config.set("voice_commands", commands)
        self._config.save()
        dlg.close()

    # ------------------------------------------------------------------
    # Asset resolution (frozen + dev paths)
    # ------------------------------------------------------------------

    def _resolve_assets_root(self) -> str | None:
        """Directory holding the bundled assets, or None if it can't be found."""
        if hasattr(sys, "_MEIPASS"):
            candidate = os.path.join(sys._MEIPASS, "src", "assets")  # type: ignore[attr-defined]
            if os.path.isdir(candidate):
                return candidate
            candidate = os.path.join(sys._MEIPASS, "assets")  # type: ignore[attr-defined]
            if os.path.isdir(candidate):
                return candidate

        here = os.path.dirname(os.path.abspath(__file__))
        candidate = os.path.normpath(os.path.join(here, "..", "assets"))
        return candidate if os.path.isdir(candidate) else None

    @staticmethod
    def _resolve_asset(filename: str) -> str | None:
        # PyInstaller frozen path
        if hasattr(sys, "_MEIPASS"):
            candidate = os.path.join(sys._MEIPASS, "assets", filename)  # type: ignore[attr-defined]
            if os.path.exists(candidate):
                return candidate

        # Dev path: this file lives at src/ui_pyqt6/settings_ui.py
        # assets are at src/assets/
        here = os.path.dirname(os.path.abspath(__file__))
        for rel in (
            os.path.join(here, "..", "assets", filename),
            os.path.join(here, "assets", filename),
            os.path.join(here, "..", "..", "assets", filename),
        ):
            resolved = os.path.normpath(rel)
            if os.path.exists(resolved):
                return resolved

        return None

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _save(self) -> None:
        self._stop_hotkey_capture()

        self._config.set("api_key", self._api_key_edit.text().strip())
        self._config.set("language", self._lang_combo.currentData())
        hotkey = self._hotkey_edit.text().strip()
        self._config.set("hotkey", hotkey)

        # A modifier-only hotkey can't toggle: every Ctrl+Shift press would flip
        # recording on or off. Refuse the combination rather than ship the trap.
        activation = self._activation_combo.currentData() or "hold"
        if activation == "toggle" and _is_modifier_only_hotkey(hotkey):
            activation = "hold"
            self._activation_combo.setCurrentIndex(0)
            self._set_status(
                "⚠ A modifier-only hotkey can't toggle — kept Hold to talk. "
                "Add a normal key (e.g. Ctrl+Shift+Space) to use toggle.",
                current_palette()["warning"],
            )
        self._config.set("activation_mode", activation)
        # Name is authoritative; the index is only a hint, since PyAudio
        # renumbers devices whenever audio hardware changes. The name comes from
        # _mic_names, not the display text, so "(not connected)" suffixes and
        # the error placeholder are never written as device names.
        self._config.set(
            "mic_device_name", self._mic_names.get(self._mic_combo.currentIndex())
        )
        self._config.set("mic_device", self._mic_combo.currentData())
        self._config.set("active_profile", self._profile_combo.currentData() or "default")
        self._config.set("auto_start", self._autostart_check.isChecked())
        self._config.set("mute_sound", self._mute_check.isChecked())
        self._config.set("always_copy", self._always_copy_check.isChecked())
        self._config.set("clipboard_notice", self._clipboard_notice_check.isChecked())
        self._config.set("auto_profile", self._auto_profile_check.isChecked())
        self._config.set("offline_mode", self._offline_check.isChecked())
        self._config.save()
        self._on_save()

        # Show "Saved!" confirmation on the button, then reset
        self._save_btn.setText("Saved!")
        self._save_btn.setStyleSheet("QPushButton#save_btn { background-color: #22c55e; }")
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1500, lambda: (
            self._save_btn.setText("Save Settings"),
            self._save_btn.setStyleSheet(""),
        ))

    # ------------------------------------------------------------------
    # API key validation
    # ------------------------------------------------------------------

    def _validate_key(self) -> None:
        if not self._on_validate_key:
            return
        key = self._api_key_edit.text().strip()
        if not key:
            self._set_status("Please enter an API key", current_palette()["warning"])
            return

        self._set_status("Validating…", current_palette()["secondary"])

        # Run in a QThread so the GUI stays responsive
        self._validate_thread = QThread()
        self._validate_worker = _ValidateWorker(self._on_validate_key, key)
        self._validate_worker.moveToThread(self._validate_thread)
        self._validate_thread.started.connect(self._validate_worker.run)
        self._validate_worker.result.connect(self._on_validate_result)
        self._validate_worker.result.connect(self._validate_thread.quit)
        self._validate_thread.start()

    def _on_validate_result(self, success: bool, message: str) -> None:
        colour = current_palette()["success"] if success else current_palette()["error"]
        prefix = "\u2713" if success else "\u2717"
        self._set_status(f"{prefix}  {message}", colour)

    def _sync_offline_state(self) -> None:
        """Grey out Dictation Mode while Offline mode is on, and say why.

        Offline transcription never calls the LLM, so the chosen mode would be
        silently ignored.
        """
        offline = self._offline_check.isChecked()
        self._profile_combo.setEnabled(not offline)
        self._profile_sub.setText(_MODE_SUBTITLE_OFFLINE if offline else _MODE_SUBTITLE)

    def show_warning(self, text: str) -> None:
        """Show a warning in the status line (e.g. the chosen mic is missing)."""
        self._set_status(text, current_palette()["warning"])

    def _set_status(self, text: str, colour: str) -> None:
        self._status_label.setText(text)
        self._status_label.setStyleSheet(f"color: {colour}; font-size: 11px;")

    # ------------------------------------------------------------------
    # Hotkey capture
    # ------------------------------------------------------------------

    def _toggle_hotkey_capture(self, target: str = "main") -> None:
        if self._capturing:
            self._stop_hotkey_capture()
        else:
            self._start_hotkey_capture(target)

    def _start_hotkey_capture(self, target: str = "main") -> None:
        self._capturing = True
        self._capture_target = target
        self._captured_keys = set()

        btn = self._capture_btn
        edit = self._hotkey_edit

        btn.setText("Press…")
        btn.setObjectName("capture_btn_recording")
        btn.setStyleSheet(
            f"background-color: {current_palette()['error']}; border-radius: 8px; "
            f"font-family: 'Segoe UI'; font-size: 12px; font-weight: bold; "
            f"color: #FFFFFF; min-height: 28px; padding: 6px 18px;"
        )
        edit.setText("Press your hotkey combo…")

        self._capture_listener = pynput_keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release,
        )
        self._capture_listener.daemon = True
        self._capture_listener.start()

    def _on_key_press(self, key) -> None:  # noqa: ANN001
        """Called from pynput listener thread on key press."""
        name = self._key_to_pynput_str(key)
        if name:
            self._captured_keys.add(name)

    def _on_key_release(self, key) -> None:  # noqa: ANN001
        """Called from pynput listener thread on key release.

        We finalise the combo on the first release so the user only needs to
        press the full combination once.  We also handle modifier-only combos
        (e.g. Ctrl+Alt) — we just need at least 1 key in the set.
        """
        if not self._captured_keys:
            return

        # Build the hotkey string from whatever was pressed
        hotkey = self._build_hotkey_string()
        # Emit into the GUI thread via pyqtSignal
        self._hotkey_captured.emit(hotkey)

    def _finish_capture(self, hotkey: str) -> None:
        """Slot — runs in the GUI thread."""
        self._hotkey_edit.setText(hotkey)
        self._stop_hotkey_capture()

    def _stop_hotkey_capture(self) -> None:
        self._capturing = False
        if self._capture_listener is not None:
            try:
                self._capture_listener.stop()
            except Exception:  # noqa: BLE001
                pass
            self._capture_listener = None

        self._capture_btn.setText("Record")
        self._capture_btn.setObjectName("")
        self._capture_btn.setStyleSheet("")

    # ------------------------------------------------------------------
    # Key → pynput string helpers
    # ------------------------------------------------------------------

    # Map pynput key names to canonical pynput hotkey tokens
    _MODIFIER_MAP: dict[str, str] = {
        "ctrl_l": "<ctrl>",
        "ctrl_r": "<ctrl>",
        "shift": "<shift>",
        "shift_r": "<shift>",
        "alt_l": "<alt>",
        "alt_r": "<alt>",
        "alt_gr": "<alt_gr>",
        "cmd": "<cmd>",
        "cmd_r": "<cmd>",
        "caps_lock": "<caps_lock>",
    }

    # Special non-modifier keys that should be wrapped in angle brackets
    _SPECIAL_KEYS: frozenset[str] = frozenset(
        {
            "space", "tab", "enter", "return", "backspace", "delete", "escape",
            "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10",
            "f11", "f12", "f13", "f14", "f15", "f16", "f17", "f18", "f19", "f20",
            "home", "end", "page_up", "page_down",
            "left", "right", "up", "down",
            "insert", "print_screen", "scroll_lock", "pause",
            "num_lock",
        }
    )

    def _key_to_pynput_str(self, key) -> str | None:  # noqa: ANN001
        """Convert a pynput Key or KeyCode to the token used in pynput hotkey strings."""
        if hasattr(key, "name") and key.name:
            name: str = key.name.lower()
            if name in self._MODIFIER_MAP:
                return self._MODIFIER_MAP[name]
            if name in self._SPECIAL_KEYS:
                return f"<{name}>"
            # Any other named key (e.g. media keys)
            return f"<{name}>"
        if hasattr(key, "char") and key.char:
            return key.char.lower()
        return None

    def _build_hotkey_string(self) -> str:
        """Assemble captured tokens into a pynput hotkey string.

        Modifiers come first (sorted for stability), then regular keys.
        Example: <ctrl>+<shift>+space
        """
        _MODIFIER_ORDER = ("<ctrl>", "<shift>", "<alt>", "<alt_gr>", "<cmd>")

        modifiers: list[str] = []
        regulars: list[str] = []

        for token in self._captured_keys:
            if token in _MODIFIER_ORDER:
                modifiers.append(token)
            else:
                regulars.append(token)

        # Sort modifiers by canonical order for determinism
        modifiers.sort(key=lambda m: _MODIFIER_ORDER.index(m) if m in _MODIFIER_ORDER else 99)
        regulars.sort()

        parts = modifiers + regulars
        return "+".join(parts) if parts else "<ctrl>+<shift>+space"

    # ------------------------------------------------------------------
    # Help dialog
    # ------------------------------------------------------------------

    def _open_history(self) -> None:
        if self._on_history:
            self._on_history()

    def _open_stats(self) -> None:
        if self._on_stats:
            self._on_stats()

    def _show_help(self) -> None:
        from PyQt6.QtWidgets import QDialog, QScrollArea

        dlg = QDialog(self)
        dlg.setWindowTitle("Voxel - Help & FAQ")
        dlg.setFixedSize(460, 520)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        clayout = QVBoxLayout(content)
        clayout.setContentsMargins(24, 24, 24, 24)
        clayout.setSpacing(16)

        _help_sections = [
            ("How to use Voxel",
             "1. Hold your hotkey (default: Ctrl+Shift+Space)\n"
             "2. Speak naturally into your microphone\n"
             "3. Release the hotkey when you're done\n"
             "4. Your cleaned-up text is pasted wherever your cursor is\n\n"
             "It works in any app - Chrome, VS Code, Word, Slack, Discord, Notepad, etc."),

            ("What is the Groq API Key?",
             "Groq provides free AI services that Voxel uses for transcription and text cleanup.\n\n"
             "To get a free key:\n"
             "1. Go to console.groq.com\n"
             "2. Sign up (Google/GitHub sign-in works)\n"
             "3. Go to API Keys in the sidebar\n"
             "4. Click Create API Key\n"
             "5. Copy the key and paste it here\n\n"
             "No credit card required. Completely free."),

            ("Recording limit",
             "Groq's free tier has a limit on audio length per request. If you hit it, "
             "just release the hotkey and press it again to start a new recording.\n\n"
             "It's seamless - you won't lose anything. For most dictation "
             "(emails, messages, code comments), you'll never hit the limit."),

            ("Hotkey setup",
             "Click 'Record' next to the hotkey field, then press your desired key combination.\n\n"
             "You can use any combination of Ctrl, Shift, Alt, and a key. "
             "Modifier-only combos like Ctrl+Alt also work.\n\n"
             "The hotkey works globally - it captures input no matter what app is focused."),

            ("Microphone selection",
             "Choose which microphone Voxel uses for recording. "
             "If you plug in a new mic, restart Voxel or reopen Settings to see it.\n\n"
             "Voxel remembers your microphone by name, so plugging in other audio "
             "devices won't quietly switch it to a different one.\n\n"
             "If your chosen mic isn't available, Voxel keeps working using your "
             "default microphone and tells you — the device name shown while "
             "recording is always the one actually in use."),

            ("Activation: hold or toggle",
             "Hold to talk: recording runs while you hold the hotkey, and stops "
             "when you let go.\n\n"
             "Press to start, press to stop: tap the hotkey once to begin and "
             "again to finish — useful for long dictation.\n\n"
             "Toggle needs a hotkey with a normal key in it (like Ctrl+Shift+Space). "
             "A modifier-only combo such as Ctrl+Alt can't toggle, because every "
             "press of those keys would flip recording on or off.\n\n"
             "Recording still stops automatically after 2 minutes."),

            ("Mute sounds",
             "When enabled, the confirmation chime that plays after you stop recording is silenced."),

            ("Always copy to clipboard",
             "When enabled, your transcribed text stays on the clipboard after pasting. "
             "When disabled, Voxel restores whatever was on your clipboard before."),

            ("Show clipboard notice",
             "When you release the hotkey while the desktop or taskbar is focused "
             "(no text field available), Voxel copies the text to your clipboard instead of pasting.\n\n"
             "This setting controls whether a notification appears telling you "
             "the text was copied and is ready to paste with Ctrl+V."),

            ("Dictation Modes",
             "Switch between different cleanup styles:\n"
             "- Raw (no cleanup): exactly what you said, no AI pass at all\n"
             "- Grammar only — keep my words: fixes grammar, tense, spelling and\n"
             "  punctuation but keeps your filler words, slang and phrasing intact\n"
             "- Grammar + tidy up: fixes grammar AND removes filler words so it\n"
             "  reads cleanly\n"
             "- Professional Email: rewritten as polished business correspondence\n"
             "- Code Comments: terse and declarative, correct identifier spelling\n"
             "- Technical Writing: precise, documentation-style prose\n\n"
             "Select a mode from the Dictation Mode dropdown in settings.\n\n"
             "Note: Dictation Mode has no effect while Offline mode is on, because\n"
             "offline transcription never runs the AI cleanup step."),

            ("Voice Commands",
             "Define trigger phrases that expand to templates.\n\n"
             "Example: say 'sign off' and Voxel inserts 'Best regards, Drax' "
             "instead of cleaning up your speech.\n\n"
             "Placeholders: {{date}}, {{time}}, {{datetime}}, {{clipboard}}\n\n"
             "Set up commands via the Voice Commands button in settings."),

            ("Dictation History",
             "All your dictations are saved automatically.\n\n"
             "Access history from the tray icon menu or settings. "
             "You can search, copy, and delete entries."),

            ("Auto-detect Language",
             "Select 'Auto-detect' in the Language dropdown and Voxel will "
             "automatically detect which language you're speaking.\n\n"
             "This works with 90+ languages. If accuracy drops, try setting "
             "the language manually instead."),

            ("Auto-switch Profile Per App",
             "When enabled, Voxel detects which app is focused and automatically "
             "switches to a matching dictation mode.\n\n"
             "To configure, edit the config file at:\n"
             "  Windows: %APPDATA%\\Voxel\\config.json\n"
             "  macOS: ~/Library/Application Support/Voxel/config.json\n\n"
             "Add app mappings like:\n"
             "  \"app_profiles\": {\n"
             "    \"outlook\": \"professional\",\n"
             "    \"code\": \"code\",\n"
             "    \"slack\": \"casual\"\n"
             "  }"),

            ("Offline Mode",
             "When enabled, Voxel uses a local Whisper model instead of the Groq API.\n\n"
             "- No internet connection needed\n"
             "- The model downloads on first use (~145MB for base)\n"
             "- Transcription is slower than the cloud API\n"
             "- No AI text cleanup in offline mode (raw transcription only)\n\n"
             "Best for: privacy-sensitive use or when you have no internet."),

            ("Statistics",
             "View your usage stats from the tray icon menu (right-click -> Statistics).\n\n"
             "Shows total dictations, words, recording time, most used profile, and more."),

            ("It's not transcribing / API errors",
             "- Check that your API key is valid (click Verify)\n"
             "- Make sure you have an internet connection\n"
             "- If you see rate limit errors, wait a few seconds and try again\n"
             "- Groq's free tier has usage limits - they reset periodically\n"
             "- Try enabling Offline Mode if you don't have internet"),
        ]

        for title, body in _help_sections:
            t = QLabel(title)
            t.setStyleSheet(f"color: {current_palette()['text']}; font-size: 14px; font-weight: 600;")
            t.setWordWrap(True)
            clayout.addWidget(t)

            b = QLabel(body)
            b.setStyleSheet(f"color: {current_palette()['secondary']}; font-size: 12px;")
            b.setWordWrap(True)
            clayout.addWidget(b)

            sep = QFrame()
            sep.setStyleSheet(f"background-color: {current_palette()['separator']}; max-height: 1px;")
            sep.setFrameShape(QFrame.Shape.HLine)
            clayout.addWidget(sep)

        clayout.addStretch()

        # Set icon
        icon_path = self._resolve_asset("icon.ico")
        if icon_path and os.path.exists(icon_path):
            dlg.setWindowIcon(QIcon(icon_path))

        dlg.exec()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:  # noqa: ANN001, N802
        self._stop_hotkey_capture()
        if self._validate_thread and self._validate_thread.isRunning():
            self._validate_thread.quit()
            self._validate_thread.wait(500)
        # If app is quitting or window is minimized (taskbar right-click close), quit
        if getattr(self, '_quitting', False) or self.isMinimized():
            if self._on_quit:
                self._on_quit()
            super().closeEvent(event)
        else:
            # X button while window is open — minimize to taskbar
            event.ignore()
            self.showMinimized()
