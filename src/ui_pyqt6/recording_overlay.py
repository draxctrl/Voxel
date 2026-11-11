"""
recording_overlay.py
--------------------
The floating window Voxel shows while it is listening.

The window itself is frameless, always-on-top and translucent; *what* it draws
is one of the displays in recording_styles.py, chosen by the user. This module
owns the window, the timers and the thread-safe API; the display owns the
pixels.

Thread safety: show_recording(), show_processing(), hide(), set_mic_text() and
show_clipboard_notice() may be called from any thread — they emit Qt signals
that are delivered on the GUI thread.
"""

from __future__ import annotations

import logging
from typing import Callable

from PyQt6.QtCore import (
    QObject,
    QPoint,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtWidgets import (
    QApplication,
    QVBoxLayout,
    QWidget,
)

from src.ui_pyqt6.recording_styles import DEFAULT_STYLE, build_display

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ANIMATION_INTERVAL_MS = 16   # ~60 fps
_TIMER_INTERVAL_MS = 500
_BOTTOM_MARGIN_PX = 60

#: Keep the device line inside the badge. Warning strings ("X not found —
#: using Y") are far longer than device names, so this applies to them too.
MAX_MIC_CHARS = 28


def _truncate_mic_name(text: str) -> str:
    if len(text) > MAX_MIC_CHARS:
        return text[:MAX_MIC_CHARS - 1] + "…"
    return text


class _OverlaySignals(QObject):
    """Carries cross-thread signals for RecordingOverlay."""
    show_recording_sig = pyqtSignal()
    show_processing_sig = pyqtSignal()
    hide_sig = pyqtSignal()
    show_clipboard_sig = pyqtSignal()
    set_mic_text_sig = pyqtSignal(str)


class RecordingOverlay(QWidget):
    """Floating, frameless, always-on-top recording indicator."""

    def __init__(
        self,
        parent: QWidget | None = None,
        style: str = DEFAULT_STYLE,
        level_provider: Callable[[], float] | None = None,
    ) -> None:
        super().__init__(parent)

        # --- window flags ---------------------------------------------------
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # The application stylesheet styles bare QWidget, and Qt type selectors
        # match subclasses — which paints an opaque rectangle over this window
        # and its badge. Opt out explicitly.
        self.setStyleSheet("QWidget { background: transparent; }")
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

        # --- state ----------------------------------------------------------
        self._is_recording = False
        self._is_processing = False
        self._elapsed_seconds = 0
        self._level_provider = level_provider
        self._style = style
        self._state = "recording"
        self._elapsed_text = "0:00"

        # Empty unless something has a warning to show: the badge does not
        # name a microphone that is working.
        self._mic_name = ""

        # --- cross-thread signals -------------------------------------------
        self._signals = _OverlaySignals()
        self._signals.show_recording_sig.connect(self._on_show_recording)
        self._signals.show_processing_sig.connect(self._on_show_processing)
        self._signals.hide_sig.connect(self._on_hide)
        self._signals.show_clipboard_sig.connect(self._on_show_clipboard)

        # --- build UI -------------------------------------------------------
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._display = None
        self._install_display(style)

        self._signals.set_mic_text_sig.connect(self._on_set_mic_text)

        # --- timers ---------------------------------------------------------
        self._wave_timer = QTimer(self)
        self._wave_timer.setInterval(_ANIMATION_INTERVAL_MS)
        self._wave_timer.timeout.connect(self._tick_animation)

        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(_TIMER_INTERVAL_MS)
        self._elapsed_timer.timeout.connect(self._tick_elapsed)

        # The clipboard notice hides itself after a moment. It must be a timer
        # we can cancel: a fire-and-forget singleShot would hide the *next*
        # dictation if the user started one within those two seconds.
        self._notice_timer = QTimer(self)
        self._notice_timer.setSingleShot(True)
        self._notice_timer.setInterval(2000)
        self._notice_timer.timeout.connect(self._on_hide_notice)

        self._reposition()

    # -----------------------------------------------------------------------
    # Display management
    # -----------------------------------------------------------------------

    @property
    def style(self) -> str:
        """The style currently installed — the default if the id was unknown."""
        return self._display.style_id if self._display is not None else self._style

    def set_style(self, style_id: str) -> None:
        """Swap the display, keeping the state, the timer and the device line."""
        # Compare against the id that was *asked* for as well as the one that
        # resolved, or an unrecognised config value rebuilds the same display
        # on every save.
        if self._display is not None and style_id in (self._style, self._display.style_id):
            return
        self._install_display(style_id)

    def _install_display(self, style_id: str) -> None:
        if self._display is not None:
            self._layout.removeWidget(self._display)
            self._display.setParent(None)
            self._display.deleteLater()
        self._style = style_id
        self._display = build_display(style_id, self)
        # A swap mid-dictation must not reset the badge to "Listening" at 0:00
        # while a transcription is still running.
        self._display.set_state(self._state)
        self._display.set_elapsed(self._elapsed_text)
        self._display.set_mic_text(self._mic_name)
        self._display.setFixedSize(self._display.preferred_size())
        self._layout.addWidget(self._display)
        self.setFixedSize(self._display.preferred_size())
        self._reposition()

    # -----------------------------------------------------------------------
    # Positioning
    # -----------------------------------------------------------------------

    def _reposition(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geom = screen.availableGeometry()
        x = geom.x() + (geom.width() - self.width()) // 2
        y = geom.y() + geom.height() - self.height() - _BOTTOM_MARGIN_PX
        self.move(QPoint(x, y))

    # -----------------------------------------------------------------------
    # Timer callbacks
    # -----------------------------------------------------------------------

    def _tick_animation(self) -> None:
        """One animation frame: read the live level, then advance the drift.

        A level provider that raises costs this frame and nothing else — the
        audio subsystem disappearing must not take the recording with it.
        """
        # Only a live recording may move the badge. The capture loop keeps
        # running afterwards, so reading the level during processing would
        # show the badge reacting to a room that is no longer being recorded.
        if not self._is_recording:
            if self._display is not None:
                self._display.set_level(self._display.level * 0.85)
                self._display.advance()
            return

        level = 0.0
        if self._level_provider is not None:
            try:
                level = float(self._level_provider())
            except Exception as e:
                logger.debug("Level provider failed: %s", e)
                level = self._display.level if self._display is not None else 0.0
        if self._display is not None:
            self._display.set_level(level)
            self._display.advance()

    def _tick_elapsed(self) -> None:
        self._elapsed_seconds += 1
        mins = self._elapsed_seconds // 60
        secs = self._elapsed_seconds % 60
        self._elapsed_text = f"{mins}:{secs:02d}"
        self._display.set_elapsed(self._elapsed_text)

    # -----------------------------------------------------------------------
    # Internal slots (always run on the GUI thread)
    # -----------------------------------------------------------------------

    def _on_show_recording(self) -> None:
        self._is_recording = True
        self._is_processing = False
        self._elapsed_seconds = 0
        self._state = "recording"
        self._elapsed_text = "0:00"
        self._notice_timer.stop()

        # Nothing from the previous dictation may leak into this one: a stale
        # level would open the badge mid-shout.
        self._display.set_level(0.0)
        self._display.set_elapsed("0:00")
        self._display.set_mic_text(self._mic_name)
        self._display.set_state("recording")

        self._wave_timer.start()
        self._elapsed_timer.start()

        self._reposition()
        super().show()
        self.raise_()

    def _on_show_processing(self) -> None:
        self._is_processing = True
        self._is_recording = False
        self._state = "processing"
        self._notice_timer.stop()

        self._display.set_state("processing")
        self._elapsed_timer.stop()
        if not self._wave_timer.isActive():
            self._wave_timer.start()

        self._reposition()
        super().show()
        self.raise_()

    def _on_show_clipboard(self) -> None:
        self._is_recording = False
        self._is_processing = False
        self._state = "clipboard"
        self._elapsed_text = ""

        self._wave_timer.stop()
        self._elapsed_timer.stop()

        self._display.set_state("clipboard")
        self._display.set_level(0.0)
        self._display.set_elapsed("")
        # Deliberately not stored in _mic_name: this is a one-off notice, not
        # the persistent device line.
        self._display.set_mic_text("Paste with Ctrl+V")

        self._reposition()
        super().show()
        self.raise_()

        self._notice_timer.start()

    def _on_hide_notice(self) -> None:
        """Hide the clipboard notice — unless a new dictation has started."""
        if self._is_recording or self._is_processing:
            return
        self._on_hide()

    def _on_set_mic_text(self, text: str) -> None:
        """Set the device line, and make it the value _on_hide() restores.

        _on_hide resets the line from _mic_name, so updating only the display
        would show a mic warning once and then lose it on the next recording.
        """
        self._mic_name = _truncate_mic_name(text)
        self._display.set_mic_text(self._mic_name)

    def _on_hide(self) -> None:
        self._is_recording = False
        self._is_processing = False
        self._notice_timer.stop()

        # A hidden badge animating at 60fps burns a core for nothing.
        self._wave_timer.stop()
        self._elapsed_timer.stop()

        self._display.set_level(0.0)
        self._display.set_mic_text(self._mic_name)

        super().hide()

    # -----------------------------------------------------------------------
    # Public API — thread-safe
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

    def set_mic_text(self, text: str) -> None:
        """Set the device line. Thread-safe.

        Used to name the microphone actually in use, or to warn when it isn't
        the one the user chose.
        """
        self._signals.set_mic_text_sig.emit(text)

    def show(self) -> None:  # noqa: A003
        """Direct show() calls go through the recording setup."""
        self.show_recording()


# ---------------------------------------------------------------------------
# Quick smoke-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import math
    import sys
    import time

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    start = time.time()
    overlay = RecordingOverlay(
        style=sys.argv[1] if len(sys.argv) > 1 else DEFAULT_STYLE,
        level_provider=lambda: 0.5 + 0.5 * math.sin((time.time() - start) * 3),
    )
    overlay.show_recording()

    QTimer.singleShot(6000, overlay.show_processing)
    QTimer.singleShot(8000, overlay.hide)
    QTimer.singleShot(8500, app.quit)

    sys.exit(app.exec())
