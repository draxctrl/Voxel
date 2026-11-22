"""Shortcuts: a key you hold to talk, and a key you tap to start and stop.

Both are live at once. Either can be turned off, but not both.
"""
from __future__ import annotations

import logging

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from src.hotkey_listener import hotkeys_clash

from ..keys import pretty_hotkey
from . import Pane, PaneContext
from .widgets import pane_surface_qss, repaint_with, PaneHeader, pane_body

logger = logging.getLogger(__name__)

#: Config key -> (row title, row description, the key's name in a warning).
_KEYS = {
    "hotkey": ("Push to talk", "Hold these keys and speak", "push to talk"),
    "toggle_hotkey": (
        "Press to start, press to stop",
        "Tap once to begin, tap again when you are done",
        "press to start",
    ),
}


class _ShortcutRow(QFrame):
    """A label, the shortcut as words, and a button that captures a new one.

    A QFrame rather than a QWidget: a plain QWidget child ignores a
    stylesheet background, so the row would carry a correct rule and still
    render as bare text on the pane.
    """

    def __init__(self, label: str, description: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("setting_row")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 11, 14, 11)
        layout.setSpacing(12)

        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(2)
        self._label = QLabel(label)
        text.addWidget(self._label)
        self._description = QLabel(description)
        self._description.setWordWrap(True)
        text.addWidget(self._description)
        layout.addLayout(text, 1)

        self.value = QLabel("")
        layout.addWidget(self.value, 0, Qt.AlignmentFlag.AlignVCenter)
        self.button = QPushButton("Change")
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.button.setFixedHeight(28)
        layout.addWidget(self.button, 0, Qt.AlignmentFlag.AlignVCenter)
        self.off_button = QPushButton("Turn off")
        self.off_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.off_button.setFixedHeight(28)
        layout.addWidget(self.off_button, 0, Qt.AlignmentFlag.AlignVCenter)

    def restyle(self, p: dict) -> None:
        self.setStyleSheet(
            "QFrame#setting_row {{ background-color: {row};"
            " border: 1px solid {row_border}; border-radius: 9px; }}".format(**p)
        )
        self._label.setStyleSheet(
            "color: {text}; font-size: 14px; font-weight: 500;"
            " background: transparent;".format(**p)
        )
        self._description.setStyleSheet(
            "color: {muted}; font-size: 12px; background: transparent;".format(**p)
        )
        self.value.setStyleSheet(
            "color: {text}; font-size: 13px; font-weight: 600;"
            " background: transparent;".format(**p)
        )
        button_qss = (
            "QPushButton {{ color: {text}; background-color: {card_alt};"
            " border: 1px solid {row_border}; border-radius: 7px;"
            " font-size: 12px; padding: 4px 14px; }}"
            "QPushButton:hover {{ border-color: {accent}; }}".format(**p)
        )
        self.button.setStyleSheet(button_qss)
        self.off_button.setStyleSheet(button_qss)


class ShortcutsPane(Pane):
    PANE_ID = "shortcuts"
    TITLE = "Shortcuts"
    SUBTITLE = "The keys that start and stop dictation."
    # No undo shortcut: it sent a blind Ctrl+Z to whatever had focus and
    # was removed from Voxel. A row for it would capture a combination
    # nothing listens for.
    OWNS = frozenset(_KEYS)

    def __init__(self, ctx: PaneContext, parent=None) -> None:
        super().__init__(ctx, parent)
        self._warning = ""
        self._rows: dict[str, _ShortcutRow] = {}

        _area, layout = pane_body(self)

        self._header = PaneHeader(self.TITLE, self.SUBTITLE, self)
        layout.addWidget(self._header)
        layout.addSpacing(6)

        self._warning_label = QLabel()
        self._warning_label.setWordWrap(True)
        self._warning_label.setVisible(False)
        layout.addWidget(self._warning_label)

        for index, (key, (title, description, _name)) in enumerate(_KEYS.items()):
            if index:
                layout.addSpacing(8)
            row = _ShortcutRow(title, description)
            row.button.clicked.connect(lambda _=False, k=key: self._capture(k))
            row.off_button.clicked.connect(lambda _=False, k=key: self.turn_off(k))
            self._rows[key] = row
            layout.addWidget(row)

        layout.addStretch(1)
        self.refresh()

    # ------------------------------------------------------------------

    def key_text(self, key: str) -> str:
        return pretty_hotkey(self.ctx.config.get(key, "")) or "Not set"

    def warning_text(self) -> str:
        return self._warning

    @staticmethod
    def _other(key: str) -> str:
        return "toggle_hotkey" if key == "hotkey" else "hotkey"

    # ------------------------------------------------------------------

    def set_key(self, key: str, combo: str) -> None:
        """Apply a captured combo to one row. An empty capture is no choice."""
        if key not in _KEYS or not combo:
            return
        other = self._other(key)
        if hotkeys_clash(combo, self.ctx.config.get(other, "")):
            self._set_warning(
                "%s would also set off your %s key (%s). Pick a different one."
                % (pretty_hotkey(combo), _KEYS[other][2],
                   pretty_hotkey(self.ctx.config.get(other, "")))
            )
            self.refresh()
            return
        self._set_warning("")
        self.ctx.apply(key, combo)
        self.refresh()

    def turn_off(self, key: str) -> None:
        """Turn one key off, unless it is the only one left."""
        if key not in _KEYS:
            return
        if not self.ctx.config.get(self._other(key), ""):
            self._set_warning(
                "Keep at least one shortcut, or Voxel has no way to start."
            )
            self.refresh()
            return
        self._set_warning("")
        self.ctx.apply(key, "")
        self.refresh()

    def _set_warning(self, text: str) -> None:
        self._warning = text
        self._warning_label.setText(text)
        self._warning_label.setVisible(bool(text))

    # ------------------------------------------------------------------

    def _capture(self, key: str) -> None:
        """Listen for one key combination and apply it to `key`."""
        from .hotkey_capture import capture_hotkey

        row = self._rows[key]
        row.button.setText("Press…")
        capture_hotkey(lambda combo: self._finish_capture(key, combo))

    def _finish_capture(self, key: str, combo: str) -> None:
        self._rows[key].button.setText("Change")
        self.set_key(key, combo)

    # ------------------------------------------------------------------

    def refresh(self) -> None:
        for key, row in self._rows.items():
            is_set = bool(self.ctx.config.get(key, ""))
            row.value.setText(self.key_text(key))
            row.button.setText("Change" if is_set else "Set")
            row.off_button.setVisible(is_set)

    def restyle(self, palette: dict) -> None:
        self._palette = dict(palette)
        repaint_with(self, pane_surface_qss(self._palette))
        self._header.restyle(self._palette)
        self._warning_label.setStyleSheet(
            "color: {warning}; font-size: 13px; background: transparent;".format(
                **self._palette
            )
        )
        for row in self._rows.values():
            row.restyle(self._palette)
