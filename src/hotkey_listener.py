import ctypes
import logging
import threading
import time
from typing import Callable

from pynput import keyboard

logger = logging.getLogger(__name__)

# Windows virtual key codes for modifier polling
_VK_CODES = {
    "ctrl_l": 0xA2, "ctrl_r": 0xA3,
    "shift": 0xA0, "shift_r": 0xA1,
    "alt_l": 0xA4, "alt_r": 0xA5,
}


def _vk_pressed(vk: int) -> bool:
    """Is this virtual key physically down right now?"""
    return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)


def _is_key_physically_pressed(vk_name: str) -> bool:
    """Check if a named modifier is currently pressed."""
    vk = _VK_CODES.get(vk_name)
    if vk is None:
        return False
    return _vk_pressed(vk)

_MODIFIER_MAP = {
    "<ctrl>": ("ctrl_l", "ctrl_r"),
    "<shift>": ("shift", "shift_r"),
    "<alt>": ("alt_l", "alt_r"),
}

# All modifier key names
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
        activation_mode: str = "hold",
        on_cancel: Callable | None = None,
    ):
        self._on_press_cb = on_press
        self._on_release_cb = on_release
        #: Called instead of on_release when a press was too short to count.
        #: on_press has already started recording by then, so something has to
        #: end it — without this the recording ran until the max-duration
        #: timer and looked to the user like the hotkey had stuck.
        self._on_cancel_cb = on_cancel
        self._min_hold_duration = min_hold_duration
        #: "hold" = press and hold to record; "toggle" = press to start, press
        #: again to stop. In toggle mode the release is meaningless, so the tap
        #: filter and the release-polling fallback are both skipped.
        self.activation_mode = activation_mode

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
            # Modifier-only combo: trigger when all required modifiers are held
            if self._all_modifiers_held():
                self._handle_press()
        else:
            # Normal combo: trigger when trigger key pressed with modifiers held
            if key == self._trigger_key and self._all_modifiers_held():
                self._handle_press()

    def _on_key_release(self, key) -> None:
        name = self._key_name(key)

        if self._modifier_only:
            # Release fires when ANY of the required modifiers is released
            if name and name in self._modifier_keys:
                self._pressed_modifiers.discard(name)
                self._handle_release()
        else:
            if name and name in self._modifier_keys:
                self._pressed_modifiers.discard(name)
            if key == self._trigger_key:
                self._handle_release()

    def _all_modifiers_held(self) -> bool:
        """Check that at least one variant of each required modifier group is pressed."""
        for token, variants in _MODIFIER_MAP.items():
            needed = set(variants) & self._modifier_keys
            if needed and not (needed & self._pressed_modifiers):
                return False
        return True

    @property
    def is_modifier_only(self) -> bool:
        """True when the hotkey is modifiers alone, with no trigger key.

        Such a combo cannot be used with toggle activation: every Ctrl+Shift
        press would flip recording on or off.
        """
        return self._modifier_only

    def _handle_press(self) -> None:
        if self._toggle_mode:
            # Holding a key repeats its press event; _is_held makes this fire
            # once per real press rather than many times per hold.
            if self._is_held:
                return
            self._is_held = True
            logger.info("Hotkey pressed (toggle)")
            self._on_press_cb()
            # Same safety net hold mode uses: if the key-up event never arrives,
            # _is_held would stick and every later press would be ignored,
            # leaving the hotkey dead until restart.
            self._start_toggle_rearm_poll()
            return

        if self._is_held:
            return
        self._is_held = True
        self._press_time = time.time()
        logger.info("Hotkey pressed")
        self._on_press_cb()
        # Start polling as a safety net for missed release events
        self._start_release_poll()

    @property
    def _toggle_mode(self) -> bool:
        return self.activation_mode == "toggle"

    def _handle_release(self) -> None:
        # In toggle mode the release carries no meaning beyond re-arming the
        # next press; the recording is stopped by pressing again.
        if self._toggle_mode:
            self._is_held = False
            return

        if not self._is_held:
            return
        self._is_held = False

        hold_duration = time.time() - self._press_time
        if hold_duration < self._min_hold_duration:
            logger.info("Tap cancelled (%.0fms < %dms)",
                        hold_duration * 1000, self._min_hold_duration * 1000)
            if self._on_cancel_cb is not None:
                self._on_cancel_cb()
            return

        logger.info("Hotkey released after %.0fms", hold_duration * 1000)
        self._on_release_cb()

    def _rearm_toggle(self) -> None:
        """Clear the press-edge latch once the keys are physically up.

        Unlike hold mode's poll, this fires no callback — in toggle mode the
        recording is stopped by the *next* press, not by letting go.
        """
        if not self._is_held:
            return
        if self._any_modifier_variant_held() and self._trigger_still_held():
            return
        logger.debug("Toggle re-armed via polling fallback")
        self._is_held = False

    def _start_toggle_rearm_poll(self) -> None:
        def _poll():
            while self._is_held:
                time.sleep(0.05)
                self._rearm_toggle()

        t = threading.Thread(target=_poll, daemon=True)
        t.start()

    def _start_release_poll(self) -> None:
        """Poll physical key state to catch releases that pynput misses."""
        def _poll():
            while self._is_held:
                time.sleep(0.05)  # 50ms poll interval
                # Check if ALL required modifiers are still physically held
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
        """Check that at least one variant of each modifier group is physically pressed."""
        for token, variants in _MODIFIER_MAP.items():
            needed = set(variants) & self._modifier_keys
            if needed and not any(_is_key_physically_pressed(v) for v in needed):
                return False
        return True

    def _trigger_vk(self) -> int | None:
        """The trigger key's Windows virtual key code, or None.

        pynput's named keys (Key.space, Key.f1 …) carry their code on
        ``.value.vk``, not on the member itself. Reading only ``.vk`` left
        every named trigger unpollable, so the release poll fell through to
        "assume still held" and could never catch a missed key-up.
        """
        key = self._trigger_key
        if key is None:
            return None
        name = getattr(key, "name", None)
        if name in _VK_CODES:
            return _VK_CODES[name]
        vk = getattr(key, "vk", None)
        if vk:
            return int(vk)
        vk = getattr(getattr(key, "value", None), "vk", None)
        if vk:
            return int(vk)
        return None

    def _trigger_still_held(self) -> bool:
        """Is the trigger key still physically down?

        True for a modifier-only hotkey, which has no trigger key, and true
        for a key whose code cannot be resolved — in that case the modifier
        check is the only safety net there is.
        """
        vk = self._trigger_vk()
        if vk is None:
            return True
        return _vk_pressed(vk)
