"""Listening for one key combination and writing it the way pynput reads it.

Ported from the old settings window. It lives on its own because two panes
and, later, the first-run flow all need it, and because the pure part -
turning captured keys into a hotkey string - is worth testing without a
keyboard.
"""
from __future__ import annotations

import logging

from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)

_MODIFIER_MAP: dict[str, str] = {
    "ctrl_l": "<ctrl>",
    "ctrl_r": "<ctrl>",
    "ctrl": "<ctrl>",
    "shift": "<shift>",
    "shift_l": "<shift>",
    "shift_r": "<shift>",
    "alt_l": "<alt>",
    "alt_r": "<alt>",
    "alt": "<alt>",
    "alt_gr": "<alt_gr>",
    "cmd": "<cmd>",
    "cmd_l": "<cmd>",
    "cmd_r": "<cmd>",
}

_SPECIAL_KEYS: frozenset[str] = frozenset(
    {
        "space", "tab", "enter", "return", "backspace", "delete", "escape",
        "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10",
        "f11", "f12", "f13", "f14", "f15", "f16", "f17", "f18", "f19", "f20",
        "home", "end", "page_up", "page_down",
        "left", "right", "up", "down",
        "insert", "print_screen", "scroll_lock", "pause",
        "num_lock",
    }
)

MODIFIER_ORDER = ("<ctrl>", "<shift>", "<alt>", "<alt_gr>", "<cmd>")


def key_token(key) -> str | None:
    """A pynput key or key code as the token a hotkey string uses."""
    name = getattr(key, "name", None)
    if name:
        lowered = name.lower()
        if lowered in _MODIFIER_MAP:
            return _MODIFIER_MAP[lowered]
        return "<%s>" % lowered
    char = getattr(key, "char", None)
    if char:
        return char.lower()
    return None


def build_hotkey(tokens) -> str:
    """Captured tokens as a pynput hotkey string, modifiers first.

    The order is canonical rather than the order they were pressed, so the
    same combination always saves as the same string.
    """
    modifiers = [t for t in tokens if t in MODIFIER_ORDER]
    regulars = sorted(t for t in tokens if t not in MODIFIER_ORDER)
    modifiers.sort(key=MODIFIER_ORDER.index)
    parts = modifiers + regulars
    return "+".join(parts)


class _Capture(QObject):
    """Owns one listener. Qt objects may only be touched on the GUI thread,
    so the combo crosses back over a signal."""

    captured = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self._tokens: set[str] = set()
        self._listener = None

    def start(self, on_captured) -> None:
        from pynput import keyboard as pynput_keyboard

        self.captured.connect(on_captured)
        self._tokens = set()
        self._listener = pynput_keyboard.Listener(
            on_press=self._on_press, on_release=self._on_release
        )
        self._listener.daemon = True
        self._listener.start()

    def _on_press(self, key) -> None:
        token = key_token(key)
        if token:
            self._tokens.add(token)

    def _on_release(self, key) -> None:
        if not self._tokens:
            return
        combo = build_hotkey(self._tokens)
        self._stop()
        self.captured.emit(combo)

    def _stop(self) -> None:
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception as e:
                logger.debug("Could not stop the capture listener: %s", e)
            self._listener = None


#: The live capture, kept alive while it listens.
_active: _Capture | None = None


def capture_hotkey(on_captured) -> None:
    """Listen for one combination, then call `on_captured(combo)`.

    Finishing on the first release means the user presses the combination
    once rather than holding it and hunting for a confirm button.
    """
    global _active
    if _active is not None:
        _active._stop()
    _active = _Capture()
    _active.start(on_captured)
