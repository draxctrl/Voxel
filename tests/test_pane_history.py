"""The History pane: everything the History window did, inside the window."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import Qt

from src.ui_pyqt6.panes.history import PAGE_SIZE, HistoryPane


def _fill(ctx, count, prefix="dictation"):
    for i in range(count):
        ctx.history.add(
            "%s %d raw" % (prefix, i),
            "%s %d" % (prefix, i),
            "en",
            1.0,
            profile="raw",
        )


class TestTheHistoryPaneKeepsWhatTheWindowCouldDo:
    def test_entries_are_listed_newest_first(self, qapp, ctx):
        _fill(ctx, 3)
        pane = HistoryPane(ctx)
        pane.refresh()
        texts = [row["cleaned_text"] for row in pane.visible_rows()]
        assert texts == ["dictation 2", "dictation 1", "dictation 0"]

    def test_an_empty_history_says_so(self, qapp, ctx):
        pane = HistoryPane(ctx)
        pane.refresh()
        assert pane.visible_rows() == []
        assert pane.empty_message() != ""

    def test_search_filters_the_list(self, qapp, ctx):
        ctx.history.add("grocery raw", "buy milk", "en", 1.0, profile="raw")
        ctx.history.add("email raw", "dear sir", "en", 1.0, profile="raw")
        pane = HistoryPane(ctx)
        pane.refresh()
        pane.search("milk")
        assert [r["cleaned_text"] for r in pane.visible_rows()] == ["buy milk"]

    def test_clearing_the_search_brings_everything_back(self, qapp, ctx):
        _fill(ctx, 3)
        pane = HistoryPane(ctx)
        pane.refresh()
        pane.search("dictation 1")
        pane.search("")
        assert len(pane.visible_rows()) == 3

    def test_a_search_that_matches_nothing_says_so(self, qapp, ctx):
        _fill(ctx, 3)
        pane = HistoryPane(ctx)
        pane.refresh()
        pane.search("zzzz-no-match")
        assert pane.visible_rows() == []
        assert pane.empty_message() != ""

    def test_copy_puts_the_text_on_the_clipboard(self, qapp, ctx):
        ctx.history.add("raw", "the cleaned text", "en", 1.0, profile="raw")
        pane = HistoryPane(ctx)
        pane.refresh()
        pane.copy_entry(pane.visible_rows()[0]["id"])
        assert qapp.clipboard().text() == "the cleaned text"

    def test_delete_removes_one_entry(self, qapp, ctx):
        _fill(ctx, 3)
        pane = HistoryPane(ctx)
        pane.refresh()
        pane.delete_entry(pane.visible_rows()[0]["id"])
        assert len(pane.visible_rows()) == 2
        assert ctx.history.count() == 2

    def test_clear_all_asks_first(self, qapp, ctx):
        _fill(ctx, 3)
        pane = HistoryPane(ctx)
        pane.refresh()
        asked = []
        pane.confirm = lambda message: asked.append(message) or False
        pane.clear_all()
        assert asked, "clearing everything did not ask"
        assert ctx.history.count() == 3, "it cleared without a yes"

    def test_clear_all_clears_when_confirmed(self, qapp, ctx):
        _fill(ctx, 3)
        pane = HistoryPane(ctx)
        pane.refresh()
        pane.confirm = lambda message: True
        pane.clear_all()
        assert ctx.history.count() == 0
        assert pane.visible_rows() == []


class TestALargeHistoryStaysUsable:
    def test_two_thousand_entries_render_within_a_page(self, qapp, ctx):
        _fill(ctx, 2000)
        pane = HistoryPane(ctx)
        pane.refresh()
        assert len(pane.visible_rows()) <= PAGE_SIZE
        assert PAGE_SIZE <= 100

    def test_more_can_be_loaded(self, qapp, ctx):
        _fill(ctx, PAGE_SIZE + 20)
        pane = HistoryPane(ctx)
        pane.refresh()
        first = len(pane.visible_rows())
        pane.load_more()
        assert len(pane.visible_rows()) > first

    def test_there_is_nothing_more_to_load_on_a_short_history(self, qapp, ctx):
        _fill(ctx, 3)
        pane = HistoryPane(ctx)
        pane.refresh()
        assert pane.has_more() is False

    def test_a_very_long_entry_does_not_stretch_the_window(self, qapp, ctx):
        from src.ui_pyqt6.panes.widgets import CONTENT_MAX_WIDTH

        ctx.history.add("x" * 4000, "y" * 4000, "en", 1.0, profile="raw")
        pane = HistoryPane(ctx)
        pane.restyle(ctx.palette())
        pane.refresh()
        assert pane.sizeHint().width() <= CONTENT_MAX_WIDTH + 120

    def test_a_very_long_entry_is_shortened_on_screen(self, qapp, ctx):
        ctx.history.add("x" * 4000, "y" * 4000, "en", 1.0, profile="raw")
        pane = HistoryPane(ctx)
        pane.refresh()
        shown = pane.row_widgets()[0].shown_text()
        assert len(shown) < 4000
        assert shown.endswith("…")

    def test_copying_a_shortened_entry_copies_all_of_it(self, qapp, ctx):
        """What is on screen is shortened; what you copy must not be."""
        ctx.history.add("x" * 4000, "y" * 4000, "en", 1.0, profile="raw")
        pane = HistoryPane(ctx)
        pane.refresh()
        pane.copy_entry(pane.visible_rows()[0]["id"])
        assert qapp.clipboard().text() == "y" * 4000


class TestThePaneDeclaresWhatItOwns:
    def test_it_owns_no_settings(self):
        assert HistoryPane.OWNS == frozenset()


class TestTheTimeLinesUpWithTheText:
    """A time pinned to the top of the row while the text floats in the
    middle reads as two columns that do not belong together."""

    def test_the_time_and_the_first_line_share_a_top_edge(self, qapp, ctx):
        ctx.history.add("raw", "I have a car.", "en", 1.0, profile="raw")
        pane = HistoryPane(ctx)
        pane.restyle(ctx.palette())
        pane.refresh()
        row = pane.row_widgets()[0]
        row.resize(700, row.sizeHint().height())
        row.show()
        qapp.processEvents()
        # Both labels occupy the same box; what differs is where the text
        # sits inside it, so the alignment flag is the thing to check.
        assert row._text.alignment() & Qt.AlignmentFlag.AlignTop, (
            "the text is centred in its box while the time is at the top"
        )
        assert row._when.alignment() & Qt.AlignmentFlag.AlignTop

    def test_a_wrapped_entry_still_starts_level_with_its_time(self, qapp, ctx):
        ctx.history.add("raw", "word " * 60, "en", 1.0, profile="raw")
        pane = HistoryPane(ctx)
        pane.restyle(ctx.palette())
        pane.refresh()
        row = pane.row_widgets()[0]
        row.resize(700, row.sizeHint().height())
        row.show()
        qapp.processEvents()
        assert row._text.alignment() & Qt.AlignmentFlag.AlignTop
        assert row._when.y() == row._text.y()
