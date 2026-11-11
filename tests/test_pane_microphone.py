"""The Microphone pane: which device, and proof that it is hearing you."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from src.ui_pyqt6.panes import microphone as mic_mod
from src.ui_pyqt6.panes.microphone import MicrophonePane


@pytest.fixture
def two_devices(monkeypatch):
    devices = [
        {"index": 1, "name": "Realtek Mic"},
        {"index": 4, "name": "Blue Yeti"},
    ]
    monkeypatch.setattr(mic_mod, "list_input_devices", lambda: list(devices))
    return devices


@pytest.fixture
def no_devices(monkeypatch):
    monkeypatch.setattr(mic_mod, "list_input_devices", lambda: [])


class TestThePaneListsWhatIsActuallyPluggedIn:
    def test_every_device_gets_a_row(self, qapp, ctx, two_devices):
        pane = MicrophonePane(ctx)
        pane.refresh()
        assert pane.device_names() == ["Realtek Mic", "Blue Yeti"]

    def test_there_is_a_system_default_row(self, qapp, ctx, two_devices):
        pane = MicrophonePane(ctx)
        pane.refresh()
        assert mic_mod.SYSTEM_DEFAULT_ID in pane.row_ids()

    def test_the_saved_device_is_the_selected_row(self, qapp, ctx, two_devices):
        ctx.config.set("mic_device_name", "Blue Yeti")
        pane = MicrophonePane(ctx)
        pane.refresh()
        assert pane.selected_id() == "Blue Yeti"

    def test_with_nothing_saved_the_system_default_is_selected(self, qapp, ctx, two_devices):
        pane = MicrophonePane(ctx)
        pane.refresh()
        assert pane.selected_id() == mic_mod.SYSTEM_DEFAULT_ID


class TestThePaneSurvivesABadDevice:
    def test_it_says_so_when_the_saved_microphone_is_gone(self, qapp, ctx, two_devices):
        ctx.config.set("mic_device_name", "Ghost Mic")
        pane = MicrophonePane(ctx)
        pane.refresh()
        assert "Ghost Mic" in pane.warning_text()

    def test_a_missing_device_is_not_silently_reselected(self, qapp, ctx, two_devices):
        ctx.config.set("mic_device_name", "Ghost Mic")
        pane = MicrophonePane(ctx)
        pane.refresh()
        assert ctx.applied == []
        assert ctx.config.get("mic_device_name") == "Ghost Mic"

    def test_no_devices_at_all_is_a_message_not_a_crash(self, qapp, ctx, no_devices):
        pane = MicrophonePane(ctx)
        pane.refresh()
        assert pane.device_names() == []
        assert pane.warning_text() != ""

    def test_an_enumeration_failure_is_a_message_not_a_crash(self, qapp, ctx, monkeypatch):
        def boom():
            raise OSError("PortAudio is not available")

        monkeypatch.setattr(mic_mod, "list_input_devices", boom)
        pane = MicrophonePane(ctx)
        pane.refresh()
        assert pane.warning_text() != ""

    def test_the_warning_clears_once_the_device_is_back(self, qapp, ctx, two_devices):
        ctx.config.set("mic_device_name", "Ghost Mic")
        pane = MicrophonePane(ctx)
        pane.refresh()
        assert pane.warning_text() != ""
        ctx.config.set("mic_device_name", "Blue Yeti")
        pane.refresh()
        assert pane.warning_text() == ""


class TestChoosingAMicrophoneAppliesBothKeys:
    def test_the_name_and_the_index_are_written(self, qapp, ctx, two_devices):
        pane = MicrophonePane(ctx)
        pane.refresh()
        pane.choose("Blue Yeti")
        assert ("mic_device_name", "Blue Yeti") in ctx.applied
        assert ("mic_device", 4) in ctx.applied

    def test_the_system_default_clears_both_keys(self, qapp, ctx, two_devices):
        ctx.config.set("mic_device_name", "Blue Yeti")
        pane = MicrophonePane(ctx)
        pane.refresh()
        pane.choose(mic_mod.SYSTEM_DEFAULT_ID)
        assert ("mic_device_name", None) in ctx.applied
        assert ("mic_device", None) in ctx.applied

    def test_choosing_a_device_that_vanished_changes_nothing(self, qapp, ctx, two_devices):
        pane = MicrophonePane(ctx)
        pane.refresh()
        pane.choose("Ghost Mic")
        assert ctx.applied == []


class TestTheLevelMeters:
    def test_the_chosen_row_shows_a_level_from_the_recorder(self, qapp, ctx, two_devices):
        class FakeRecorder:
            def current_level(self):
                return 0.6

        ctx.recorder = FakeRecorder()
        pane = MicrophonePane(ctx)
        pane.refresh()
        pane.poll_levels()
        assert pane.level_for(pane.selected_id()) == pytest.approx(0.6, abs=0.01)

    def test_no_recorder_means_a_flat_meter_not_a_crash(self, qapp, ctx, two_devices):
        ctx.recorder = None
        pane = MicrophonePane(ctx)
        pane.refresh()
        pane.poll_levels()
        assert pane.level_for(pane.selected_id()) == 0.0

    def test_a_recorder_that_throws_does_not_take_the_pane_down(self, qapp, ctx, two_devices):
        class AngryRecorder:
            def current_level(self):
                raise RuntimeError("stream closed")

        ctx.recorder = AngryRecorder()
        pane = MicrophonePane(ctx)
        pane.refresh()
        pane.poll_levels()
        assert pane.level_for(pane.selected_id()) == 0.0


class TestThePaneDeclaresWhatItOwns:
    def test_it_owns_both_microphone_keys(self):
        assert MicrophonePane.OWNS == frozenset({"mic_device_name", "mic_device"})


class TestTheMetersActuallyMove:
    """The pane tells the user to pick the device whose bars move. Nothing
    called poll_levels, so the bars never moved and the instruction was
    impossible to follow."""

    def test_showing_the_pane_starts_polling(self, qapp, ctx, two_devices):
        pane = MicrophonePane(ctx)
        pane.refresh()
        pane.show()
        qapp.processEvents()
        assert pane._level_timer.isActive() is True

    def test_hiding_the_pane_stops_polling(self, qapp, ctx, two_devices):
        pane = MicrophonePane(ctx)
        pane.refresh()
        pane.show()
        qapp.processEvents()
        pane.hide()
        qapp.processEvents()
        assert pane._level_timer.isActive() is False

    def test_a_tick_moves_the_chosen_row_s_meter(self, qapp, ctx, two_devices):
        class FakeRecorder:
            def current_level(self):
                return 0.8

        ctx.recorder = FakeRecorder()
        pane = MicrophonePane(ctx)
        pane.refresh()
        pane.show()
        qapp.processEvents()
        assert pane.level_for(pane.selected_id()) == 0.0
        pane._level_timer.timeout.emit()
        assert pane.level_for(pane.selected_id()) > 0.5, (
            "a timer tick did not reach the meter"
        )
