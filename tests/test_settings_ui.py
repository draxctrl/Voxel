"""Settings window behaviour. Runs headless via Qt's offscreen platform."""
import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from src.config import Config


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def window(qapp, tmp_path):
    from src.ui_pyqt6.settings_ui import SettingsWindow
    cfg = Config(config_path=str(tmp_path / "config.json"))
    cfg.load()
    w = SettingsWindow(
        config=cfg,
        on_save=lambda: None,
        on_validate_key=lambda key: True,
        on_quit=lambda: None,
    )
    yield w
    w.deleteLater()


class TestOfflineModeDisablesDictationMode:
    """Offline transcription skips LLM cleanup, so the mode control is inert."""

    def test_mode_control_is_enabled_by_default(self, window):
        from src.ui_pyqt6.settings_ui import _MODE_SUBTITLE
        assert window._profile_combo.isEnabled() is True
        assert window._profile_sub.text() == _MODE_SUBTITLE

    def test_ticking_offline_disables_and_explains(self, window):
        from src.ui_pyqt6.settings_ui import _MODE_SUBTITLE_OFFLINE
        window._offline_check.setChecked(True)
        assert window._profile_combo.isEnabled() is False
        assert window._profile_sub.text() == _MODE_SUBTITLE_OFFLINE

    def test_unticking_offline_restores(self, window):
        from src.ui_pyqt6.settings_ui import _MODE_SUBTITLE
        window._offline_check.setChecked(True)
        window._offline_check.setChecked(False)
        assert window._profile_combo.isEnabled() is True
        assert window._profile_sub.text() == _MODE_SUBTITLE


class TestUndoRowRemoved:
    def test_no_undo_widgets_remain(self, window):
        assert not hasattr(window, "_undo_hotkey_edit")
        assert not hasattr(window, "_undo_capture_btn")


class TestActivationMode:
    def test_defaults_to_hold(self, window):
        assert window._activation_combo.currentData() == "hold"

    def test_saving_toggle_with_normal_hotkey_is_kept(self, window):
        window._hotkey_edit.setText("<ctrl>+<shift>+space")
        window._activation_combo.setCurrentIndex(1)
        window._save()
        assert window._config.get("activation_mode") == "toggle"

    def test_toggle_is_refused_for_modifier_only_hotkey(self, window):
        # Every Ctrl+Alt press would flip recording, so this must be refused.
        window._hotkey_edit.setText("<ctrl>+<alt>")
        window._activation_combo.setCurrentIndex(1)
        window._save()
        assert window._config.get("activation_mode") == "hold"
        assert window._activation_combo.currentData() == "hold"


class TestMicListIdentity:
    """The mic you chose must survive being unplugged and reopening Settings."""

    def _fake_pa(self, names):
        from unittest.mock import MagicMock
        pa = MagicMock()
        pa.get_device_count.return_value = len(names)
        pa.get_device_info_by_index.side_effect = lambda i: {
            "index": i, "name": names[i], "maxInputChannels": 1,
            "hostApi": 0, "defaultSampleRate": 16000,
        }
        pa.get_default_input_device_info.return_value = {
            "index": 0, "name": names[0] if names else "", "maxInputChannels": 1,
            "hostApi": 0, "defaultSampleRate": 16000,
        }
        pa.get_host_api_count.return_value = 1
        pa.get_host_api_info_by_index.side_effect = lambda h: {"name": "MME", "index": h}
        pa.get_default_host_api_info.return_value = {"index": 0, "name": "MME"}
        return pa

    def test_repopulating_does_not_duplicate_entries(self, window):
        from unittest.mock import patch
        with patch("pyaudio.PyAudio", return_value=self._fake_pa(["Realtek Mic", "Blue Yeti"])):
            window._populate_mics()
            first = window._mic_combo.count()
            window._populate_mics()
            assert window._mic_combo.count() == first

    def test_disconnected_saved_mic_is_kept_and_marked(self, window):
        from unittest.mock import patch
        window._config.set("mic_device_name", "Blue Yeti")
        with patch("pyaudio.PyAudio", return_value=self._fake_pa(["Realtek Mic"])):
            window._populate_mics()

        assert "Blue Yeti" in window._mic_combo.currentText()
        assert "not connected" in window._mic_combo.currentText()

    def test_saving_with_disconnected_mic_preserves_the_name(self, window):
        """The real trap: open Settings for an unrelated reason, hit Save, and
        your chosen mic is silently replaced by whatever was listed first."""
        from unittest.mock import patch
        window._config.set("mic_device_name", "Blue Yeti")
        with patch("pyaudio.PyAudio", return_value=self._fake_pa(["Realtek Mic"])):
            window._populate_mics()
            window._save()

        assert window._config.get("mic_device_name") == "Blue Yeti"

    def test_enumeration_failure_does_not_save_a_placeholder_as_a_name(self, window):
        from unittest.mock import patch
        with patch("pyaudio.PyAudio", side_effect=OSError("audio subsystem down")):
            window._populate_mics()
            window._save()

        assert window._config.get("mic_device_name") is None
