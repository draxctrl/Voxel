"""General: the API key, and the switches that do not belong anywhere else."""
from __future__ import annotations

import logging

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from . import Pane, PaneContext
from .widgets import PaneHeader, SwitchRow, link_markup, pane_body

logger = logging.getLogger(__name__)

GROQ_CONSOLE_URL = "https://console.groq.com/keys"

#: key -> (label, line underneath)
_SWITCHES = {
    "auto_start": ("Start with Windows", "Voxel runs quietly in the background"),
    "always_copy": (
        "Always copy to the clipboard",
        "Keeps a copy of everything Voxel types",
    ),
    "clipboard_notice": (
        "Tell me when text is copied, not typed",
        "Some apps refuse typed text; Voxel copies it instead",
    ),
    "mute_sound": ("Mute sounds", "No chime when a dictation finishes"),
    "auto_profile": (
        "Match the writing style to the app",
        "Use a different style in your email app than in your editor",
    ),
}


class GeneralPane(Pane):
    PANE_ID = "general"
    TITLE = "General"
    SUBTITLE = "Your key, and how Voxel behaves day to day."
    OWNS = frozenset({"api_key"}) | frozenset(_SWITCHES)

    def __init__(self, ctx: PaneContext, parent=None) -> None:
        super().__init__(ctx, parent)
        self._rows: dict[str, SwitchRow] = {}
        self._key_visible = False

        _area, layout = pane_body(self)

        self._header = PaneHeader(self.TITLE, self.SUBTITLE)
        layout.addWidget(self._header)
        layout.addSpacing(6)

        self._key_card = QFrame()
        self._key_card.setObjectName("setting_row")
        key_layout = QVBoxLayout(self._key_card)
        key_layout.setContentsMargins(14, 12, 14, 12)
        key_layout.setSpacing(8)

        self._key_label = QLabel("Groq API key")
        key_layout.addWidget(self._key_label)

        self._key_help = QLabel(
            "Voxel needs a free key from Groq to turn speech into text."
        )
        self._key_help.setWordWrap(True)
        key_layout.addWidget(self._key_help)

        field_row = QHBoxLayout()
        field_row.setSpacing(8)
        self._key_field = QLineEdit()
        self._key_field.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_field.setPlaceholderText("gsk_…")
        self._key_field.setFixedHeight(30)
        self._key_field.returnPressed.connect(self.save_key)
        field_row.addWidget(self._key_field, 1)

        self._reveal_button = QPushButton("Show")
        self._reveal_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reveal_button.setFixedHeight(30)
        self._reveal_button.clicked.connect(self.toggle_key_visible)
        field_row.addWidget(self._reveal_button)

        self._save_button = QPushButton("Save")
        self._save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_button.setFixedHeight(30)
        self._save_button.clicked.connect(self.save_key)
        field_row.addWidget(self._save_button)
        key_layout.addLayout(field_row)

        self._key_status = QLabel("")
        self._key_status.setWordWrap(True)
        self._key_status.setVisible(False)
        key_layout.addWidget(self._key_status)

        self._get_key_link = QLabel(
            link_markup("Get a free key from Groq", GROQ_CONSOLE_URL, "#6366f1")
        )
        self._get_key_link.setOpenExternalLinks(True)
        key_layout.addWidget(self._get_key_link)

        layout.addWidget(self._key_card)
        layout.addSpacing(10)

        for key, (label, description) in _SWITCHES.items():
            row = SwitchRow(label, description)
            row.toggled.connect(lambda value, k=key: self.ctx.apply(k, value))
            self._rows[key] = row
            layout.addWidget(row)

        layout.addStretch(1)
        self.refresh()

    # ------------------------------------------------------------------

    def key_field(self) -> QLineEdit:
        return self._key_field

    def switch(self, key: str):
        return self._rows[key].switch()

    def toggle_key_visible(self) -> None:
        self._key_visible = not self._key_visible
        self._key_field.setEchoMode(
            QLineEdit.EchoMode.Normal if self._key_visible else QLineEdit.EchoMode.Password
        )
        self._reveal_button.setText("Hide" if self._key_visible else "Show")

    def save_key(self) -> None:
        """Apply a pasted key.

        An empty field means "I did not type anything", never "delete my
        key" - a user who clears the box by accident would otherwise lose
        the only thing making Voxel work.
        """
        key = self._key_field.text().strip()
        if not key:
            self._set_status("Paste your key into the box first.")
            return
        self._set_status("")
        self.ctx.apply("api_key", key)

    def _set_status(self, text: str) -> None:
        self._key_status.setText(text)
        self._key_status.setVisible(bool(text))

    # ------------------------------------------------------------------

    def refresh(self) -> None:
        self._key_field.setText(self.ctx.config.get("api_key", "") or "")
        for key, row in self._rows.items():
            row.set_checked_quietly(
                self.ctx.config.get(key, _default_for(key))
            )

    def restyle(self, palette: dict) -> None:
        self._palette = dict(palette)
        p = self._palette
        self.setStyleSheet(
            "QWidget#pane_inner, QScrollArea#pane_scroll {{"
            " background-color: {pane}; }}".format(**p)
        )
        self._header.restyle(p)
        self._key_card.setStyleSheet(
            "QFrame#setting_row {{ background-color: {row};"
            " border: 1px solid {row_border}; border-radius: 9px; }}".format(**p)
        )
        self._key_label.setStyleSheet(
            "color: {text}; font-size: 13.5px; font-weight: 600;"
            " background: transparent;".format(**p)
        )
        for label in (self._key_help, self._key_status):
            label.setStyleSheet(
                "color: {muted}; font-size: 12px; background: transparent;".format(**p)
            )
        self._get_key_link.setText(
            link_markup("Get a free key from Groq", GROQ_CONSOLE_URL, p["accent"])
        )
        self._get_key_link.setStyleSheet(
            "font-size: 12.5px; background: transparent;"
        )
        self._key_field.setStyleSheet(
            "QLineEdit {{ color: {text}; background-color: {card_alt};"
            " border: 1px solid {row_border}; border-radius: 7px;"
            " padding: 4px 10px; font-size: 12.5px; }}"
            "QLineEdit:focus {{ border-color: {accent}; }}".format(**p)
        )
        button_qss = (
            "QPushButton {{ color: {text}; background-color: {card_alt};"
            " border: 1px solid {row_border}; border-radius: 7px;"
            " font-size: 12px; padding: 4px 14px; }}"
            "QPushButton:hover {{ border-color: {accent}; }}".format(**p)
        )
        self._reveal_button.setStyleSheet(button_qss)
        self._save_button.setStyleSheet(
            "QPushButton {{ color: #ffffff; background-color: {accent};"
            " border: none; border-radius: 7px; font-size: 12px;"
            " font-weight: 600; padding: 4px 16px; }}"
            "QPushButton:hover {{ background-color: {accent_hover}; }}".format(**p)
        )
        for row in self._rows.values():
            row.restyle(p)


def _default_for(key: str):
    from src.config import DEFAULT_CONFIG

    return DEFAULT_CONFIG.get(key, False)
