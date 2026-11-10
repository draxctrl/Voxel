import ctypes
import logging
import platform
import subprocess
import time
from dataclasses import dataclass

import pyautogui
import pyperclip

try:
    import winsound
except ImportError:
    winsound = None

logger = logging.getLogger(__name__)


@dataclass
class InjectionResult:
    pasted: bool          # True if Ctrl+V was sent
    old_clipboard: str    # what was on clipboard before
    injected_text: str    # what was injected


_PASTE_DELAY = 0.05
_IS_MAC = platform.system() == "Darwin"
_IS_WIN = platform.system() == "Windows"

# Windows class names that indicate no real app is focused
_NO_TEXT_CLASSES = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}

# Shell surfaces that look like text fields but execute what you type into them.
# The Windows 11 Start menu and search are XAML island windows, so their class
# names are generic ("Windows.UI.Core.CoreWindow") and shared with real apps —
# the owning process is the reliable signal. Pasting here made Windows try to
# run the dictation as a command.
_NO_TEXT_PROCESSES = {
    "startmenuexperiencehost",
    "searchhost",
    "searchapp",
    "searchui",
    "shellexperiencehost",
}


def _is_shell_surface(process_name: str | None, window_class: str | None) -> bool:
    """True when the focused window is a shell surface, not a text field.

    Kept pure so both signals can be tested without a live desktop.
    """
    if window_class and window_class in _NO_TEXT_CLASSES:
        return True
    if process_name and process_name.lower() in _NO_TEXT_PROCESSES:
        return True
    return False


def _play_sound(path: str) -> None:
    """Play a sound file cross-platform."""
    if winsound:
        winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
    elif _IS_MAC:
        subprocess.Popen(["afplay", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.Popen(["aplay", "-q", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _is_desktop_focused() -> bool:
    """True when the focused window can't accept pasted text (Windows only).

    Covers the desktop and taskbar, and the Start menu and search, which would
    otherwise *execute* the pasted text. Any failure returns False so a
    detection problem degrades to pasting rather than silently swallowing
    dictation.
    """
    if not _IS_WIN:
        return False
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return True

        buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buf, 256)
        window_class = buf.value

        try:
            from src.app_detector import AppDetector
            process_name = AppDetector().get_active_app()
        except Exception:
            process_name = None

        return _is_shell_surface(process_name, window_class)
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

    def inject(self, text: str) -> InjectionResult:
        """Inject text. Returns an InjectionResult with paste status and clipboard info.

        If always_copy is True, text is always left on clipboard.
        If desktop/taskbar is focused, skips paste and returns pasted=False.
        """
        logger.info("Injecting %d chars into focused app", len(text))

        try:
            old_clipboard = pyperclip.paste()
        except Exception:
            old_clipboard = ""

        desktop = _is_desktop_focused()

        if desktop:
            logger.info("Desktop/taskbar focused — copying to clipboard only")
            pyperclip.copy(text)
            return InjectionResult(pasted=False, old_clipboard=old_clipboard, injected_text=text)

        if self._always_copy:
            pyperclip.copy(text)
            time.sleep(_PASTE_DELAY)
            paste_modifier = "command" if _IS_MAC else "ctrl"
            pyautogui.hotkey(paste_modifier, "v")
            # Leave text on clipboard
            return InjectionResult(pasted=True, old_clipboard=old_clipboard, injected_text=text)
        else:
            pyperclip.copy(text)
            time.sleep(_PASTE_DELAY)
            paste_modifier = "command" if _IS_MAC else "ctrl"
            pyautogui.hotkey(paste_modifier, "v")
            time.sleep(0.1)

            try:
                pyperclip.copy(old_clipboard)
            except Exception as e:
                logger.warning("Failed to restore clipboard: %s", e)
            return InjectionResult(pasted=True, old_clipboard=old_clipboard, injected_text=text)
