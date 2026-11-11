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

    def test_report_mic_fallback_names_the_active_device(self, app):
        app._report_mic_fallback()

        app._overlay.set_mic_text.assert_called()
        assert "Realtek Mic" in app._overlay.set_mic_text.call_args[0][0]

    def test_report_mic_fallback_warns_when_device_missing(self, app):
        app._recorder.requested_device_missing = True
        app._config.set("mic_device_name", "Blue Yeti")

        app._report_mic_fallback()

        message = app._overlay.set_mic_text.call_args[0][0]
        assert "Blue Yeti" in message
        assert "not found" in message
        app._settings_window.show_warning.assert_called()

    def test_settings_saved_path_runs(self, app):
        """_on_settings_saved also called the deleted method."""
        app._config.set("api_key", "gsk_fake_key_for_test")
        app._on_settings_saved()


class TestOverlayIsWiredToTheLiveRecorder:
    """The recording animation is only honest if it reads the microphone that
    is actually recording — and _on_settings_saved replaces the recorder."""

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
