"""The General pane, and the promise that every setting has exactly one home."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.config import DEFAULT_CONFIG
from src.ui_pyqt6.panes import all_panes
from src.ui_pyqt6.panes.general import GeneralPane

class TestEverySettingHasAHome:
    # The "nothing is orphaned" half of this invariant lives in
    # tests/test_pane_voice_commands.py, with the last pane that has to
    # exist before it can hold.

    def test_no_pane_claims_a_setting_that_does_not_exist(self):
        """A pane owning a key the config never defines writes a setting
        nothing reads back."""
        for pane in all_panes():
            for key in pane.OWNS:
                assert key in DEFAULT_CONFIG, f"{pane.PANE_ID} owns unknown {key}"


class TestTheConfigDefaultsMatchTheUI:
    def test_always_copy_and_clipboard_notice_have_defaults(self):
        assert "always_copy" in DEFAULT_CONFIG
        assert "clipboard_notice" in DEFAULT_CONFIG

    def test_the_defaults_are_what_voxel_already_did(self):
        """These two were read with inline defaults before they existed in
        DEFAULT_CONFIG. Writing a different value here would change what a
        new install does, which this rebuild is not for."""
        assert DEFAULT_CONFIG["always_copy"] is False
        assert DEFAULT_CONFIG["clipboard_notice"] is True

    def test_the_theme_follows_windows_by_default(self):
        assert DEFAULT_CONFIG["theme"] == "system"

    def test_there_is_no_undo_hotkey_setting(self):
        """It was removed from Voxel; a default here would reintroduce a
        key nothing reads."""
        assert "undo_hotkey" not in DEFAULT_CONFIG


class TestTheApiKeyIsNotLeaked:
    def test_the_field_is_masked_until_revealed(self, qapp, ctx):
        from PyQt6.QtWidgets import QLineEdit

        pane = GeneralPane(ctx)
        pane.refresh()
        assert pane.key_field().echoMode() == QLineEdit.EchoMode.Password
        pane.toggle_key_visible()
        assert pane.key_field().echoMode() == QLineEdit.EchoMode.Normal

    def test_the_key_is_not_in_any_label_on_the_pane(self, qapp, ctx):
        from PyQt6.QtWidgets import QLabel

        ctx.config.set("api_key", "gsk_a_secret_value")
        pane = GeneralPane(ctx)
        pane.refresh()
        for label in pane.findChildren(QLabel):
            assert "gsk_a_secret_value" not in label.text()


class TestSavingTheApiKey:
    def test_a_key_is_applied_when_saved(self, qapp, ctx):
        pane = GeneralPane(ctx)
        pane.refresh()
        pane.key_field().setText("gsk_a_new_key")
        pane.save_key()
        assert ("api_key", "gsk_a_new_key") in ctx.applied

    def test_whitespace_around_a_pasted_key_is_trimmed(self, qapp, ctx):
        pane = GeneralPane(ctx)
        pane.refresh()
        pane.key_field().setText("  gsk_padded_key\n")
        pane.save_key()
        assert ("api_key", "gsk_padded_key") in ctx.applied

    def test_an_empty_field_does_not_wipe_a_working_key(self, qapp, ctx):
        ctx.config.set("api_key", "gsk_existing")
        pane = GeneralPane(ctx)
        pane.refresh()
        pane.key_field().setText("")
        pane.save_key()
        assert ctx.applied == []
        assert ctx.config.get("api_key") == "gsk_existing"


class TestTheSwitches:
    def test_each_switch_reads_its_saved_value(self, qapp, ctx):
        ctx.config.set("auto_start", True)
        ctx.config.set("mute_sound", True)
        pane = GeneralPane(ctx)
        pane.refresh()
        assert pane.switch("auto_start").isChecked() is True
        assert pane.switch("mute_sound").isChecked() is True

    def test_flipping_a_switch_applies_that_key(self, qapp, ctx):
        pane = GeneralPane(ctx)
        pane.refresh()
        pane.switch("auto_profile").setChecked(True)
        assert ("auto_profile", True) in ctx.applied

    def test_refreshing_applies_nothing(self, qapp, ctx):
        ctx.config.set("mute_sound", True)
        pane = GeneralPane(ctx)
        pane.refresh()
        pane.refresh()
        assert ctx.applied == []


class TestThePaneDeclaresWhatItOwns:
    def test_it_owns_the_app_wide_settings(self):
        assert GeneralPane.OWNS == frozenset(
            {
                "api_key",
                "auto_start",
                "always_copy",
                "clipboard_notice",
                "mute_sound",
                "auto_profile",
            }
        )


class TestTheGroqLinkIsStyled:
    def test_it_carries_the_accent_colour_rather_than_qt_default_blue(self, qapp, ctx):
        from src.ui_pyqt6.theme import palette_for

        p = palette_for("dark")
        pane = GeneralPane(ctx)
        pane.restyle(p)
        assert p["accent"] in pane._get_key_link.text()
