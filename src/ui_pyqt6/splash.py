"""The window Voxel shows while it starts up.

The first thing anyone sees of the app, so it is the app's own mark, its
own typeface and its own colours - not an emoji the system font cannot
draw and a progress bar painted through the text.
"""
from __future__ import annotations

import math
import os
import sys

from PyQt6.QtCore import QObject, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPainter, QPainterPath
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .theme import current_palette

WIDTH, HEIGHT = 380, 196
LOGO_SIZE = 40
#: Where the progress bar is painted, measured from the bottom.
BAR_BOTTOM_MARGIN = 26
BAR_HEIGHT = 4
BAR_SIDE_MARGIN = 40


def _icon_path() -> str | None:
    """The app icon, or None when it is not bundled."""
    meipass = getattr(sys, "_MEIPASS", None)
    candidates = []
    if meipass:
        candidates.append(os.path.join(meipass, "src", "assets", "icon.ico"))
        candidates.append(os.path.join(meipass, "assets", "icon.ico"))
    here = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.normpath(os.path.join(here, "..", "assets", "icon.ico")))
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return None


class _SplashSignals(QObject):
    set_status = pyqtSignal(str)
    close = pyqtSignal()


class SplashScreen(QWidget):
    """Shown while Voxel starts, closed when it is ready."""

    def __init__(self, parent=None, shortcut: str = "") -> None:
        super().__init__(parent)
        self._signals = _SplashSignals()
        self._signals.set_status.connect(self._on_set_status)
        self._signals.close.connect(self._on_close)
        self._phase = 0.0
        self._shortcut = shortcut or ""
        self._has_logo = False
        self._palette = dict(current_palette())
        self._build_ui()

    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        p = self._palette
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(WIDTH, HEIGHT)

        path = _icon_path()
        if path:
            self.setWindowIcon(QIcon(path))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 30, 28, BAR_BOTTOM_MARGIN + BAR_HEIGHT + 14)
        layout.setSpacing(0)

        # The mark and the name, side by side.
        brand = QHBoxLayout()
        brand.setSpacing(12)
        brand.addStretch(1)

        self._logo = QLabel(self)
        self._logo.setFixedSize(QSize(LOGO_SIZE, LOGO_SIZE))
        if path:
            # From the .ico, which carries artwork drawn for small sizes.
            pixmap = QIcon(path).pixmap(QSize(LOGO_SIZE, LOGO_SIZE))
            if not pixmap.isNull():
                self._logo.setPixmap(pixmap)
                self._has_logo = True
        brand.addWidget(self._logo, 0, Qt.AlignmentFlag.AlignVCenter)

        self._title = QLabel("Voxel", self)
        self._title.setStyleSheet(
            "color: {text}; font-size: 26px; font-weight: 700;"
            " background: transparent;".format(**p)
        )
        brand.addWidget(self._title, 0, Qt.AlignmentFlag.AlignVCenter)
        brand.addStretch(1)
        layout.addLayout(brand)

        layout.addSpacing(6)

        self._subtitle = QLabel(
            "Speak anywhere, and your words are typed for you", self
        )
        self._subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._subtitle.setStyleSheet(
            "color: {muted}; font-size: 12px; background: transparent;".format(**p)
        )
        layout.addWidget(self._subtitle)

        layout.addStretch(1)

        self._status_label = QLabel("Starting up…", self)
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setStyleSheet(
            "color: {muted}; font-size: 12px; background: transparent;".format(**p)
        )
        layout.addWidget(self._status_label)

        layout.addSpacing(4)

        self._hint = QLabel(self._hint_for(self._shortcut), self)
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint.setStyleSheet(
            "color: {faint}; font-size: 11px; background: transparent;".format(**p)
        )
        layout.addWidget(self._hint)

        self._anim_timer = QTimer()
        self._anim_timer.timeout.connect(self._animate)
        self._anim_timer.start(30)

        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move(
                geo.x() + (geo.width() - self.width()) // 2,
                geo.y() + (geo.height() - self.height()) // 2,
            )

    @staticmethod
    def _hint_for(shortcut: str) -> str:
        """What to say about the shortcut.

        With no shortcut to hand, say nothing about it: naming the default
        to someone who changed it is worse than silence.
        """
        return ("Hold %s to dictate" % shortcut) if shortcut else "Getting ready…"

    # ------------------------------------------------------------------

    def logo_is_shown(self) -> bool:
        return self._has_logo

    def hint_text(self) -> str:
        return self._hint.text()

    def progress_band(self) -> tuple[int, int]:
        """The top and bottom of the painted progress bar."""
        top = self.height() - BAR_BOTTOM_MARGIN - BAR_HEIGHT
        return top, top + BAR_HEIGHT

    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt naming
        p = self._palette
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        card = QPainterPath()
        card.addRoundedRect(
            0.5, 0.5, float(self.width() - 1), float(self.height() - 1), 16.0, 16.0
        )
        painter.fillPath(card, QColor(p["pane"]))
        painter.setPen(QColor(p["row_border"]))
        painter.drawPath(card)

        top, _bottom = self.progress_band()
        bar_x = BAR_SIDE_MARGIN
        bar_w = self.width() - BAR_SIDE_MARGIN * 2

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(p["row"]))
        track = QPainterPath()
        track.addRoundedRect(
            float(bar_x), float(top), float(bar_w), float(BAR_HEIGHT), 2.0, 2.0
        )
        painter.drawPath(track)

        fill_w = bar_w * (0.18 + 0.08 * abs(math.sin(self._phase * 1.5)))
        fill_x = bar_x + (math.sin(self._phase) + 1) / 2 * (bar_w - fill_w)
        painter.setBrush(QColor(p["accent"]))
        fill = QPainterPath()
        fill.addRoundedRect(fill_x, float(top), fill_w, float(BAR_HEIGHT), 2.0, 2.0)
        painter.drawPath(fill)

        painter.end()

    def _animate(self) -> None:
        self._phase += 0.03
        self.update()

    # ------------------------------------------------------------------

    def set_status(self, text: str) -> None:
        """Thread-safe status update."""
        self._signals.set_status.emit(text)

    def set_shortcut(self, shortcut: str) -> None:
        self._shortcut = shortcut or ""
        self._hint.setText(self._hint_for(self._shortcut))

    def close_splash(self) -> None:
        """Thread-safe close."""
        self._signals.close.emit()

    def _on_set_status(self, text: str) -> None:
        self._status_label.setText(text)

    def _on_close(self) -> None:
        self._anim_timer.stop()
        self.close()
