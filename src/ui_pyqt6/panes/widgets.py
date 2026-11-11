"""Shared furniture for the settings panes.

Every pane is a heading, then rows. Building those twice would be how the
ten panes drift apart, so they are built once here.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..theme import IOSSwitch

#: Rows stop growing here. A 900px-wide row puts its label and its control
#: a screen apart; the window's remaining width becomes margin instead.
CONTENT_MAX_WIDTH = 720


def link_markup(text: str, url: str, colour: str) -> str:
    """Anchor markup that carries its own colour.

    A QLabel's anchors ignore the widget's `color` rule and render in Qt's
    default blue with an underline, so the colour goes in the tag.
    """
    return (
        '<a href="%s" style="color: %s; text-decoration: none;">%s</a>'
        % (url, colour, text)
    )


class PaneHeader(QWidget):
    """The title and one line of explanation at the top of a pane."""

    def __init__(self, title: str, subtitle: str = "", parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self._title = QLabel(title)
        self._title.setObjectName("pane_title")
        layout.addWidget(self._title)
        self._subtitle = QLabel(subtitle)
        self._subtitle.setObjectName("pane_subtitle")
        self._subtitle.setWordWrap(True)
        self._subtitle.setVisible(bool(subtitle))
        layout.addWidget(self._subtitle)

    def restyle(self, p: dict) -> None:
        self._title.setStyleSheet(
            "color: {text}; font-size: 20px; font-weight: 700;"
            " background: transparent;".format(**p)
        )
        self._subtitle.setStyleSheet(
            "color: {muted}; font-size: 12.5px; background: transparent;".format(**p)
        )


class _Ring(QWidget):
    """The radio mark on a choice row. Painted: a stylesheet border-radius
    leaves square corners at this size."""

    SIZE = 17

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(QSize(self.SIZE, self.SIZE))
        self._selected = False
        self._ring = QColor("#6d6f78")
        self._accent = QColor("#6366f1")

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self.update()

    def set_colours(self, ring: str, accent: str) -> None:
        self._ring = QColor(ring)
        self._accent = QColor(accent)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt naming
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        colour = self._accent if self._selected else self._ring
        painter.setPen(QPen(colour, 1.6))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(1, 1, self.SIZE - 2, self.SIZE - 2)
        if self._selected:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._accent)
            painter.drawEllipse(5, 5, self.SIZE - 10, self.SIZE - 10)
        painter.end()


class ChoiceRow(QFrame):
    """One tap-to-choose option: a ring, a title, and a line underneath.

    Rows instead of a dropdown, because a dropdown hides every option but
    the chosen one, and these need their explanations read.
    """

    clicked = pyqtSignal(str)

    def __init__(self, row_id: str, title: str, subtitle: str = "", parent=None) -> None:
        super().__init__(parent)
        self.row_id = row_id
        self.setObjectName("choice_row")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._selected = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 11, 14, 11)
        layout.setSpacing(12)

        self._ring = _Ring()
        layout.addWidget(self._ring, 0, Qt.AlignmentFlag.AlignTop)

        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(2)
        self._title = QLabel(title)
        self._title.setObjectName("choice_title")
        text.addWidget(self._title)
        self._subtitle = QLabel(subtitle)
        self._subtitle.setObjectName("choice_subtitle")
        self._subtitle.setWordWrap(True)
        self._subtitle.setVisible(bool(subtitle))
        text.addWidget(self._subtitle)
        layout.addLayout(text, 1)

    @property
    def selected(self) -> bool:
        return self._selected

    def set_selected(self, selected: bool) -> None:
        self._selected = bool(selected)
        self._ring.set_selected(self._selected)
        self._paint()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.row_id)
        super().mouseReleaseEvent(event)

    def restyle(self, p: dict) -> None:
        self._palette = dict(p)
        self._ring.set_colours(p["faint"], p["accent"])
        self._title.setStyleSheet(
            "color: {text}; font-size: 13.5px; font-weight: 600;"
            " background: transparent;".format(**p)
        )
        self._subtitle.setStyleSheet(
            "color: {muted}; font-size: 12px; background: transparent;".format(**p)
        )
        self._paint()

    def _paint(self) -> None:
        p = getattr(self, "_palette", None)
        if p is None:
            return
        if self._selected:
            border, background = p["accent"], p["row"]
        else:
            border, background = p["row_border"], p["row"]
        self.setStyleSheet(
            "QFrame#choice_row { background-color: %s; border: 1px solid %s;"
            " border-radius: 9px; }" % (background, border)
        )


class SwitchRow(QFrame):
    """A labelled switch. `toggled` carries the new value."""

    toggled = pyqtSignal(bool)

    def __init__(self, label: str, description: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("setting_row")
        self._quiet = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 11, 14, 11)
        layout.setSpacing(12)

        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(2)
        self._label = QLabel(label)
        self._label.setObjectName("row_label")
        text.addWidget(self._label)
        self._description = QLabel(description)
        self._description.setObjectName("row_description")
        self._description.setWordWrap(True)
        self._description.setVisible(bool(description))
        text.addWidget(self._description)
        layout.addLayout(text, 1)

        self._switch = IOSSwitch()
        self._switch.setFixedWidth(IOSSwitch.TRACK_W + 4)
        self._switch.toggled.connect(self._on_toggled)
        layout.addWidget(self._switch, 0, Qt.AlignmentFlag.AlignVCenter)

    def _on_toggled(self, value: bool) -> None:
        if self._quiet:
            return
        self.toggled.emit(value)

    def switch(self) -> IOSSwitch:
        return self._switch

    def set_checked_quietly(self, value: bool) -> None:
        """Show a saved value without it reading as a user action."""
        self._quiet = True
        try:
            self._switch.setChecked(bool(value))
        finally:
            self._quiet = False

    def restyle(self, p: dict) -> None:
        self.setStyleSheet(
            "QFrame#setting_row {{ background-color: {row};"
            " border: 1px solid {row_border}; border-radius: 9px; }}".format(**p)
        )
        self._label.setStyleSheet(
            "color: {text}; font-size: 13.5px; font-weight: 500;"
            " background: transparent;".format(**p)
        )
        self._description.setStyleSheet(
            "color: {muted}; font-size: 12px; background: transparent;".format(**p)
        )


class LinkLabel(QLabel):
    """A line of text that behaves like a link. Used for disclosures."""

    clicked = pyqtSignal()

    def __init__(self, text: str, parent=None) -> None:
        super().__init__(text, parent)
        self.setObjectName("link_label")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def restyle(self, p: dict) -> None:
        self.setStyleSheet(
            "color: {accent}; font-size: 12.5px; font-weight: 600;"
            " background: transparent;".format(**p)
        )


def pane_body(pane) -> tuple[QScrollArea, QVBoxLayout]:
    """A scrolling body for a pane, and the layout to put rows in.

    Panes scroll rather than clip: a pane with more rows than fit must
    still reach its last row on a small window.
    """
    area = QScrollArea(pane)
    area.setObjectName("pane_scroll")
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    inner = QWidget()
    inner.setObjectName("pane_inner")
    inner_layout = QHBoxLayout(inner)
    inner_layout.setContentsMargins(28, 24, 28, 24)

    column = QWidget()
    column.setObjectName("pane_column")
    column.setMaximumWidth(CONTENT_MAX_WIDTH)
    layout = QVBoxLayout(column)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)
    inner_layout.addWidget(column, 1)
    inner_layout.addStretch(0)
    area.setWidget(inner)

    outer = QVBoxLayout(pane)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.addWidget(area)
    return area, layout
