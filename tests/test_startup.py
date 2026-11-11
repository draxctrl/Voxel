"""Walks VoxelApp's real startup sequence with fakes for the OS-level parts.

This exists because a method was deleted while its call sites survived: the
module still imported, all unit tests still passed, and the app aborted inside
a Qt slot the moment a configured user launched it. Import checks don't catch
that; running the startup chain does.

The global hotkey listener and the tray are stubbed — registering a real
system-wide hook during tests would fight the installed copy of Voxel.
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
    """A VoxelApp wired to a temp config, with OS-level collaborators faked."""
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


class TestStartupChain:
    def test_startup_completes_for_a_configured_user(self, app):
        """The path a real user with an API key takes. This aborted before."""
        app._config.set("api_key", "gsk_fake_key_for_test")

        app._startup_stage_1()
        app._startup_stage_2()
        app._startup_stage_3()
        app._startup_finish()   # calls _report_mic_fallback

        # Reaching here without an exception is the assertion.
        assert app._config.get("api_key") == "gsk_fake_key_for_test"

    def test_startup_completes_without_an_api_key(self, app):
        app._config.set("api_key", "")

        app._startup_stage_1()
        app._startup_stage_2()

        assert app._config.get("api_key") == ""

    def test_a_working_microphone_is_not_announced_on_the_badge(self, app):
        """The badge is what you look at while you talk. Naming the device
        there every time is noise; it only earns its place as a warning."""
        app._report_mic_fallback()

        shown = [c[0][0] for c in app._overlay.set_mic_text.call_args_list]
        assert all("Realtek Mic" not in text for text in shown), (
            f"the badge was told to show the device name: {shown}"
        )

    def test_a_working_microphone_is_still_backfilled(self, app):
        """Dropping the badge line must not drop the backfill, which is what
        stops a renumbered device silently moving the user to another mic."""
        from unittest.mock import patch
        with patch.object(app._config, "backfill_mic_name") as backfill:
            app._report_mic_fallback()
        backfill.assert_called_once_with("Realtek Mic")

    def test_report_mic_fallback_warns_when_device_missing(self, app):
        app._recorder.requested_device_missing = True
        app._config.set("mic_device_name", "Blue Yeti")

        app._report_mic_fallback()

        message = app._overlay.set_mic_text.call_args[0][0]
        assert "Blue Yeti" in message
        assert "not found" in message

    def test_the_microphone_pane_says_so_too(self, app):
        """The old settings window was pushed a warning. The pane reads the
        same config the recorder did and says it for itself."""
        app._build_settings_window()
        app._config.set("mic_device_name", "Blue Yeti")
        pane = app._settings_window.pane("microphone")
        pane.refresh()
        assert "Blue Yeti" in pane.warning_text()

    def test_there_is_no_save_everything_path_any_more(self, app):
        """Settings apply one at a time through apply_setting, which
        tests/test_apply_setting.py covers. A surviving _on_settings_saved
        would be a second route that restarts the whole app on a toggle."""
        assert not hasattr(app, "_on_settings_saved")


class TestOverlayIsWiredToTheLiveRecorder:
    """The recording animation is only honest if it reads the microphone that
    is actually recording — and applying a microphone setting replaces the
    recorder."""

    def test_the_overlay_is_built_with_the_configured_style(self, qapp, tmp_path):
        from unittest.mock import MagicMock, patch
        from PyQt6.QtWidgets import QApplication as RealQApp
        import src.main as main_mod

        cfg = Config(config_path=str(tmp_path / "config.json"))
        cfg.load()
        cfg.set("recording_style", "island")
        # VoxelApp reloads the config at startup, so it has to be on disk.
        cfg.save()

        fake_recorder = MagicMock()
        fake_recorder.current_level.return_value = 0.4
        with patch.object(main_mod, "QApplication", lambda *a, **k: RealQApp.instance()), \
             patch.object(main_mod, "Config", lambda *a, **k: cfg), \
             patch.object(main_mod, "MicRecorder", return_value=fake_recorder), \
             patch.object(main_mod, "TrayApp", return_value=MagicMock()), \
             patch.object(main_mod, "Groq", return_value=MagicMock()), \
             patch.object(main_mod, "HotkeyListener", return_value=MagicMock()):
            voxel = main_mod.VoxelApp()

        assert voxel._overlay.style == "island"

    def test_the_level_provider_follows_a_replaced_recorder(self, app):
        """_on_settings_saved builds a *new* MicRecorder. A provider bound to
        the old object would animate from a dead stream for ever after."""
        from unittest.mock import MagicMock
        provider = app._overlay_level

        first = MagicMock()
        first.current_level.return_value = 0.1
        app._recorder = first
        assert provider() == pytest.approx(0.1)

        second = MagicMock()
        second.current_level.return_value = 0.9
        app._recorder = second
        assert provider() == pytest.approx(0.9)

    def test_the_level_provider_survives_a_recorder_that_has_gone_away(self, app):
        app._recorder = None
        assert app._overlay_level() == 0.0


class TestThePressToTalkKeyCanAlsoCancel:
    """A press that starts a recording must always be able to end it — by a
    second press, or by the tap filter — or the badge sits there listening
    until the max-duration timer fires."""

    def test_cancelling_stops_the_recorder_without_transcribing(self, app):
        app._recorder.is_recording = True
        app._cancel_recording()

        app._recorder.stop.assert_called_once()
        app._overlay.hide.assert_called()
        app._tray.set_state.assert_called_with("idle")

    def test_cancelling_when_nothing_is_recording_does_nothing(self, app):
        app._recorder.is_recording = False
        app._cancel_recording()
        app._recorder.stop.assert_not_called()

    def test_pressing_again_while_recording_cancels_it(self, app):
        """The recording is already running, so this press cannot be a start.
        It is the user asking to get out of a recording that did not stop."""
        app._recorder.is_recording = True
        app._on_hotkey_press()

        app._recorder.stop.assert_called_once()
        app._recorder.start.assert_not_called()

    def test_cancelling_stops_the_max_duration_timer(self, app):
        from unittest.mock import MagicMock
        timer = MagicMock()
        app._max_record_timer = timer
        app._recorder.is_recording = True
        app._cancel_recording()

        timer.cancel.assert_called_once()
        assert app._max_record_timer is None

    def test_the_listener_is_given_a_cancel_callback(self, app):
        from unittest.mock import patch
        with patch("src.main.HotkeyListener") as listener_cls:
            app._start_hotkey_listener()
        assert listener_cls.call_args.kwargs["on_cancel"] == app._cancel_recording


class TestACleanupFailureDoesNotSwallowTheDictation:
    """The transcript is the user's words; the LLM pass is a polish step. When
    the polish fails, typing the raw transcript loses a little tidiness —
    dropping it loses what they said."""

    def _wire(self, app, cleaner_error):
        app._transcriber = MagicMock()
        app._transcriber.transcribe.return_value = "um so how do i access this"
        app._cleaner = MagicMock()
        app._cleaner.clean.side_effect = cleaner_error
        app._injector = MagicMock()
        app._injector.inject.return_value = MagicMock(pasted=True)
        app._history = MagicMock()
        app._voice_commands = MagicMock()
        app._voice_commands.match.return_value = None
        app._tray = MagicMock()

    def test_the_raw_transcript_is_typed_when_cleanup_fails(self, app):
        self._wire(app, RuntimeError("model_not_found"))

        app._process_audio(b"\x00" * 100, 2.0)

        app._injector.inject.assert_called_once_with("um so how do i access this")

    def test_the_failure_is_recorded_in_history(self, app):
        self._wire(app, RuntimeError("model_not_found"))

        app._process_audio(b"\x00" * 100, 2.0)

        assert app._history.add.called


class TestTheAppOpensTheNewWindow:
    """The old settings, History and Statistics windows are gone; everything
    is one window with a sidebar."""

    def _real_window(self, app):
        """Replace the fixture's MagicMock with the window the app builds."""
        app._build_settings_window()
        return app._settings_window

    def test_settings_opens_the_sidebar_window(self, app):
        from src.ui_pyqt6.settings_window import SettingsWindow

        window = self._real_window(app)
        app._show_settings()
        assert isinstance(window, SettingsWindow)

    def test_the_tray_history_item_opens_the_history_pane(self, app):
        window = self._real_window(app)
        app._show_history()
        assert window.current_pane().PANE_ID == "history"

    def test_the_tray_stats_item_opens_the_stats_pane(self, app):
        window = self._real_window(app)
        app._show_stats()
        assert window.current_pane().PANE_ID == "stats"

    def test_the_old_windows_are_gone(self):
        import importlib

        for name in ("settings_ui", "history_window", "stats_window"):
            try:
                importlib.import_module("src.ui_pyqt6." + name)
            except ImportError:
                continue
            raise AssertionError("src.ui_pyqt6.%s still exists" % name)


class TestTheRailFollowsTheApp:
    def test_recording_turns_the_rail_dot_to_listening(self, app):
        app._build_settings_window()
        app._set_state("recording")
        assert app._settings_window._rail.status_text().startswith("Listening")

    def test_the_tray_and_the_rail_are_told_together(self, app):
        app._build_settings_window()
        app._set_state("error")
        app._tray.set_state.assert_called_with("error")
        assert app._settings_window._rail.status_text().startswith("Problem")

    def test_a_state_change_before_the_window_exists_does_not_crash(self, app):
        app._settings_window = None
        app._set_state("processing")
        app._tray.set_state.assert_called_with("processing")


class TestAUserWithNoApiKeyLandsSomewhereUseful:
    def test_a_keyless_start_is_routed_to_the_no_key_finish(self, app, monkeypatch):
        app._config.set("api_key", "")
        taken = []
        monkeypatch.setattr(
            "src.main.QTimer.singleShot",
            lambda _ms, fn: taken.append(getattr(fn, "__name__", str(fn))),
        )
        app._startup_stage_2()
        assert taken == ["_startup_finish_no_key"]

    def test_an_unconfigured_start_opens_the_general_pane(self, app):
        app._build_settings_window()
        app._config.set("api_key", "")
        app._startup_finish_no_key()
        assert app._settings_window.current_pane().PANE_ID == "general"


class TestSettingsChangesGoThroughApplySetting:
    def test_the_window_is_given_an_apply_that_reaches_the_app(self, app):
        app._build_settings_window()
        app._settings_window.ctx.apply("language", "de")
        assert app._config.get("language") == "de"
