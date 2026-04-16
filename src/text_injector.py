import ctypes
import logging
import platform
import subprocess
import time

import pyautogui
import pyperclip

try:
    import winsound
except ImportError:
    winsound = None

logger = logging.getLogger(__name__)

_PASTE_DELAY = 0.05
_IS_MAC = platform.system() == "Darwin"
_IS_WIN = platform.system() == "Windows"

# Windows class names that indicate no real app is focused
_NO_TEXT_CLASSES = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}


def _play_sound(path: str) -> None:
    """Play a sound file cross-platform."""
    if winsound:
        winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
    elif _IS_MAC:
        subprocess.Popen(["afplay", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.Popen(["aplay", "-q", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _is_desktop_focused() -> bool:
    """Check if the desktop, taskbar, or no real window is focused (Windows only)."""
    if not _IS_WIN:
        return False
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return True
        buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buf, 256)
        return buf.value in _NO_TEXT_CLASSES
    except Exception:
        return False


class TextInjector:
    def __init__(self, chime_path: str | None = None, always_copy: bool = False):
        self._chime_path = chime_path
        self._always_copy = always_copy

    @staticmethod
    def is_desktop_focused() -> bool:
        """Check if desktop/taskbar is focused."""
        return _is_desktop_focused()

    def play_chime(self) -> None:
        """Play the chime sound immediately."""
        if self._chime_path:
            try:
                _play_sound(self._chime_path)
            except Exception as e:
                logger.warning("Failed to play chime: %s", e)

    def inject(self, text: str) -> bool:
        """Inject text. Returns True if pasted, False if clipboard-only.

        If always_copy is True, text is always left on clipboard.
        If desktop/taskbar is focused, skips paste and returns False.
        """
        logger.info("Injecting %d chars into focused app", len(text))

        desktop = _is_desktop_focused()

        if desktop:
            logger.info("Desktop/taskbar focused — copying to clipboard only")
            pyperclip.copy(text)
            return False

        if self._always_copy:
            pyperclip.copy(text)
            time.sleep(_PASTE_DELAY)
            paste_modifier = "command" if _IS_MAC else "ctrl"
            pyautogui.hotkey(paste_modifier, "v")
            # Leave text on clipboard
            return True
        else:
            try:
                old_clipboard = pyperclip.paste()
            except Exception:
                old_clipboard = ""

            pyperclip.copy(text)
            time.sleep(_PASTE_DELAY)
            paste_modifier = "command" if _IS_MAC else "ctrl"
            pyautogui.hotkey(paste_modifier, "v")
            time.sleep(0.1)

            try:
                pyperclip.copy(old_clipboard)
            except Exception as e:
                logger.warning("Failed to restore clipboard: %s", e)
            return True
