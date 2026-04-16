import pytest
from unittest.mock import patch, MagicMock, call

from src.text_injector import TextInjector


class TestTextInjector:
    @patch("src.text_injector.pyperclip")
    @patch("src.text_injector.pyautogui")
    @patch("src.text_injector.winsound", create=True)
    def test_inject_pastes_text(self, mock_winsound, mock_pyautogui, mock_pyperclip):
        mock_pyperclip.paste.return_value = "old clipboard"

        injector = TextInjector(chime_path=None)
        injector.inject("Hello world")

        mock_pyperclip.copy.assert_any_call("Hello world")
        mock_pyautogui.hotkey.assert_called_once_with("ctrl", "v")

    @patch("src.text_injector.pyperclip")
    @patch("src.text_injector.pyautogui")
    @patch("src.text_injector.winsound", create=True)
    def test_inject_restores_clipboard(self, mock_winsound, mock_pyautogui, mock_pyperclip):
        mock_pyperclip.paste.return_value = "original content"

        injector = TextInjector(chime_path=None)
        injector.inject("new text")

        copy_calls = mock_pyperclip.copy.call_args_list
        assert copy_calls[-1] == call("original content")

    @patch("src.text_injector.pyperclip")
    @patch("src.text_injector.pyautogui")
    @patch("src.text_injector.winsound", create=True)
    def test_inject_handles_empty_clipboard(self, mock_winsound, mock_pyautogui, mock_pyperclip):
        mock_pyperclip.paste.return_value = ""

        injector = TextInjector(chime_path=None)
        injector.inject("text")

        mock_pyautogui.hotkey.assert_called_once()

    @patch("src.text_injector.pyperclip")
    @patch("src.text_injector.pyautogui")
    @patch("src.text_injector.winsound", create=True)
    def test_inject_plays_chime_when_path_given(self, mock_winsound, mock_pyautogui, mock_pyperclip):
        mock_pyperclip.paste.return_value = ""

        injector = TextInjector(chime_path="assets/chime.wav")
        injector.inject("text")

        mock_winsound.PlaySound.assert_called_once()
