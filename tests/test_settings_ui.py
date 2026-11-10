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
