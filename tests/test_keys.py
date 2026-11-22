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


class TestWhichKeyToName:
    """Splash, sidebar status and the first run name one key: push-to-talk
    if it is set, otherwise the press-to-start key."""

    def _cfg(self, tmp_path, **values):
        from src.config import Config
        cfg = Config(config_path=str(tmp_path / "c.json"))
        cfg.load()
        for k, v in values.items():
            cfg.set(k, v)
        return cfg

    def test_push_to_talk_wins(self, tmp_path):
        from src.ui_pyqt6.keys import dictation_shortcut
        cfg = self._cfg(tmp_path, hotkey="<ctrl>+<alt>", toggle_hotkey="k")
        assert dictation_shortcut(cfg) == ("Ctrl + Alt", "hold")

    def test_the_press_to_start_key_when_push_to_talk_is_off(self, tmp_path):
        from src.ui_pyqt6.keys import dictation_shortcut
        cfg = self._cfg(tmp_path, hotkey="", toggle_hotkey="k")
        assert dictation_shortcut(cfg) == ("K", "toggle")

    def test_nothing_set(self, tmp_path):
        from src.ui_pyqt6.keys import dictation_shortcut
        cfg = self._cfg(tmp_path, hotkey="", toggle_hotkey="")
        assert dictation_shortcut(cfg) == ("", "hold")
