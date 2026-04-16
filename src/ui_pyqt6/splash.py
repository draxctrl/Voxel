# src/ui_pyqt6/splash.py
import math
import os
import sys

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QApplication
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtSignal, QObject
from PyQt6.QtGui import QPainter, QColor, QPainterPath, QFont, QIcon


def _get_icon_path() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, "src", "assets", "icon.ico")
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "icon.ico")


class _SplashSignals(QObject):
    set_status = pyqtSignal(str)
    close = pyqtSignal()


class SplashScreen(QWidget):
    """Animated splash screen shown during app startup."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._signals = _SplashSignals()
        self._signals.set_status.connect(self._on_set_status)
        self._signals.close.connect(self._on_close)
        self._phase = 0.0
        self._build_ui()

    def _build_ui(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(360, 200)

        ico = _get_icon_path()
        if os.path.exists(ico):
            self.setWindowIcon(QIcon(ico))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 28, 24, 20)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Title
        title = QLabel("\U0001f399  Voxel")
        title.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        title.setStyleSheet("color: #f0f0f0;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Subtitle
        sub = QLabel("Voice dictation for any app")
        sub.setFont(QFont("Segoe UI", 11))
        sub.setStyleSheet("color: #666666;")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub)

        layout.addSpacing(20)

        # Progress bar is drawn in paintEvent
        layout.addSpacing(8)

        # Status
        self._status_label = QLabel("Starting up...")
        self._status_label.setFont(QFont("Segoe UI", 10))
        self._status_label.setStyleSheet("color: #666666;")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status_label)

        # Hotkey hint
        hint = QLabel("Ctrl + Shift + Space to dictate")
        hint.setFont(QFont("Consolas", 9))
        hint.setStyleSheet("color: #444444;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        # Animation timer
        self._anim_timer = QTimer()
        self._anim_timer.timeout.connect(self._animate)
        self._anim_timer.start(30)

        # Center on screen
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.x() + (geo.width() - self.width()) // 2
            y = geo.y() + (geo.height() - self.height()) // 2
            self.move(x, y)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Card background
        path = QPainterPath()
        path.addRoundedRect(0.0, 0.0, float(self.width()), float(self.height()), 16.0, 16.0)
        painter.fillPath(path, QColor(20, 20, 24, 240))

        # Border
        painter.setPen(QColor(42, 42, 50))
        painter.drawPath(path)

        # Progress bar track
        bar_y = self.height() - 72
        bar_x = 40
        bar_w = self.width() - 80
        bar_h = 4

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(10, 10, 14))
        track_path = QPainterPath()
        track_path.addRoundedRect(float(bar_x), float(bar_y), float(bar_w), float(bar_h), 2.0, 2.0)
        painter.drawPath(track_path)

        # Progress bar fill (sliding)
        fill_w = bar_w * (0.15 + 0.1 * abs(math.sin(self._phase * 1.5)))
        fill_x = bar_x + (math.sin(self._phase) + 1) / 2 * (bar_w - fill_w)
        painter.setBrush(QColor(99, 102, 241))
        fill_path = QPainterPath()
        fill_path.addRoundedRect(fill_x, float(bar_y), fill_w, float(bar_h), 2.0, 2.0)
        painter.drawPath(fill_path)

        painter.end()

    def _animate(self) -> None:
        self._phase += 0.03
        self.update()  # trigger repaint

    def set_status(self, text: str) -> None:
        """Thread-safe status update."""
        self._signals.set_status.emit(text)

    def close_splash(self) -> None:
        """Thread-safe close."""
        self._signals.close.emit()

    def _on_set_status(self, text: str) -> None:
        self._status_label.setText(text)

    def _on_close(self) -> None:
        self._anim_timer.stop()
        self.close()
