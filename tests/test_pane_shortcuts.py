"""The Shortcuts pane: a push-to-talk key and a press-to-start key, both live."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.ui_pyqt6.panes.shortcuts import ShortcutsPane


def _pane(ctx, hotkey="<ctrl>+<alt>", toggle_hotkey=""):
    ctx.config.set("hotkey", hotkey)
    ctx.config.set("toggle_hotkey", toggle_hotkey)
    pane = ShortcutsPane(ctx)
    pane.refresh()
    return pane


class TestTheShortcutsAreShownAsWords:
    def test_both_keys_are_readable(self, qapp, ctx):
        pane = _pane(ctx, "<ctrl>+<shift>+space", "k")
        assert pane.key_text("hotkey") == "Ctrl + Shift + Space"
        assert pane.key_text("toggle_hotkey") == "K"

    def test_an_off_key_says_not_set(self, qapp, ctx):
        pane = _pane(ctx, "<ctrl>+<alt>", "")
        assert pane.key_text("toggle_hotkey") == "Not set"

    def test_there_is_no_undo_shortcut_row(self, qapp, ctx):
        """Undo sent a blind Ctrl+Z to whatever had focus and was removed
        from Voxel. Offering to set a shortcut for it would promise a
        feature that is not there."""
        assert not hasattr(ShortcutsPane(ctx), "_undo_row")

    def test_there_is_no_mode_choice_any_more(self, qapp, ctx):
        """Both keys are always live, so "How it activates" is gone."""
        assert not hasattr(ShortcutsPane(ctx), "_mode_rows")


class TestSettingEachKey:
    def test_setting_the_press_to_start_key_leaves_push_to_talk_alone(self, qapp, ctx):
        pane = _pane(ctx, "<ctrl>+<alt>", "")
        pane.set_key("toggle_hotkey", "k")
        assert ctx.applied == [("toggle_hotkey", "k")]
        assert ctx.config.get("hotkey") == "<ctrl>+<alt>"
        assert pane.warning_text() == ""

    def test_setting_push_to_talk(self, qapp, ctx):
        pane = _pane(ctx, "<ctrl>+<alt>", "k")
        pane.set_key("hotkey", "<ctrl>+<alt>+v")
        assert ctx.applied == [("hotkey", "<ctrl>+<alt>+v")]
        assert pane.key_text("hotkey") == "Ctrl + Alt + V"

    def test_an_empty_capture_is_not_saved(self, qapp, ctx):
        pane = _pane(ctx)
        pane.set_key("toggle_hotkey", "")
        assert ctx.applied == []

    def test_the_same_key_for_both_is_refused(self, qapp, ctx):
        pane = _pane(ctx, "<ctrl>+<alt>", "")
        pane.set_key("toggle_hotkey", "<alt>+<ctrl>")
        assert ctx.applied == []
        assert pane.warning_text() != ""
        assert pane.key_text("toggle_hotkey") == "Not set"

    def test_a_good_key_clears_an_old_warning(self, qapp, ctx):
        pane = _pane(ctx, "<ctrl>+<alt>", "")
        pane.set_key("toggle_hotkey", "<ctrl>+<alt>")
        pane.set_key("toggle_hotkey", "k")
        assert pane.warning_text() == ""


class TestTurningAKeyOff:
    def test_turning_off_the_press_to_start_key(self, qapp, ctx):
        pane = _pane(ctx, "<ctrl>+<alt>", "k")
        pane.turn_off("toggle_hotkey")
        assert ctx.applied == [("toggle_hotkey", "")]
        assert pane.key_text("toggle_hotkey") == "Not set"

    def test_turning_off_push_to_talk_when_the_other_is_set(self, qapp, ctx):
        pane = _pane(ctx, "<ctrl>+<alt>", "k")
        pane.turn_off("hotkey")
        assert ctx.applied == [("hotkey", "")]

    def test_the_last_key_cannot_be_turned_off(self, qapp, ctx):
        pane = _pane(ctx, "<ctrl>+<alt>", "")
        pane.turn_off("hotkey")
        assert ctx.applied == []
        assert pane.warning_text() != ""


class TestThePaneDeclaresWhatItOwns:
    def test_it_owns_both_shortcut_keys(self):
        assert ShortcutsPane.OWNS == frozenset({"hotkey", "toggle_hotkey"})


class TestKeysThatOnePressWouldSetOffTogether:
    def test_ctrl_space_and_ctrl_shift_space_are_refused(self, qapp, ctx):
        pane = _pane(ctx, "<ctrl>+space", "")
        pane.set_key("toggle_hotkey", "<ctrl>+<shift>+space")
        assert ctx.applied == []
        assert pane.warning_text() != ""

    def test_ctrl_alt_and_ctrl_alt_space_are_allowed(self, qapp, ctx):
        pane = _pane(ctx, "<ctrl>+<alt>", "")
        pane.set_key("toggle_hotkey", "<ctrl>+<alt>+space")
        assert ctx.applied == [("toggle_hotkey", "<ctrl>+<alt>+space")]
