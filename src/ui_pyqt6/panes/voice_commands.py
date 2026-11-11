"""Voice commands: say a short phrase, get a block of text.

This was a modal dialog hanging off the old settings page. It is a pane
now, which is the whole change - the editing works as it always did.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..icons import icon as load_icon
from . import Pane, PaneContext
from .widgets import pane_surface_qss, repaint_with, PaneHeader, pane_body

EMPTY_MESSAGE = (
    'No voice commands yet. Add one below - say "brb" and Voxel can type '
    '"be right back" for you.'
)


class _CommandRow(QFrame):
    """One trigger, its expansion, and a button to remove it."""

    def __init__(self, trigger: str, expansion: str, on_delete, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("setting_row")
        self.trigger = trigger

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 10, 10)
        layout.setSpacing(10)

        self._trigger = QLabel(trigger)
        self._trigger.setFixedWidth(130)
        layout.addWidget(self._trigger)

        self._arrow = QLabel("→")
        self._arrow.setFixedWidth(18)
        self._arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._arrow)

        self._expansion = QLabel(expansion)
        self._expansion.setWordWrap(True)
        layout.addWidget(self._expansion, 1)

        self.delete_button = QPushButton()
        self.delete_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_button.setFixedSize(QSize(28, 28))
        self.delete_button.setIconSize(QSize(16, 16))
        self.delete_button.setToolTip("Remove this command")
        self.delete_button.clicked.connect(lambda: on_delete(trigger))
        layout.addWidget(self.delete_button, 0, Qt.AlignmentFlag.AlignVCenter)

    def restyle(self, p: dict) -> None:
        self.setStyleSheet(
            "QFrame#setting_row {{ background-color: {row};"
            " border: 1px solid {row_border}; border-radius: 9px; }}".format(**p)
        )
        self._trigger.setStyleSheet(
            "color: {text}; font-size: 13px; font-weight: 600;"
            " background: transparent;".format(**p)
        )
        self._arrow.setStyleSheet(
            "color: {faint}; font-size: 13px; background: transparent;".format(**p)
        )
        self._expansion.setStyleSheet(
            "color: {muted}; font-size: 13px; background: transparent;".format(**p)
        )
        self.delete_button.setIcon(load_icon("trash", p["muted"], 16))
        self.delete_button.setStyleSheet(
            "QPushButton {{ background: transparent; border: none;"
            " border-radius: 6px; }}"
            "QPushButton:hover {{ background-color: {card_alt}; }}".format(**p)
        )


class VoiceCommandsPane(Pane):
    PANE_ID = "voice_commands"
    TITLE = "Voice commands"
    SUBTITLE = "Short phrases Voxel types out in full."
    OWNS = frozenset({"voice_commands"})

    def __init__(self, ctx: PaneContext, parent=None) -> None:
        super().__init__(ctx, parent)
        self._rows: list[_CommandRow] = []

        _area, layout = pane_body(self)

        self._header = PaneHeader(self.TITLE, self.SUBTITLE)
        layout.addWidget(self._header)
        layout.addSpacing(6)

        self._empty = QLabel(EMPTY_MESSAGE)
        self._empty.setWordWrap(True)
        self._empty.setVisible(False)
        layout.addWidget(self._empty)

        self._rows_host = QWidget()
        self._rows_layout = QVBoxLayout(self._rows_host)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(8)
        layout.addWidget(self._rows_host)

        layout.addSpacing(10)

        self._add_card = QFrame()
        self._add_card.setObjectName("setting_row")
        add_layout = QVBoxLayout(self._add_card)
        add_layout.setContentsMargins(14, 12, 14, 12)
        add_layout.setSpacing(8)

        self._add_label = QLabel("Add a command")
        add_layout.addWidget(self._add_label)

        fields = QHBoxLayout()
        fields.setSpacing(8)
        self._trigger_field = QLineEdit()
        self._trigger_field.setPlaceholderText("When I say…")
        self._trigger_field.setFixedHeight(30)
        self._trigger_field.setFixedWidth(150)
        fields.addWidget(self._trigger_field)

        self._expansion_field = QLineEdit()
        self._expansion_field.setPlaceholderText("…type this")
        self._expansion_field.setFixedHeight(30)
        self._expansion_field.returnPressed.connect(self._add_from_fields)
        fields.addWidget(self._expansion_field, 1)

        self._add_button = QPushButton("Add")
        self._add_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_button.setFixedHeight(30)
        self._add_button.clicked.connect(self._add_from_fields)
        fields.addWidget(self._add_button)
        add_layout.addLayout(fields)

        self._add_status = QLabel("")
        self._add_status.setWordWrap(True)
        self._add_status.setVisible(False)
        add_layout.addWidget(self._add_status)

        layout.addWidget(self._add_card)
        layout.addStretch(1)
        self.refresh()

    # ------------------------------------------------------------------

    def commands(self) -> dict[str, str]:
        return dict(self.ctx.config.get("voice_commands", {}) or {})

    def empty_message(self) -> str:
        return EMPTY_MESSAGE

    # ------------------------------------------------------------------

    def add_command(self, trigger: str, expansion: str) -> bool:
        """Add or replace one command.

        The trigger is trimmed and lower-cased because the transcript comes
        back in whatever case the model chose, so a trigger stored as "BRB"
        would never match anything the user said. A blank trigger or a
        blank expansion is not a command - the second would delete what
        the user said rather than expanding it.
        """
        key = (trigger or "").strip().lower()
        value = (expansion or "").strip()
        if not key or not value:
            self._set_status("Both boxes need something in them.")
            return False
        self._set_status("")
        commands = self.commands()
        commands[key] = value
        self.ctx.apply("voice_commands", commands)
        self.refresh()
        return True

    def delete_command(self, trigger: str) -> None:
        commands = self.commands()
        if trigger not in commands:
            return
        del commands[trigger]
        self.ctx.apply("voice_commands", commands)
        self.refresh()

    def _add_from_fields(self) -> None:
        added = self.add_command(
            self._trigger_field.text(), self._expansion_field.text()
        )
        if added:
            self._trigger_field.clear()
            self._expansion_field.clear()

    def _set_status(self, text: str) -> None:
        self._add_status.setText(text)
        self._add_status.setVisible(bool(text))

    # ------------------------------------------------------------------

    def refresh(self) -> None:
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._rows = []

        commands = self.commands()
        palette = getattr(self, "_palette", None) or self.ctx.palette()
        for trigger in sorted(commands):
            row = _CommandRow(trigger, commands[trigger], self.delete_command)
            row.restyle(palette)
            self._rows.append(row)
            self._rows_layout.addWidget(row)

        self._empty.setVisible(not commands)

    def restyle(self, palette: dict) -> None:
        self._palette = dict(palette)
        p = self._palette
        repaint_with(self, pane_surface_qss(p))
        self._header.restyle(p)
        for label in (self._empty, self._add_status):
            label.setStyleSheet(
                "color: {muted}; font-size: 13px; background: transparent;".format(**p)
            )
        self._add_card.setStyleSheet(
            "QFrame#setting_row {{ background-color: {row};"
            " border: 1px solid {row_border}; border-radius: 9px; }}".format(**p)
        )
        self._add_label.setStyleSheet(
            "color: {text}; font-size: 14px; font-weight: 600;"
            " background: transparent;".format(**p)
        )
        field_qss = (
            "QLineEdit {{ color: {text}; background-color: {card_alt};"
            " border: 1px solid {row_border}; border-radius: 7px;"
            " padding: 4px 10px; font-size: 13px; }}"
            "QLineEdit:focus {{ border-color: {accent}; }}".format(**p)
        )
        self._trigger_field.setStyleSheet(field_qss)
        self._expansion_field.setStyleSheet(field_qss)
        self._add_button.setStyleSheet(
            "QPushButton {{ color: #ffffff; background-color: {accent};"
            " border: none; border-radius: 7px; font-size: 12px;"
            " font-weight: 600; padding: 4px 18px; }}"
            "QPushButton:hover {{ background-color: {accent_hover}; }}".format(**p)
        )
        for row in self._rows:
            row.restyle(p)
