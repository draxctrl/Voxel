"""The Shortcuts pane: the push-to-talk key, undo, and how it activates."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.ui_pyqt6.panes.shortcuts import ShortcutsPane


class TestTheShortcutsAreShownAsWords:
    def test_the_saved_hotkey_is_readable(self, qapp, ctx):
        ctx.config.set("hotkey", "<ctrl>+<shift>+space")
        pane = ShortcutsPane(ctx)
        pane.refresh()
        assert pane.hotkey_text() == "Ctrl + Shift + Space"

    def test_there_is_no_undo_shortcut_row(self, qapp, ctx):
        """Undo sent a blind Ctrl+Z to whatever had focus and was removed
        from Voxel. Offering to set a shortcut for it would promise a
        feature that is not there."""
        assert not hasattr(ShortcutsPane(ctx), "_undo_row")


class TestTheActivationMode:
    def test_hold_and_toggle_are_the_two_choices(self, qapp, ctx):
        pane = ShortcutsPane(ctx)
        assert pane.mode_ids() == ("hold", "toggle")

    def test_the_copy_is_plain_english(self, qapp, ctx):
        titles = ShortcutsPane(ctx).mode_titles()
        assert titles["hold"] == "Hold to talk"
        assert titles["toggle"] == "Press to start, press to stop"

    def test_hold_is_what_an_unconfigured_user_gets(self, qapp, ctx):
        pane = ShortcutsPane(ctx)
        pane.refresh()
        assert pane.selected_mode() == "hold"

    def test_choosing_toggle_applies_it(self, qapp, ctx):
        ctx.config.set("hotkey", "<ctrl>+<shift>+space")
        pane = ShortcutsPane(ctx)
        pane.refresh()
        pane.choose_mode("toggle")
        assert ("activation_mode", "toggle") in ctx.applied


class TestAModifierOnlyHotkeyIsRejectedForToggleMode:
    """Ctrl+Shift alone cannot toggle: every Ctrl+Shift press anywhere would
    flip recording on and off. The old window caught this on save; with no
    save button it has to be caught at the moment of choosing."""

    def test_it_explains_rather_than_silently_failing(self, qapp, ctx):
        ctx.config.set("hotkey", "<ctrl>+<shift>")
        pane = ShortcutsPane(ctx)
        pane.refresh()
        pane.choose_mode("toggle")
        assert pane.warning_text() != ""
        assert "toggle" in pane.warning_text().lower()

    def test_the_mode_is_not_applied(self, qapp, ctx):
        ctx.config.set("hotkey", "<ctrl>+<shift>")
        pane = ShortcutsPane(ctx)
        pane.refresh()
        pane.choose_mode("toggle")
        assert ctx.applied == []
        assert pane.selected_mode() == "hold"

    def test_a_normal_combo_toggles_fine(self, qapp, ctx):
        ctx.config.set("hotkey", "<ctrl>+<shift>+space")
        pane = ShortcutsPane(ctx)
        pane.refresh()
        pane.choose_mode("toggle")
        assert pane.warning_text() == ""
        assert ("activation_mode", "toggle") in ctx.applied

    def test_setting_a_modifier_only_hotkey_while_in_toggle_mode_warns(self, qapp, ctx):
        ctx.config.set("activation_mode", "toggle")
        ctx.config.set("hotkey", "<ctrl>+<shift>+space")
        pane = ShortcutsPane(ctx)
        pane.refresh()
        pane.set_hotkey("<ctrl>+<alt>")
        assert pane.warning_text() != ""


class TestSettingAHotkey:
    def test_a_captured_combo_is_applied(self, qapp, ctx):
        pane = ShortcutsPane(ctx)
        pane.refresh()
        pane.set_hotkey("<ctrl>+<alt>+v")
        assert ("hotkey", "<ctrl>+<alt>+v") in ctx.applied
        assert pane.hotkey_text() == "Ctrl + Alt + V"

    def test_an_empty_capture_is_not_saved(self, qapp, ctx):
        ctx.config.set("hotkey", "<ctrl>+<shift>+space")
        pane = ShortcutsPane(ctx)
        pane.refresh()
        pane.set_hotkey("")
        assert ctx.applied == []


class TestThePaneDeclaresWhatItOwns:
    def test_it_owns_the_three_shortcut_keys(self):
        assert ShortcutsPane.OWNS == frozenset({"hotkey", "activation_mode"})
