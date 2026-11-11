"""The settings window shell: the rail, the pane stack, and restyling."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from src.ui_pyqt6.nav_rail import NavRail
from src.ui_pyqt6.settings_window import SettingsWindow
from src.ui_pyqt6.theme import palette_for

ALL_PANE_IDS = [pid for _, rows in NavRail.ENTRIES for pid, _, _ in rows]


class TestTheWindowHasAPaneForEveryRailEntry:
    def test_no_rail_entry_leads_nowhere(self, qapp, ctx):
        win = SettingsWindow(ctx)
        for pane_id in ALL_PANE_IDS:
            win.show_pane(pane_id)
            assert win.current_pane().PANE_ID == pane_id

    def test_clicking_the_rail_changes_the_pane(self, qapp, ctx):
        win = SettingsWindow(ctx)
        win._rail.entry_button("stats").click()
        assert win.current_pane().PANE_ID == "stats"

    def test_showing_a_pane_moves_the_rail_highlight_too(self, qapp, ctx):
        win = SettingsWindow(ctx)
        win.show_pane("about")
        assert win._rail.current == "about"

    def test_an_unknown_pane_id_is_ignored_not_fatal(self, qapp, ctx):
        win = SettingsWindow(ctx)
        before = win.current_pane().PANE_ID
        win.show_pane("no_such_pane")
        assert win.current_pane().PANE_ID == before

    def test_showing_a_pane_refreshes_it_first(self, qapp, ctx):
        win = SettingsWindow(ctx)
        pane = win.pane("history")
        calls = []
        pane.refresh = lambda: calls.append(1)
        win.show_pane("history")
        assert calls == [1]


class TestTheWindowIsSizedForTheSidebarLayout:
    def test_it_opens_at_the_designed_size_and_can_be_resized(self, qapp, ctx):
        win = SettingsWindow(ctx)
        assert (win.width(), win.height()) == (980, 620)
        assert (win.minimumWidth(), win.minimumHeight()) == (860, 560)
        assert win.maximumWidth() > 980  # not setFixedSize

    def test_nothing_is_clipped_at_the_minimum_size(self, qapp, ctx):
        win = SettingsWindow(ctx)
        assert win.minimumSizeHint().width() <= 860
        assert win.minimumSizeHint().height() <= 560


class TestASystemThemeChangeRestylesEverything:
    def test_every_pane_and_the_rail_are_restyled_together(self, qapp, ctx):
        win = SettingsWindow(ctx)
        restyled = []
        for pane in win.panes():
            pane.restyle = lambda p, _n=pane.PANE_ID: restyled.append(_n)
        rail_seen = []
        win._rail.restyle = lambda p: rail_seen.append(p)
        win.restyle(palette_for("light"))
        assert set(restyled) == {p.PANE_ID for p in win.panes()}
        assert len(rail_seen) == 1

    def test_the_window_itself_takes_the_new_surface(self, qapp, ctx):
        win = SettingsWindow(ctx)
        win.restyle(palette_for("light"))
        assert palette_for("light")["pane"] in win.styleSheet()
        win.restyle(palette_for("dark"))
        assert palette_for("dark")["pane"] in win.styleSheet()


class TestTheStatusReachesTheRail:
    def test_set_status_uses_the_users_own_shortcut(self, qapp, ctx):
        ctx.config.set("hotkey", "ctrl+alt")
        win = SettingsWindow(ctx)
        win.set_status("recording")
        assert win._rail.status_text().startswith("Listening")
        assert "Ctrl + Alt" in win._rail.status_text()


class TestEveryPaneDeclaresWhatItOwns:
    def test_each_pane_has_an_owns_set(self, qapp, ctx):
        for pane in SettingsWindow(ctx).panes():
            assert isinstance(pane.OWNS, frozenset)

    def test_no_two_panes_claim_the_same_setting(self, qapp, ctx):
        seen: dict[str, str] = {}
        for pane in SettingsWindow(ctx).panes():
            for key in pane.OWNS:
                assert key not in seen, f"{key} is on {seen.get(key)} and {pane.PANE_ID}"
                seen[key] = pane.PANE_ID


class TestThePaneRegistry:
    def test_all_panes_lists_a_class_per_rail_entry(self):
        from src.ui_pyqt6.panes import all_panes
        assert {p.PANE_ID for p in all_panes()} == set(ALL_PANE_IDS)
