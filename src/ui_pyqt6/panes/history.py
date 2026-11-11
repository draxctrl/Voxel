"""History: everything you have dictated, searchable.

This was a window of its own. It is a pane now. The list is paged: a
history of a few thousand entries would otherwise build a few thousand
widgets the moment the pane opened.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..icons import icon as load_icon
from . import Pane, PaneContext
from .widgets import PaneHeader, pane_body

logger = logging.getLogger(__name__)

#: How many rows are built at once.
PAGE_SIZE = 50

#: Where a long dictation is cut off on screen. The whole thing is still
#: what gets copied.
PREVIEW_CHARS = 220

#: How long to wait after the last keystroke before searching.
SEARCH_DELAY_MS = 200

EMPTY_MESSAGE = "Nothing here yet. Anything you dictate will show up on this page."
NO_MATCHES_MESSAGE = "No dictations match that."


def _short(text: str) -> str:
    """A dictation cut to one readable preview."""
    text = " ".join((text or "").split())
    if len(text) <= PREVIEW_CHARS:
        return text
    return text[:PREVIEW_CHARS].rstrip() + "…"


def _when(timestamp: str) -> str:
    """An ISO timestamp as something a person reads at a glance."""
    try:
        moment = datetime.fromisoformat(timestamp)
    except (TypeError, ValueError):
        return ""
    if moment.tzinfo is not None:
        moment = moment.astimezone()
    now = datetime.now(moment.tzinfo) if moment.tzinfo else datetime.now()
    if moment.date() == now.date():
        return moment.strftime("%H:%M")
    if (now.date() - moment.date()).days == 1:
        return "Yesterday"
    return moment.strftime("%d %b")


class _EntryRow(QFrame):
    """One dictation: when it was, what it said, copy and delete."""

    def __init__(self, entry: dict, on_copy, on_delete, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("setting_row")
        self.entry_id = entry["id"]
        self._full_text = entry.get("cleaned_text") or entry.get("raw_text") or ""

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 10, 10)
        layout.setSpacing(10)

        self._when = QLabel(_when(entry.get("timestamp", "")))
        self._when.setFixedWidth(64)
        self._when.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        layout.addWidget(self._when)

        self._text = QLabel(_short(self._full_text))
        self._text.setWordWrap(True)
        layout.addWidget(self._text, 1)

        self.copy_button = QPushButton()
        self.copy_button.setToolTip("Copy this text")
        self.delete_button = QPushButton()
        self.delete_button.setToolTip("Delete this dictation")
        for button, handler in (
            (self.copy_button, on_copy),
            (self.delete_button, on_delete),
        ):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setFixedSize(QSize(28, 28))
            button.setIconSize(QSize(16, 16))
            button.clicked.connect(lambda _c, h=handler: h(self.entry_id))
            layout.addWidget(button, 0, Qt.AlignmentFlag.AlignTop)

    def shown_text(self) -> str:
        return self._text.text()

    def restyle(self, p: dict) -> None:
        self.setStyleSheet(
            "QFrame#setting_row {{ background-color: {row};"
            " border: 1px solid {row_border}; border-radius: 9px; }}".format(**p)
        )
        self._when.setStyleSheet(
            "color: {faint}; font-size: 11.5px; background: transparent;".format(**p)
        )
        self._text.setStyleSheet(
            "color: {text}; font-size: 12.5px; background: transparent;".format(**p)
        )
        button_qss = (
            "QPushButton {{ background: transparent; border: none;"
            " border-radius: 6px; }}"
            "QPushButton:hover {{ background-color: {card_alt}; }}".format(**p)
        )
        self.copy_button.setIcon(load_icon("copy", p["muted"], 16))
        self.copy_button.setStyleSheet(button_qss)
        self.delete_button.setIcon(load_icon("trash", p["muted"], 16))
        self.delete_button.setStyleSheet(button_qss)


class HistoryPane(Pane):
    PANE_ID = "history"
    TITLE = "History"
    SUBTITLE = "Everything you have dictated."
    OWNS = frozenset()

    def __init__(self, ctx: PaneContext, parent=None) -> None:
        super().__init__(ctx, parent)
        self._entries: list[dict] = []
        self._query = ""
        self._limit = PAGE_SIZE
        self._rows: list[_EntryRow] = []

        _area, layout = pane_body(self)

        self._header = PaneHeader(self.TITLE, self.SUBTITLE)
        layout.addWidget(self._header)
        layout.addSpacing(6)

        top = QHBoxLayout()
        top.setSpacing(8)
        self._search_field = QLineEdit()
        self._search_field.setPlaceholderText("Search what you have said…")
        self._search_field.setFixedHeight(30)
        self._search_field.textChanged.connect(self._on_search_typed)
        top.addWidget(self._search_field, 1)

        self._clear_button = QPushButton("Clear all")
        self._clear_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_button.setFixedHeight(30)
        self._clear_button.clicked.connect(self.clear_all)
        top.addWidget(self._clear_button)
        layout.addLayout(top)

        # Typing one letter at a time should not run one query per letter.
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(SEARCH_DELAY_MS)
        self._search_timer.timeout.connect(self._run_search)

        self._empty = QLabel(EMPTY_MESSAGE)
        self._empty.setWordWrap(True)
        layout.addWidget(self._empty)

        self._rows_host = QWidget()
        self._rows_layout = QVBoxLayout(self._rows_host)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(8)
        layout.addWidget(self._rows_host)

        self._more_button = QPushButton("Show older")
        self._more_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._more_button.setFixedHeight(30)
        self._more_button.clicked.connect(self.load_more)
        self._more_button.setVisible(False)
        layout.addWidget(self._more_button)

        layout.addStretch(1)
        self.refresh()

    # ------------------------------------------------------------------

    def visible_rows(self) -> list[dict]:
        return list(self._entries)

    def row_widgets(self) -> list[_EntryRow]:
        return list(self._rows)

    def empty_message(self) -> str:
        return NO_MATCHES_MESSAGE if self._query else EMPTY_MESSAGE

    def has_more(self) -> bool:
        return self._more_button.isVisible()

    # ------------------------------------------------------------------

    def search(self, query: str) -> None:
        """Filter the list. Paging starts again from the top."""
        self._query = (query or "").strip()
        self._limit = PAGE_SIZE
        self._reload()

    def _on_search_typed(self, _text: str) -> None:
        self._search_timer.start()

    def _run_search(self) -> None:
        self.search(self._search_field.text())

    def load_more(self) -> None:
        self._limit += PAGE_SIZE
        self._reload()

    def copy_entry(self, entry_id: int) -> None:
        """Put the whole dictation on the clipboard, not the preview."""
        entry = next((e for e in self._entries if e["id"] == entry_id), None)
        if entry is None:
            return
        from PyQt6.QtWidgets import QApplication

        text = entry.get("cleaned_text") or entry.get("raw_text") or ""
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)

    def delete_entry(self, entry_id: int) -> None:
        self.ctx.history.delete(entry_id)
        self._reload()

    def confirm(self, message: str) -> bool:
        """Ask before something that cannot be undone."""
        answer = QMessageBox.question(
            self,
            "Delete everything?",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def clear_all(self) -> None:
        """Delete the whole history, once the user has said yes."""
        if not self.confirm(
            "This deletes every dictation Voxel has saved. It cannot be undone."
        ):
            return
        self.ctx.history.clear_all()
        self._reload()

    # ------------------------------------------------------------------

    def refresh(self) -> None:
        self._reload()

    def _reload(self) -> None:
        try:
            if self._query:
                entries = self.ctx.history.search(self._query, limit=self._limit + 1)
            else:
                entries = self.ctx.history.get_recent(limit=self._limit + 1)
        except Exception as e:
            logger.error("Could not read the history: %s", e)
            entries = []

        has_more = len(entries) > self._limit
        self._entries = entries[: self._limit]
        self._rebuild_rows()
        self._more_button.setVisible(has_more)
        self._empty.setText(self.empty_message())
        self._empty.setVisible(not self._entries)

    def _rebuild_rows(self) -> None:
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._rows = []

        palette = getattr(self, "_palette", None) or self.ctx.palette()
        for entry in self._entries:
            row = _EntryRow(entry, self.copy_entry, self.delete_entry)
            row.restyle(palette)
            self._rows.append(row)
            self._rows_layout.addWidget(row)

    # ------------------------------------------------------------------

    def restyle(self, palette: dict) -> None:
        self._palette = dict(palette)
        p = self._palette
        self.setStyleSheet(
            "QWidget#pane_inner, QScrollArea#pane_scroll {{"
            " background-color: {pane}; }}".format(**p)
        )
        self._header.restyle(p)
        self._empty.setStyleSheet(
            "color: {muted}; font-size: 12.5px; background: transparent;".format(**p)
        )
        self._search_field.setStyleSheet(
            "QLineEdit {{ color: {text}; background-color: {card_alt};"
            " border: 1px solid {row_border}; border-radius: 7px;"
            " padding: 4px 10px; font-size: 12.5px; }}"
            "QLineEdit:focus {{ border-color: {accent}; }}".format(**p)
        )
        button_qss = (
            "QPushButton {{ color: {text}; background-color: {card_alt};"
            " border: 1px solid {row_border}; border-radius: 7px;"
            " font-size: 12px; padding: 4px 14px; }}"
            "QPushButton:hover {{ border-color: {accent}; }}".format(**p)
        )
        self._clear_button.setStyleSheet(button_qss)
        self._more_button.setStyleSheet(button_qss)
        for row in self._rows:
            row.restyle(p)
