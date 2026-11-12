"""Stats: three numbers, large enough to read from across the desk.

The old window had a seven-card grid, one of whose cards advertised
"streaks" that were never implemented. Three figures that are all true
beat seven that are mostly filler.
"""
from __future__ import annotations

import logging

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from ..icons import icon as load_icon
from . import Pane, PaneContext
from .widgets import pane_surface_qss, repaint_with, PaneHeader, pane_body

logger = logging.getLogger(__name__)

#: Typing speed the time saved is measured against. Stated on the pane,
#: because a number nobody can check is a number nobody believes.
TYPING_WPM = 40


def format_time_saved(words: int) -> str:
    """Words at `TYPING_WPM` as a span of time a person would say."""
    minutes = int(max(0, words) // TYPING_WPM)
    hours, remainder = divmod(minutes, 60)
    if hours and remainder:
        return "%dh %dm" % (hours, remainder)
    if hours:
        return "%dh" % hours
    return "%dm" % remainder


class _Figure(QFrame):
    """One big number, under its own mark and over its caption."""

    #: How big the mark is drawn. Large enough to read as a symbol, small
    #: enough that the number stays the thing you see first.
    MARK_PX = 20

    def __init__(self, caption: str, icon_name: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("setting_row")
        self._icon_name = icon_name
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(2)
        self.mark = QLabel()
        self.mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mark.setFixedHeight(self.MARK_PX + 6)
        layout.addWidget(self.mark)
        self.value = QLabel("0")
        self.value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.value)
        self.caption = QLabel(caption)
        self.caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.caption.setWordWrap(True)
        layout.addWidget(self.caption)

    def restyle(self, p: dict) -> None:
        self.setStyleSheet(
            "QFrame#setting_row {{ background-color: {row};"
            " border: 1px solid {row_border}; border-radius: 11px; }}".format(**p)
        )
        # The mark is tinted every restyle: a pixmap drawn for the dark
        # palette keeps its colour when the theme flips.
        self.mark.setPixmap(
            load_icon(self._icon_name, p["accent"], self.MARK_PX).pixmap(
                QSize(self.MARK_PX, self.MARK_PX)
            )
        )
        self.mark.setStyleSheet("background: transparent;")
        self.value.setStyleSheet(
            "color: {text}; font-size: 30px; font-weight: 700;"
            " background: transparent;".format(**p)
        )
        self.caption.setStyleSheet(
            "color: {muted}; font-size: 12px; background: transparent;".format(**p)
        )


class StatsPane(Pane):
    PANE_ID = "stats"
    TITLE = "Stats"
    SUBTITLE = "How much you have said, and what it would have cost to type."
    OWNS = frozenset()

    #: figure key -> caption
    FIGURES = {
        "words": "Words dictated",
        "time_saved": "Time saved",
        "this_week": "Dictations this week",
    }

    #: figure key -> the Phosphor icon that marks it.
    ICONS = {
        "words": "chat-text",
        "time_saved": "clock-counter-clockwise",
        "this_week": "chart-bar",
    }

    def __init__(self, ctx: PaneContext, parent=None) -> None:
        super().__init__(ctx, parent)
        self._figures: dict[str, _Figure] = {}

        _area, layout = pane_body(self)

        self._header = PaneHeader(self.TITLE, self.SUBTITLE, self)
        layout.addWidget(self._header)
        layout.addSpacing(10)

        row = QHBoxLayout()
        row.setSpacing(10)
        for key, caption in self.FIGURES.items():
            figure = _Figure(caption, self.ICONS[key], self)
            self._figures[key] = figure
            row.addWidget(figure, 1)
        layout.addLayout(row)

        self._footnote = QLabel(
            "Time saved compares speaking with typing at %d words a minute."
            % TYPING_WPM
        )
        self._footnote.setWordWrap(True)
        layout.addWidget(self._footnote)

        layout.addStretch(1)
        self.refresh()

    # ------------------------------------------------------------------

    def figures(self) -> dict[str, str]:
        return {key: figure.value.text() for key, figure in self._figures.items()}

    def all_text(self) -> list[str]:
        """Every string on the pane, for tests that check what it claims."""
        texts = [self._header._title.text(), self._header._subtitle.text()]
        texts.append(self._footnote.text())
        for figure in self._figures.values():
            texts.extend([figure.value.text(), figure.caption.text()])
        return texts

    # ------------------------------------------------------------------

    def refresh(self) -> None:
        words = self._safe(self.ctx.history.total_words)
        this_week = self._safe(self.ctx.history.week_count)
        self._figures["words"].value.setText("{:,}".format(words))
        self._figures["time_saved"].value.setText(format_time_saved(words))
        self._figures["this_week"].value.setText("{:,}".format(this_week))

    @staticmethod
    def _safe(read) -> int:
        """A statistic that cannot be read is zero, never a broken pane."""
        try:
            return int(read())
        except Exception as e:
            logger.warning("Could not read a statistic: %s", e)
            return 0

    def restyle(self, palette: dict) -> None:
        self._palette = dict(palette)
        p = self._palette
        repaint_with(self, pane_surface_qss(p))
        self._header.restyle(p)
        self._footnote.setStyleSheet(
            "color: {faint}; font-size: 12px; background: transparent;".format(**p)
        )
        for figure in self._figures.values():
            figure.restyle(p)
