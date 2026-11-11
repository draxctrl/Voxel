"""The settings window: a sidebar on the left, one pane at a time on the right.

This window replaces the old single scrolling settings page, and absorbs
what used to be the separate History and Statistics windows. It has no Save
button: each control applies as it is touched, through `ctx.apply`.
"""
from __future__ import annotations

import logging

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QGuiApplication, QIcon
from PyQt6.QtWidgets import QHBoxLayout, QStackedWidget, QWidget

from .keys import pretty_hotkey
from .nav_rail import LOGO_SIZE, NavRail, _logo_path
from .panes import Pane, PaneContext, all_panes
from .panes.widgets import repaint_with
from .theme import current_palette

logger = logging.getLogger(__name__)

DEFAULT_SIZE = (980, 620)
MINIMUM_SIZE = (860, 560)


class SettingsWindow(QWidget):
    """The shell. Owns the rail, the pane stack and the restyling."""

    def __init__(self, ctx: PaneContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self.setObjectName("settings_window")
        self.setWindowTitle("Voxel")
        self._set_window_icon()
        self.resize(*DEFAULT_SIZE)
        self.setMinimumSize(*MINIMUM_SIZE)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._rail = NavRail()
        self._rail.selected.connect(self.show_pane)
        layout.addWidget(self._rail)

        self._stack = QStackedWidget()
        self._stack.setObjectName("pane_stack")
        layout.addWidget(self._stack, 1)

        # Eager construction: ten small widgets, and lazy building would
        # mean restyle() could not reach a pane the user had not opened.
        self._panes: dict[str, Pane] = {}
        for pane_class in all_panes():
            pane = pane_class(ctx)
            self._panes[pane.PANE_ID] = pane
            self._stack.addWidget(pane)

        self._state = "idle"
        self.restyle(current_palette())

        hints = QGuiApplication.styleHints()
        if hasattr(hints, "colorSchemeChanged"):
            hints.colorSchemeChanged.connect(self._on_system_theme_changed)

        first = self._rail.current
        if first in self._panes:
            self.show_pane(first)

    def _set_window_icon(self) -> None:
        """Put the same mark in the title bar as in the rail.

        The icon set draws a deliberately different, flattened mark at
        16px for the tray. Letting Windows pick that frame for the title
        bar puts two different-looking logos on one window, so the icon is
        built from the one rendition the rail uses.
        """
        path = _logo_path()
        if not path:
            return
        pixmap = QIcon(path).pixmap(QSize(LOGO_SIZE, LOGO_SIZE))
        if pixmap.isNull():
            return
        icon = QIcon()
        icon.addPixmap(pixmap)
        self.setWindowIcon(icon)

    # ------------------------------------------------------------------
    # panes

    def panes(self) -> list[Pane]:
        return list(self._panes.values())

    def pane(self, pane_id: str) -> Pane:
        return self._panes[pane_id]

    def current_pane(self) -> Pane:
        return self._stack.currentWidget()

    def show_pane(self, pane_id: str) -> None:
        """Raise a pane, refreshing it first. An unknown id is ignored."""
        pane = self._panes.get(pane_id)
        if pane is None:
            logger.warning("No settings pane called '%s'", pane_id)
            return
        pane.refresh()
        self._stack.setCurrentWidget(pane)
        if self._rail.current != pane_id:
            self._rail.select(pane_id)

    # ------------------------------------------------------------------
    # status

    def set_status(self, state: str) -> None:
        """Mirror the app's state in the rail footer."""
        self._state = state
        shortcut = pretty_hotkey(self.ctx.config.get("hotkey", ""))
        self._rail.set_status(state, shortcut)

    # ------------------------------------------------------------------
    # theme

    def _on_system_theme_changed(self, *_args) -> None:
        """Windows switched light/dark.

        A theme the user pinned under Appearance wins: following the
        system here regardless would undo their choice at sunset.
        """
        from .theme import apply_theme

        choice = self.ctx.config.get("theme", "system")
        name = None if choice in (None, "", "system") else choice
        app = QGuiApplication.instance()
        if app is not None:
            apply_theme(app, name)
        self.restyle(current_palette())

    def restyle(self, palette: dict) -> None:
        """Repaint the whole window. A half-restyled window is the bug
        this project exists to kill, so the rail and every pane - not only
        the visible one - are done together."""
        self._palette = dict(palette)
        repaint_with(
            self,
            "QWidget#settings_window, QStackedWidget#pane_stack {{"
            " background-color: {pane}; }}".format(**self._palette),
        )
        self._rail.restyle(self._palette)
        for pane in self._panes.values():
            pane.restyle(self._palette)
        self.set_status(self._state)

    # ------------------------------------------------------------------

    def show(self) -> None:  # noqa: D102 - Qt naming
        super().show()
        self.raise_()
        self.activateWindow()
        self.setWindowState(
            self.windowState() & ~Qt.WindowState.WindowMinimized
            | Qt.WindowState.WindowActive
        )
