"""The Stats pane: three numbers, and no mystery about where they come from."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from src.ui_pyqt6.panes.stats import TYPING_WPM, StatsPane, format_time_saved


def _add_words(ctx, words, times=1):
    """Dictations whose cleaned text has `words` words each."""
    text = " ".join(["word"] * words)
    for _ in range(times):
        ctx.history.add(text, text, "en", 1.0, profile="raw")


class TestThreeNumbersNotSeven:
    def test_the_pane_shows_exactly_three_figures(self, qapp, ctx):
        assert len(StatsPane(ctx).figures()) == 3

    def test_they_are_words_time_saved_and_this_week(self, qapp, ctx):
        assert set(StatsPane(ctx).figures()) == {"words", "time_saved", "this_week"}

    def test_streaks_are_not_advertised(self, qapp, ctx):
        """The old settings row promised streaks; history.py never had them."""
        pane = StatsPane(ctx)
        pane.refresh()
        assert "streak" not in " ".join(pane.all_text()).lower()


class TestTheNumbers:
    def test_words_dictated_is_the_total(self, qapp, ctx):
        _add_words(ctx, 10, times=3)
        pane = StatsPane(ctx)
        pane.refresh()
        assert pane.figures()["words"] == "30"

    def test_a_big_number_is_grouped_so_it_can_be_read(self, qapp, ctx):
        _add_words(ctx, 500, times=5)
        pane = StatsPane(ctx)
        pane.refresh()
        assert pane.figures()["words"] == "2,500"

    def test_time_saved_is_derived_from_words_at_40wpm(self, qapp, ctx):
        _add_words(ctx, 500, times=8)  # 4000 words
        pane = StatsPane(ctx)
        pane.refresh()
        assert pane.figures()["time_saved"] == "1h 40m"

    def test_this_week_counts_recent_dictations(self, qapp, ctx):
        _add_words(ctx, 5, times=4)
        pane = StatsPane(ctx)
        pane.refresh()
        assert pane.figures()["this_week"] == "4"

    def test_the_typing_speed_is_stated_rather_than_assumed(self, qapp, ctx):
        pane = StatsPane(ctx)
        pane.refresh()
        assert str(TYPING_WPM) in " ".join(pane.all_text())


class TestFormattingTimeSaved:
    @pytest.mark.parametrize("words,expected", [
        (0, "0m"),
        (40, "1m"),
        (2400, "1h"),
        (4000, "1h 40m"),
        (39, "0m"),
        (96000, "40h"),
    ])
    def test_minutes_and_hours_read_naturally(self, words, expected):
        assert format_time_saved(words) == expected


class TestAnEmptyHistory:
    def test_it_shows_zeroes_rather_than_an_error(self, qapp, ctx):
        pane = StatsPane(ctx)
        pane.refresh()
        assert pane.figures() == {"words": "0", "time_saved": "0m", "this_week": "0"}

    def test_a_history_that_cannot_be_read_still_renders(self, qapp, ctx):
        class BrokenHistory:
            def total_words(self):
                raise OSError("database is locked")

            def week_count(self):
                raise OSError("database is locked")

        ctx.history = BrokenHistory()
        pane = StatsPane(ctx)
        pane.refresh()
        assert pane.figures()["words"] == "0"


class TestThePaneDeclaresWhatItOwns:
    def test_it_owns_no_settings(self):
        assert StatsPane.OWNS == frozenset()
