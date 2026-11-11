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


class TestWheelOverAControlScrollsThePage:
    """Qt's QComboBox changes its value on a wheel roll and accepts the event.
    Inside a scroll area that means scrolling past Microphone silently picks a
    different microphone, and the next Save writes it."""

    def _wheel(self, widget, qapp):
        from PyQt6.QtCore import QPoint, QPointF, Qt
        from PyQt6.QtGui import QWheelEvent
        centre = QPointF(widget.rect().center())
        event = QWheelEvent(
            centre,
            QPointF(widget.mapToGlobal(widget.rect().center())),
            QPoint(0, -40),
            QPoint(0, -120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        qapp.sendEvent(widget, event)
        qapp.processEvents()
        return event

    def test_wheeling_over_a_closed_dropdown_does_not_change_it(self, qapp, window):
        window.show()
        for name in ("_mic_combo", "_profile_combo", "_lang_combo", "_activation_combo"):
            combo = getattr(window, name)
            before = combo.currentIndex()
            self._wheel(combo, qapp)
            assert combo.currentIndex() == before, (
                f"wheeling over {name} changed the setting to "
                f"{combo.currentText()!r}"
            )

    def test_the_wheel_event_is_left_for_the_scroll_area(self, qapp, window):
        window.show()
        event = self._wheel(window._mic_combo, qapp)
        assert not event.isAccepted(), (
            "the combo swallowed the wheel event, so the page cannot scroll"
        )


class TestStatusMessagesAreSeen:
    """The status line lives at the top of the first card, inside the scroll
    area, while Save sits outside it. A refusal the user never sees is a
    setting that silently did not take."""

    def test_a_refusal_scrolls_itself_into_view(self, qapp, window):
        window.show()
        window._scroll.verticalScrollBar().setValue(
            window._scroll.verticalScrollBar().maximum()
        )
        qapp.processEvents()
        window._hotkey_edit.setText("<ctrl>+<alt>")
        window._activation_combo.setCurrentIndex(1)
        window._save()
        qapp.processEvents()

        top = window._status_label.mapTo(window._scroll.viewport(), window._status_label.rect().topLeft()).y()
        assert 0 <= top <= window._scroll.viewport().height(), (
            f"the warning is at y={top} in a {window._scroll.viewport().height()}px viewport"
        )


class TestHelpMatchesTheWindow:
    def test_the_faq_does_not_point_at_deleted_buttons(self, window):
        """Task 3 turned the Voice Commands button into a row."""
        import inspect
        from src.ui_pyqt6 import settings_ui
        source = inspect.getsource(settings_ui.SettingsWindow._show_help)
        assert "Voice Commands button" not in source


class TestRecordingStylePicker:
    def test_it_offers_every_style(self, window):
        from src.ui_pyqt6.recording_styles import RECORDING_STYLES
        assert set(window._style_picker.style_ids()) == set(RECORDING_STYLES)

    def test_it_starts_on_the_configured_style(self, qapp, tmp_path):
        from src.ui_pyqt6.settings_ui import SettingsWindow
        cfg = Config(config_path=str(tmp_path / "config.json"))
        cfg.load()
        cfg.set("recording_style", "island")
        w = SettingsWindow(config=cfg, on_save=lambda: None)
        assert w._style_picker.selected() == "island"
        w.deleteLater()

    def test_an_unknown_saved_style_falls_back_to_the_default(self, qapp, tmp_path):
        from src.ui_pyqt6.settings_ui import SettingsWindow
        from src.ui_pyqt6.recording_styles import DEFAULT_STYLE
        cfg = Config(config_path=str(tmp_path / "config.json"))
        cfg.load()
        cfg.set("recording_style", "spinning-pizza")
        w = SettingsWindow(config=cfg, on_save=lambda: None)
        assert w._style_picker.selected() == DEFAULT_STYLE
        w.deleteLater()

    def test_choosing_one_saves_it(self, window):
        window._style_picker.select("waveform")
        window._save()
        assert window._config.get("recording_style") == "waveform"

    def test_the_picker_lives_in_the_recording_group(self, window):
        assert _card_of(window._style_picker) is window._groups["RECORDING"]

    def test_the_previews_animate_only_while_the_window_is_visible(self, qapp, window):
        """A hidden window animating three displays at 60fps burns a core."""
        window.show()
        qapp.processEvents()
        assert window._style_picker._timer.isActive()
        window.hide()
        qapp.processEvents()
        assert not window._style_picker._timer.isActive()

    def test_the_previews_do_not_touch_the_microphone(self, qapp, window):
        """A preview that opened the mic would fight the recorder for it."""
        from unittest.mock import patch
        with patch("pyaudio.PyAudio", side_effect=AssertionError("preview opened the mic")):
            window.show()
            qapp.processEvents()
            window._style_picker._tick()
            window._style_picker._tick()

    def test_a_tick_repaints_the_thumbnails(self, qapp, window):
        """The level moving is not the same as the picture moving. The display
        is a hidden child widget, so an update() on it is dropped: unless the
        tile itself is repainted the user watches one frozen frame."""
        from src.ui_pyqt6.ios_layout import _StyleTile
        painted = []
        original = _StyleTile.paintEvent

        def counting_paint(tile_self, event):
            painted.append(tile_self.style_id)
            return original(tile_self, event)

        window.show()
        qapp.processEvents()
        _StyleTile.paintEvent = counting_paint
        try:
            painted.clear()
            for _ in range(4):
                window._style_picker._tick()
                qapp.processEvents()
        finally:
            _StyleTile.paintEvent = original

        assert painted, "a preview tick never repainted a thumbnail"
