"""Hotkeys stored for pynput, shown to a person."""
from src.ui_pyqt6.keys import pretty_hotkey


class TestAStoredHotkeyIsReadable:
    def test_the_shipped_default_reads_as_words(self):
        assert pretty_hotkey("<ctrl>+<shift>+space") == "Ctrl + Shift + Space"

    def test_a_letter_key_is_upper_case(self):
        assert pretty_hotkey("<ctrl>+<alt>+v") == "Ctrl + Alt + V"

    def test_a_modifier_only_combo_works(self):
        assert pretty_hotkey("<ctrl>+<alt>") == "Ctrl + Alt"

    def test_an_unset_hotkey_is_empty_rather_than_the_word_none(self):
        assert pretty_hotkey(None) == ""
        assert pretty_hotkey("") == ""

    def test_an_unknown_key_name_is_still_shown(self):
        assert pretty_hotkey("<ctrl>+f13") == "Ctrl + F13"
