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
