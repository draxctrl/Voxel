# Separate Toggle Shortcut Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Push-to-talk and press-to-start/press-to-stop each get their own key, both active at once.

**Architecture:** Two `HotkeyListener`s run side by side - one in hold mode on `hotkey`, one in toggle mode on the new `toggle_hotkey` - wrapped in a small `HotkeySet` so the app still holds one `_hotkey_listener` object. `activation_mode` is retired by a config migration. The Shortcuts pane shows two key rows and drops the mode choice.

**Tech Stack:** Python 3.13, PyQt6, pynput. Tests: `py -3.13 -m pytest -q` from the repo root (no venv; plain `python` lacks pytest). Full run takes ~4 min.

**Spec:** `docs/superpowers/specs/2026-11-22-separate-toggle-shortcut-design.md`

## Global Constraints

- Config keys: `hotkey` (push to talk), `toggle_hotkey` (press to start, press to stop). Empty string = turned off. `toggle_hotkey` default `""`.
- Row copy, verbatim: "Push to talk" / "Hold these keys and speak"; "Press to start, press to stop" / "Tap once to begin, tap again when you are done". Off value reads "Not set". Buttons: "Change", "Turn off".
- Never both keys off; never the same key on both rows. Refusals keep the previous value and show the orange warning label.
- Builds on the uncommitted clean-tap change already in the working tree (`HotkeyListener._tap_to_toggle`).
- No commits until Isuru says so (his standing rule); leave changes in the working tree.

## Review Focus

1. Ctrl + Alt push-to-talk with Ctrl + Alt + Space press-to-start: pressing Ctrl+Alt+Space must start a toggle recording and leave no push-to-talk recording behind - Task 1 + Task 4 tests.
2. An old config with `activation_mode: "toggle"` must keep its key working the same way after upgrade - Task 2 test.
3. Pressing push-to-talk during a press-to-start recording types the text instead of throwing it away - Task 4 test.
4. "Same key" must compare keys, not strings: `<ctrl>+<alt>` and `<alt>+<ctrl>` are the same - Task 1 test.
5. With push-to-talk off, splash/status/first-run must name the press-to-start key, not show blank - Task 3 test.

---

### Task 1: Listener - extra keys cancel a modifier-only hold; `same_hotkey`; `HotkeySet`

**Files:**
- Modify: `src/hotkey_listener.py`
- Test: `tests/test_hotkey_listener.py`

**Interfaces:**
- Produces: `same_hotkey(a: str, b: str) -> bool` (compares parsed `(modifiers, trigger)`; False if either is empty).
- Produces: `class HotkeySet` with `__init__(self, hold: HotkeyListener | None, toggle: HotkeyListener | None)`, `start()`, `stop()`, attributes `hold`, `toggle`.

- [ ] **Step 1: Write failing tests**
  - `test_another_key_during_a_modifier_only_hold_cancels_it`: hold-mode `<ctrl>+<alt>` listener, `_start_release_poll` patched; press ctrl_l, alt_l, then `Key.space` -> `on_cancel` called once; then release all -> `on_release` not called.
  - `test_same_hotkey_ignores_order`: `same_hotkey("<ctrl>+<alt>", "<alt>+<ctrl>")` is True; `same_hotkey("<ctrl>+<alt>", "<ctrl>+<alt>+space")` is False; `same_hotkey("", "")` is False.
  - `test_hotkey_set_starts_and_stops_both`: two MagicMocks -> `start()`/`stop()` called on each; `HotkeySet(None, m)` works.
- [ ] **Step 2:** `py -3.13 -m pytest -q tests/test_hotkey_listener.py` - new tests FAIL.
- [ ] **Step 3: Implement.** In `_on_key_press`, hold mode with `_modifier_only` and `_is_held`: a key not in `_modifier_keys` sets `_is_held = False` and calls `_on_cancel_cb` (if set). Add `same_hotkey` and `HotkeySet` at module level.
- [ ] **Step 4:** same command - all PASS.

### Task 2: Config - `toggle_hotkey` and the `activation_mode` migration

**Files:**
- Modify: `src/config.py`, `tests/test_pipeline.py:177`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `DEFAULT_CONFIG["toggle_hotkey"] == ""`; `"activation_mode"` no longer in `DEFAULT_CONFIG` or in loaded data.

- [ ] **Step 1: Write failing tests** in `tests/test_config.py`:
  - `test_toggle_hotkey_defaults_to_off`: fresh load -> `get("toggle_hotkey") == ""`, `get("hotkey") == "<ctrl>+<shift>+space"`.
  - `test_a_toggle_user_keeps_their_key_behaving_the_same`: saved `{"hotkey": "k", "activation_mode": "toggle"}` -> after load `toggle_hotkey == "k"`, `hotkey == ""`, `get("activation_mode") is None`.
  - `test_a_hold_user_is_unchanged`: saved `{"hotkey": "<ctrl>+<alt>", "activation_mode": "hold"}` -> `hotkey == "<ctrl>+<alt>"`, `toggle_hotkey == ""`, no `activation_mode`.
- [ ] **Step 2:** run `tests/test_config.py` - FAIL.
- [ ] **Step 3:** Replace the `activation_mode` default with `toggle_hotkey: ""`; add `_migrate_activation_mode()` called from `load()`. Change `tests/test_pipeline.py:177` to assert `DEFAULT_CONFIG["toggle_hotkey"] == ""`.
- [ ] **Step 4:** run `tests/test_config.py tests/test_pipeline.py` - PASS.

### Task 3: Naming the shortcut - `dictation_shortcut`

**Files:**
- Modify: `src/ui_pyqt6/keys.py`, `src/main.py` (splash at ~169, `_startup_finish` "Ready!" text), `src/ui_pyqt6/settings_window.py:122`, `src/ui_pyqt6/first_run.py:390`
- Test: `tests/test_keys.py`, `tests/test_first_run.py`

**Interfaces:**
- Produces: `dictation_shortcut(config) -> tuple[str, str]` in `keys.py`: `(pretty key, "hold")` when `hotkey` set, else `(pretty toggle_hotkey, "toggle")`, else `("", "hold")`.

- [ ] **Step 1: Failing tests:** `dictation_shortcut` returns `("Ctrl + Alt", "hold")` / `("K", "toggle")` / `("", "hold")` for the three configs; first-run hint with only `toggle_hotkey="k"` reads `"Waiting for you. Press K, say anything, then press it again."`.
- [ ] **Step 2:** run - FAIL.
- [ ] **Step 3:** Implement; splash, rail status and first run use it. Hold hint stays `"Waiting for you. Hold %s and say anything."`. `_startup_finish` text: `"Ready! Hold %s to dictate"` / `"Ready! Press %s to dictate"`.
- [ ] **Step 4:** run - PASS.

### Task 4: App wiring - both listeners, and either key stops a recording

**Files:**
- Modify: `src/main.py` (`_start_hotkey_listener`, `_on_hotkey_press`, `_on_hotkey_trigger`, `_HOTKEY_KEYS`, `apply_setting` cleaner branch)
- Test: `tests/test_apply_setting.py`, `tests/test_startup.py`

**Interfaces:**
- Consumes: `HotkeySet`, `HotkeyListener` (Task 1); `toggle_hotkey` (Task 2).
- Produces: `self._hotkey_listener: HotkeySet | None`; `self._recording_source: str | None` (`"hold"`/`"toggle"`).

- [ ] **Step 1: Failing tests:**
  - `test_apply_setting.py`: rename the activation-mode test to `test_the_toggle_hotkey_restarts_the_listener` using `apply_setting("toggle_hotkey", "k")`.
  - `test_startup.py`: `test_both_keys_get_a_listener` - config `hotkey="<ctrl>+<alt>"`, `toggle_hotkey="k"`, `HotkeyListener` patched -> two constructions, one with `activation_mode="hold"` and `hotkey_str="<ctrl>+<alt>"`, one with `activation_mode="toggle"`, `hotkey_str="k"`, `on_press=app._on_hotkey_trigger`.
  - `test_an_off_key_gets_no_listener`: `toggle_hotkey=""` -> one construction.
  - `test_push_to_talk_during_a_toggle_recording_finishes_it`: `_recording_source="toggle"`, recorder recording -> `_on_hotkey_press()` calls `_on_hotkey_release` path (recorder `stop` called, `_process_audio` thread started / state "processing"), not cancel.
  - Existing `test_pressing_again_while_recording_cancels_it` keeps passing with `_recording_source="hold"`.
- [ ] **Step 2:** run both files - FAIL.
- [ ] **Step 3:** Implement. `_start_hotkey_listener` builds a `HotkeySet` from non-empty keys (both get `on_cancel=self._cancel_recording`). `_on_hotkey_press` sets `_recording_source="hold"` on start; when already recording and source is `"toggle"` it calls `_on_hotkey_release()`. `_on_hotkey_trigger` sets `"toggle"` on start. `_HOTKEY_KEYS = {"hotkey", "toggle_hotkey"}`.
- [ ] **Step 4:** run - PASS.

### Task 5: Shortcuts pane - two rows, Turn off, refusals

**Files:**
- Modify: `src/ui_pyqt6/panes/shortcuts.py`
- Test: `tests/test_pane_shortcuts.py` (drop the mode-choice and modifier-only classes)

**Interfaces:**
- Consumes: `same_hotkey` (Task 1).
- Produces: `ShortcutsPane.OWNS == {"hotkey", "toggle_hotkey"}`; `set_key(key: str, combo: str)`, `turn_off(key: str)`, `key_text(key: str) -> str`, `warning_text()`.

- [ ] **Step 1: Failing tests:**
  - both rows show their key; an empty key shows `"Not set"`.
  - `set_key("toggle_hotkey", "k")` applies `("toggle_hotkey", "k")` and leaves `hotkey` untouched.
  - `set_key("toggle_hotkey", "<alt>+<ctrl>")` while `hotkey="<ctrl>+<alt>"` -> nothing applied, warning non-empty.
  - `turn_off("toggle_hotkey")` applies `("toggle_hotkey", "")`.
  - `turn_off("hotkey")` while `toggle_hotkey==""` -> nothing applied, warning non-empty.
  - the pane has no "How it activates" heading (no `_mode_rows` attribute).
- [ ] **Step 2:** run - FAIL.
- [ ] **Step 3:** Implement; `_ShortcutRow` gains a "Turn off" button (hidden when the key is already off). Warning copy: same key -> `"%s is already your %s key. Pick a different one."`; last key -> `"Keep at least one shortcut, or Voxel has no way to start."`.
- [ ] **Step 4:** run - PASS.

### Task 6: Whole-suite check and look at it

- [ ] `py -3.13 -m pytest -q` - all pass.
- [ ] Render the Shortcuts pane to PNG (offscreen, dark theme, `hotkey="<ctrl>+<alt>"`, `toggle_hotkey=""`) and look at it: rows aligned, buttons not clipped, "Not set" readable.
