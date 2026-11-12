"""The splash screen: the first thing anyone sees of Voxel."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QLabel

from src.ui_pyqt6.splash import SplashScreen


class TestNothingOnItIsABrokenGlyph:
    def test_the_title_is_text_not_an_emoji(self, qapp):
        """Windows draws an emoji in a text font as an empty box. The title
        read "[tofu] Voxel" on every machine without an emoji fallback."""
        splash = SplashScreen()
        for label in splash.findChildren(QLabel):
            for char in label.text():
                point = ord(char)
                # Emoji and pictographs. Typographic marks such as an
                # ellipsis are fine; a microphone emoji is not.
                assert not (0x2600 <= point <= 0x27BF), label.text()
                assert point < 0x1F000, (
                    f"{label.text()!r} contains an emoji the UI font cannot draw"
                )

    def test_the_mark_is_the_app_icon(self, qapp):
        splash = SplashScreen()
        assert splash.logo_is_shown() is True


class TestTheProgressBarDoesNotCrossTheText:
    def test_the_bar_sits_clear_of_the_status_line(self, qapp):
        splash = SplashScreen()
        splash.show()
        qapp.processEvents()
        bar_top, bar_bottom = splash.progress_band()
        status = splash._status_label
        assert status.y() + status.height() <= bar_top or status.y() >= bar_bottom, (
            "the progress bar is painted through the status text"
        )


class TestItShowsTheUsersOwnShortcut:
    def test_the_hint_names_the_shortcut_it_was_given(self, qapp):
        splash = SplashScreen(shortcut="Ctrl + Alt")
        assert "Ctrl + Alt" in splash.hint_text()

    def test_without_one_it_does_not_invent_a_shortcut(self, qapp):
        """Claiming Ctrl + Shift + Space to someone who set Ctrl + Alt is
        worse than saying nothing."""
        splash = SplashScreen()
        assert "Ctrl + Shift + Space" not in splash.hint_text()


class TestItFollowsTheTheme:
    def test_it_uses_palette_colours_rather_than_its_own(self, qapp):
        import inspect
        import re

        import src.ui_pyqt6.splash as splash_mod

        source = inspect.getsource(splash_mod)
        found = re.findall(r"#[0-9a-fA-F]{6}", source)
        assert found == [], f"hard-coded colours: {found}"

    def test_the_status_text_is_readable(self, qapp):
        from src.ui_pyqt6.theme import DARK

        splash = SplashScreen()
        assert DARK["muted"] in splash._status_label.styleSheet()
