import pytest
from unittest.mock import patch, MagicMock, call

from src.text_injector import TextInjector, InjectionResult, _is_shell_surface


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
        # inject() no longer plays the chime; main.py calls play_chime()
        # separately on hotkey release so the sound lands before transcription.
        injector.play_chime()

        mock_winsound.PlaySound.assert_called_once()


class TestShellSurfaceDetection:
    """Pasting into the Start menu makes Windows execute the text as a command.

    Observed in the wild: a dictation reached the Start menu and produced
    "Windows cannot find 'fresh'".
    """

    def test_start_menu_is_a_shell_surface(self):
        assert _is_shell_surface("startmenuexperiencehost", "Windows.UI.Core.CoreWindow") is True

    def test_search_host_is_a_shell_surface(self):
        assert _is_shell_surface("searchhost", "Windows.UI.Core.CoreWindow") is True

    def test_search_app_is_a_shell_surface(self):
        assert _is_shell_surface("searchapp", None) is True

    def test_desktop_window_class_is_still_detected(self):
        assert _is_shell_surface("explorer", "Progman") is True

    def test_taskbar_window_class_is_still_detected(self):
        assert _is_shell_surface("explorer", "Shell_TrayWnd") is True

    def test_ordinary_editor_is_not_a_shell_surface(self):
        assert _is_shell_surface("code", "Chrome_WidgetWin_1") is False

    def test_explorer_window_is_not_a_shell_surface(self):
        # File Explorer has a real rename/address field; don't block it.
        assert _is_shell_surface("explorer", "CabinetWClass") is False

    def test_process_name_case_is_ignored(self):
        assert _is_shell_surface("StartMenuExperienceHost", None) is True

    def test_unknown_values_are_not_blocked(self):
        assert _is_shell_surface(None, None) is False


class TestInjectIntoShellSurface:
    @patch("src.text_injector.pyperclip")
    @patch("src.text_injector.pyautogui")
    def test_copies_without_pasting(self, mock_pyautogui, mock_pyperclip):
        mock_pyperclip.paste.return_value = "before"

        injector = TextInjector()
        with patch("src.text_injector._is_desktop_focused", return_value=True):
            result = injector.inject("hello there")

        assert result.pasted is False
        mock_pyautogui.hotkey.assert_not_called()
        mock_pyperclip.copy.assert_called_once_with("hello there")
