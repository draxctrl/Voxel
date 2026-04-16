"""
recording_overlay.py
--------------------
A PyQt6 floating recording/processing overlay for Voxel.

The overlay is frameless, always-on-top, and uses a pill-shaped dark card
with a purple border.  It is thread-safe: show_recording(), show_processing(),
and hide() may be called from any thread — they emit Qt signals that are
delivered on the GUI thread.
"""

from __future__ import annotations

import math
import time

import pyaudio
from PyQt6.QtCore import (
    QObject,
    QPoint,
    QRect,
    QSize,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QColor,
    QPainter,
    QPainterPath,
    QPen,
)
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CARD_BG = QColor(0x13, 0x13, 0x1F, int(255 * 0.92))   # dark indigo @ 92%
_BORDER_COLOR = QColor(0x3D, 0x3D, 0x8B)                # indigo border
_DOT_RECORDING = QColor(0x63, 0x66, 0xF1)               # #6366f1 – indigo
_DOT_PROCESSING = QColor(0x81, 0x8C, 0xF8)              # #818cf8 – lighter indigo
_TEXT_COLOR = QColor(0xFF, 0xFF, 0xFF)
_TIMER_COLOR = QColor(0xCC, 0xCC, 0xCC)

_BORDER_RADIUS = 28          # px – makes it pill-shaped
_BORDER_WIDTH = 1.5          # px

_NUM_BARS = 24
_BAR_WIDTH = 5               # px
_BAR_GAP = 3                 # px
_BAR_MAX_HEIGHT = 38         # px
_BAR_MIN_HEIGHT = 4          # px

_WAVEFORM_INTERVAL_MS = 16   # ~60 fps
_TIMER_INTERVAL_MS = 500
_BOTTOM_MARGIN_PX = 60

_FONT_LABEL_PT = 13
_FONT_TIMER_PT = 11


# ---------------------------------------------------------------------------
# Helper – retrieve the default input device name via PyAudio
# ---------------------------------------------------------------------------

def _get_mic_name() -> str:
    try:
        pa = pyaudio.PyAudio()
        idx = pa.get_default_input_device_info().get("index", None)
        if idx is not None:
            info = pa.get_device_info_by_index(idx)
            name = str(info.get("name", "Microphone"))
        else:
            name = "Microphone"
        pa.terminate()
        return name
    except Exception:
        return "Microphone"


# ---------------------------------------------------------------------------
# Waveform widget
# ---------------------------------------------------------------------------

class _WaveformWidget(QWidget):
    """Renders 24 animated bars driven by overlapping sine waves."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._phase: float = 0.0
        self._active: bool = False

        w = _NUM_BARS * (_BAR_WIDTH + _BAR_GAP) - _BAR_GAP
        self.setFixedSize(QSize(w, _BAR_MAX_HEIGHT + 4))
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    # ------------------------------------------------------------------
    def set_active(self, active: bool) -> None:
        self._active = active

    def advance_phase(self, delta: float = 0.07) -> None:
        self._phase += delta
        self.update()

    # ------------------------------------------------------------------
    def _bar_height(self, bar_index: int) -> float:
        if not self._active:
            return _BAR_MIN_HEIGHT

        # Three overlapping sine waves at different frequencies / offsets
        x = bar_index / _NUM_BARS  # 0..1
        h = (
            0.45 * math.sin(2 * math.pi * x * 2.1 + self._phase)
            + 0.30 * math.sin(2 * math.pi * x * 3.7 - self._phase * 1.3)
            + 0.25 * math.sin(2 * math.pi * x * 1.3 + self._phase * 0.7 + 1.0)
        )
        # h is in [-1, 1]; map to [_BAR_MIN_HEIGHT, _BAR_MAX_HEIGHT]
        normalised = (h + 1.0) / 2.0            # 0..1
        return _BAR_MIN_HEIGHT + normalised * (_BAR_MAX_HEIGHT - _BAR_MIN_HEIGHT)

    def _bar_color(self, bar_index: int, height: float) -> QColor:
        """Vary colour intensity with bar height."""
        intensity = (height - _BAR_MIN_HEIGHT) / max(1, _BAR_MAX_HEIGHT - _BAR_MIN_HEIGHT)
        # Interpolate between dim indigo and bright indigo (#6366f1)
        r = int(30 + intensity * (99 - 30))
        g = int(30 + intensity * (102 - 30))
        b = int(90 + intensity * (241 - 90))
        return QColor(r, g, b, 220)

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        widget_h = self.height()
        x = 0
        for i in range(_NUM_BARS):
            bar_h = self._bar_height(i)
            color = self._bar_color(i, bar_h)
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)

            y = (widget_h - bar_h) / 2
            path = QPainterPath()
            radius = min(_BAR_WIDTH / 2, bar_h / 2)
            path.addRoundedRect(float(x), float(y), float(_BAR_WIDTH), float(bar_h), radius, radius)
            painter.fillPath(path, color)

            x += _BAR_WIDTH + _BAR_GAP

        painter.end()


# ---------------------------------------------------------------------------
# Pulsing dot widget
# ---------------------------------------------------------------------------

class _PulsingDot(QWidget):
    """A small circle that fades in/out to signal recording activity."""

    _DOT_SIZE = 12

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(_PulsingDot._DOT_SIZE + 4, _PulsingDot._DOT_SIZE + 4)
        self._alpha: float = 1.0
        self._pulse_dir: float = -1.0       # -1 = fading out, +1 = fading in
        self._color = _DOT_RECORDING
        self._pulsing: bool = False
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def set_color(self, color: QColor) -> None:
        self._color = color
        self.update()

    def set_pulsing(self, pulsing: bool) -> None:
        self._pulsing = pulsing
        if not pulsing:
            self._alpha = 1.0
        self.update()

    def advance_pulse(self, step: float = 0.024) -> None:
        if not self._pulsing:
            return
        self._alpha += self._pulse_dir * step
        if self._alpha <= 0.25:
            self._alpha = 0.25
            self._pulse_dir = 1.0
        elif self._alpha >= 1.0:
            self._alpha = 1.0
            self._pulse_dir = -1.0
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(self._color)
        color.setAlphaF(self._alpha)
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        size = _PulsingDot._DOT_SIZE
        offset = (self.width() - size) // 2
        painter.drawEllipse(offset, offset, size, size)
        painter.end()


# ---------------------------------------------------------------------------
# Main overlay widget
# ---------------------------------------------------------------------------

class _OverlaySignals(QObject):
    """Carries cross-thread signals for RecordingOverlay."""
    show_recording_sig = pyqtSignal()
    show_processing_sig = pyqtSignal()
    hide_sig = pyqtSignal()
    show_clipboard_sig = pyqtSignal()


class RecordingOverlay(QWidget):
    """
    Floating, frameless, always-on-top recording/processing indicator.

    Thread safety
    -------------
    ``show_recording()``, ``show_processing()``, and ``hide()`` are safe to
    call from any thread.  They post Qt signals to the GUI thread.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # --- window flags ---------------------------------------------------
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

        # --- state ----------------------------------------------------------
        self._is_recording = False
        self._is_processing = False
        self._elapsed_seconds = 0

        # --- mic name -------------------------------------------------------
        self._mic_name = _get_mic_name()
        _max_mic_chars = 28
        if len(self._mic_name) > _max_mic_chars:
            self._mic_name = self._mic_name[:_max_mic_chars - 1] + "…"

        # --- cross-thread signals -------------------------------------------
        self._signals = _OverlaySignals()
        self._signals.show_recording_sig.connect(self._on_show_recording)
        self._signals.show_processing_sig.connect(self._on_show_processing)
        self._signals.hide_sig.connect(self._on_hide)
        self._signals.show_clipboard_sig.connect(self._on_show_clipboard)

        # --- build UI -------------------------------------------------------
        self._build_ui()

        # --- timers ---------------------------------------------------------
        self._wave_timer = QTimer(self)
        self._wave_timer.setInterval(_WAVEFORM_INTERVAL_MS)
        self._wave_timer.timeout.connect(self._tick_waveform)

        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(_TIMER_INTERVAL_MS)
        self._elapsed_timer.timeout.connect(self._tick_elapsed)

        # --- initial position -----------------------------------------------
        self._reposition()

    # -----------------------------------------------------------------------
    # UI construction
    # -----------------------------------------------------------------------

    def _build_ui(self) -> None:
        # Outer layout adds room for the border shadow
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # The card is a child widget so we can clip to rounded rect
        self._card = QWidget(self)
        self._card.setObjectName("card")
        outer.addWidget(self._card)

        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(20, 14, 20, 14)
        card_layout.setSpacing(8)

        # --- top row: dot + label + timer -----------------------------------
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        self._dot = _PulsingDot(self._card)
        top_row.addWidget(self._dot, 0, Qt.AlignmentFlag.AlignVCenter)

        self._status_label = QLabel("Listening", self._card)
        font = self._status_label.font()
        font.setPointSize(_FONT_LABEL_PT)
        font.setBold(True)
        self._status_label.setFont(font)
        self._status_label.setStyleSheet(f"color: {_TEXT_COLOR.name()};")
        top_row.addWidget(self._status_label, 0, Qt.AlignmentFlag.AlignVCenter)

        top_row.addStretch(1)

        self._timer_label = QLabel("0:00", self._card)
        tfont = self._timer_label.font()
        tfont.setPointSize(_FONT_TIMER_PT)
        self._timer_label.setFont(tfont)
        self._timer_label.setStyleSheet(f"color: {_TIMER_COLOR.name()};")
        top_row.addWidget(self._timer_label, 0, Qt.AlignmentFlag.AlignVCenter)

        card_layout.addLayout(top_row)

        # --- waveform -------------------------------------------------------
        self._waveform = _WaveformWidget(self._card)
        card_layout.addWidget(self._waveform, 0, Qt.AlignmentFlag.AlignHCenter)

        # --- mic name -------------------------------------------------------
        self._mic_label = QLabel(self._mic_name, self._card)
        mfont = self._mic_label.font()
        mfont.setPointSize(9)
        self._mic_label.setFont(mfont)
        self._mic_label.setStyleSheet("color: rgba(200,180,255,160);")
        self._mic_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self._mic_label)

        self.adjustSize()

    # -----------------------------------------------------------------------
    # Custom painting – pill-shaped card with border
    # -----------------------------------------------------------------------

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRect(0, 0, self.width(), self.height())
        radius = float(_BORDER_RADIUS)

        # Fill
        path = QPainterPath()
        path.addRoundedRect(rect.x(), rect.y(), rect.width(), rect.height(), radius, radius)
        painter.fillPath(path, _CARD_BG)

        # Border
        pen = QPen(_BORDER_COLOR, _BORDER_WIDTH)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        shrink = _BORDER_WIDTH / 2
        border_rect = QRect(
            int(shrink), int(shrink),
            int(self.width() - _BORDER_WIDTH),
            int(self.height() - _BORDER_WIDTH),
        )
        border_path = QPainterPath()
        border_path.addRoundedRect(
            border_rect.x(), border_rect.y(),
            border_rect.width(), border_rect.height(),
            radius - shrink, radius - shrink,
        )
        painter.drawPath(border_path)
        painter.end()

    # -----------------------------------------------------------------------
    # Positioning
    # -----------------------------------------------------------------------

    def _reposition(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geom = screen.availableGeometry()
        self.adjustSize()
        x = geom.x() + (geom.width() - self.width()) // 2
        y = geom.y() + geom.height() - self.height() - _BOTTOM_MARGIN_PX
        self.move(QPoint(x, y))

    # -----------------------------------------------------------------------
    # Timer callbacks
    # -----------------------------------------------------------------------

    def _tick_waveform(self) -> None:
        self._waveform.advance_phase()
        self._dot.advance_pulse()

    def _tick_elapsed(self) -> None:
        self._elapsed_seconds += 1
        mins = self._elapsed_seconds // 60
        secs = self._elapsed_seconds % 60
        self._timer_label.setText(f"{mins}:{secs:02d}")

    # -----------------------------------------------------------------------
    # Internal slot implementations (always run on GUI thread)
    # -----------------------------------------------------------------------

    def _on_show_recording(self) -> None:
        self._is_recording = True
        self._is_processing = False
        self._elapsed_seconds = 0
        self._timer_label.setText("0:00")

        self._status_label.setText("Listening")
        self._dot.set_color(_DOT_RECORDING)
        self._dot.set_pulsing(True)
        self._waveform.set_active(True)

        self._wave_timer.start()
        self._elapsed_timer.start()

        self._reposition()
        super().show()
        self.raise_()

    def _on_show_processing(self) -> None:
        self._is_processing = True
        self._is_recording = False

        self._status_label.setText("Processing")
        self._dot.set_color(_DOT_PROCESSING)
        self._dot.set_pulsing(False)
        self._waveform.set_active(True)   # bars keep animating

        # Stop elapsed timer but keep waveform animation running
        self._elapsed_timer.stop()
        if not self._wave_timer.isActive():
            self._wave_timer.start()

        self._reposition()
        super().show()
        self.raise_()

    def _on_show_clipboard(self) -> None:
        self._is_recording = False
        self._is_processing = False

        self._wave_timer.stop()
        self._elapsed_timer.stop()
        self._dot.set_pulsing(False)
        self._waveform.set_active(False)

        self._status_label.setText("Copied to clipboard")
        self._dot.set_color(_DOT_RECORDING)  # indigo theme color
        self._timer_label.setText("")
        self._mic_label.setText("Paste with Ctrl+V")

        self._reposition()
        super().show()
        self.raise_()

        # Auto-hide after 2 seconds
        QTimer.singleShot(2000, self._on_hide)

    def _on_hide(self) -> None:
        self._is_recording = False
        self._is_processing = False

        self._wave_timer.stop()
        self._elapsed_timer.stop()
        self._dot.set_pulsing(False)
        self._waveform.set_active(False)

        # Restore mic label for next use
        self._mic_label.setText(self._mic_name)

        super().hide()

    # -----------------------------------------------------------------------
    # Public API – thread-safe
    # -----------------------------------------------------------------------

    def show_recording(self) -> None:
        """Switch to recording (Listening) state. Thread-safe."""
        self._signals.show_recording_sig.emit()

    def show_processing(self) -> None:
        """Switch to processing state. Thread-safe."""
        self._signals.show_processing_sig.emit()

    def hide(self) -> None:  # noqa: A003
        """Hide the overlay. Thread-safe."""
        self._signals.hide_sig.emit()

    def show_clipboard_notice(self) -> None:
        """Show a brief 'Copied to clipboard' notice. Thread-safe."""
        self._signals.show_clipboard_sig.emit()

    # Override show() so direct calls also go through our setup
    def show(self) -> None:  # noqa: A003
        self.show_recording()


# ---------------------------------------------------------------------------
# Quick smoke-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    overlay = RecordingOverlay()
    overlay.show_recording()

    # After 4 s switch to processing, after 6 s hide
    QTimer.singleShot(4000, overlay.show_processing)
    QTimer.singleShot(6000, overlay.hide)
    QTimer.singleShot(6500, app.quit)

    sys.exit(app.exec())
