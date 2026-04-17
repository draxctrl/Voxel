"""
history_window.py - PyQt6 history window for Voxel voice dictation app.
Shows dictation history with search, copy, delete, and clear-all functionality.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime

import pyperclip
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QFrame,
    QSizePolicy,
    QMessageBox,
)

from src.ui_pyqt6.theme import (
    BG, CARD, BORDER, INPUT_BG, TEXT, SUBTLE, ACCENT, ACCENT_HOVER, QSS,
)
from src.history import HistoryStore

logger = logging.getLogger(__name__)

_MAX_PREVIEW = 200


def _format_timestamp(iso_str: str) -> str:
    """Format an ISO timestamp into a friendly local string like 'Apr 17, 2:30 PM'."""
    try:
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is not None:
            dt = dt.astimezone()
        # Windows uses %#I for no-padding, Unix uses %-I
        hour_fmt = "%#I" if sys.platform == "win32" else "%-I"
        return dt.strftime(f"%b %d, {hour_fmt}:%M %p")
    except Exception:
        try:
            dt = datetime.fromisoformat(iso_str)
            if dt.tzinfo is not None:
                dt = dt.astimezone()
            return dt.strftime("%b %d, %I:%M %p").lstrip("0")
        except Exception:
            return iso_str


# ---------------------------------------------------------------------------
# History card widget
# ---------------------------------------------------------------------------
class _HistoryCard(QFrame):
    """A single dictation entry card."""

    delete_requested = pyqtSignal(int)  # emits entry id

    def __init__(self, entry: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entry = entry
        self._entry_id: int = entry["id"]

        self.setStyleSheet(
            f"_HistoryCard {{ background-color: {CARD}; border: 1px solid {BORDER}; "
            f"border-radius: 8px; }}"
        )
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        # Top row: timestamp + profile badge
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        ts_label = QLabel(_format_timestamp(entry.get("timestamp", "")))
        ts_label.setStyleSheet(f"color: {SUBTLE}; font-size: 11px; background: transparent;")
        top_row.addWidget(ts_label)

        profile = entry.get("profile", "default")
        badge = QLabel(profile)
        badge.setStyleSheet(
            f"background-color: {ACCENT}; color: white; font-size: 10px; "
            f"font-weight: bold; border-radius: 4px; padding: 1px 6px;"
        )
        badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        top_row.addWidget(badge)

        top_row.addStretch()

        # Copy button
        copy_btn = QPushButton("Copy")
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.setFixedHeight(24)
        copy_btn.setStyleSheet(
            f"QPushButton {{ background-color: {ACCENT}; color: white; font-size: 11px; "
            f"border-radius: 4px; padding: 2px 10px; font-weight: bold; min-height: 20px; }}"
            f"QPushButton:hover {{ background-color: {ACCENT_HOVER}; }}"
        )
        copy_btn.clicked.connect(self._copy_text)
        top_row.addWidget(copy_btn)

        # Delete button
        del_btn = QPushButton("\u00d7")
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setFixedSize(24, 24)
        del_btn.setToolTip("Delete this entry")
        del_btn.setStyleSheet(
            f"QPushButton {{ background-color: transparent; color: {SUBTLE}; font-size: 16px; "
            f"border: none; border-radius: 4px; padding: 0; min-height: 20px; }}"
            f"QPushButton:hover {{ color: #ef4444; background-color: {BORDER}; }}"
        )
        del_btn.clicked.connect(lambda: self.delete_requested.emit(self._entry_id))
        top_row.addWidget(del_btn)

        layout.addLayout(top_row)

        # Preview text
        cleaned = entry.get("cleaned_text", "")
        preview = cleaned[:_MAX_PREVIEW] + "..." if len(cleaned) > _MAX_PREVIEW else cleaned
        text_label = QLabel(preview)
        text_label.setWordWrap(True)
        text_label.setStyleSheet(f"color: {TEXT}; font-size: 12px; background: transparent;")
        layout.addWidget(text_label)

    def _copy_text(self) -> None:
        text = self._entry.get("cleaned_text", "")
        try:
            pyperclip.copy(text)
        except Exception as e:
            logger.warning("Failed to copy to clipboard: %s", e)


# ---------------------------------------------------------------------------
# History window
# ---------------------------------------------------------------------------
class HistoryWindow(QWidget):
    """Main history window showing all past dictations."""

    # Signal for thread-safe refresh from background threads
    _refresh_signal = pyqtSignal()

    def __init__(self, store: HistoryStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._store = store

        self.setWindowTitle("Voxel - History")
        self.resize(650, 550)
        self.setMinimumSize(400, 300)
        self.setStyleSheet(QSS)

        # Icon
        icon_path = self._resolve_asset("icon.ico")
        if icon_path and os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self._refresh_signal.connect(self._do_refresh)

        self._build_ui()
        self._do_refresh()

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

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 16)
        root.setSpacing(12)

        # ---- Search bar ----
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search dictations...")
        self._search_input.setClearButtonEnabled(True)
        root.addWidget(self._search_input)

        # Debounce timer
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._do_refresh)
        self._search_input.textChanged.connect(lambda _: self._search_timer.start())

        # ---- Scroll area ----
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        root.addWidget(self._scroll, stretch=1)

        # Container inside scroll
        self._cards_container = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(8)
        self._cards_layout.addStretch()
        self._scroll.setWidget(self._cards_container)

        # ---- Empty state label (hidden by default) ----
        self._empty_label = QLabel("No dictations yet")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(
            f"color: {SUBTLE}; font-size: 15px; padding: 40px; background: transparent;"
        )
        self._empty_label.hide()
        root.addWidget(self._empty_label)

        # ---- Bottom bar ----
        bottom = QHBoxLayout()
        bottom.setSpacing(12)

        self._count_label = QLabel("0 entries")
        self._count_label.setStyleSheet(f"color: {SUBTLE}; font-size: 11px; background: transparent;")
        bottom.addWidget(self._count_label)

        bottom.addStretch()

        clear_btn = QPushButton("Clear All")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setStyleSheet(
            f"QPushButton {{ background-color: transparent; color: {SUBTLE}; "
            f"font-size: 12px; border: 1px solid {BORDER}; border-radius: 6px; "
            f"padding: 4px 14px; min-height: 24px; }}"
            f"QPushButton:hover {{ color: #ef4444; border-color: #ef4444; }}"
        )
        clear_btn.clicked.connect(self._on_clear_all)
        bottom.addWidget(clear_btn)

        root.addLayout(bottom)

    # ------------------------------------------------------------------
    # Data loading / refresh
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        """Thread-safe refresh — can be called from any thread."""
        self._refresh_signal.emit()

    def _do_refresh(self) -> None:
        """Reload entries from the store and rebuild cards (must run on GUI thread)."""
        query = self._search_input.text().strip()
        if query:
            entries = self._store.search(query)
        else:
            entries = self._store.get_recent(limit=200)

        # Clear existing cards
        layout = self._cards_layout
        while layout.count() > 1:  # keep the trailing stretch
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        # Populate
        if entries:
            self._empty_label.hide()
            self._scroll.show()
            for entry in entries:
                card = _HistoryCard(entry)
                card.delete_requested.connect(self._on_delete_entry)
                layout.insertWidget(layout.count() - 1, card)
        else:
            self._scroll.show()
            self._empty_label.show()

        count = self._store.count()
        self._count_label.setText(f"{count} {'entry' if count == 1 else 'entries'}")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _on_delete_entry(self, entry_id: int) -> None:
        self._store.delete(entry_id)
        self._do_refresh()

    def _on_clear_all(self) -> None:
        reply = QMessageBox.question(
            self,
            "Clear All History",
            "Are you sure you want to delete all dictation history?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._store.clear_all()
            self._do_refresh()
