"""Writing style: how much Voxel is allowed to change what you said.

Three everyday choices sit on the pane. Voxel has six built-in styles and
the user may have made more; the rest live behind "More styles" rather
than being deleted, and a user whose style is one of those keeps it.
"""
from __future__ import annotations

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from src import resource_use
from src.offline_transcriber import (
    UNAVAILABLE_NOTICE,
    is_available as offline_is_available,
)

from . import Pane, PaneContext
from .widgets import pane_surface_qss, repaint_with, ChoiceRow, LinkLabel, PaneHeader, SwitchRow, pane_body

#: The three on the pane itself, in this order.
HEADLINE_IDS = ("grammar_only", "grammar_tidy", "raw")

#: What offline mode actually does, rather than what it is called.
OFFLINE_DESCRIPTION = (
    "Turns your speech into text on this computer instead of sending it "
    "to Groq. Nothing leaves the machine. It is slower, it works your "
    "processor hard, and the first use downloads a model."
)

#: How often the usage figures are refreshed while offline mode is on.
USAGE_INTERVAL_MS = 1500

#: Plain-English copy. These replace "Dictation Mode" and "Raw mode".
_HEADLINES = {
    "grammar_only": (
        "Grammar only",
        "Fixes grammar and punctuation, keeps your own wording",
    ),
    "grammar_tidy": (
        "Tidy up",
        'Also drops "um", "uh" and false starts',
    ),
    "raw": (
        "Exactly what I said",
        "No changes at all, word for word",
    ),
}


class WritingStylePane(Pane):
    PANE_ID = "writing_style"
    TITLE = "Writing style"
    SUBTITLE = "How much Voxel tidies up what you say."
    OWNS = frozenset({"active_profile", "offline_mode"})

    HEADLINE_IDS = HEADLINE_IDS

    def __init__(self, ctx: PaneContext, parent=None) -> None:
        super().__init__(ctx, parent)
        self._rows: dict[str, ChoiceRow] = {}
        self._more_open = False

        _area, layout = pane_body(self)

        self._header = PaneHeader(self.TITLE, self.SUBTITLE)
        layout.addWidget(self._header)
        layout.addSpacing(6)

        for style_id in HEADLINE_IDS:
            title, subtitle = _HEADLINES[style_id]
            row = ChoiceRow(style_id, title, subtitle)
            row.clicked.connect(self.choose)
            self._rows[style_id] = row
            layout.addWidget(row)

        layout.addSpacing(4)
        self._more_link = LinkLabel("More styles")
        self._more_link.clicked.connect(self._toggle_more)
        layout.addWidget(self._more_link)

        self._more = QWidget()
        self._more_layout = QVBoxLayout(self._more)
        self._more_layout.setContentsMargins(0, 4, 0, 0)
        self._more_layout.setSpacing(10)
        self._more.setVisible(False)
        layout.addWidget(self._more)

        layout.addSpacing(10)
        self._offline = SwitchRow("Work offline", OFFLINE_DESCRIPTION)
        self._offline.toggled.connect(self._on_offline_toggled)
        layout.addWidget(self._offline)

        self._notice = QLabel("")
        self._notice.setObjectName("row_description")
        self._notice.setWordWrap(True)
        self._notice.setVisible(False)
        layout.addWidget(self._notice)

        self._usage = QLabel("")
        self._usage.setObjectName("row_description")
        self._usage.setWordWrap(True)
        self._usage.setVisible(False)
        layout.addWidget(self._usage)

        self._meter = resource_use.CpuMeter()
        self._usage_timer = QTimer(self)
        self._usage_timer.setInterval(USAGE_INTERVAL_MS)
        self._usage_timer.timeout.connect(self.poll_usage)

        layout.addStretch(1)
        self.refresh()

    # ------------------------------------------------------------------

    def headline_ids(self) -> tuple[str, ...]:
        return HEADLINE_IDS

    def headline_titles(self) -> dict[str, str]:
        return {k: v[0] for k, v in _HEADLINES.items()}

    def headline_subtitles(self) -> dict[str, str]:
        return {k: v[1] for k, v in _HEADLINES.items()}

    def more_style_ids(self) -> tuple[str, ...]:
        """Every style that is not one of the three headline rows."""
        return tuple(
            pid
            for pid in self.ctx.profiles.list_profiles()
            if pid not in HEADLINE_IDS
        )

    def more_styles_is_open(self) -> bool:
        return self._more_open

    def selected_id(self) -> str:
        return self.ctx.config.get(
            "active_profile", self.ctx.profiles.DEFAULT_PROFILE_ID
        )

    def offline_switch(self):
        return self._offline.switch()

    def offline_description(self) -> str:
        return OFFLINE_DESCRIPTION

    def offline_notice(self) -> str:
        return self._notice.text()

    def usage_text(self) -> str:
        return self._usage.text()

    def usage_is_shown(self) -> bool:
        return self._usage.isVisible()

    # ------------------------------------------------------------------

    def _on_offline_toggled(self, value: bool) -> None:
        self.ctx.apply("offline_mode", value)
        self._set_usage_shown(bool(value))

    def _set_usage_shown(self, shown: bool) -> None:
        """Only meter the machine while there is something to meter."""
        self._usage.setVisible(shown)
        if shown:
            self.poll_usage()
            if self.isVisible():
                self._usage_timer.start()
        else:
            self._usage_timer.stop()

    def poll_usage(self) -> None:
        """Refresh the usage line. A figure that cannot be read says so."""
        self._usage.setText(resource_use.summary(self._meter))

    def showEvent(self, event) -> None:  # noqa: N802 - Qt naming
        super().showEvent(event)
        if self._usage.isVisible():
            self.poll_usage()
            self._usage_timer.start()

    def hideEvent(self, event) -> None:  # noqa: N802 - Qt naming
        super().hideEvent(event)
        self._usage_timer.stop()

    # ------------------------------------------------------------------

    def choose(self, style_id: str) -> None:
        """Apply a style. An id no profile has is ignored, not written."""
        if style_id not in self.ctx.profiles.list_profiles():
            return
        self.ctx.apply("active_profile", style_id)
        self.refresh()

    def _toggle_more(self) -> None:
        self._set_more_open(not self._more_open)

    def _set_more_open(self, is_open: bool) -> None:
        self._more_open = bool(is_open)
        self._more.setVisible(self._more_open)
        self._more_link.setText("Fewer styles" if self._more_open else "More styles")

    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Re-read the active style. Never writes: a style this pane does
        not show is still the user's choice, and resetting it here is how
        a custom style would quietly disappear."""
        active = self.selected_id()

        self._rebuild_more_rows()
        for style_id, row in self._rows.items():
            row.set_selected(style_id == active)

        self._set_more_open(active not in HEADLINE_IDS)

        wanted = bool(self.ctx.config.get("offline_mode", False))
        available = offline_is_available()
        if not available and wanted:
            # Left on, every dictation fails with nothing on screen. Groq
            # still works, so fall back to it rather than leave the user
            # with a shortcut that does nothing.
            self.ctx.apply("offline_mode", False)
            wanted = False
        self._offline.set_checked_quietly(wanted and available)
        self._offline.switch().setEnabled(available)
        self._notice.setText("" if available else UNAVAILABLE_NOTICE)
        self._notice.setVisible(not available)
        self._set_usage_shown(wanted and available)

    def _rebuild_more_rows(self) -> None:
        for style_id in list(self._rows):
            if style_id in HEADLINE_IDS:
                continue
            row = self._rows.pop(style_id)
            self._more_layout.removeWidget(row)
            # Detach before deleting: removeWidget takes it out of the
            # layout but leaves it a child, so it survives until the event
            # loop runs - still painted, still carrying the old theme.
            row.setParent(None)
            row.deleteLater()

        while self._more_layout.count():
            item = self._more_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        profiles = self.ctx.profiles.list_profiles()
        hidden = [pid for pid in profiles if pid not in HEADLINE_IDS]
        if not hidden:
            empty = QLabel("No other styles yet.")
            empty.setObjectName("row_description")
            self._more_layout.addWidget(empty)
            return

        for style_id in hidden:
            name = profiles[style_id].get("name", style_id)
            row = ChoiceRow(style_id, name, "")
            row.clicked.connect(self.choose)
            row.restyle(self._current_palette())
            self._rows[style_id] = row
            self._more_layout.addWidget(row)

    def _current_palette(self) -> dict:
        return getattr(self, "_palette", None) or self.ctx.palette()

    # ------------------------------------------------------------------

    def restyle(self, palette: dict) -> None:
        self._palette = dict(palette)
        repaint_with(self, pane_surface_qss(self._palette))
        self._header.restyle(self._palette)
        self._more_link.restyle(self._palette)
        self._offline.restyle(self._palette)
        for label in (self._notice, self._usage):
            label.setStyleSheet(
                "color: {muted}; font-size: 12px; background: transparent;".format(
                    **self._palette
                )
            )
        for row in self._rows.values():
            row.restyle(self._palette)
