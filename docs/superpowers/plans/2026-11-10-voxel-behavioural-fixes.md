# Voxel Behavioural Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Voxel's settings honest — the microphone you pick is the one that records, the dictation mode you pick is the one that runs, the unpredictable undo hotkey is gone, and you can choose between holding the hotkey and toggling it.

**Architecture:** All changes are to the existing `src/` modules; no new subsystems. The two structural moves are (a) identifying the microphone by **name** instead of a volatile PyAudio index, and (b) resolving one **effective profile** per dictation inside `_process_audio` instead of mutating `TextCleaner`'s prompt in place. Activation mode is a flag on `HotkeyListener` that suppresses release handling; the recording state itself is read from `MicRecorder`, never mirrored in a second boolean.

**Tech Stack:** Python 3.13, PyAudio, pynput, PyQt6, Groq SDK, pytest.

**Spec:** [`docs/superpowers/specs/2026-11-10-voxel-fixes-design.md`](../specs/2026-11-10-voxel-fixes-design.md)

This plan covers **Part one** of that spec only. The iOS redesign (Part two) is a
separate plan, written after this one ships.

## Global Constraints

- Python 3.13 — run everything with `py -3.13`, not bare `python` (that resolves to 3.12 here, which lacks the deps).
- Test command: `py -3.13 -m pytest -q`. Full suite must be green at the end of every task.
- Config lives at `%APPDATA%\Voxel\config.json`. Every new key needs a `DEFAULT_CONFIG` entry.
- **Existing user configs must keep working.** Migrations run in `Config.load()` and are silent.
- The `__RAW__` sentinel stays as the marker for "skip LLM cleanup".
- Every built-in profile prompt except `__RAW__` contains the literal `{raw_transcript}`.
- No visual redesign in this plan — new controls use the existing `_TickCheckBox` / `_ArrowComboBox` widgets and current styling. The iOS pass replaces them later.
- No new runtime dependencies.

## Review Focus

Failure modes the spec implies but which no feature's happy path exercises. Each has a test assigned to the task that owns the code.

1. **Two input devices with the same name** — resolution must be deterministic (first match by index order), not arbitrary. *Task 2.*
2. **A config written by the current version**, where `mic_device` is a bare integer and no name key exists — must migrate without the user noticing. *Task 2.*
3. **`active_profile` or an `app_profiles` value naming a profile id that consolidation removed** — must land on a sensible mode, never crash or silently fall back to a different style of cleanup than the user had. *Task 5.*
4. **The 2-minute cap firing while in toggle mode** — the next hotkey press must start a new recording, not be swallowed as a "stop". *Task 8.*
5. **A modifier-only hotkey combined with toggle mode** — every Ctrl+Shift press would flip recording; must be refused rather than shipped as a trap. *Task 8.*

---

### Task 1: Repair the red test suite and the dependency list

Nothing else in this plan can claim "tests pass" until this is true. All three failures and the import error pre-date this work.

**Files:**
- Modify: `tests/test_mic_recorder.py` (import of removed `SAMPLE_RATE`)
- Modify: `tests/test_profiles.py:38`, `tests/test_profiles.py:149`
- Modify: `tests/test_text_injector.py` (chime mock)
- Modify: `requirements.txt`

**Interfaces:**
- Consumes: nothing.
- Produces: a green baseline. No source API changes.

- [ ] **Step 1: Run the suite and record the baseline**

Run: `py -3.13 -m pytest -q`
Expected: 1 collection error (`test_mic_recorder.py`), 3 failures, 88 passed.

- [ ] **Step 2: Fix the collection error**

`tests/test_mic_recorder.py` imports `SAMPLE_RATE`, which is now `TARGET_SAMPLE_RATE` in `src/mic_recorder.py`. Update the import and every use.

- [ ] **Step 3: De-hardcode the two profile assertions**

In `test_builtin_profiles_have_name_and_prompt`, exempt the raw sentinel:

```python
for pid, profile in ProfileManager.BUILTIN_PROFILES.items():
    assert "name" in profile
    assert "prompt" in profile
    if profile["prompt"] != "__RAW__":
        assert "{raw_transcript}" in profile["prompt"]
```

In `test_custom_profiles_merge_with_builtins`, assert against the live count so adding profiles never breaks it again:

```python
assert len(profiles) == len(ProfileManager.BUILTIN_PROFILES) + 1
```

- [ ] **Step 4: Fix `test_inject_plays_chime_when_path_given`**

It asserts `winsound.PlaySound` was called once, but `inject()` no longer plays the chime — `play_chime()` does, called separately from `main.py`. Point the test at `play_chime()`.

- [ ] **Step 5: Correct `requirements.txt`**

Add `PyQt6` (the entire UI imports it and it is absent). Remove `customtkinter` and `pystray`— verify with `grep -rn "customtkinter\|pystray" src/` first; `pystray` **is** used by `src/tray_app.py`, so keep it and remove only `customtkinter`. Add `pytest` so the suite is runnable from a clean checkout.

- [ ] **Step 6: Verify green**

Run: `py -3.13 -m pytest -q`
Expected: 0 failures, 0 errors.

- [ ] **Step 7: Commit**

```bash
git add tests/ requirements.txt
git commit -m "fix: repair pre-existing test failures and correct requirements"
```

---

### Task 2: Identify the microphone by name

**Files:**
- Modify: `src/mic_recorder.py`
- Modify: `src/config.py` (new keys + migration)
- Test: `tests/test_mic_recorder.py`, `tests/test_config.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `find_input_device_by_name(pa, name: str) -> int | None` in `src/mic_recorder.py` — module-level, returns the **lowest** matching device index, or `None`.
  - `MicRecorder(device_name: str | None = None, device_index: int | None = None)` — resolution order: name, then index, then system default.
  - `MicRecorder.active_device_name -> str | None` — what is actually open.
  - `MicRecorder.requested_device_missing -> bool` — `True` when a name was asked for and not found.
  - Config keys `mic_device_name: str | None` (new, authoritative) and `mic_device: int | None` (retained as a hint).

- [ ] **Step 1: Write the failing tests**

Use a stub exposing `get_device_count()` and `get_device_info_by_index(i)` returning dicts with `name` and `maxInputChannels` — no real PyAudio.

```python
def test_finds_device_index_by_exact_name():
    pa = _FakePA([("Realtek Mic", 1), ("Blue Yeti", 1)])
    assert find_input_device_by_name(pa, "Blue Yeti") == 1

def test_returns_none_when_name_absent():
    pa = _FakePA([("Realtek Mic", 1)])
    assert find_input_device_by_name(pa, "Blue Yeti") is None

def test_ignores_output_only_devices():
    pa = _FakePA([("Speakers", 0), ("Blue Yeti", 1)])
    assert find_input_device_by_name(pa, "Speakers") is None

def test_duplicate_names_resolve_to_lowest_index():   # Review Focus 1
    pa = _FakePA([("USB Audio", 1), ("USB Audio", 1)])
    assert find_input_device_by_name(pa, "USB Audio") == 0
```

And in `tests/test_config.py`, the migration (Review Focus 2):

```python
def test_legacy_integer_mic_device_is_preserved_as_hint(tmp_path):
    # config written by the old version: {"mic_device": 3}, no name key
    # after load(): mic_device == 3 and mic_device_name is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3.13 -m pytest tests/test_mic_recorder.py tests/test_config.py -q`
Expected: FAIL — `find_input_device_by_name` not defined.

- [ ] **Step 3: Implement `find_input_device_by_name` and the new `MicRecorder` signature**

Skip devices with `maxInputChannels <= 0`. In `MicRecorder._start_stream`, resolve the index before opening, and set `active_device_name` from the device actually opened. Set `requested_device_missing = True` only when `device_name` was given and resolution failed. `_find_supported_rate` keeps working off the resolved index.

- [ ] **Step 4: Add `mic_device_name` to `DEFAULT_CONFIG`**

Default `None`. No migration code is needed for the legacy integer — it stays readable as the hint. Confirm the config test passes.

- [ ] **Step 5: Run tests to verify they pass**

Run: `py -3.13 -m pytest tests/test_mic_recorder.py tests/test_config.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/mic_recorder.py src/config.py tests/
git commit -m "feat: identify microphone by name so device renumbering can't switch it"
```

---

### Task 3: Tell the user when the microphone isn't the one they chose

**Files:**
- Modify: `src/main.py` (construct `MicRecorder` with the name; surface the warning)
- Modify: `src/ui_pyqt6/settings_ui.py` (`_populate_mics` saves the name; status line shows the active device)
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `MicRecorder.active_device_name`, `MicRecorder.requested_device_missing` (Task 2).
- Produces: nothing new for later tasks.

- [ ] **Step 1: Write the failing test**

```python
def test_missing_requested_mic_still_records_and_flags_fallback():
    # MicRecorder asked for "Blue Yeti", only "Realtek Mic" present:
    #   requested_device_missing is True
    #   active_device_name == "Realtek Mic"
    #   start()/stop() still return WAV bytes
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3.13 -m pytest tests/test_pipeline.py -q`
Expected: FAIL.

- [ ] **Step 3: Pass the saved name through `main.py`**

`VoxelApp.__init__` and `_on_settings_saved` construct `MicRecorder(device_name=self._config.get("mic_device_name"), device_index=self._config.get("mic_device"))`.

- [ ] **Step 4: Save the device name in settings**

In `_save`, write both `mic_device_name` (`self._mic_combo.currentText()`) and `mic_device` (`currentData()`). In `_populate_mics`, select the saved entry by **name** first, falling back to the index.

- [ ] **Step 5: Surface the warning**

After the recorder is constructed, if `requested_device_missing`, show it: the Settings status label (`_set_status`, `_WARNING` colour) naming both the missing and the active device. Log at WARNING too. The overlay carries the same notice when recording starts — reuse `RecordingOverlay.show_clipboard_notice`'s mechanism rather than inventing a new overlay state.

- [ ] **Step 6: Run the full suite**

Run: `py -3.13 -m pytest -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/main.py src/ui_pyqt6/settings_ui.py tests/
git commit -m "feat: warn when the chosen microphone is missing instead of switching silently"
```

---

### Task 4: Remove the undo hotkey

**Files:**
- Modify: `src/main.py` (remove `_start_undo_listener`, `_on_undo_press`, undo state, listener teardown)
- Modify: `src/config.py` (drop `undo_hotkey` from `DEFAULT_CONFIG`)
- Modify: `src/ui_pyqt6/settings_ui.py` (remove the undo row, its capture target, the FAQ entry)
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `InjectionResult.old_clipboard` **stays** — `TextInjector` still uses it to restore the clipboard after pasting. Only the hotkey and its state are removed.

- [ ] **Step 1: Write the failing test**

```python
def test_undo_hotkey_is_gone():
    assert "undo_hotkey" not in DEFAULT_CONFIG
    assert not hasattr(VoxelApp, "_on_undo_press")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3.13 -m pytest tests/test_pipeline.py -q`
Expected: FAIL.

- [ ] **Step 3: Remove it**

From `main.py`: `_undo_listener`, `_start_undo_listener`, `_on_undo_press`, `_last_injection`, `_last_injection_time`, `_undo_lock`, `UNDO_STALE_SECONDS`, both assignment sites in `_process_audio`, and the teardown in `_quit`. Drop the now-unused `pyautogui` import **only if** nothing else in the module uses it. From `settings_ui.py`: the "Undo hotkey" label and row, `_undo_hotkey_edit`, `_undo_capture_btn`, the `target="undo"` branch in `_toggle_hotkey_capture`, the `undo_hotkey` line in `_save`, and the undo FAQ entry.

- [ ] **Step 4: Run the full suite**

Run: `py -3.13 -m pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ tests/
git commit -m "feat!: remove the undo hotkey, which sent a blind Ctrl+Z to any focused app"
```

---

### Task 5: Consolidate the dictation modes and add the two grammar modes

**Files:**
- Modify: `src/profiles.py` (`BUILTIN_PROFILES`, new `migrate_profile_id`)
- Modify: `src/config.py` (run the migration in `load()`)
- Test: `tests/test_profiles.py`, `tests/test_config.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - Final built-in ids: `raw`, `grammar_only`, `grammar_tidy`, `professional`, `code`, `technical`.
  - `ProfileManager.LEGACY_PROFILE_IDS: dict[str, str]` — `{"default": "grammar_tidy", "casual": "grammar_only"}`.
  - `ProfileManager.migrate_profile_id(profile_id: str) -> str` — maps a removed id to its replacement, returns unknown ids unchanged.

- [ ] **Step 1: Write the failing tests**

```python
def test_grammar_only_and_grammar_tidy_exist():
    assert "grammar_only" in ProfileManager.BUILTIN_PROFILES
    assert "grammar_tidy" in ProfileManager.BUILTIN_PROFILES

def test_removed_ids_map_to_replacements():
    assert ProfileManager.migrate_profile_id("default") == "grammar_tidy"
    assert ProfileManager.migrate_profile_id("casual") == "grammar_only"

def test_unknown_id_passes_through():
    assert ProfileManager.migrate_profile_id("my_custom") == "my_custom"

def test_grammar_only_prompt_preserves_filler_words():
    p = ProfileManager.BUILTIN_PROFILES["grammar_only"]["prompt"]
    assert "{raw_transcript}" in p

def test_active_profile_is_migrated_on_load(tmp_path):      # Review Focus 3
    # config {"active_profile": "default"} -> after load(), "grammar_tidy"

def test_app_profile_values_are_migrated_on_load(tmp_path):  # Review Focus 3
    # config {"app_profiles": {"Code.exe": "casual"}} -> {"Code.exe": "grammar_only"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3.13 -m pytest tests/test_profiles.py tests/test_config.py -q`
Expected: FAIL.

- [ ] **Step 3: Rewrite `BUILTIN_PROFILES`**

Six entries. Each prompt keeps the existing no-censorship clause verbatim and ends with `Dictated text: "{raw_transcript}"`. The two new ones must be genuinely distinguishable:

- `grammar_only` — "Grammar only — keep my words": fix grammar, tense, agreement, spelling, punctuation. **Keep filler words, slang, and sentence structure exactly as spoken.** Change nothing else.
- `grammar_tidy` — "Grammar + tidy up": fix grammar *and* remove filler words so it reads cleanly.

Rewrite `professional`, `code` and `technical` so each is clearly distinct rather than a restatement of the same instructions. `raw` is unchanged.

- [ ] **Step 4: Implement the migration**

Add `LEGACY_PROFILE_IDS` and `migrate_profile_id`. In `Config.load()`, after merging saved data, rewrite `active_profile` and every value in `app_profiles` through it. An id that is neither built-in nor custom falls back to `grammar_tidy` at *use* time via the existing `get_active_profile` warning path — do not delete custom profiles.

- [ ] **Step 5: Run tests to verify they pass**

Run: `py -3.13 -m pytest tests/test_profiles.py tests/test_config.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/profiles.py src/config.py tests/
git commit -m "feat: consolidate dictation modes and add two distinct grammar modes"
```

---

### Task 6: Resolve one effective profile per dictation

Fixes three bugs in one block: the sticky auto-switch, Raw being ignored when an app maps to it, and History recording the wrong mode name.

**Files:**
- Modify: `src/main.py:281-311` (`_process_audio`)
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `ProfileManager.list_profiles()`, `get_active_profile()` (Task 5).
- Produces: `VoxelApp._resolve_profile(app_name: str | None) -> tuple[str, dict]` — returns `(profile_id, profile)`; the app mapping wins when `auto_profile` is on and the app is mapped, otherwise the configured active profile.

- [ ] **Step 1: Write the failing tests**

```python
def test_unmapped_app_falls_back_to_active_profile():
    # auto_profile on, active=professional, app "Notepad.exe" unmapped
    # -> resolves to professional, NOT whatever the last mapped app used

def test_mapped_app_to_raw_skips_cleanup():
    # app_profiles {"Code.exe": "raw"} -> cleaner is never called

def test_history_records_the_effective_profile_name():
    # app mapped to professional -> history row profile == "Professional Email"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3.13 -m pytest tests/test_pipeline.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement `_resolve_profile` and rewrite the block**

`_process_audio` calls `_resolve_profile(self._target_app)` once, then derives everything from that single result: `is_raw` from its prompt being `__RAW__`, the prompt passed to the cleaner, and the name written to history. Set the cleaner's prompt per dictation from the resolved profile — never leave it mutated for the next one.

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -3.13 -m pytest tests/test_pipeline.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/main.py tests/
git commit -m "fix: resolve one effective profile per dictation so auto-switch stops sticking"
```

---

### Task 7: Make Offline mode's effect on Dictation Mode visible

Offline transcription skips LLM cleanup entirely, so the mode dropdown does nothing. Today nothing says so.

**Files:**
- Modify: `src/ui_pyqt6/settings_ui.py` (offline checkbox handler, mode row)
- Test: manual — this is UI state with no logic worth a unit test.

**Interfaces:**
- Consumes: the `_offline_check` and `_profile_combo` widgets.
- Produces: nothing for later tasks.

- [ ] **Step 1: Disable the mode control when offline is checked**

Connect `_offline_check.stateChanged` to a handler that calls `self._profile_combo.setEnabled(not checked)` and sets the Dictation Mode subtitle to "Not used in Offline mode — transcription only" when checked, restoring "How your speech is cleaned up" when unchecked. Apply the same state once at construction so a config that already has offline on opens correctly.

- [ ] **Step 2: Verify by running the app**

Run: `py -3.13 -m src.main`
Expected: ticking Offline mode greys out the Dictation Mode dropdown and changes its subtitle; unticking restores both. Close the app.

- [ ] **Step 3: Run the full suite**

Run: `py -3.13 -m pytest -q`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/ui_pyqt6/settings_ui.py
git commit -m "feat: show that Dictation Mode is inert while Offline mode is on"
```

---

### Task 8: Toggle-to-talk activation mode

**Files:**
- Modify: `src/hotkey_listener.py` (activation mode)
- Modify: `src/main.py` (toggle handling, max-duration reset)
- Modify: `src/config.py` (`activation_mode` key)
- Modify: `src/ui_pyqt6/settings_ui.py` (the control + modifier-only guard)
- Test: `tests/test_hotkey_listener.py`, `tests/test_pipeline.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `HotkeyListener(..., activation_mode: str = "hold")` — `"hold"` or `"toggle"`. In toggle mode `on_press` fires on each qualifying press, `on_release` is never called, the `min_hold_duration` tap filter is bypassed, and no release-polling thread starts.
  - `HotkeyListener.is_modifier_only -> bool` — public, so the settings UI can refuse the combination.
  - Config key `activation_mode: str = "hold"`.

- [ ] **Step 1: Write the failing tests**

```python
def test_toggle_mode_fires_press_on_each_press():
    # two press/release cycles -> on_press called twice, on_release never

def test_toggle_mode_ignores_min_hold_duration():
    # a 50ms tap still fires on_press

def test_hold_mode_is_unchanged_by_default():
    # existing press/release behaviour intact

def test_is_modifier_only_true_for_modifier_combo():
    assert HotkeyListener("<ctrl>+<alt>", ...).is_modifier_only is True

def test_toggle_after_max_duration_autostop_starts_a_new_recording():  # Review Focus 4
    # recorder auto-stopped by the cap; next press starts recording again
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3.13 -m pytest tests/test_hotkey_listener.py tests/test_pipeline.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement the listener change**

In `_handle_press`, when `activation_mode == "toggle"`: fire the callback and return without setting `_is_held` or starting `_start_release_poll`. `_handle_release` returns immediately in toggle mode. Expose `is_modifier_only`.

- [ ] **Step 4: Implement toggle handling in `main.py`**

`_start_hotkey_listener` passes `activation_mode` from config. In toggle mode the press callback branches on `self._recorder.is_recording` — stop if recording, start if not. **Derive the state from the recorder; do not add a second boolean**, which is what makes the 2-minute auto-stop path safe (it stops the recorder, so the next press reads as "start").

- [ ] **Step 5: Add the setting and the modifier-only guard**

A two-item `_ArrowComboBox` under the Hotkey section: "Hold to talk" / "Press to start, press to stop", saved as `activation_mode` (`hold` / `toggle`). In `_save`, if the chosen hotkey is modifier-only and the mode is toggle, refuse: show a warning via `_set_status` explaining that a modifier-only hotkey would toggle on every press, and leave `activation_mode` at `hold` (Review Focus 5).

- [ ] **Step 6: Run tests to verify they pass**

Run: `py -3.13 -m pytest -q`
Expected: PASS.

- [ ] **Step 7: Verify by running the app**

Run: `py -3.13 -m src.main`
Expected: with toggle selected, one press starts recording and a second stops it; with hold selected, behaviour is unchanged. Close the app.

- [ ] **Step 8: Commit**

```bash
git add src/ tests/
git commit -m "feat: add toggle-to-talk alongside push-to-talk"
```

---

### Task 9: Stop pasting into the Start menu and search

Observed in the wild on 2026-11-10: a dictation landed on a shell surface and Windows tried to **execute** the text, producing "Windows cannot find 'fresh'". `_is_desktop_focused()` only recognises `Progman`, `WorkerW`, `Shell_TrayWnd`, `Shell_SecondaryTrayWnd` — the desktop and taskbar. The Windows 11 Start menu and search are XAML island windows with different class names, so Voxel believes a text field is focused and pastes into them.

**Files:**
- Modify: `src/text_injector.py:48-61`
- Test: `tests/test_text_injector.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `_is_non_text_surface() -> bool` replaces `_is_desktop_focused()` as the internal check. **`TextInjector.is_desktop_focused()` keeps its name and signature** — `main.py:202` calls it and this plan does not change that call site.

- [ ] **Step 1: Write the failing tests**

```python
def test_start_menu_process_is_a_non_text_surface():
    # foreground process StartMenuExperienceHost.exe -> True

def test_search_host_is_a_non_text_surface():
    # foreground process SearchHost.exe -> True

def test_ordinary_app_is_not_a_non_text_surface():
    # foreground process Code.exe, class Chrome_WidgetWin_1 -> False

def test_inject_into_non_text_surface_copies_without_pasting():
    # pasted is False, text is on the clipboard, no hotkey() call
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3.13 -m pytest tests/test_text_injector.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement process-based detection**

Add `_NO_TEXT_PROCESSES = {"startmenuexperiencehost.exe", "searchhost.exe", "searchapp.exe", "shellexperiencehost.exe"}` (compared lowercased). Resolve the foreground window's process with `GetWindowThreadProcessId` + `OpenProcess` + `QueryFullProcessImageNameW`; `src/app_detector.py` already does this — reuse it rather than writing a second copy. Keep the existing class-name check and return `True` if **either** matches. Windows-only; return `False` on other platforms and on any exception, so a detection failure degrades to today's behaviour rather than blocking dictation.

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -3.13 -m pytest tests/test_text_injector.py -q`
Expected: PASS.

- [ ] **Step 5: Run the full suite**

Run: `py -3.13 -m pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/text_injector.py tests/
git commit -m "fix: don't paste dictation into the Start menu, where Windows executes it"
```

**Known remaining gap** — record it in the Task 10 FAQ rather than fixing it here: the **Run dialog** (`#32770` owned by `explorer.exe`) is not covered. Blocking that class wholesale would also block legitimate dialogs that do have text fields, so it needs a narrower signal than this task has.

---

### Task 10: Update the FAQ and README to match

**Files:**
- Modify: `src/ui_pyqt6/settings_ui.py` (FAQ entries)
- Modify: `README.md`

**Interfaces:**
- Consumes: everything above.
- Produces: nothing.

- [ ] **Step 1: Correct the FAQ**

The "Dictation Modes" entry lists the old mode names — rewrite for the six current ones. The "Microphone selection" entry says "If you plug in a new mic, restart Voxel or reopen Settings to see it" — it must now also say Voxel remembers the device by name and will tell you if it goes missing. Add an entry for the activation mode. The undo entry was removed in Task 4 — confirm nothing still references it.

- [ ] **Step 2: Update the README**

Correct any mention of the undo hotkey, the old mode names, and the microphone behaviour.

- [ ] **Step 3: Run the full suite**

Run: `py -3.13 -m pytest -q`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/ui_pyqt6/settings_ui.py README.md
git commit -m "docs: update FAQ and README for the behavioural changes"
```
