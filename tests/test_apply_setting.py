"""Applying one setting restarts only what that setting affects.

The old settings window saved everything at once: reload the config,
restart the hotkey listener, rebuild the injector and reopen the
microphone stream. The new window has no Save button, so that happens on
every toggle unless each key knows what it costs.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import MagicMock, patch

import pytest

from src.config import Config


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def app(qapp, tmp_path):
    """A VoxelApp wired to a temp config, with OS-level parts faked."""
    from PyQt6.QtWidgets import QApplication as RealQApp
    import src.main as main_mod

    cfg = Config(config_path=str(tmp_path / "config.json"))

    fake_recorder = MagicMock()
    fake_recorder.active_device_name = "Realtek Mic"
    fake_recorder.requested_device_missing = False
    fake_recorder.is_recording = False

    with patch.object(main_mod, "QApplication", lambda *a, **k: RealQApp.instance()), \
         patch.object(main_mod, "Config", lambda *a, **k: cfg), \
         patch.object(main_mod, "MicRecorder", return_value=fake_recorder), \
         patch.object(main_mod, "TrayApp", return_value=MagicMock()), \
         patch.object(main_mod, "Groq", return_value=MagicMock()), \
         patch.object(main_mod, "HotkeyListener", return_value=MagicMock()):

        voxel = main_mod.VoxelApp()
        voxel._splash = MagicMock()
        voxel._overlay = MagicMock()
        voxel._settings_window = MagicMock()
        yield voxel


class TestOnlyWhatChangedIsRestarted:
    def test_a_checkbox_does_not_reopen_the_microphone(self, app):
        app._recorder.reset_mock()
        app.apply_setting("always_copy", False)
        assert not app._recorder.method_calls
        assert app._config.get("always_copy") is False

    def test_changing_the_microphone_reopens_the_stream(self, app):
        # The fixture hands back one recorder mock for every MicRecorder(),
        # so identity cannot prove a reopen. Closing the old stream can:
        # the checkbox test above proves close() is not called otherwise.
        app._recorder.reset_mock()
        app.apply_setting("mic_device_name", "Blue Yeti")
        app._recorder.close.assert_called_once()

    def test_changing_the_hotkey_restarts_the_listener(self, app):
        before = app._hotkey_listener
        app.apply_setting("hotkey", "<ctrl>+<alt>+v")
        assert app._hotkey_listener is not before

    def test_changing_the_hotkey_does_not_reopen_the_microphone(self, app):
        before = app._recorder
        app.apply_setting("hotkey", "<ctrl>+<alt>+v")
        assert app._recorder is before

    def test_changing_the_microphone_does_not_restart_the_listener(self, app):
        before = app._hotkey_listener
        app.apply_setting("mic_device", 3)
        assert app._hotkey_listener is before

    def test_the_activation_mode_restarts_the_listener(self, app):
        before = app._hotkey_listener
        app.apply_setting("activation_mode", "toggle")
        assert app._hotkey_listener is not before

    def test_the_recording_style_reaches_the_badge(self, app):
        app.apply_setting("recording_style", "waveform")
        app._overlay.set_style.assert_called_once_with("waveform")

    def test_the_recording_style_does_not_touch_audio_or_hotkeys(self, app):
        recorder, listener = app._recorder, app._hotkey_listener
        app.apply_setting("recording_style", "orb")
        assert app._recorder is recorder
        assert app._hotkey_listener is listener

    def test_a_new_api_key_rebuilds_the_cleaner(self, app):
        app._config.set("api_key", "gsk_a_fake_key")
        before = app._cleaner
        app.apply_setting("api_key", "gsk_another_fake_key")
        assert app._cleaner is not before

    def test_changing_the_style_reaches_the_cleaner_without_a_rebuild(self, app):
        app._config.set("api_key", "gsk_a_fake_key")
        app._init_groq()
        app._cleaner.set_prompt = MagicMock()
        app.apply_setting("active_profile", "raw")
        app._cleaner.set_prompt.assert_called_once()

    def test_muting_sounds_rebuilds_the_injector_only(self, app):
        recorder, listener = app._recorder, app._hotkey_listener
        before = app._injector
        app.apply_setting("mute_sound", True)
        assert app._injector is not before
        assert app._recorder is recorder
        assert app._hotkey_listener is listener

    def test_voice_commands_are_reloaded_in_place(self, app):
        app._voice_commands.reload = MagicMock()
        app.apply_setting("voice_commands", {"brb": "be right back"})
        app._voice_commands.reload.assert_called_once_with({"brb": "be right back"})


class TestEverySettingIsWrittenThrough:
    def test_the_value_reaches_the_config_file(self, app):
        app.apply_setting("language", "fr")
        reloaded = Config(config_path=app._config._path)
        reloaded.load()
        assert reloaded.get("language") == "fr"

    def test_a_setting_with_nothing_to_restart_is_still_saved(self, app):
        app.apply_setting("clipboard_notice", False)
        reloaded = Config(config_path=app._config._path)
        reloaded.load()
        assert reloaded.get("clipboard_notice") is False


class TestAFailedRestartDoesNotLoseTheSetting:
    def test_a_microphone_that_will_not_open_still_leaves_the_choice_saved(self, app):
        """Picking a device that then fails must not silently revert: the
        user would pick it again and watch nothing happen."""
        import src.main as main_mod

        with patch.object(main_mod, "MicRecorder", side_effect=OSError("no device")):
            app.apply_setting("mic_device_name", "Broken Mic")

        reloaded = Config(config_path=app._config._path)
        reloaded.load()
        assert reloaded.get("mic_device_name") == "Broken Mic"


class TestChangingTheThemeRestylesTheWholeWindow:
    """Review Focus 3. A theme change that reaches the rows but not the
    rail leaves a half-light, half-dark window - the exact thing this
    rebuild exists to kill."""

    def _window(self, app):
        app._build_settings_window()
        return app._settings_window

    def test_choosing_light_restyles_the_rail_too(self, app):
        from src.ui_pyqt6.theme import LIGHT

        window = self._window(app)
        app.apply_setting("theme", "light")
        assert "background-color: " + LIGHT["rail"] in window._rail.styleSheet()

    def test_choosing_light_restyles_the_window_surface(self, app):
        from src.ui_pyqt6.theme import LIGHT

        window = self._window(app)
        app.apply_setting("theme", "light")
        assert LIGHT["pane"] in window.styleSheet()

    def test_choosing_light_restyles_every_pane_not_only_the_visible_one(self, app):
        from src.ui_pyqt6.theme import LIGHT

        window = self._window(app)
        app.apply_setting("theme", "light")
        for pane in window.panes():
            assert LIGHT["pane"] in pane.styleSheet(), pane.PANE_ID

    def test_choosing_dark_again_puts_it_back(self, app):
        from src.ui_pyqt6.theme import DARK

        window = self._window(app)
        app.apply_setting("theme", "light")
        app.apply_setting("theme", "dark")
        assert "background-color: " + DARK["rail"] in window._rail.styleSheet()
