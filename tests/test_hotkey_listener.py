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


class TestAModifierOnlyHotkeyTogglesOnACleanTap:
    """Ctrl + Alt on its own can toggle - as a tap. Pressing both and letting
    go with nothing else pressed flips recording; Ctrl + Alt + Del and every
    other shortcut that starts with those keys is left alone."""

    @pytest.fixture(autouse=True)
    def _keys_physically_match_events(self):
        """The listener double-checks Windows' physical key state; in tests
        the keyboard is whatever the test has pressed."""
        self._down = set()
        with patch("src.hotkey_listener._is_key_physically_pressed",
                   side_effect=lambda name: name in self._down):
            yield

    def _listener(self, on_press, mode="toggle"):
        listener = HotkeyListener(
            hotkey_str="<ctrl>+<alt>",
            on_press=on_press, on_release=MagicMock(),
            activation_mode=mode,
        )
        real_press, real_release = listener._on_key_press, listener._on_key_release

        def press(key):
            real_press(key)
            if getattr(key, "name", None):
                self._down.add(key.name)

        def release(key):
            self._down.discard(getattr(key, "name", None))
            real_release(key)

        listener._on_key_press, listener._on_key_release = press, release
        return listener

    def _tap(self, listener, *extra):
        from pynput.keyboard import Key
        listener._on_key_press(Key.ctrl_l)
        listener._on_key_press(Key.alt_l)
        for key in extra:
            listener._on_key_press(key)
            listener._on_key_release(key)
        listener._on_key_release(Key.alt_l)
        listener._on_key_release(Key.ctrl_l)

    def test_holding_the_keys_down_does_not_fire_yet(self):
        from pynput.keyboard import Key
        on_press = MagicMock()
        listener = self._listener(on_press)
        listener._on_key_press(Key.ctrl_l)
        listener._on_key_press(Key.alt_l)
        on_press.assert_not_called()

    def test_a_clean_tap_fires_once(self):
        on_press = MagicMock()
        listener = self._listener(on_press)
        self._tap(listener)
        on_press.assert_called_once()

    def test_two_taps_fire_twice(self):
        on_press = MagicMock()
        listener = self._listener(on_press)
        self._tap(listener)
        self._tap(listener)
        assert on_press.call_count == 2

    def test_ctrl_alt_del_does_not_fire(self):
        from pynput.keyboard import Key
        on_press = MagicMock()
        listener = self._listener(on_press)
        self._tap(listener, Key.delete)
        on_press.assert_not_called()

    def test_ctrl_alt_and_a_letter_does_not_fire(self):
        from pynput.keyboard import KeyCode
        on_press = MagicMock()
        listener = self._listener(on_press)
        self._tap(listener, KeyCode.from_char("v"))
        on_press.assert_not_called()

    def test_adding_another_modifier_does_not_fire(self):
        from pynput.keyboard import Key
        on_press = MagicMock()
        listener = self._listener(on_press)
        self._tap(listener, Key.shift)
        on_press.assert_not_called()

    def test_a_spoiled_tap_does_not_spoil_the_next_one(self):
        from pynput.keyboard import Key
        on_press = MagicMock()
        listener = self._listener(on_press)
        self._tap(listener, Key.delete)
        self._tap(listener)
        on_press.assert_called_once()

    def test_hold_mode_still_starts_the_moment_both_keys_are_down(self):
        from pynput.keyboard import Key
        on_press = MagicMock()
        listener = self._listener(on_press, mode="hold")
        with patch.object(listener, "_start_release_poll"):
            listener._on_key_press(Key.ctrl_l)
            listener._on_key_press(Key.alt_l)
        on_press.assert_called_once()


class TestAnotherKeyCancelsAModifierOnlyHold:
    """Ctrl + Alt as push-to-talk starts recording the moment both are down.
    Pressing any other key while they are held means the user was typing a
    shortcut (Ctrl + Alt + Del, or a Ctrl + Alt + Space press-to-start key),
    so that recording is thrown away."""

    def test_another_key_during_a_modifier_only_hold_cancels_it(self):
        from pynput.keyboard import Key
        on_press, on_release, on_cancel = MagicMock(), MagicMock(), MagicMock()
        listener = HotkeyListener(
            hotkey_str="<ctrl>+<alt>",
            on_press=on_press, on_release=on_release, on_cancel=on_cancel,
        )
        # Without an on_interrupt, an interruption falls back to on_cancel.
        with patch.object(listener, "_start_release_poll"):
            listener._on_key_press(Key.ctrl_l)
            listener._on_key_press(Key.alt_l)
            # Held long enough that the short-tap filter is not what cancels.
            listener._press_time = time.time() - 1.0
            listener._on_key_press(Key.space)
            listener._on_key_release(Key.space)
            listener._on_key_release(Key.alt_l)
            listener._on_key_release(Key.ctrl_l)
        on_press.assert_called_once()
        on_cancel.assert_called_once()
        on_release.assert_not_called()


class TestSameHotkey:
    def test_same_hotkey_ignores_order(self):
        from src.hotkey_listener import same_hotkey
        assert same_hotkey("<ctrl>+<alt>", "<alt>+<ctrl>") is True
        assert same_hotkey("<ctrl>+<alt>", "<ctrl>+<alt>+space") is False
        assert same_hotkey("<ctrl>+k", "<ctrl>+k") is True
        assert same_hotkey("", "") is False


class TestHotkeySet:
    def test_hotkey_set_starts_and_stops_both(self):
        from src.hotkey_listener import HotkeySet
        hold, toggle = MagicMock(), MagicMock()
        keys = HotkeySet(hold, toggle)
        keys.start()
        keys.stop()
        hold.start.assert_called_once(); hold.stop.assert_called_once()
        toggle.start.assert_called_once(); toggle.stop.assert_called_once()

    def test_a_missing_listener_is_skipped(self):
        from src.hotkey_listener import HotkeySet
        toggle = MagicMock()
        keys = HotkeySet(None, toggle)
        keys.start(); keys.stop()
        toggle.start.assert_called_once()
        assert keys.hold is None and keys.toggle is toggle


class TestStaleKeysAfterCtrlAltDel:
    """Windows swallows Ctrl + Alt + Del and its key releases. The listener
    must not be left thinking Ctrl and Alt are still down."""

    def test_a_lone_ctrl_tap_afterwards_does_not_start_dictation(self):
        from pynput.keyboard import Key
        on_press = MagicMock()
        listener = HotkeyListener(
            hotkey_str="<ctrl>+<alt>",
            on_press=on_press, on_release=MagicMock(),
            activation_mode="toggle",
        )
        down = set()
        with patch("src.hotkey_listener._is_key_physically_pressed",
                   side_effect=lambda name: name in down):
            listener._on_key_press(Key.ctrl_l); down.add("ctrl_l")
            listener._on_key_press(Key.alt_l); down.add("alt_l")
            # Del and both releases never reach the hook.
            down.clear()
            listener._on_key_press(Key.ctrl_l); down.add("ctrl_l")
            down.discard("ctrl_l"); listener._on_key_release(Key.ctrl_l)
        on_press.assert_not_called()


class TestAutorepeatDuringAModifierOnlyHold:
    """Holding Space on Ctrl + Alt + Space repeats Space. Once another key
    has cancelled a Ctrl + Alt hold, nothing restarts it until the
    modifiers come up."""

    def _hold(self):
        on_press, on_release, on_cancel, on_interrupt = (MagicMock() for _ in range(4))
        listener = HotkeyListener(
            hotkey_str="<ctrl>+<alt>",
            on_press=on_press, on_release=on_release, on_cancel=on_cancel,
            on_interrupt=on_interrupt,
        )
        return listener, on_press, on_release, on_cancel, on_interrupt

    def test_repeated_space_does_not_restart_it(self):
        from pynput.keyboard import Key
        listener, on_press, on_release, on_cancel, on_interrupt = self._hold()
        with patch.object(listener, "_start_release_poll"):
            listener._on_key_press(Key.ctrl_l)
            listener._on_key_press(Key.alt_l)
            for _ in range(3):
                listener._on_key_press(Key.space)
            listener._on_key_release(Key.space)
            listener._on_key_release(Key.alt_l)
            listener._on_key_release(Key.ctrl_l)
        on_press.assert_called_once()
        on_interrupt.assert_called_once()
        on_release.assert_not_called()
        on_cancel.assert_not_called()

    def test_it_works_again_after_the_keys_come_up(self):
        from pynput.keyboard import Key
        listener, on_press, *_ = self._hold()
        with patch.object(listener, "_start_release_poll"):
            listener._on_key_press(Key.ctrl_l)
            listener._on_key_press(Key.alt_l)
            listener._on_key_press(Key.space)
            listener._on_key_release(Key.space)
            listener._on_key_release(Key.alt_l)
            listener._on_key_release(Key.ctrl_l)
            listener._on_key_press(Key.ctrl_l)
            listener._on_key_press(Key.alt_l)
        assert on_press.call_count == 2

    def test_a_short_tap_is_still_a_cancel_not_an_interrupt(self):
        from pynput.keyboard import Key
        listener, on_press, on_release, on_cancel, on_interrupt = self._hold()
        with patch.object(listener, "_start_release_poll"):
            listener._on_key_press(Key.ctrl_l)
            listener._on_key_press(Key.alt_l)
            listener._on_key_release(Key.alt_l)
        on_cancel.assert_called_once()
        on_interrupt.assert_not_called()


class TestKeysThatClash:
    def test_the_same_trigger_with_more_modifiers_clashes(self):
        from src.hotkey_listener import hotkeys_clash
        assert hotkeys_clash("<ctrl>+space", "<ctrl>+<shift>+space") is True
        assert hotkeys_clash("<ctrl>+<alt>", "<alt>+<ctrl>") is True

    def test_shared_modifiers_with_different_triggers_do_not(self):
        from src.hotkey_listener import hotkeys_clash
        assert hotkeys_clash("<ctrl>+<alt>", "<ctrl>+<alt>+space") is False
        assert hotkeys_clash("<ctrl>+space", "<alt>+space") is False
        assert hotkeys_clash("k", "") is False
