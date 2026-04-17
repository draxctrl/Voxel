import logging
import platform
import threading
import time
from typing import Callable

from pynput import keyboard

logger = logging.getLogger(__name__)

_IS_WIN = platform.system() == "Windows"
_IS_MAC = platform.system() == "Darwin"

# Windows virtual key codes for modifier polling (only used on Windows)
_VK_CODES = {
    "ctrl_l": 0xA2, "ctrl_r": 0xA3,
    "shift": 0xA0, "shift_r": 0xA1,
    "alt_l": 0xA4, "alt_r": 0xA5,
}

if _IS_WIN:
    import ctypes

    def _is_key_physically_pressed(vk_name: str) -> bool:
        vk = _VK_CODES.get(vk_name)
        if vk is None:
            return False
        return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)
else:
    def _is_key_physically_pressed(vk_name: str) -> bool:
        # On macOS/Linux we rely on pynput events only (no polling fallback)
        return False


_MODIFIER_MAP = {
    "<ctrl>": ("ctrl_l", "ctrl_r"),
    "<shift>": ("shift", "shift_r"),
    "<alt>": ("alt_l", "alt_r"),
    "<cmd>": ("cmd", "cmd_r"),
}

_ALL_MODIFIER_NAMES = set()
for _variants in _MODIFIER_MAP.values():
    _ALL_MODIFIER_NAMES.update(_variants)


def _parse_hotkey(hotkey_str: str):
    """Parse hotkey string. Returns (modifier_keys, trigger_key).
    If no trigger key, trigger_key is None (modifier-only combo)."""
    parts = [p.strip().lower() for p in hotkey_str.split("+")]
    modifiers = set()
    trigger = None

    for part in parts:
        if part in _MODIFIER_MAP:
            modifiers.update(_MODIFIER_MAP[part])
        else:
            # Strip angle brackets for special keys like <space>, <f1>, <tab>
            bare = part[1:-1] if part.startswith("<") and part.endswith(">") else part
            try:
                if hasattr(keyboard.Key, bare):
                    trigger = getattr(keyboard.Key, bare)
                else:
                    trigger = keyboard.KeyCode.from_char(bare)
            except (KeyError, ValueError):
                trigger = keyboard.KeyCode.from_char(bare)

    return modifiers, trigger


class HotkeyListener:
    def __init__(
        self,
        hotkey_str: str,
        on_press: Callable,
        on_release: Callable,
        min_hold_duration: float = 0.3,
    ):
        self._on_press_cb = on_press
        self._on_release_cb = on_release
        self._min_hold_duration = min_hold_duration

        self._modifier_keys, self._trigger_key = _parse_hotkey(hotkey_str)
        self._modifier_only = self._trigger_key is None
        self._pressed_modifiers: set[str] = set()
        self._is_held = False
        self._press_time: float = 0.0
        self._listener: keyboard.Listener | None = None

        logger.info("Hotkey configured: modifiers=%s, trigger=%s, modifier_only=%s",
                     self._modifier_keys, self._trigger_key, self._modifier_only)

    def start(self) -> None:
        self._listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release,
        )
        self._listener.daemon = True
        self._listener.start()
        logger.info("Hotkey listener started")

    def stop(self) -> None:
        if self._listener:
            self._listener.stop()
            try:
                self._listener.join(timeout=1.0)
            except Exception:
                pass
            self._listener = None
        self._is_held = False
        self._pressed_modifiers.clear()
        logger.info("Hotkey listener stopped")

    def _key_name(self, key) -> str | None:
        if hasattr(key, "name"):
            return key.name
        return None

    def _on_key_press(self, key) -> None:
        name = self._key_name(key)
        if name and name in self._modifier_keys:
            self._pressed_modifiers.add(name)

        if self._modifier_only:
            if self._all_modifiers_held():
                self._handle_press()
        else:
            if key == self._trigger_key and self._all_modifiers_held():
                self._handle_press()

    def _on_key_release(self, key) -> None:
        name = self._key_name(key)

        if self._modifier_only:
            if name and name in self._modifier_keys:
                self._pressed_modifiers.discard(name)
                self._handle_release()
        else:
            if name and name in self._modifier_keys:
                self._pressed_modifiers.discard(name)
            if key == self._trigger_key:
                self._handle_release()

    def _all_modifiers_held(self) -> bool:
        for token, variants in _MODIFIER_MAP.items():
            needed = set(variants) & self._modifier_keys
            if needed and not (needed & self._pressed_modifiers):
                return False
        return True

    def _handle_press(self) -> None:
        if self._is_held:
            return
        self._is_held = True
        self._press_time = time.time()
        logger.info("Hotkey pressed")
        self._on_press_cb()
        # Start polling as a safety net (Windows only — macOS relies on pynput events)
        if _IS_WIN:
            self._start_release_poll()

    def _handle_release(self) -> None:
        if not self._is_held:
            return
        self._is_held = False

        hold_duration = time.time() - self._press_time
        if hold_duration < self._min_hold_duration:
            logger.debug("Tap ignored (%.0fms < %dms)",
                         hold_duration * 1000, self._min_hold_duration * 1000)
            return

        logger.info("Hotkey released after %.0fms", hold_duration * 1000)
        self._on_release_cb()

    def _start_release_poll(self) -> None:
        """Poll physical key state to catch releases that pynput misses (Windows only)."""
        def _poll():
            while self._is_held:
                time.sleep(0.05)
                if self._modifier_only:
                    still_held = self._any_modifier_variant_held()
                else:
                    still_held = self._any_modifier_variant_held() and self._trigger_still_held()
                if not still_held:
                    logger.info("Release detected via polling fallback")
                    self._handle_release()
                    break

        t = threading.Thread(target=_poll, daemon=True)
        t.start()

    def _any_modifier_variant_held(self) -> bool:
        for token, variants in _MODIFIER_MAP.items():
            needed = set(variants) & self._modifier_keys
            if needed and not any(_is_key_physically_pressed(v) for v in needed):
                return False
        return True

    def _trigger_still_held(self) -> bool:
        if self._trigger_key is None:
            return True
        if _IS_WIN:
            if hasattr(self._trigger_key, 'name'):
                vk_name = self._trigger_key.name
                if vk_name in _VK_CODES:
                    return _is_key_physically_pressed(vk_name)
            if hasattr(self._trigger_key, 'vk') and self._trigger_key.vk:
                return bool(ctypes.windll.user32.GetAsyncKeyState(self._trigger_key.vk) & 0x8000)
        return True
