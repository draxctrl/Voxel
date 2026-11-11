"""The Language pane: what Voxel expects to hear."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.ui_pyqt6.panes.language import LANGUAGES, LanguagePane


class TestTheLanguageChoice:
    def test_auto_detect_is_offered_first(self, qapp, ctx):
        assert LANGUAGES[0][0] == "auto"

    def test_the_nine_languages_are_all_there(self, qapp, ctx):
        codes = {code for code, _ in LANGUAGES}
        assert {"en", "es", "fr", "de", "it", "pt", "ja", "ko", "zh"} <= codes

    def test_english_is_what_an_unconfigured_user_gets(self, qapp, ctx):
        pane = LanguagePane(ctx)
        pane.refresh()
        assert pane.selected_language() == "en"

    def test_the_saved_language_is_selected(self, qapp, ctx):
        ctx.config.set("language", "ja")
        pane = LanguagePane(ctx)
        pane.refresh()
        assert pane.selected_language() == "ja"

    def test_choosing_a_language_applies_it(self, qapp, ctx):
        pane = LanguagePane(ctx)
        pane.refresh()
        pane.choose("fr")
        assert ("language", "fr") in ctx.applied

    def test_a_language_voxel_does_not_offer_is_ignored(self, qapp, ctx):
        pane = LanguagePane(ctx)
        pane.refresh()
        pane.choose("xx")
        assert ctx.applied == []

    def test_a_saved_language_voxel_no_longer_offers_does_not_crash(self, qapp, ctx):
        ctx.config.set("language", "xx")
        pane = LanguagePane(ctx)
        pane.refresh()
        assert pane.selected_language() == "xx"
        assert ctx.applied == []


class TestThePaneDeclaresWhatItOwns:
    def test_it_owns_the_language(self):
        assert LanguagePane.OWNS == frozenset({"language"})


class TestTheFlagsActuallyLoad:
    """Windows draws flag emoji as letter pairs, so these are images. A
    resolver that quietly returns None costs every row its picture and
    nothing fails - which is how it shipped unnoticed."""

    def test_the_assets_directory_resolves(self):
        from src.ui_pyqt6.panes.language import _flags_dir

        directory = _flags_dir()
        assert directory is not None, "the flags directory was not found"
        assert os.path.isdir(os.path.join(directory, "flags"))

    def test_a_language_with_a_flag_gets_a_picture(self, qapp, ctx):
        pane = LanguagePane(ctx)
        assert pane.has_flag("en") is True

    def test_auto_detect_has_no_flag_and_that_is_fine(self, qapp, ctx):
        pane = LanguagePane(ctx)
        assert pane.has_flag("auto") is False
