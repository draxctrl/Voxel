"""The Writing style pane: three everyday choices, the rest behind a link."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.ui_pyqt6.panes.writing_style import WritingStylePane


class TestTheThreeEverydayStylesAreUpFront:
    def test_the_headline_rows_are_these_three_in_this_order(self, qapp, ctx):
        assert WritingStylePane(ctx).headline_ids() == (
            "grammar_only",
            "grammar_tidy",
            "raw",
        )

    def test_the_copy_is_the_plain_english_the_design_fixes(self, qapp, ctx):
        pane = WritingStylePane(ctx)
        titles = pane.headline_titles()
        assert titles["grammar_only"] == "Grammar only"
        assert titles["grammar_tidy"] == "Tidy up"
        assert titles["raw"] == "Exactly what I said"
        assert "Raw" not in " ".join(titles.values())
        assert "Dictation Mode" not in " ".join(titles.values())

    def test_each_headline_row_explains_itself_in_one_line(self, qapp, ctx):
        for text in WritingStylePane(ctx).headline_subtitles().values():
            assert text and len(text) < 80


class TestAStyleThatIsNotAHeadlineIsNotLost:
    def test_a_hidden_builtin_shows_as_selected_under_more_styles(self, qapp, ctx):
        ctx.config.set("active_profile", "professional")
        pane = WritingStylePane(ctx)
        pane.refresh()
        assert pane.selected_id() == "professional"
        assert pane.more_styles_is_open() is True

    def test_a_custom_profile_shows_as_selected_under_more_styles(self, qapp, ctx):
        ctx.profiles.add_profile("my_style", "My style", "Do it my way")
        ctx.config.set("active_profile", "my_style")
        pane = WritingStylePane(ctx)
        pane.refresh()
        assert pane.selected_id() == "my_style"
        assert pane.more_styles_is_open() is True

    def test_opening_the_pane_never_rewrites_the_active_profile(self, qapp, ctx):
        ctx.config.set("active_profile", "technical")
        WritingStylePane(ctx).refresh()
        assert ctx.config.get("active_profile") == "technical"
        assert ctx.applied == []

    def test_more_styles_lists_every_profile_that_is_not_a_headline(self, qapp, ctx):
        ctx.profiles.add_profile("my_style", "My style", "Do it my way")
        pane = WritingStylePane(ctx)
        pane.refresh()
        listed = set(pane.more_style_ids())
        assert listed == {"professional", "code", "technical", "my_style"}

    def test_more_styles_starts_closed_for_a_headline_style(self, qapp, ctx):
        ctx.config.set("active_profile", "grammar_tidy")
        pane = WritingStylePane(ctx)
        pane.refresh()
        assert pane.more_styles_is_open() is False


class TestChoosingAStyleAppliesIt:
    def test_clicking_a_row_applies_that_profile_id(self, qapp, ctx):
        pane = WritingStylePane(ctx)
        pane.refresh()
        pane.choose("raw")
        assert ctx.applied == [("active_profile", "raw")]

    def test_choosing_a_hidden_style_applies_it_too(self, qapp, ctx):
        pane = WritingStylePane(ctx)
        pane.refresh()
        pane.choose("professional")
        assert ctx.applied == [("active_profile", "professional")]
        assert pane.selected_id() == "professional"

    def test_choosing_a_style_that_does_not_exist_changes_nothing(self, qapp, ctx):
        pane = WritingStylePane(ctx)
        pane.refresh()
        pane.choose("not_a_profile")
        assert ctx.applied == []


class TestWorkingOffline:
    def test_the_switch_reads_the_saved_setting(self, qapp, ctx):
        ctx.config.set("offline_mode", True)
        pane = WritingStylePane(ctx)
        pane.refresh()
        assert pane.offline_switch().isChecked() is True

    def test_turning_it_on_applies_offline_mode(self, qapp, ctx):
        pane = WritingStylePane(ctx)
        pane.refresh()
        pane.offline_switch().setChecked(True)
        assert ("offline_mode", True) in ctx.applied

    def test_refreshing_does_not_apply_anything(self, qapp, ctx):
        """Setting a switch programmatically must not read as a user click."""
        ctx.config.set("offline_mode", True)
        pane = WritingStylePane(ctx)
        pane.refresh()
        pane.refresh()
        assert ctx.applied == []


class TestThePaneDeclaresWhatItOwns:
    def test_it_owns_the_style_and_the_offline_switch(self, qapp, ctx):
        assert WritingStylePane.OWNS == frozenset({"active_profile", "offline_mode"})
