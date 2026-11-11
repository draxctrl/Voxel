"""Turning captured keys into the hotkey string pynput reads back."""
from src.ui_pyqt6.panes.hotkey_capture import build_hotkey, key_token


class _Named:
    def __init__(self, name):
        self.name = name
        self.char = None


class _Char:
    def __init__(self, char):
        self.char = char


class TestAKeyBecomesAToken:
    def test_left_and_right_modifiers_are_the_same_token(self):
        assert key_token(_Named("ctrl_l")) == key_token(_Named("ctrl_r")) == "<ctrl>"

    def test_a_letter_is_lower_cased(self):
        assert key_token(_Char("V")) == "v"

    def test_a_named_key_is_wrapped(self):
        assert key_token(_Named("space")) == "<space>"

    def test_a_key_that_is_neither_is_ignored(self):
        assert key_token(_Char(None)) is None


class TestACombinationIsAlwaysWrittenTheSameWay:
    def test_modifiers_come_first_in_a_fixed_order(self):
        assert build_hotkey({"v", "<shift>", "<ctrl>"}) == "<ctrl>+<shift>+v"

    def test_the_press_order_does_not_change_the_string(self):
        first = build_hotkey({"<shift>", "<ctrl>", "<space>"})
        second = build_hotkey({"<space>", "<ctrl>", "<shift>"})
        assert first == second

    def test_the_shipped_default_round_trips(self):
        assert build_hotkey({"<ctrl>", "<shift>", "space"}) == "<ctrl>+<shift>+space"

    def test_a_modifier_only_combo_is_written_too(self):
        assert build_hotkey({"<alt>", "<ctrl>"}) == "<ctrl>+<alt>"

    def test_nothing_captured_is_an_empty_string_not_a_default(self):
        """An empty capture must not read as a choice - the pane refuses it."""
        assert build_hotkey(set()) == ""
