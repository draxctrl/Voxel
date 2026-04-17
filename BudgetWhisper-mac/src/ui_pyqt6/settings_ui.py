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

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
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

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------
_BG = "#0f0f0f"
_CARD = "#1a1a1a"
_BORDER = "#2a2a2a"
_INPUT_BG = "#111111"
_TEXT = "#e8e8e8"
_SUBTLE = "#777777"
_ACCENT = "#6366f1"
_ACCENT_HOVER = "#818cf8"
_SUCCESS = "#22c55e"
_ERROR = "#ef4444"
_WARNING = "#f59e0b"

# ---------------------------------------------------------------------------
# QSS stylesheet
# ---------------------------------------------------------------------------
_QSS = f"""
QWidget {{
    background-color: {_BG};
    color: {_TEXT};
    font-family: "SF Pro Display", "Helvetica Neue", "Segoe UI", sans-serif;
    font-size: 13px;
}}

QLabel {{
    background: transparent;
    color: {_TEXT};
}}

QLabel#subtitle {{
    color: {_SUBTLE};
    font-size: 11px;
}}

QLabel#section_title {{
    color: {_TEXT};
    font-size: 13px;
    font-weight: bold;
}}

QLabel#section_sub {{
    color: {_SUBTLE};
    font-size: 11px;
}}

QLabel#status_label {{
    color: {_SUBTLE};
    font-size: 11px;
}}

QLabel#app_title {{
    color: {_TEXT};
    font-size: 22px;
    font-weight: bold;
}}

QLineEdit {{
    background-color: {_INPUT_BG};
    color: {_TEXT};
    border: 1px solid {_BORDER};
    border-radius: 8px;
    padding: 6px 10px;
    font-family: "SF Pro Display", "Helvetica Neue", "Segoe UI", sans-serif;
    font-size: 13px;
    selection-background-color: {_ACCENT};
}}

QLineEdit:focus {{
    border: 1px solid {_ACCENT};
}}

QLineEdit[readOnly="true"] {{
    color: {_SUBTLE};
    font-family: "Consolas";
}}

QComboBox {{
    background-color: {_INPUT_BG};
    color: {_TEXT};
    border: 1px solid {_BORDER};
    border-radius: 8px;
    padding: 6px 10px;
    font-family: "SF Pro Display", "Helvetica Neue", "Segoe UI", sans-serif;
    font-size: 13px;
    min-width: 120px;
}}

QComboBox:focus {{
    border: 1px solid {_ACCENT};
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 28px;
    border: none;
    background: transparent;
}}

QComboBox::down-arrow {{
    width: 0px;
    height: 0px;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {_SUBTLE};
    margin-right: 6px;
}}

QComboBox QAbstractItemView {{
    background-color: {_CARD};
    color: {_TEXT};
    border: 1px solid {_BORDER};
    border-radius: 6px;
    selection-background-color: {_ACCENT};
    outline: none;
}}

QPushButton {{
    background-color: {_ACCENT};
    color: {_TEXT};
    border: none;
    border-radius: 8px;
    padding: 6px 18px;
    font-family: "SF Pro Display", "Helvetica Neue", "Segoe UI", sans-serif;
    font-size: 12px;
    font-weight: bold;
    min-height: 28px;
}}

QPushButton:hover {{
    background-color: {_ACCENT_HOVER};
}}

QPushButton:pressed {{
    background-color: {_ACCENT};
}}

QPushButton#save_btn {{
    font-size: 14px;
    border-radius: 10px;
    min-height: 42px;
    padding: 10px 18px;
}}

QPushButton#capture_btn_recording {{
    background-color: {_ERROR};
}}

QPushButton#capture_btn_recording:hover {{
    background-color: #f87171;
}}

QCheckBox {{
    color: {_SUBTLE};
    font-size: 12px;
    spacing: 8px;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 1px solid {_BORDER};
    border-radius: 4px;
    background-color: {_INPUT_BG};
}}

QCheckBox::indicator:checked {{
    background-color: {_ACCENT};
    border-color: {_ACCENT};
}}

QCheckBox::indicator:checked:hover {{
    background-color: {_ACCENT_HOVER};
}}

QFrame#divider {{
    background-color: {_BORDER};
    max-height: 1px;
    min-height: 1px;
    border: none;
}}
"""


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
# Custom checkbox with visible tick mark
# ---------------------------------------------------------------------------
class _TickCheckBox(QCheckBox):
    """QCheckBox that draws a white checkmark when checked."""

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.isChecked():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            # Draw tick over the indicator area
            indicator_x = 1
            indicator_y = (self.height() - 18) // 2
            pen = QPen(QColor(255, 255, 255), 2.5)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            # Checkmark path: ✓
            painter.drawLine(indicator_x + 4, indicator_y + 9, indicator_x + 7, indicator_y + 13)
            painter.drawLine(indicator_x + 7, indicator_y + 13, indicator_x + 14, indicator_y + 5)
            painter.end()


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
    ) -> None:
        super().__init__()

        self._config = config
        self._on_save = on_save
        self._on_validate_key = on_validate_key
        self._on_quit = on_quit

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
        self.setFixedSize(480, 560)
        self.setStyleSheet(_QSS)
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
        title_lbl = QLabel("Voxel")
        title_lbl.setObjectName("app_title")
        root_layout.addWidget(title_lbl)

        sub_lbl = QLabel("Voice dictation settings")
        sub_lbl.setObjectName("subtitle")
        root_layout.addWidget(sub_lbl)

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

        root_layout.addSpacing(16)

        # ── Language + checkboxes row ────────────────────────────────────
        options_row = QHBoxLayout()
        options_row.setSpacing(16)

        # Language column
        lang_col = QVBoxLayout()
        lang_col.setSpacing(4)
        lang_title = QLabel("Language")
        lang_title.setObjectName("section_title")
        lang_col.addWidget(lang_title)

        self._lang_combo = QComboBox()
        _LANGUAGES = [
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
        for code, label in _LANGUAGES:
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

        self._mute_check = _TickCheckBox("Mute sounds")
        self._mute_check.setChecked(self._config.get("mute_sound", False))
        check_col.addWidget(self._mute_check)

        self._autostart_check = _TickCheckBox("Run at login")
        self._autostart_check.setChecked(self._config.get("auto_start", False))
        check_col.addWidget(self._autostart_check)

        self._always_copy_check = _TickCheckBox("Always copy to clipboard")
        self._always_copy_check.setChecked(self._config.get("always_copy", False))
        check_col.addWidget(self._always_copy_check)

        self._clipboard_notice_check = _TickCheckBox("Show clipboard notice")
        self._clipboard_notice_check.setChecked(self._config.get("clipboard_notice", True))
        check_col.addWidget(self._clipboard_notice_check)

        options_row.addLayout(check_col, stretch=1)

        root_layout.addLayout(options_row)

        # ── Spacer ───────────────────────────────────────────────────────
        root_layout.addStretch(1)

        # ── Save button ──────────────────────────────────────────────────
        self._save_btn = QPushButton("Save Settings")
        self._save_btn.setObjectName("save_btn")
        self._save_btn.clicked.connect(self._save)
        root_layout.addWidget(self._save_btn)

    # ------------------------------------------------------------------
    # Helper: section header
    # ------------------------------------------------------------------

    def _add_section(self, layout: QVBoxLayout, title: str, subtitle: str) -> None:
        t = QLabel(title)
        t.setObjectName("section_title")
        layout.addWidget(t)

        s = QLabel(subtitle)
        s.setObjectName("section_sub")
        layout.addWidget(s)

        layout.addSpacing(4)

    # ------------------------------------------------------------------
    # Asset resolution (frozen + dev paths)
    # ------------------------------------------------------------------

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
        self._config.set("hotkey", self._hotkey_edit.text().strip())
        self._config.set("auto_start", self._autostart_check.isChecked())
        self._config.set("mute_sound", self._mute_check.isChecked())
        self._config.set("always_copy", self._always_copy_check.isChecked())
        self._config.set("clipboard_notice", self._clipboard_notice_check.isChecked())
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
            self._set_status("Please enter an API key", _WARNING)
            return

        self._set_status("Validating…", _SUBTLE)

        # Run in a QThread so the GUI stays responsive
        self._validate_thread = QThread()
        self._validate_worker = _ValidateWorker(self._on_validate_key, key)
        self._validate_worker.moveToThread(self._validate_thread)
        self._validate_thread.started.connect(self._validate_worker.run)
        self._validate_worker.result.connect(self._on_validate_result)
        self._validate_worker.result.connect(self._validate_thread.quit)
        self._validate_thread.start()

    def _on_validate_result(self, success: bool, message: str) -> None:
        colour = _SUCCESS if success else _ERROR
        prefix = "\u2713" if success else "\u2717"
        self._set_status(f"{prefix}  {message}", colour)

    def _set_status(self, text: str, colour: str) -> None:
        self._status_label.setText(text)
        self._status_label.setStyleSheet(f"color: {colour}; font-size: 11px;")

    # ------------------------------------------------------------------
    # Hotkey capture
    # ------------------------------------------------------------------

    def _toggle_hotkey_capture(self) -> None:
        if self._capturing:
            self._stop_hotkey_capture()
        else:
            self._start_hotkey_capture()

    def _start_hotkey_capture(self) -> None:
        self._capturing = True
        self._captured_keys = set()

        # Update button appearance
        self._capture_btn.setText("Press…")
        self._capture_btn.setObjectName("capture_btn_recording")
        self._capture_btn.setStyleSheet(
            f"background-color: {_ERROR}; border-radius: 8px; "
            f"font-family: 'Segoe UI'; font-size: 12px; font-weight: bold; "
            f"color: {_TEXT}; min-height: 28px; padding: 6px 18px;"
        )
        self._hotkey_edit.setText("Press your hotkey combo…")

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

        # Restore button appearance by clearing the per-widget stylesheet
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
