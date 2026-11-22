"""Turning a stored hotkey into something a person can read.

Voxel stores hotkeys the way pynput writes them - `<ctrl>+<shift>+space` -
and that string is fine in a config file and wrong on screen.
"""
from __future__ import annotations

_NAMES = {
    "ctrl": "Ctrl",
    "shift": "Shift",
    "alt": "Alt",
    "alt_gr": "AltGr",
    "cmd": "Win",
    "space": "Space",
    "esc": "Esc",
    "enter": "Enter",
    "tab": "Tab",
    "backspace": "Backspace",
    "caps_lock": "Caps Lock",
}


def pretty_hotkey(raw: str | None) -> str:
    """`<ctrl>+<shift>+space` -> `Ctrl + Shift + Space`."""
    if not raw:
        return ""
    parts = []
    for piece in str(raw).split("+"):
        piece = piece.strip().strip("<>").strip()
        if not piece:
            continue
        parts.append(_NAMES.get(piece.lower(), piece.upper() if len(piece) == 1 else piece.title()))
    return " + ".join(parts)


def dictation_shortcut(config) -> tuple[str, str]:
    """The one key to name on screen, and how it is used.

    Push-to-talk if it is set, otherwise the press-to-start key:
    `("Ctrl + Alt", "hold")`, `("K", "toggle")`, or `("", "hold")`.
    """
    hold = pretty_hotkey(config.get("hotkey", ""))
    if hold:
        return hold, "hold"
    toggle = pretty_hotkey(config.get("toggle_hotkey", ""))
    if toggle:
        return toggle, "toggle"
    return "", "hold"
