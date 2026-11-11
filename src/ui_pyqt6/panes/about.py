"""About: what this is, who made it, and where to go next."""
from __future__ import annotations

from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout

from src.version import APP_VERSION

from . import Pane, PaneContext
from .widgets import pane_surface_qss, repaint_with, PaneHeader, link_markup, pane_body

LINKS = {
    "Project page on GitHub": "https://github.com/draxctrl/Voxel",
    "Report a problem": "https://github.com/draxctrl/Voxel/issues",
    # The link the old settings window already used.
    "Support this project": "https://paypal.me/draxctrl",
}

LICENCE = "MIT License - free to use, change and share."


class AboutPane(Pane):
    PANE_ID = "about"
    TITLE = "About Voxel"
    SUBTITLE = "Speak anywhere in Windows, and your words are typed for you."
    OWNS = frozenset()

    def __init__(self, ctx: PaneContext, parent=None) -> None:
        super().__init__(ctx, parent)

        _area, layout = pane_body(self)

        self._header = PaneHeader(self.TITLE, self.SUBTITLE)
        layout.addWidget(self._header)
        layout.addSpacing(6)

        self._card = QFrame()
        self._card.setObjectName("setting_row")
        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(6)

        self._version = QLabel("Version %s" % APP_VERSION)
        card_layout.addWidget(self._version)

        self._licence = QLabel(LICENCE)
        self._licence.setWordWrap(True)
        card_layout.addWidget(self._licence)

        self._links: list[QLabel] = []
        for text, url in LINKS.items():
            label = QLabel(link_markup(text, url, "#6366f1"))
            label.setProperty("link_text", text)
            label.setProperty("link_url", url)
            label.setOpenExternalLinks(True)
            card_layout.addWidget(label)
            self._links.append(label)

        layout.addWidget(self._card)
        layout.addStretch(1)

    # ------------------------------------------------------------------

    def version_text(self) -> str:
        return self._version.text()

    def licence_text(self) -> str:
        return self._licence.text()

    def links(self) -> dict[str, str]:
        return dict(LINKS)

    def restyle(self, palette: dict) -> None:
        self._palette = dict(palette)
        p = self._palette
        repaint_with(self, pane_surface_qss(p))
        self._header.restyle(p)
        self._card.setStyleSheet(
            "QFrame#setting_row {{ background-color: {row};"
            " border: 1px solid {row_border}; border-radius: 9px; }}".format(**p)
        )
        self._version.setStyleSheet(
            "color: {text}; font-size: 14px; font-weight: 600;"
            " background: transparent;".format(**p)
        )
        self._licence.setStyleSheet(
            "color: {muted}; font-size: 12px; background: transparent;".format(**p)
        )
        for label in self._links:
            label.setText(
                link_markup(
                    label.property("link_text"),
                    label.property("link_url"),
                    p["accent"],
                )
            )
            label.setStyleSheet(
                "font-size: 13px; background: transparent;"
            )
