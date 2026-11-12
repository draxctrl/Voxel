"""Appearance: light or dark, and which badge shows while you talk."""
from __future__ import annotations

from PyQt6.QtWidgets import QLabel

from ..recording_styles import DEFAULT_STYLE, RECORDING_STYLES
from . import Pane, PaneContext
from .widgets import pane_surface_qss, repaint_with, ChoiceRow, PaneHeader, pane_body

THEME_IDS = ("system", "light", "dark")

_THEMES = {
    "system": ("Follow Windows", "Changes with your Windows light/dark setting"),
    "light": ("Light", "Always light, whatever Windows is set to"),
    "dark": ("Dark", "Always dark, whatever Windows is set to"),
}

_STYLE_SUBTITLES = {
    "orb": "A small glowing dot near the bottom of the screen",
    "waveform": "A bar that moves with your voice",
    "island": "A pill at the top of the screen, like a phone",
}


class AppearancePane(Pane):
    PANE_ID = "appearance"
    TITLE = "Appearance"
    SUBTITLE = "How Voxel looks, and what it shows while you talk."
    OWNS = frozenset({"theme", "recording_style"})

    THEME_IDS = THEME_IDS

    def __init__(self, ctx: PaneContext, parent=None) -> None:
        super().__init__(ctx, parent)
        self._theme_rows: dict[str, ChoiceRow] = {}
        self._style_rows: dict[str, ChoiceRow] = {}

        _area, layout = pane_body(self)

        self._header = PaneHeader(self.TITLE, self.SUBTITLE, self)
        layout.addWidget(self._header)
        layout.addSpacing(6)

        self._theme_heading = QLabel("Theme")
        self._theme_heading.setObjectName("section_heading")
        layout.addWidget(self._theme_heading)

        for theme_id in THEME_IDS:
            title, subtitle = _THEMES[theme_id]
            row = ChoiceRow(theme_id, title, subtitle, self)
            row.clicked.connect(self.choose_theme)
            self._theme_rows[theme_id] = row
            layout.addWidget(row)

        layout.addSpacing(12)
        self._style_heading = QLabel("While you are talking")
        self._style_heading.setObjectName("section_heading")
        layout.addWidget(self._style_heading)

        for style_id, name in RECORDING_STYLES.items():
            row = ChoiceRow(style_id, name, _STYLE_SUBTITLES.get(style_id, ""), self)
            row.clicked.connect(self.choose_style)
            self._style_rows[style_id] = row
            layout.addWidget(row)

        layout.addStretch(1)
        self.refresh()

    # ------------------------------------------------------------------

    def theme_ids(self) -> tuple[str, ...]:
        return THEME_IDS

    def theme_titles(self) -> dict[str, str]:
        return {k: v[0] for k, v in _THEMES.items()}

    def style_ids(self) -> tuple[str, ...]:
        return tuple(RECORDING_STYLES)

    def selected_theme(self) -> str:
        choice = self.ctx.config.get("theme", "system")
        return choice if choice in THEME_IDS else "system"

    def selected_style(self) -> str:
        choice = self.ctx.config.get("recording_style", DEFAULT_STYLE)
        return choice if choice in RECORDING_STYLES else DEFAULT_STYLE

    # ------------------------------------------------------------------

    def choose_theme(self, theme_id: str) -> None:
        if theme_id not in THEME_IDS:
            return
        self.ctx.apply("theme", theme_id)
        self.refresh()

    def choose_style(self, style_id: str) -> None:
        if style_id not in RECORDING_STYLES:
            return
        self.ctx.apply("recording_style", style_id)
        self.refresh()

    # ------------------------------------------------------------------

    def refresh(self) -> None:
        theme = self.selected_theme()
        for theme_id, row in self._theme_rows.items():
            row.set_selected(theme_id == theme)
        style = self.selected_style()
        for style_id, row in self._style_rows.items():
            row.set_selected(style_id == style)

    def restyle(self, palette: dict) -> None:
        self._palette = dict(palette)
        repaint_with(self, pane_surface_qss(self._palette))
        self._header.restyle(self._palette)
        heading_qss = (
            "color: {faint}; font-size: 11px; font-weight: 700;"
            " letter-spacing: 0.8px; background: transparent;".format(**self._palette)
        )
        self._theme_heading.setStyleSheet(heading_qss)
        self._style_heading.setStyleSheet(heading_qss)
        for row in list(self._theme_rows.values()) + list(self._style_rows.values()):
            row.restyle(self._palette)
