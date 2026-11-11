"""The Appearance pane: the recording badge, and light or dark."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.ui_pyqt6.panes.appearance import AppearancePane


class TestTheThemeChoice:
    def test_the_three_choices_are_follow_windows_light_and_dark(self, qapp, ctx):
        pane = AppearancePane(ctx)
        assert pane.theme_ids() == ("system", "light", "dark")

    def test_follow_windows_is_the_default(self, qapp, ctx):
        pane = AppearancePane(ctx)
        pane.refresh()
        assert pane.selected_theme() == "system"

    def test_the_copy_names_windows_not_the_operating_system(self, qapp, ctx):
        assert AppearancePane(ctx).theme_titles()["system"] == "Follow Windows"

    def test_choosing_dark_applies_it_immediately(self, qapp, ctx):
        pane = AppearancePane(ctx)
        pane.refresh()
        pane.choose_theme("dark")
        assert ("theme", "dark") in ctx.applied
        assert pane.selected_theme() == "dark"

    def test_an_unknown_theme_is_ignored(self, qapp, ctx):
        pane = AppearancePane(ctx)
        pane.refresh()
        pane.choose_theme("solarized")
        assert ctx.applied == []


class TestTheRecordingBadge:
    def test_every_built_in_style_is_offered(self, qapp, ctx):
        from src.ui_pyqt6.recording_styles import RECORDING_STYLES

        assert set(AppearancePane(ctx).style_ids()) == set(RECORDING_STYLES)

    def test_the_saved_style_is_the_selected_one(self, qapp, ctx):
        ctx.config.set("recording_style", "island")
        pane = AppearancePane(ctx)
        pane.refresh()
        assert pane.selected_style() == "island"

    def test_the_shipped_default_is_what_an_unconfigured_user_sees(self, qapp, ctx):
        from src.ui_pyqt6.recording_styles import DEFAULT_STYLE

        pane = AppearancePane(ctx)
        pane.refresh()
        assert pane.selected_style() == DEFAULT_STYLE

    def test_choosing_a_style_applies_it(self, qapp, ctx):
        pane = AppearancePane(ctx)
        pane.refresh()
        pane.choose_style("waveform")
        assert ("recording_style", "waveform") in ctx.applied

    def test_a_style_that_does_not_exist_is_ignored(self, qapp, ctx):
        pane = AppearancePane(ctx)
        pane.refresh()
        pane.choose_style("fireworks")
        assert ctx.applied == []


class TestThePaneDeclaresWhatItOwns:
    def test_it_owns_the_theme_and_the_badge_style(self):
        assert AppearancePane.OWNS == frozenset({"theme", "recording_style"})
