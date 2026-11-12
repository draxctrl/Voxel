"""Shortcuts: the keys you hold to talk, and how holding them behaves."""
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

from ..keys import pretty_hotkey
from . import Pane, PaneContext
from .widgets import pane_surface_qss, repaint_with, ChoiceRow, PaneHeader, pane_body

logger = logging.getLogger(__name__)

MODE_IDS = ("hold", "toggle")

_MODES = {
    "hold": ("Hold to talk", "Hold the keys down while you speak"),
    "toggle": (
        "Press to start, press to stop",
        "Tap once to begin, tap again when you are done",
    ),
}


def is_modifier_only(hotkey: str) -> bool:
    """True when the combo is modifiers alone, with no ordinary key."""
    from src.hotkey_listener import HotkeyListener

    try:
        return HotkeyListener(
            hotkey_str=hotkey, on_press=lambda: None, on_release=lambda: None
        ).is_modifier_only
    except Exception:
        return False


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
        self.button.setStyleSheet(
            "QPushButton {{ color: {text}; background-color: {card_alt};"
            " border: 1px solid {row_border}; border-radius: 7px;"
            " font-size: 12px; padding: 4px 14px; }}"
            "QPushButton:hover {{ border-color: {accent}; }}".format(**p)
        )


class ShortcutsPane(Pane):
    PANE_ID = "shortcuts"
    TITLE = "Shortcuts"
    SUBTITLE = "The keys that start and stop dictation."
    # No undo shortcut: it sent a blind Ctrl+Z to whatever had focus and
    # was removed from Voxel. A row for it would capture a combination
    # nothing listens for.
    OWNS = frozenset({"hotkey", "activation_mode"})

    MODE_IDS = MODE_IDS

    def __init__(self, ctx: PaneContext, parent=None) -> None:
        super().__init__(ctx, parent)
        self._warning = ""
        self._mode_rows: dict[str, ChoiceRow] = {}

        _area, layout = pane_body(self)

        self._header = PaneHeader(self.TITLE, self.SUBTITLE, self)
        layout.addWidget(self._header)
        layout.addSpacing(6)

        self._warning_label = QLabel()
        self._warning_label.setWordWrap(True)
        self._warning_label.setVisible(False)
        layout.addWidget(self._warning_label)

        self._hotkey_row = _ShortcutRow(
            "Push to talk", "Hold these keys and speak"
        )
        self._hotkey_row.button.clicked.connect(self._capture_hotkey)
        layout.addWidget(self._hotkey_row)

        layout.addSpacing(10)
        self._mode_header = QLabel("How it activates")
        self._mode_header.setObjectName("section_heading")
        layout.addWidget(self._mode_header)

        for mode_id in MODE_IDS:
            title, subtitle = _MODES[mode_id]
            row = ChoiceRow(mode_id, title, subtitle, self)
            row.clicked.connect(self.choose_mode)
            self._mode_rows[mode_id] = row
            layout.addWidget(row)

        layout.addStretch(1)
        self.refresh()

    # ------------------------------------------------------------------

    def mode_ids(self) -> tuple[str, ...]:
        return MODE_IDS

    def mode_titles(self) -> dict[str, str]:
        return {k: v[0] for k, v in _MODES.items()}

    def selected_mode(self) -> str:
        mode = self.ctx.config.get("activation_mode", "hold")
        return mode if mode in MODE_IDS else "hold"

    def hotkey_text(self) -> str:
        return pretty_hotkey(self.ctx.config.get("hotkey", ""))

    def warning_text(self) -> str:
        return self._warning

    # ------------------------------------------------------------------

    def choose_mode(self, mode_id: str) -> None:
        """Apply an activation mode, refusing one the hotkey cannot do."""
        if mode_id not in MODE_IDS:
            return
        hotkey = self.ctx.config.get("hotkey", "")
        if mode_id == "toggle" and is_modifier_only(hotkey):
            self._set_warning(
                "%s cannot toggle on its own - every press of those keys "
                "anywhere would start or stop recording. Add a normal key "
                "(Ctrl + Shift + Space, say) and try again."
                % (pretty_hotkey(hotkey) or "That shortcut")
            )
            self.refresh()
            return
        self._set_warning("")
        self.ctx.apply("activation_mode", mode_id)
        self.refresh()

    def set_hotkey(self, hotkey: str) -> None:
        """Apply a captured combo. An empty capture is not a choice."""
        if not hotkey:
            return
        if self.selected_mode() == "toggle" and is_modifier_only(hotkey):
            self._set_warning(
                "%s cannot toggle on its own. Voxel has kept your previous "
                "shortcut; add a normal key and try again."
                % pretty_hotkey(hotkey)
            )
            self.refresh()
            return
        self._set_warning("")
        self.ctx.apply("hotkey", hotkey)
        self.refresh()

    def _set_warning(self, text: str) -> None:
        self._warning = text
        self._warning_label.setText(text)
        self._warning_label.setVisible(bool(text))

    # ------------------------------------------------------------------

    def _capture_hotkey(self) -> None:
        self._capture(self.set_hotkey, self._hotkey_row)

    def _capture(self, apply_to, row: _ShortcutRow) -> None:
        """Listen for one key combination and hand it to `apply_to`."""
        from .hotkey_capture import capture_hotkey

        row.button.setText("Press…")
        capture_hotkey(
            lambda combo: self._finish_capture(apply_to, row, combo)
        )

    def _finish_capture(self, apply_to, row: _ShortcutRow, combo: str) -> None:
        row.button.setText("Change")
        apply_to(combo)

    # ------------------------------------------------------------------

    def refresh(self) -> None:
        self._hotkey_row.value.setText(self.hotkey_text() or "Not set")
        mode = self.selected_mode()
        for mode_id, row in self._mode_rows.items():
            row.set_selected(mode_id == mode)

    def restyle(self, palette: dict) -> None:
        self._palette = dict(palette)
        repaint_with(self, pane_surface_qss(self._palette))
        self._header.restyle(self._palette)
        self._warning_label.setStyleSheet(
            "color: {warning}; font-size: 13px; background: transparent;".format(
                **self._palette
            )
        )
        self._mode_header.setStyleSheet(
            "color: {faint}; font-size: 11px; font-weight: 700;"
            " letter-spacing: 0.8px; background: transparent;".format(**self._palette)
        )
        self._hotkey_row.restyle(self._palette)
        for row in self._mode_rows.values():
            row.restyle(self._palette)
