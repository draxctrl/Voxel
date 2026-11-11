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


class TestRowsFitTheirContent:
    """Inter is wider than Segoe UI, and the row controls are fixed-width: a
    title must never be squeezed out by the control beside it."""

    def test_no_row_title_is_clipped(self, window):
        from src.ui_pyqt6.ios_layout import SettingsRow
        window.show()
        for row in window.findChildren(SettingsRow):
            label = row.title_label
            needed = label.fontMetrics().horizontalAdvance(label.text())
            assert label.width() >= needed, (
                f"{label.text()!r} has {label.width()}px but needs {needed}px"
            )

    def test_a_control_stays_inside_its_card(self, window):
        window.show()
        for name in ("_mic_combo", "_profile_combo", "_lang_combo", "_activation_combo"):
            widget = getattr(window, name)
            card = _card_of(widget)
            right = widget.mapTo(card, widget.rect().topRight()).x()
            assert right <= card.width(), f"{name} overflows its card by {right - card.width()}px"


def _ancestor(widget, cls):
    """Nearest ancestor of *widget* that is a *cls*, or None."""
    node = widget.parent()
    while node is not None:
        if isinstance(node, cls):
            return node
        node = node.parent()
    return None


def _card_of(widget):
    from src.ui_pyqt6.ios_layout import GroupCard
    return _ancestor(widget, GroupCard)


def _row_of(widget):
    from src.ui_pyqt6.ios_layout import SettingsRow, StackedRow
    return _ancestor(widget, SettingsRow) or _ancestor(widget, StackedRow)


def _row_titled(window, title):
    from src.ui_pyqt6.ios_layout import DisclosureRow
    for row in window.findChildren(DisclosureRow):
        if row.title_label.text() == title:
            return row
    raise AssertionError(f"no disclosure row titled {title!r}")


class TestGroupedLayout:
    def test_every_setting_lives_in_a_group(self, window):
        assert set(window._groups) == {
            "TRANSCRIPTION", "RECORDING", "BEHAVIOUR", "YOUR DATA",
        }

    def test_controls_are_inside_their_card(self, window):
        assert _card_of(window._mic_combo) is window._groups["RECORDING"]
        assert _card_of(window._activation_combo) is window._groups["RECORDING"]
        assert _card_of(window._profile_combo) is window._groups["TRANSCRIPTION"]
        assert _card_of(window._lang_combo) is window._groups["TRANSCRIPTION"]
        assert _card_of(window._api_key_edit) is window._groups["TRANSCRIPTION"]
        assert _card_of(window._mute_check) is window._groups["BEHAVIOUR"]
        assert _card_of(window._autostart_check) is window._groups["BEHAVIOUR"]

    def test_switch_rows_keep_their_explanation(self, window):
        """The switch text moved to the row title; the tooltip must move too."""
        assert "chime" in _row_of(window._mute_check).toolTip()
        assert "Windows starts" in _row_of(window._autostart_check).toolTip()

    def test_no_switch_carries_its_own_duplicate_label(self, window):
        from src.ui_pyqt6.theme import IOSSwitch
        for switch in window.findChildren(IOSSwitch):
            assert switch.text() == ""

    def test_every_switch_is_titled_by_its_row(self, window):
        from src.ui_pyqt6.theme import IOSSwitch
        for switch in window.findChildren(IOSSwitch):
            row = _row_of(switch)
            assert row is not None and row.title_label.text().strip()

    def test_the_old_header_buttons_are_gone(self, window):
        for attr in ("_history_btn", "_stats_btn", "_help_btn", "_voice_cmd_btn"):
            assert not hasattr(window, attr)


class TestDisclosureRowsAreWired:
    def _window(self, tmp_path, **callbacks):
        from src.ui_pyqt6.settings_ui import SettingsWindow
        cfg = Config(config_path=str(tmp_path / "config.json"))
        cfg.load()
        return SettingsWindow(config=cfg, on_save=lambda: None, **callbacks)

    def test_history_row_calls_the_history_callback(self, qapp, tmp_path):
        seen = []
        w = self._window(tmp_path, on_history=lambda: seen.append("history"))
        _row_titled(w, "History").clicked.emit()
        assert seen == ["history"]
        w.deleteLater()

    def test_stats_row_calls_the_stats_callback(self, qapp, tmp_path):
        seen = []
        w = self._window(tmp_path, on_stats=lambda: seen.append("stats"))
        _row_titled(w, "Stats").clicked.emit()
        assert seen == ["stats"]
        w.deleteLater()

    def test_help_and_voice_commands_rows_exist(self, window):
        assert _row_titled(window, "Help & FAQ") is not None
        assert _row_titled(window, "Voice Commands") is not None


class TestContentIsReachable:
    """Grouped cards are taller than the flat stack they replaced. If the
    content outgrows the window, every row must still be reachable and Save
    must never scroll away."""

    def test_the_groups_scroll(self, window):
        assert window._scroll is not None
        assert window._scroll.widgetResizable() is True

    def test_save_is_outside_the_scroll_area(self, window):
        assert not window._scroll.isAncestorOf(window._save_btn)

    def test_the_last_group_is_reachable(self, window):
        window.show()
        bar = window._scroll.verticalScrollBar()
        card = window._groups["YOUR DATA"]
        bar.setValue(bar.maximum())
        bottom = card.mapTo(window._scroll.viewport(), card.rect().bottomLeft()).y()
        assert bottom <= window._scroll.viewport().height(), (
            "the last group is still below the viewport at full scroll"
        )

    def test_there_is_no_horizontal_scrollbar(self, window):
        from PyQt6.QtCore import Qt
        window.show()
        assert (
            window._scroll.horizontalScrollBarPolicy()
            == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
