"""The settings sidebar: a brand mark, grouped entries, and a status footer.

Fixed width, one topic per entry, and a footer that answers "is this thing
on?" without a click - the dot and the word mirror the four states main.py
already tracks for the tray.
"""
from __future__ import annotations

import os
import sys

from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPainter
from PyQt6.QtWidgets import (
    QFrame,
    QSizePolicy,
    QSpacerItem,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .icons import icon
from .panes.widgets import repaint_with
from .theme import current_palette

RAIL_WIDTH = 198

#: How tall the app mark is beside the name.
LOGO_SIZE = 24

#: Breathing room between two entries in the same group.
ENTRY_GAP = 3


def _logo_path() -> str | None:
    """The app icon, or None when it is not bundled.

    The .ico rather than the .png: the icon set is drawn per size - a soft
    glow turns to mush when it is scaled down - and the .ico carries the
    32px and 48px artwork made for exactly this job. icon.png is 512px and
    squashing it here is what made the mark look muddy.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    candidates = []
    if meipass:
        candidates.append(os.path.join(meipass, "src", "assets", "icon.ico"))
        candidates.append(os.path.join(meipass, "assets", "icon.ico"))
    here = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.normpath(os.path.join(here, "assets", "icon.ico")))
    candidates.append(os.path.normpath(os.path.join(here, "..", "assets", "icon.ico")))
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return None

#: state -> (word, colour). "accent" is resolved from the live palette.
_STATES: dict[str, tuple[str, str]] = {
    "idle": ("Ready", "#43b581"),
    "recording": ("Listening", "#ff453a"),
    "processing": ("Working", "accent"),
    "error": ("Problem", "#ef4444"),
}


class _StatusDot(QWidget):
    """A 7px filled circle.

    Painted rather than styled: a stylesheet border-radius leaves square
    corners at this size.
    """

    SIZE = 7

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._colour = QColor("#43b581")
        self.setFixedSize(QSize(self.SIZE, self.SIZE))

    def set_colour(self, colour: str) -> None:
        self._colour = QColor(colour)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt naming
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._colour)
        painter.drawEllipse(0, 0, self.SIZE, self.SIZE)
        painter.end()


def _soft_gap(layout, height: int) -> None:
    """A decorative gap that gives way before the content does.

    A rigid spacer makes ten entries, four group headings and the gaps
    between them taller than the window's own minimum height, which pushes
    the status footer off the bottom. These gaps shrink instead.
    """
    layout.addItem(
        QSpacerItem(0, height, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Maximum)
    )


class NavRail(QWidget):
    """The left rail. Emits `selected` with a pane id when clicked."""

    #: group title -> ((pane id, label, icon name), ...)
    ENTRIES: tuple[tuple[str, tuple[tuple[str, str, str], ...]], ...] = (
        (
            "Dictation",
            (
                ("writing_style", "Writing style", "pencil-simple"),
                ("voice_commands", "Voice commands", "chat-text"),
                ("language", "Language", "globe-simple"),
            ),
        ),
        (
            "Your setup",
            (
                ("microphone", "Microphone", "microphone"),
                ("shortcuts", "Shortcuts", "keyboard"),
                ("appearance", "Appearance", "waveform"),
            ),
        ),
        (
            "Your words",
            (
                ("history", "History", "clock-counter-clockwise"),
                ("stats", "Stats", "chart-bar"),
            ),
        ),
        (
            "App",
            (
                ("general", "General", "sliders-horizontal"),
                ("about", "About", "info"),
            ),
        ),
    )

    selected = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("nav_rail")
        self.setFixedWidth(RAIL_WIDTH)

        self._buttons: dict[str, QPushButton] = {}
        self._current = self.ENTRIES[0][1][0][0]
        self._state = "idle"
        self._shortcut = ""
        self._palette = dict(current_palette())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 16, 10, 12)
        layout.setSpacing(0)

        # The app mark beside the name. A missing file costs the picture,
        # never the window.
        brand_row = QHBoxLayout()
        brand_row.setContentsMargins(6, 0, 0, 0)
        brand_row.setSpacing(8)
        self._logo = QLabel(self)
        self._logo.setFixedSize(QSize(LOGO_SIZE, LOGO_SIZE))
        self._logo.setVisible(False)
        self._has_logo = False
        path = _logo_path()
        if path:
            # QIcon picks the nearest size the .ico actually contains and
            # scales from that, rather than from the largest one.
            pixmap = QIcon(path).pixmap(QSize(LOGO_SIZE, LOGO_SIZE))
            if not pixmap.isNull():
                self._logo.setPixmap(pixmap)
                self._logo.setVisible(True)
                self._has_logo = True
        brand_row.addWidget(self._logo, 0, Qt.AlignmentFlag.AlignVCenter)

        self._brand = QLabel("Voxel", self)
        self._brand.setObjectName("rail_brand")
        brand_row.addWidget(self._brand, 1, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(brand_row)
        _soft_gap(layout, 16)

        for title, rows in self.ENTRIES:
            group = QLabel(title.upper(), self)
            group.setObjectName("rail_group")
            layout.addWidget(group)
            _soft_gap(layout, 2)
            for index, (pane_id, label, icon_name) in enumerate(rows):
                if index:
                    _soft_gap(layout, ENTRY_GAP)
                button = self._make_entry(pane_id, label, icon_name)
                self._buttons[pane_id] = button
                layout.addWidget(button)
            _soft_gap(layout, 12)

        layout.addStretch(1)

        self._divider = QFrame(self)
        self._divider.setObjectName("rail_divider")
        self._divider.setFixedHeight(1)
        layout.addWidget(self._divider)
        _soft_gap(layout, 10)

        footer = QHBoxLayout()
        footer.setContentsMargins(6, 0, 0, 0)
        footer.setSpacing(8)
        self._dot = _StatusDot(self)
        footer.addWidget(self._dot, 0, Qt.AlignmentFlag.AlignVCenter)
        self._status = QLabel(self)
        self._status.setObjectName("rail_status")
        # "Ctrl + Shift + Space" is wider than the rail; wrapping it beats
        # running it off the edge, and the rail has the vertical room.
        self._status.setWordWrap(True)
        footer.addWidget(self._status, 1)
        layout.addLayout(footer)

        self.restyle(self._palette)

    # ------------------------------------------------------------------
    # entries

    def _make_entry(self, pane_id: str, label: str, icon_name: str) -> QPushButton:
        button = QPushButton("  " + label, self)
        button.setObjectName("rail_entry")
        button.setProperty("pane_id", pane_id)
        button.setProperty("icon_name", icon_name)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFixedHeight(30)
        button.setIconSize(QSize(18, 18))
        button.setCheckable(True)
        button.setAutoExclusive(False)
        button.clicked.connect(lambda _checked, pid=pane_id: self._on_clicked(pid))
        return button

    def logo_is_shown(self) -> bool:
        """Whether the app mark loaded.

        Not `isVisible()`: a child of a window that has not been shown yet
        reports False, which would say "no logo" for a rail that has one.
        """
        return self._has_logo

    def entry_button(self, pane_id: str) -> QPushButton:
        """The clickable row for a pane id."""
        return self._buttons[pane_id]

    def _on_clicked(self, pane_id: str) -> None:
        self.select(pane_id)
        self.selected.emit(pane_id)

    @property
    def current(self) -> str:
        return self._current

    def select(self, pane_id: str) -> None:
        """Move the highlight. Emits nothing - the caller decided."""
        if pane_id not in self._buttons:
            self._apply_selection()
            return
        self._current = pane_id
        self._apply_selection()

    def _apply_selection(self) -> None:
        for pane_id, button in self._buttons.items():
            active = pane_id == self._current
            button.setChecked(active)
            colour = (
                self._palette["rail_text_active"]
                if active
                else self._palette["rail_text"]
            )
            button.setIcon(icon(button.property("icon_name"), colour, 18))

    # ------------------------------------------------------------------
    # status footer

    def set_status(self, state: str, shortcut: str) -> None:
        """Mirror one of main.py's four states, beside the user's shortcut."""
        self._state = state
        self._shortcut = shortcut
        word, _ = _STATES.get(state, _STATES["idle"])
        colour = self.status_colour()
        self._dot.set_colour(colour)
        self._status.setText(word + " · " + shortcut if shortcut else word)

    def status_labels(self) -> list:
        return [self._status]

    def status_text(self) -> str:
        return self._status.text()

    def status_colour(self) -> str:
        _, colour = _STATES.get(self._state, _STATES["idle"])
        if colour == "accent":
            colour = self._palette["accent"]
        return colour

    # ------------------------------------------------------------------
    # theme

    def restyle(self, palette: dict) -> None:
        self._palette = dict(palette)
        repaint_with(self, _rail_qss(self._palette))
        self._apply_selection()
        self.set_status(self._state, self._shortcut)


def _rail_qss(p: dict) -> str:
    return """
QWidget#nav_rail {{
    background-color: {rail};
    border: none;
}}
QLabel#rail_brand {{
    color: {rail_text_active};
    font-size: 16px;
    font-weight: 700;
    background: transparent;
}}
QLabel#rail_group {{
    color: {faint};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
    padding-left: 6px;
    background: transparent;
}}
QPushButton#rail_entry {{
    color: {rail_text};
    background: transparent;
    border: none;
    border-radius: 6px;
    font-size: 14px;
    padding-left: 8px;
    text-align: left;
}}
QPushButton#rail_entry:hover {{
    background-color: {rail_active_bg};
    color: {rail_text_active};
}}
QPushButton#rail_entry:checked {{
    background-color: {rail_active_bg};
    color: {rail_text_active};
    font-weight: 600;
}}
QFrame#rail_divider {{
    background-color: {row_border};
    border: none;
}}
QLabel#rail_status {{
    color: {muted};
    font-size: 12px;
    background: transparent;
}}
""".format(**p)
