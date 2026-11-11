"""Language: what Voxel should expect to hear."""
from __future__ import annotations

import logging
import os
import sys

from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QHBoxLayout, QLabel

from ..flags import flag_icon
from . import Pane, PaneContext
from .widgets import ChoiceRow, PaneHeader, pane_body

logger = logging.getLogger(__name__)

LANGUAGES: tuple[tuple[str, str], ...] = (
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
)

_CODES = {code for code, _ in LANGUAGES}


def _flags_dir() -> str | None:
    """Where the flag images live, frozen build first."""
    meipass = getattr(sys, "_MEIPASS", None)
    candidates = []
    if meipass:
        candidates.append(os.path.join(meipass, "src", "assets"))
        candidates.append(os.path.join(meipass, "assets"))
    # This file is src/ui_pyqt6/panes/language.py; the assets are two
    # levels up, at src/assets.
    here = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.normpath(os.path.join(here, "..", "..", "assets")))
    for candidate in candidates:
        if os.path.isdir(candidate):
            return candidate
    return None


class LanguagePane(Pane):
    PANE_ID = "language"
    TITLE = "Language"
    SUBTITLE = "The language you speak. Auto-detect works, but naming it is more accurate."
    OWNS = frozenset({"language"})

    def __init__(self, ctx: PaneContext, parent=None) -> None:
        super().__init__(ctx, parent)
        self._rows: dict[str, ChoiceRow] = {}
        self._flags: set[str] = set()

        _area, layout = pane_body(self)

        self._header = PaneHeader(self.TITLE, self.SUBTITLE)
        layout.addWidget(self._header)
        layout.addSpacing(6)

        assets = _flags_dir()
        for code, name in LANGUAGES:
            row = ChoiceRow(code, name, "")
            self._add_flag(row, code, assets)
            row.clicked.connect(self.choose)
            self._rows[code] = row
            layout.addWidget(row)

        layout.addStretch(1)
        self.refresh()

    def has_flag(self, code: str) -> bool:
        """Whether this language's row got its picture."""
        return code in self._flags

    def _add_flag(self, row: ChoiceRow, code: str, assets: str | None) -> None:
        """A flag picture beside the name. Windows draws flag emoji as
        letter pairs, so these are images; a language with no flag simply
        has none."""
        if not assets:
            return
        try:
            icon = flag_icon(code, assets)
        except Exception as e:
            logger.debug("No flag for %s: %s", code, e)
            return
        if icon is None:
            return
        label = QLabel()
        label.setPixmap(icon.pixmap(QSize(20, 15)))
        label.setFixedWidth(24)
        layout = row.layout()
        if isinstance(layout, QHBoxLayout):
            layout.insertWidget(1, label)
            self._flags.add(code)

    # ------------------------------------------------------------------

    def selected_language(self) -> str:
        return self.ctx.config.get("language", "en")

    def choose(self, code: str) -> None:
        if code not in _CODES:
            return
        self.ctx.apply("language", code)
        self.refresh()

    def refresh(self) -> None:
        current = self.selected_language()
        for code, row in self._rows.items():
            row.set_selected(code == current)

    def restyle(self, palette: dict) -> None:
        self._palette = dict(palette)
        self.setStyleSheet(
            "QWidget#pane_inner, QScrollArea#pane_scroll {{"
            " background-color: {pane}; }}".format(**self._palette)
        )
        self._header.restyle(self._palette)
        for row in self._rows.values():
            row.restyle(self._palette)
