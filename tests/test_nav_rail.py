"""The settings sidebar: grouped entries, selection, and the status footer."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from src.ui_pyqt6.nav_rail import NavRail
from src.ui_pyqt6.theme import palette_for


class TestTheRailListsEverySettingsPane:
    def test_every_pane_id_appears_once(self):
        ids = [pid for _, rows in NavRail.ENTRIES for pid, _, _ in rows]
        assert len(ids) == len(set(ids)) == 10

    def test_the_labels_are_in_plain_english(self):
        labels = {lbl for _, rows in NavRail.ENTRIES for _, lbl, _ in rows}
        assert "Writing style" in labels
        assert "Exactly what I said" not in labels  # that belongs on the pane
        assert "Dictation Mode" not in labels
        assert "Raw mode" not in labels

    def test_the_groups_are_the_four_the_design_fixes(self):
        assert [title for title, _ in NavRail.ENTRIES] == [
            "Dictation", "Your setup", "Your words", "App"
        ]

    def test_every_entry_names_an_icon_that_is_bundled(self):
        from src.ui_pyqt6.icons import ICON_NAMES
        for _, rows in NavRail.ENTRIES:
            for pid, _, icon_name in rows:
                assert icon_name in ICON_NAMES, f"{pid} wants {icon_name}"


class TestSelectingAnEntry:
    def test_clicking_an_entry_emits_its_pane_id(self, qapp):
        rail = NavRail()
        heard = []
        rail.selected.connect(heard.append)
        rail.entry_button("history").click()
        assert heard == ["history"]
        assert rail.current == "history"

    def test_select_moves_the_highlight_without_emitting(self, qapp):
        rail = NavRail()
        heard = []
        rail.selected.connect(heard.append)
        rail.select("stats")
        assert rail.current == "stats"
        assert heard == []

    def test_the_first_entry_is_selected_to_begin_with(self, qapp):
        assert NavRail().current == "writing_style"

    def test_selecting_an_unknown_pane_leaves_the_highlight_alone(self, qapp):
        rail = NavRail()
        rail.select("no_such_pane")
        assert rail.current == "writing_style"


class TestTheStatusFooterMirrorsTheApp:
    def test_each_state_has_its_own_word_and_colour(self, qapp):
        rail = NavRail()
        seen = set()
        for state in ("idle", "recording", "processing", "error"):
            rail.set_status(state, "Ctrl + Alt")
            seen.add((rail.status_text(), rail.status_colour()))
        assert len(seen) == 4

    def test_the_words_are_the_ones_the_design_fixes(self, qapp):
        rail = NavRail()
        for state, word in (("idle", "Ready"), ("recording", "Listening"),
                            ("processing", "Working"), ("error", "Problem")):
            rail.set_status(state, "Ctrl + Alt")
            assert rail.status_text().startswith(word)

    def test_the_footer_shows_the_users_own_shortcut(self, qapp):
        rail = NavRail()
        rail.set_status("idle", "Ctrl + Shift + Space")
        assert "Ctrl + Shift + Space" in rail.status_text()

    def test_an_unknown_state_does_not_crash_the_footer(self, qapp):
        """main.py owns these names; a new one must not take the window down."""
        rail = NavRail()
        rail.set_status("reticulating", "Ctrl + Alt")
        assert rail.status_text() != ""


class TestTheRailFollowsTheTheme:
    def test_restyling_repaints_the_rail_and_every_entry(self, qapp):
        rail = NavRail()
        rail.restyle(palette_for("dark"))
        dark_sheet = rail.styleSheet()
        rail.restyle(palette_for("light"))
        light_sheet = rail.styleSheet()
        # The rail's own background is the one thing that must follow the
        # palette. Asserting the dark hex is absent would not work: light's
        # active rail text is #16171a, which is also dark's rail colour.
        assert "background-color: " + palette_for("light")["rail"] in light_sheet
        assert "background-color: " + palette_for("dark")["rail"] not in light_sheet
        assert dark_sheet != light_sheet

    def test_the_status_colour_survives_a_restyle(self, qapp):
        rail = NavRail()
        rail.set_status("recording", "Ctrl + Alt")
        before = rail.status_colour()
        rail.restyle(palette_for("light"))
        assert rail.status_colour() == before


class TestTheRailIsTheWidthTheDesignFixes:
    def test_it_is_fixed_at_198_pixels(self, qapp):
        rail = NavRail()
        assert rail.width() == 198
        assert rail.minimumWidth() == rail.maximumWidth() == 198


class TestTheRailFitsTheSmallestWindow:
    """The window may be resized down to 560px tall. A rail whose own
    minimum is taller than that clips its footer - exactly the bug that
    got through the mockups, where ten entries outgrew the window."""

    WINDOW_MIN_HEIGHT = 560

    def test_the_rail_fits_at_the_minimum_window_height(self, qapp):
        rail = NavRail()
        assert rail.minimumSizeHint().height() <= self.WINDOW_MIN_HEIGHT

    def test_the_footer_is_still_visible_when_squeezed(self, qapp):
        rail = NavRail()
        rail.set_status("idle", "Ctrl + Alt")
        rail.resize(198, self.WINDOW_MIN_HEIGHT)
        rail.show()
        qapp.processEvents()
        footer_bottom = rail._status.y() + rail._status.height()
        assert footer_bottom <= self.WINDOW_MIN_HEIGHT, (
            "the status footer is pushed off the bottom at the minimum height"
        )
        assert rail._status.y() > rail.entry_button("about").y(), (
            "the footer is not below the last entry"
        )


class TestTheFooterFitsTheRail:
    """The shipped default shortcut is Ctrl + Shift + Space, which is wider
    than the rail. It must wrap or shrink, not run off the edge."""

    def test_the_longest_shortcut_stays_inside_the_rail(self, qapp):
        from src.ui_pyqt6.nav_rail import RAIL_WIDTH

        rail = NavRail()
        rail.set_status("idle", "Ctrl + Shift + Space")
        rail.resize(RAIL_WIDTH, 620)
        rail.show()
        qapp.processEvents()
        label = rail._status
        needed = label.fontMetrics().horizontalAdvance(label.text())
        assert label.wordWrap() or needed <= label.width(), (
            "the shortcut is wider than the footer label and will be clipped"
        )
