"""iOS grouped-settings building blocks.

iOS settings are not a flat stack of labels and controls: they are inset cards
of rows, each row carrying its own label on the left and its control on the
right, separated by hairlines that stop short of the card's left edge. These
three widgets are that structure, and nothing else — every colour comes from
the application stylesheet in theme.py, so a theme change restyles them with
everything else.
"""
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PyQt6.QtWidgets import (
    QFrame,
    QStyle,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

#: Minimum row height. iOS uses 44pt; anything shorter stops reading as a list.
ROW_HEIGHT = 44
#: Card corner radius. Owned by theme.py, which draws it, and re-exported
#: here so callers have one import.
from src.ui_pyqt6.theme import CARD_RADIUS  # noqa: E402
#: How far a separator is inset from the card's left edge, so the hairlines
#: line up under the row text rather than cutting the card in half.
SEPARATOR_INSET = 16
#: Width reserved for a disclosure chevron.
CHEVRON_WIDTH = 18


def section_header(text: str) -> QLabel:
    """The small grey uppercase label that sits above a group card."""
    label = QLabel(text.upper())
    label.setObjectName("group_header")
    return label


class GroupCard(QFrame):
    """A rounded card holding a stack of rows separated by hairlines."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("group_card")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._rows: list[QWidget] = []

    def add_row(self, widget: QWidget) -> None:
        """Append a row, with a separator above it if it isn't the first."""
        if self._rows:
            self._layout.addWidget(self._make_separator())
        self._layout.addWidget(widget)
        self._rows.append(widget)

    def rows(self) -> list[QWidget]:
        return list(self._rows)

    def _make_separator(self) -> QWidget:
        # The hairline lives inside a wrapper so the inset is layout margin
        # rather than a transparent slice of the line itself.
        holder = QFrame()
        holder.setObjectName("row_separator")
        layout = QHBoxLayout(holder)
        layout.setContentsMargins(SEPARATOR_INSET, 0, 0, 0)
        layout.setSpacing(0)
        line = QFrame()
        line.setObjectName("hairline")
        line.setFixedHeight(1)
        layout.addWidget(line)
        holder.setFixedHeight(1)
        return holder


class SettingsRow(QWidget):
    """One setting: title (and optional subtitle) left, control right."""

    def __init__(
        self,
        title: str,
        control: QWidget | None = None,
        subtitle: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("settings_row")

        self._row = QHBoxLayout(self)
        self._row.setContentsMargins(16, 8, 16, 8)
        self._row.setSpacing(12)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(1)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("row_title")
        text_col.addWidget(self.title_label)

        self.subtitle_label: QLabel | None = None
        if subtitle is not None:
            self.subtitle_label = QLabel(subtitle)
            self.subtitle_label.setObjectName("row_sub")
            self.subtitle_label.setWordWrap(True)
            text_col.addWidget(self.subtitle_label)

        # The text column takes the room the control does not want, so a
        # subtitle wraps only when it genuinely cannot fit.
        self._row.addLayout(text_col, 1)

        self.control = control
        if control is not None:
            control.setParent(self)
            self._row.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter)

        self.setMinimumHeight(ROW_HEIGHT)

    def add_trailing(self, widget: QWidget) -> None:
        """Put another widget to the right of the control (e.g. a button)."""
        widget.setParent(self)
        self._row.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)


class StackedRow(QWidget):
    """A row whose control needs the full card width, under its title.

    Used for the API key and hotkey fields, which are text inputs with a button
    beside them and would be squeezed to nothing in a right-aligned row.
    """

    def __init__(
        self,
        title: str,
        subtitle: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("settings_row")

        self._col = QVBoxLayout(self)
        self._col.setContentsMargins(16, 10, 16, 12)
        self._col.setSpacing(6)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("row_title")
        self._col.addWidget(self.title_label)

        self.subtitle_label: QLabel | None = None
        if subtitle is not None:
            self.subtitle_label = QLabel(subtitle)
            self.subtitle_label.setObjectName("row_sub")
            self.subtitle_label.setWordWrap(True)
            self._col.addWidget(self.subtitle_label)

        self._controls = QHBoxLayout()
        self._controls.setContentsMargins(0, 0, 0, 0)
        self._controls.setSpacing(8)
        self._col.addLayout(self._controls)

    def add_control(self, widget: QWidget, stretch: int = 0) -> None:
        widget.setParent(self)
        self._controls.addWidget(widget, stretch)

    def add_below(self, widget: QWidget) -> None:
        widget.setParent(self)
        self._col.addWidget(widget)


class DisclosureRow(SettingsRow):
    """A row that opens something else: optional value, then a chevron."""

    clicked = pyqtSignal()

    def __init__(
        self,
        title: str,
        value: str = "",
        subtitle: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(title, subtitle=subtitle, parent=parent)

        self.value_label = QLabel("")
        self.value_label.setObjectName("row_value")
        self.value_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self._row.addWidget(self.value_label, 0, Qt.AlignmentFlag.AlignVCenter)

        # Room for the chevron, which is painted rather than laid out.
        self._row.addSpacing(CHEVRON_WIDTH)

        self._value_text = value
        self.set_value(value)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_value(self, text: str) -> None:
        """Set the right-hand value, elided to whatever room the row has.

        A long mic name must cost ellipsis, never a row wider than its card.
        """
        self._value_text = text
        self.value_label.setText(self._elided(text))

    def _elided(self, text: str) -> str:
        if not text:
            return ""
        # Leave the title its room: the value gets at most half the row.
        budget = max(60, (self.width() or 320) // 2)
        metrics = QFontMetrics(self.value_label.font())
        return metrics.elidedText(text, Qt.TextElideMode.ElideRight, budget)

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self.value_label.setText(self._elided(self._value_text))

    def mouseReleaseEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(
            event.position().toPoint()
        ):
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):  # noqa: N802
        super().paintEvent(event)
        # Read the palette at paint time, not construction: a row built before
        # a theme change would otherwise keep the old chevron colour.
        from src.ui_pyqt6.theme import current_palette

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(current_palette()["secondary"]), 1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        x = self.width() - 18
        y = self.height() // 2
        painter.drawLine(x - 2, y - 4, x + 2, y)
        painter.drawLine(x + 2, y, x - 2, y + 4)
        painter.end()


class StylePicker(QWidget):
    """Pick a recording display from live animated thumbnails.

    The thumbnails are the real display widgets, scaled down and fed a
    synthetic level: the user sees exactly what they are choosing, and the
    preview never opens the microphone — that would fight the recorder for the
    device.
    """

    selection_changed = pyqtSignal(str)

    THUMB_W = 136
    THUMB_H = 86
    #: How fast the synthetic level cycles, in radians per frame.
    PREVIEW_SPEED = 0.12

    def __init__(
        self,
        styles: dict[str, str],
        selected: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("style_picker")

        from PyQt6.QtCore import QTimer

        self._styles = dict(styles)
        self._selected = selected if selected in self._styles else next(iter(self._styles))
        self._phase = 0.0
        self._tiles: dict[str, _StyleTile] = {}

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        for style_id, label in self._styles.items():
            tile = _StyleTile(style_id, label, self.THUMB_W, self.THUMB_H, self)
            tile.clicked.connect(self.select)
            row.addWidget(tile)
            self._tiles[style_id] = tile

        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._tick)

        self.select(self._selected)

    # -- selection ------------------------------------------------------
    def style_ids(self) -> list[str]:
        return list(self._styles)

    def selected(self) -> str:
        return self._selected

    def select(self, style_id: str) -> None:
        if style_id not in self._styles:
            return
        self._selected = style_id
        for sid, tile in self._tiles.items():
            tile.set_selected(sid == style_id)
        self.selection_changed.emit(style_id)

    def _preview_for(self, style_id: str):
        return self._tiles[style_id].display

    # -- animation ------------------------------------------------------
    def _tick(self) -> None:
        import math

        self._phase += self.PREVIEW_SPEED
        # A synthetic level: speech-like, and nothing to do with the mic.
        level = 0.5 + 0.45 * math.sin(self._phase) * math.sin(self._phase * 0.37)
        for tile in self._tiles.values():
            tile.display.set_level(max(0.0, min(1.0, level)))
            tile.display.advance()

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        self._timer.start()

    def hideEvent(self, event):  # noqa: N802
        super().hideEvent(event)
        self._timer.stop()


class _StyleTile(QFrame):
    """One thumbnail in the StylePicker: a scaled display plus its name."""

    clicked = pyqtSignal(str)

    def __init__(
        self,
        style_id: str,
        label: str,
        width: int,
        height: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        from src.ui_pyqt6.recording_styles import build_display

        self.style_id = style_id
        self.setObjectName("style_tile")
        self.setProperty("selected", False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(width, height + 22)

        self.display = build_display(style_id, self)
        self.display.set_state("recording")
        self.display.set_elapsed("0:07")
        self.display.set_mic_text("")
        native = self.display.preferred_size()
        # Fit the real display into the thumbnail rather than redrawing it at
        # another size: a preview that is not the thing itself is a lie.
        self._scale = min(
            (width - 12) / native.width(), (height - 12) / native.height()
        )
        self.display.setFixedSize(native)
        self.display.setVisible(False)

        self._label = QLabel(label, self)
        self._label.setObjectName("tile_label")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setGeometry(0, height, width, 20)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", selected)
        # A property change needs the style re-polished to take effect.
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def mouseReleaseEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.style_id)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        native = self.display.preferred_size()
        painter.save()
        painter.translate(
            (self.width() - native.width() * self._scale) / 2,
            (self.height() - 22 - native.height() * self._scale) / 2,
        )
        painter.scale(self._scale, self._scale)
        self.display.render(
            painter,
            flags=QWidget.RenderFlag.DrawChildren,
        )
        painter.restore()
        painter.end()
