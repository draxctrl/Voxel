"""
stats_window.py - Statistics dashboard for Voxel voice dictation app.
Displays usage statistics queried from the HistoryStore (SQLite).
"""

from __future__ import annotations

import os
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QScrollArea,
    QApplication,
)

from src.ui_pyqt6.theme import BG, CARD, BORDER, INPUT_BG, TEXT, SUBTLE, ACCENT, ACCENT_HOVER, QSS
from src.history import HistoryStore


class StatsWindow(QWidget):
    """Statistics dashboard showing dictation usage data."""

    def __init__(self, history: HistoryStore) -> None:
        super().__init__()
        self._history = history
        self._value_labels: dict[str, QLabel] = {}
        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show(self) -> None:
        """Show (or raise) the statistics window."""
        if self.isMinimized():
            self.showNormal()
            self.raise_()
            self.activateWindow()
            return
        if self.isVisible():
            self.raise_()
            self.activateWindow()
            return
        screen = QApplication.primaryScreen()
        if screen is not None:
            geom = screen.availableGeometry()
            self.move(
                geom.center().x() - self.width() // 2,
                geom.center().y() - self.height() // 2,
            )
        super().show()
        self.raise_()
        self.activateWindow()

    def refresh(self) -> None:
        """Re-query all statistics from the HistoryStore and update labels."""
        total = self._history.count()
        total_words = self._history.total_words()
        total_duration = self._history.total_duration()
        today = self._history.today_count()
        week = self._history.week_count()
        profile = self._history.most_used_profile()

        avg_words = round(total_words / total) if total > 0 else 0

        hours = int(total_duration // 3600)
        minutes = int((total_duration % 3600) // 60)
        if hours > 0:
            duration_str = f"{hours} hours {minutes} minutes"
        else:
            duration_str = f"{minutes} minutes"

        self._value_labels["total_dictations"].setText(str(total))
        self._value_labels["total_words"].setText(f"{total_words:,}")
        self._value_labels["recording_time"].setText(duration_str)
        self._value_labels["avg_words"].setText(str(avg_words))
        self._value_labels["most_used_profile"].setText(profile.replace("_", " ").title())
        self._value_labels["today"].setText(str(today))
        self._value_labels["this_week"].setText(str(week))

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.setWindowTitle("Voxel - Statistics")
        self.setFixedSize(450, 400)
        self.setStyleSheet(QSS)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowMinimizeButtonHint
        )

        icon_path = self._resolve_asset("icon.ico")
        if icon_path and os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(0)

        # Header
        title = QLabel("Statistics")
        title.setObjectName("app_title")
        root.addWidget(title)

        subtitle = QLabel("Your dictation usage at a glance")
        subtitle.setObjectName("subtitle")
        root.addWidget(subtitle)

        root.addSpacing(12)

        divider = QFrame()
        divider.setObjectName("divider")
        divider.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(divider)

        root.addSpacing(12)

        # Scrollable stat cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        root.addWidget(scroll, stretch=1)

        scroll_content = QWidget()
        scroll.setWidget(scroll_content)
        cards_layout = QVBoxLayout(scroll_content)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(8)

        # Define stat cards
        stats = [
            ("total_dictations", "Total Dictations"),
            ("total_words", "Total Words Dictated"),
            ("recording_time", "Total Recording Time"),
            ("avg_words", "Average Words per Dictation"),
            ("most_used_profile", "Most Used Profile"),
            ("today", "Today's Dictations"),
            ("this_week", "This Week's Dictations"),
        ]

        for key, label_text in stats:
            card = self._make_card(key, label_text)
            cards_layout.addWidget(card)

        cards_layout.addStretch()

    def _make_card(self, key: str, label_text: str) -> QFrame:
        """Create a single stat card widget."""
        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background-color: {CARD}; border: 1px solid {BORDER}; border-radius: 10px; }}"
        )

        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # Label on the left
        name_lbl = QLabel(label_text)
        name_lbl.setStyleSheet(f"color: {SUBTLE}; font-size: 12px; border: none;")
        layout.addWidget(name_lbl, stretch=1)

        # Value on the right
        value_lbl = QLabel("--")
        value_lbl.setStyleSheet(f"color: {ACCENT}; font-size: 18px; font-weight: bold; border: none;")
        value_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(value_lbl)

        self._value_labels[key] = value_lbl
        return card

    # ------------------------------------------------------------------
    # Asset resolution (same pattern as settings_ui.py)
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_asset(filename: str) -> str | None:
        if hasattr(sys, "_MEIPASS"):
            candidate = os.path.join(sys._MEIPASS, "assets", filename)  # type: ignore[attr-defined]
            if os.path.exists(candidate):
                return candidate

        here = os.path.dirname(os.path.abspath(__file__))
        for rel in (
            os.path.join(here, "..", "assets", filename),
            os.path.join(here, "assets", filename),
            os.path.join(here, "..", "..", "assets", filename),
        ):
            resolved = os.path.normpath(rel)
            if os.path.exists(resolved):
                return resolved

        return None
