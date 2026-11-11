import time
import pytest
from unittest.mock import MagicMock, patch

from src.hotkey_listener import HotkeyListener


class TestHotkeyListener:
    def test_parses_hotkey_string(self):
        listener = HotkeyListener(
            hotkey_str="<ctrl>+<shift>+space",
            on_press=MagicMock(),
            on_release=MagicMock(),
        )
        assert listener._modifier_keys == {"ctrl_l", "ctrl_r", "shift", "shift_r"}
        assert listener._trigger_key is not None

    def test_min_hold_duration_default(self):
        listener = HotkeyListener(
            hotkey_str="<ctrl>+<shift>+space",
            on_press=MagicMock(),
            on_release=MagicMock(),
        )
        assert listener._min_hold_duration == 0.3

    def test_tap_too_short_does_not_trigger(self):
        on_press = MagicMock()
        on_release = MagicMock()

        listener = HotkeyListener(
            hotkey_str="<ctrl>+<shift>+space",
            on_press=on_press,
            on_release=on_release,
            min_hold_duration=0.3,
        )

        listener._handle_press()
        listener._press_time = time.time() - 0.1
        listener._handle_release()

        on_press.assert_called_once()
        on_release.assert_not_called()

    def test_hold_long_enough_triggers_release(self):
        on_press = MagicMock()
        on_release = MagicMock()

        listener = HotkeyListener(
            hotkey_str="<ctrl>+<shift>+space",
            on_press=on_press,
            on_release=on_release,
            min_hold_duration=0.3,
        )

        listener._handle_press()
        listener._press_time = time.time() - 0.5
        listener._handle_release()

        on_press.assert_called_once()
        on_release.assert_called_once()

    def test_ignores_repeated_press_events(self):
        on_press = MagicMock()
        listener = HotkeyListener(
            hotkey_str="<ctrl>+<shift>+space",
            on_press=on_press,
            on_release=MagicMock(),
        )

        listener._handle_press()
        listener._handle_press()
        listener._handle_press()

        on_press.assert_called_once()


class TestActivationModes:
    def test_hold_is_the_default_mode(self):
        listener = HotkeyListener(
            hotkey_str="<ctrl>+<shift>+space",
            on_press=MagicMock(), on_release=MagicMock(),
        )
        assert listener.activation_mode == "hold"

    def test_toggle_fires_press_on_each_press_and_never_release(self):
        on_press, on_release = MagicMock(), MagicMock()
        listener = HotkeyListener(
            hotkey_str="<ctrl>+<shift>+space",
            on_press=on_press, on_release=on_release,
            activation_mode="toggle",
        )

        listener._handle_press()
        listener._handle_release()
        listener._handle_press()
        listener._handle_release()

        assert on_press.call_count == 2
        on_release.assert_not_called()

    def test_toggle_ignores_the_tap_filter(self):
        # A quick tap must still toggle; min_hold_duration only guards hold mode.
        on_press = MagicMock()
        listener = HotkeyListener(
            hotkey_str="<ctrl>+<shift>+space",
            on_press=on_press, on_release=MagicMock(),
            min_hold_duration=0.3, activation_mode="toggle",
        )

        listener._handle_press()
        listener._press_time = time.time() - 0.05
        listener._handle_release()
        listener._handle_press()

        assert on_press.call_count == 2

    def test_hold_mode_behaviour_is_unchanged(self):
        on_press, on_release = MagicMock(), MagicMock()
        listener = HotkeyListener(
            hotkey_str="<ctrl>+<shift>+space",
            on_press=on_press, on_release=on_release,
            min_hold_duration=0.3,
        )

        listener._handle_press()
        listener._press_time = time.time() - 1.0
        listener._handle_release()

        on_press.assert_called_once()
        on_release.assert_called_once()

    def test_is_modifier_only_true_for_modifier_combo(self):
        listener = HotkeyListener(
            hotkey_str="<ctrl>+<alt>", on_press=MagicMock(), on_release=MagicMock(),
        )
        assert listener.is_modifier_only is True

    def test_is_modifier_only_false_with_trigger_key(self):
        listener = HotkeyListener(
            hotkey_str="<ctrl>+<shift>+space", on_press=MagicMock(), on_release=MagicMock(),
        )
        assert listener.is_modifier_only is False

    def test_toggle_ignores_key_auto_repeat(self):
        """Holding the hotkey down repeats key events; it must toggle once."""
        on_press = MagicMock()
        listener = HotkeyListener(
            hotkey_str="<ctrl>+<shift>+space",
            on_press=on_press, on_release=MagicMock(),
            activation_mode="toggle",
        )

        listener._handle_press()
        listener._handle_press()   # auto-repeat
        listener._handle_press()   # auto-repeat
        assert on_press.call_count == 1

        listener._handle_release()
        listener._handle_press()   # a genuine second press
        assert on_press.call_count == 2

    def test_toggle_rearms_when_keys_are_physically_released(self):
        """If pynput misses the key-up, _is_held sticks True and the hotkey dies.

        Hold mode has a polling fallback for exactly this; toggle mode needs one
        too, but only to re-arm — it must not fire the callback.
        """
        on_press, on_release = MagicMock(), MagicMock()
        listener = HotkeyListener(
            hotkey_str="<ctrl>+<shift>+space",
            on_press=on_press, on_release=on_release,
            activation_mode="toggle",
        )

        listener._handle_press()
        assert listener._is_held is True
        on_press.reset_mock()

        # Keys are physically up, but no release event ever arrived.
        with patch.object(listener, "_any_modifier_variant_held", return_value=False), \
             patch.object(listener, "_trigger_still_held", return_value=False):
            listener._rearm_toggle()

        assert listener._is_held is False
        on_press.assert_not_called()
        on_release.assert_not_called()

    def test_toggle_does_not_rearm_while_keys_are_still_down(self):
        listener = HotkeyListener(
            hotkey_str="<ctrl>+<shift>+space",
            on_press=MagicMock(), on_release=MagicMock(),
            activation_mode="toggle",
        )
        listener._handle_press()

        with patch.object(listener, "_any_modifier_variant_held", return_value=True), \
             patch.object(listener, "_trigger_still_held", return_value=True):
            listener._rearm_toggle()

        assert listener._is_held is True


class TestATapCannotLeaveRecordingRunning:
    """The press callback starts recording immediately. A tap shorter than
    the hold threshold used to return without calling anything back, so the
    recording it had already started ran on until the max-duration timer."""

    def _listener(self):
        self.on_press = MagicMock()
        self.on_release = MagicMock()
        self.on_cancel = MagicMock()
        return HotkeyListener(
            hotkey_str="<ctrl>+<shift>+space",
            on_press=self.on_press,
            on_release=self.on_release,
            on_cancel=self.on_cancel,
            min_hold_duration=0.3,
        )

    def test_a_tap_cancels_what_the_press_started(self):
        listener = self._listener()
        listener._handle_press()
        listener._press_time = time.time() - 0.1
        listener._handle_release()

        self.on_press.assert_called_once()
        self.on_release.assert_not_called()
        self.on_cancel.assert_called_once()

    def test_a_real_hold_still_transcribes(self):
        listener = self._listener()
        listener._handle_press()
        listener._press_time = time.time() - 1.0
        listener._handle_release()

        self.on_release.assert_called_once()
        self.on_cancel.assert_not_called()

    def test_a_missing_cancel_callback_is_not_fatal(self):
        """on_cancel is optional, so older call sites keep working."""
        listener = HotkeyListener(
            hotkey_str="<ctrl>+<shift>+space",
            on_press=MagicMock(),
            on_release=MagicMock(),
            min_hold_duration=0.3,
        )
        listener._handle_press()
        listener._press_time = time.time() - 0.1
        listener._handle_release()   # must not raise


class TestTheReleasePollCanSeeTheTriggerKey:
    """The poll is the safety net for a key-up pynput misses. It could not
    see <space> at all — pynput's Key.space has no .vk, only .value.vk — so
    it fell through to 'assume still held' and the net never caught anything
    unless a modifier was released too."""

    def _listener(self):
        return HotkeyListener(
            hotkey_str="<ctrl>+<shift>+space",
            on_press=MagicMock(),
            on_release=MagicMock(),
        )

    def test_the_trigger_key_resolves_to_a_virtual_key_code(self):
        assert self._listener()._trigger_vk() == 32   # VK_SPACE

    def test_a_released_trigger_is_reported_as_released(self):
        listener = self._listener()
        with patch("src.hotkey_listener._vk_pressed", return_value=False) as pressed:
            assert listener._trigger_still_held() is False
        pressed.assert_called_with(32)

    def test_a_held_trigger_is_reported_as_held(self):
        listener = self._listener()
        with patch("src.hotkey_listener._vk_pressed", return_value=True):
            assert listener._trigger_still_held() is True

    def test_a_modifier_only_hotkey_has_no_trigger_to_poll(self):
        listener = HotkeyListener(
            hotkey_str="<ctrl>+<shift>",
            on_press=MagicMock(),
            on_release=MagicMock(),
        )
        assert listener._trigger_vk() is None
        assert listener._trigger_still_held() is True
