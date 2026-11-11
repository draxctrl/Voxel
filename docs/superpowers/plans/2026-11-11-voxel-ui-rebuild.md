# Voxel UI Rebuild — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Voxel's single scrolling settings page with a Discord-style sidebar window that absorbs the History and Stats windows, in plain language, with Phosphor icons and a light/dark theme that follows Windows.

**Architecture:** A `SettingsWindow` shell owns a `NavRail` (left) and a `QStackedWidget` (right). Each sidebar entry is one pane module in `src/ui_pyqt6/panes/`, built against a shared `PaneContext` that gives it the config, the profile manager, the history store and a single `apply(key, value)` callback. There is no Save button: `apply` writes the config and restarts only the subsystem that changed. The engine (`main.py`'s recording, hotkey and transcription paths) is untouched except for that one narrow apply route and the tray rewiring.

**Tech Stack:** Python 3.13, PyQt6 6.10 (`QtSvg`, `QStackedWidget`), Phosphor Icons (MIT) as bundled SVG, pytest.

**Spec:** `docs/superpowers/specs/2026-11-11-voxel-ui-rebuild-design.md`

**Scope note:** The spec also describes a four-step first-run flow. That is a
second plan, written after this one ships. This plan produces a complete,
working settings window on its own; first run keeps today's behaviour until
then.

## Global Constraints

- Python 3.13 + PyQt6 6.10. Tests: `py -3.13 -m pytest -q` from `C:\Voxel`. There is no virtualenv; plain `python` is a 3.12 without pytest.
- The ~265 engine tests (everything outside `test_settings_ui.py`, `test_theme.py`, `test_theme_widgets.py`, `test_ios_layout.py`) stay green at every commit.
- No new runtime dependencies. Phosphor SVGs are static assets committed to the repo.
- Windows is the target. `BudgetWhisper-mac/` is out of scope — do not edit it.
- The repo is public: no key, token or personal path may enter it.
- Accent stays indigo `#6366f1` (hover `#818cf8`, pressed `#4f46e5`).
- Dark surfaces are exactly: rail `#16171a`, pane `#1e1f23`, rows `#2a2c32`, borders `#32343b`, muted text `#9b9ca5`, faint text `#6d6f78`.
- Every user-facing string is plain English: "Writing style", not "Dictation Mode"; "Exactly what I said", not "Raw mode".
- Rendering a screen to PNG and looking at it is expected practice here — pytest's offscreen Qt does not draw platform-styled widgets the way real Windows does, and has passed tests over live visual bugs before.

## Review Focus

1. **An active profile that is not one of the three headline styles** (`professional`, `code`, `technical`, or a user-defined id) must show as selected under "More styles" — never silently reset to `grammar_only`. Pinned in Task 6.
2. **No microphone present, or the chosen one missing.** The Microphone pane must list what exists and say plainly that the saved device is gone, not crash or show an empty list. Pinned in Task 7.
3. **Windows switches light↔dark while the window is open.** The rail, panes and icons must all restyle together; a half-restyled window is the bug this project exists to kill. Pinned in Task 4.
4. **A missing or unreadable SVG asset** (packaged build without the `datas` entry) must degrade to a blank icon, not take the window down on launch. Pinned in Task 1.
5. **A history of thousands of entries, and entries thousands of characters long.** The History pane must stay responsive and must not stretch the window. Pinned in Task 10.

---

## File Structure

**New:**
- `assets/icons/phosphor/*.svg` — the ~14 icons this UI uses, from Phosphor regular + fill
- `src/ui_pyqt6/icons.py` — load an SVG by name, tint it, return a `QIcon`
- `src/ui_pyqt6/nav_rail.py` — the sidebar: brand, grouped entries, status footer
- `src/ui_pyqt6/settings_window.py` — the shell: rail + stack + restyling
- `src/ui_pyqt6/panes/__init__.py` — `PaneContext`, `Pane` base
- `src/ui_pyqt6/panes/{writing_style,language,microphone,shortcuts,appearance,voice_commands,history,stats,general,about}.py`

**Modified:**
- `src/ui_pyqt6/theme.py` — new palette values and QSS; `ArrowComboBox` and `IOSSwitch` survive as-is
- `src/main.py` — `apply_setting`, tray rewiring, window construction
- `src/tray_app.py` — History/Statistics open the main window on a pane
- `src/config.py` — add `always_copy` and `clipboard_notice` to `DEFAULT_CONFIG`
- `build.spec` — bundle `assets/icons/phosphor`

**Deleted at the end (Task 12):** `src/ui_pyqt6/settings_ui.py`, `history_window.py`, `stats_window.py`, and their tests.

---

### Task 1: Phosphor icons

**Files:**
- Create: `assets/icons/phosphor/*.svg`, `src/ui_pyqt6/icons.py`
- Test: `tests/test_icons_phosphor.py`

**Interfaces:**
- Produces: `icon(name: str, colour: str, size: int = 18) -> QIcon` and `ICON_NAMES: frozenset[str]` in `src/ui_pyqt6/icons.py`.

Icons needed (Phosphor regular unless noted): `pencil-simple`, `globe-simple`, `microphone`, `microphone-fill`, `keyboard`, `waveform`, `clock-counter-clockwise`, `chart-bar`, `sliders-horizontal`, `info`, `magnifying-glass`, `copy`, `trash`, `chat-text`, `arrow-right`, `check-circle-fill`.

- [ ] **Step 1: Fetch the SVGs** from `https://unpkg.com/@phosphor-icons/core@2.1.1/assets/regular/<name>.svg` (and `/fill/<name>-fill.svg`) into `assets/icons/phosphor/`, keeping the filename as `<name>.svg`. Add `assets/icons/phosphor/LICENSE` from the package's MIT licence.

- [ ] **Step 2: Write the failing tests** in `tests/test_icons_phosphor.py`

```python
class TestTheIconSetIsComplete:
    def test_every_named_icon_has_a_file(self):
        for name in ICON_NAMES:
            assert _svg_path(name) is not None, name

    def test_an_icon_is_tinted_to_the_colour_asked_for(self):
        pixmap = icon("microphone", "#6366f1", 32).pixmap(32, 32)
        colours = {pixmap.toImage().pixelColor(x, y).name()
                   for x in range(32) for y in range(32)
                   if pixmap.toImage().pixelColor(x, y).alpha() > 200}
        assert "#6366f1" in colours

class TestAMissingIconDoesNotTakeTheWindowDown:
    def test_an_unknown_name_returns_an_empty_icon(self):
        assert icon("no-such-icon", "#ffffff").isNull() is False  # usable, blank
```

- [ ] **Step 3: Run them** — `py -3.13 -m pytest tests/test_icons_phosphor.py -q`. Expected: FAIL, no module named `icons`.

- [ ] **Step 4: Implement `icons.py`.** Resolve the assets dir the way `settings_ui._resolve_assets_root` already does (PyInstaller `sys._MEIPASS` first, repo root second). Tint by replacing `currentColor`/`#000` in the SVG text before handing it to `QSvgRenderer`, and cache by `(name, colour, size)`. A missing or unreadable file logs a warning and returns an empty `QIcon`.

- [ ] **Step 5: Run them** — Expected: PASS, 3/3.

- [ ] **Step 6: Commit** — `feat(ui): bundle Phosphor icons with a tinting loader`

---

### Task 2: The new palette

**Files:**
- Modify: `src/ui_pyqt6/theme.py:25-62` (`LIGHT`, `DARK`), `build_qss`
- Test: `tests/test_theme.py` (rewrite the palette assertions)

**Interfaces:**
- Produces: `DARK`/`LIGHT` gain the keys `rail`, `rail_text`, `rail_text_active`, `rail_active_bg`, `pane`, `row`, `row_border`, `muted`, `faint`. Existing keys keep their names so `ArrowComboBox`/`IOSSwitch` keep working.

- [ ] **Step 1: Write the failing tests** in `tests/test_theme.py`, replacing the hard-coded iOS hex assertions

```python
class TestTheDarkSurfacesAreTheOnesTheDesignFixes:
    def test_the_rail_is_darker_than_the_pane(self):
        assert DARK["rail"] == "#16171a"
        assert DARK["pane"] == "#1e1f23"
        assert DARK["row"] == "#2a2c32"
        assert DARK["row_border"] == "#32343b"

class TestBothPalettesDefineEveryKey:
    def test_light_and_dark_have_the_same_keys(self):
        assert set(LIGHT) == set(DARK)

class TestTextStaysReadableOnEverySurface:
    @pytest.mark.parametrize("palette", [LIGHT, DARK])
    @pytest.mark.parametrize("fg,bg", [("text", "pane"), ("text", "row"),
                                       ("muted", "row"), ("rail_text", "rail")])
    def test_contrast_is_at_least_4_5_to_1(self, palette, fg, bg):
        assert _contrast(palette[fg], palette[bg]) >= 4.5
```

- [ ] **Step 2: Run them** — Expected: FAIL on the missing `rail` key.

- [ ] **Step 3: Add the keys to both palettes.** Dark values are fixed by Global Constraints. Light values are yours to choose and must pass the contrast test; start from rail `#ececf0`, pane `#f7f7fa`, row `#ffffff`, border `#dddde3`.

- [ ] **Step 4: Run the theme tests** — Expected: PASS. Delete any surviving assertion that pins a value this task changed; do not weaken the contrast test to make a colour fit.

- [ ] **Step 5: Run the whole suite** — `py -3.13 -m pytest -q`. Expected: the engine tests pass; failures confined to `test_settings_ui.py`/`test_theme_widgets.py`/`test_ios_layout.py` are expected at this point and are resolved by Task 12.

- [ ] **Step 6: Commit** — `feat(ui): new dark and light surfaces for the sidebar design`

---

### Task 3: The sidebar

**Files:**
- Create: `src/ui_pyqt6/nav_rail.py`
- Test: `tests/test_nav_rail.py`

**Interfaces:**
- Consumes: `icons.icon` (Task 1), `theme.current_palette` (Task 2).
- Produces: `NavRail(QWidget)` with `ENTRIES: tuple[tuple[str, tuple[tuple[str, str, str], ...]], ...]` (group title → (pane id, label, icon name)), signal `selected = pyqtSignal(str)`, methods `select(pane_id: str) -> None`, `set_status(state: str, shortcut: str) -> None`, `restyle(palette: dict) -> None`, property `current -> str`.

`ENTRIES` is exactly the spec's table: Dictation → `writing_style` "Writing style" `pencil-simple`, `voice_commands` "Voice commands" `chat-text`, `language` "Language" `globe-simple`; Your setup → `microphone` "Microphone" `microphone`, `shortcuts` "Shortcuts" `keyboard`, `appearance` "Appearance" `waveform`; Your words → `history` "History" `clock-counter-clockwise`, `stats` "Stats" `chart-bar`; App → `general` "General" `sliders-horizontal`, `about` "About" `info`.

`set_status` states are `idle`→"Ready" green `#43b581`, `recording`→"Listening" red `#ff453a`, `processing`→"Working" accent, `error`→"Problem" `#ef4444`.

- [ ] **Step 1: Write the failing tests** in `tests/test_nav_rail.py`

```python
class TestTheRailListsEverySettingsPane:
    def test_every_pane_id_appears_once(self):
        ids = [pid for _, rows in NavRail.ENTRIES for pid, _, _ in rows]
        assert len(ids) == len(set(ids)) == 10

    def test_the_labels_are_in_plain_english(self):
        labels = {lbl for _, rows in NavRail.ENTRIES for _, lbl, _ in rows}
        assert "Writing style" in labels
        assert "Dictation Mode" not in labels

class TestSelectingAnEntry:
    def test_clicking_an_entry_emits_its_pane_id(self, qtbot): ...
    def test_select_moves_the_highlight_without_emitting(self, qtbot): ...

class TestTheStatusFooterMirrorsTheApp:
    def test_each_state_has_its_own_word_and_colour(self, qtbot):
        rail = NavRail()
        seen = set()
        for state in ("idle", "recording", "processing", "error"):
            rail.set_status(state, "Ctrl + Alt")
            seen.add((rail.status_text(), rail.status_colour()))
        assert len(seen) == 4

    def test_the_footer_shows_the_users_own_shortcut(self, qtbot):
        rail = NavRail(); rail.set_status("idle", "Ctrl + Shift + Space")
        assert "Ctrl + Shift + Space" in rail.status_text()
```

- [ ] **Step 2: Run them** — Expected: FAIL, no module named `nav_rail`.

- [ ] **Step 3: Implement `NavRail`.** Fixed width 198px. Group titles are 10.5px uppercase, letter-spaced, in `faint`. Entries are 13.5px rows with a 18px icon; the active one gets `rail_active_bg` and `rail_text_active`. The footer is pinned to the bottom with a 7px dot above a border.

- [ ] **Step 4: Run them** — Expected: PASS.

- [ ] **Step 5: Commit** — `feat(ui): the settings sidebar`

---

### Task 4: The window shell

**Files:**
- Create: `src/ui_pyqt6/settings_window.py`, `src/ui_pyqt6/panes/__init__.py`
- Test: `tests/test_settings_window.py`

**Interfaces:**
- Consumes: `NavRail` (Task 3).
- Produces:
  - `PaneContext` (dataclass) with fields `config`, `profiles`, `history`, `apply: Callable[[str, object], None]`, `palette: Callable[[], dict]`.
  - `Pane(QWidget)` base with `PANE_ID: str`, `TITLE: str`, `SUBTITLE: str`, `def refresh(self) -> None`, `def restyle(self, palette: dict) -> None`.
  - `SettingsWindow(QWidget)` with `__init__(self, ctx: PaneContext)`, `show_pane(pane_id: str) -> None`, `set_status(state: str) -> None`, `show()`.
  - A `ctx` fixture in `tests/conftest.py` — a `PaneContext` over a temp-file `Config`, a real `ProfileManager` and `HistoryStore`, whose `apply` appends `(key, value)` to `ctx.applied`. Every pane task's tests use it; build it in this task.

- [ ] **Step 1: Write the failing tests** in `tests/test_settings_window.py`

```python
class TestTheWindowHasAPaneForEveryRailEntry:
    def test_no_rail_entry_leads_nowhere(self, qtbot, ctx):
        win = SettingsWindow(ctx)
        for _, rows in NavRail.ENTRIES:
            for pid, _, _ in rows:
                win.show_pane(pid)
                assert win.current_pane().PANE_ID == pid

class TestTheWindowIsSizedForTheSidebarLayout:
    def test_it_opens_at_the_designed_size_and_can_be_resized(self, qtbot, ctx):
        win = SettingsWindow(ctx)
        assert (win.width(), win.height()) == (980, 620)
        assert (win.minimumWidth(), win.minimumHeight()) == (860, 560)
        assert win.maximumWidth() > 980   # not setFixedSize

class TestASystemThemeChangeRestylesEverything:
    def test_every_pane_and_the_rail_are_restyled_together(self, qtbot, ctx):
        win = SettingsWindow(ctx)
        restyled = []
        for pane in win.panes():
            pane.restyle = lambda p, _n=pane.PANE_ID: restyled.append(_n)
        win.restyle(palette_for("light"))
        assert set(restyled) == {p.PANE_ID for p in win.panes()}
```

- [ ] **Step 2: Run them** — Expected: FAIL, no module named `settings_window`.

- [ ] **Step 3: Implement the shell.** A `QHBoxLayout` of `NavRail` and a `QStackedWidget`. Panes are constructed eagerly (ten small widgets; lazy construction would complicate restyling for no measurable gain) and registered by `PANE_ID`. `show_pane` calls the pane's `refresh()` before raising it. Hook `QGuiApplication.styleHints().colorSchemeChanged` to `restyle`.

- [ ] **Step 4: Run them** — Expected: PASS. Until later tasks land, register a placeholder `Pane` subclass for each id.

- [ ] **Step 5: Commit** — `feat(ui): the settings window shell`

---

### Task 5: Instant apply

**Files:**
- Modify: `src/main.py` (`_on_settings_saved` at :478 and the window construction at :140)
- Test: `tests/test_apply_setting.py`

**Interfaces:**
- Produces: `VoxelApp.apply_setting(key: str, value: object) -> None` — writes the key, saves the config, and restarts only what that key affects.

Restart map: `mic_device_name`/`mic_device` → reopen the recorder; `hotkey`/`undo_hotkey`/`activation_mode` → restart the hotkey listener; `recording_style` → `overlay.set_style`; `llm_model`/`active_profile`/`api_key` → rebuild the cleaner; theme key → restyle. Everything else writes and nothing restarts.

- [ ] **Step 1: Write the failing tests** in `tests/test_apply_setting.py`, built on `tests/test_startup.py`'s `app` fixture

```python
class TestOnlyWhatChangedIsRestarted:
    def test_a_checkbox_does_not_reopen_the_microphone(self, app):
        app._recorder.reset_mock()
        app.apply_setting("always_copy", False)
        assert not app._recorder.method_calls
        assert app._config.get("always_copy") is False

    def test_changing_the_microphone_reopens_the_stream(self, app): ...
    def test_changing_the_hotkey_restarts_the_listener(self, app): ...
    def test_changing_the_hotkey_does_not_reopen_the_microphone(self, app): ...

class TestEverySettingIsWrittenThrough:
    def test_the_value_reaches_the_config_file(self, app, tmp_path):
        app.apply_setting("language", "fr")
        reloaded = Config(config_path=app._config._path); reloaded.load()
        assert reloaded.get("language") == "fr"
```

- [ ] **Step 2: Run them** — Expected: FAIL, `VoxelApp` has no `apply_setting`.

- [ ] **Step 3: Implement `apply_setting`.** Keep `_on_settings_saved` for now — Task 12 removes it with the old window.

- [ ] **Step 4: Run them** — Expected: PASS.

- [ ] **Step 5: Commit** — `feat: apply a setting without restarting everything`

---

### Task 6: Writing style pane

**Files:**
- Create: `src/ui_pyqt6/panes/writing_style.py`
- Test: `tests/test_pane_writing_style.py`

**Interfaces:**
- Consumes: `Pane`, `PaneContext` (Task 4); `ProfileManager` (`src/profiles.py`), whose `BUILTIN_PROFILES` ids are `raw`, `grammar_only`, `grammar_tidy`, `professional`, `code`, `technical`.
- Produces: `WritingStylePane(Pane)` with `PANE_ID = "writing_style"`, `HEADLINE_IDS = ("grammar_only", "grammar_tidy", "raw")`.

Headline rows, in order and with this exact copy:
| id | Title | Line underneath |
|---|---|---|
| `grammar_only` | Grammar only | Fixes grammar and punctuation, keeps your own wording |
| `grammar_tidy` | Tidy up | Also drops "um", "uh" and false starts |
| `raw` | Exactly what I said | No changes at all, word for word |

Below them a **More styles** disclosure holding every other profile — the three
remaining built-ins and any user-defined one — and below that the **Work
offline** switch ("Slower, but nothing leaves this computer").

- [ ] **Step 1: Write the failing tests** in `tests/test_pane_writing_style.py`

```python
class TestTheThreeEverydayStylesAreUpFront:
    def test_the_headline_rows_are_these_three_in_this_order(self, qtbot, ctx):
        assert WritingStylePane(ctx).headline_ids() == ("grammar_only", "grammar_tidy", "raw")

class TestAStyleThatIsNotAHeadlineIsNotLost:
    def test_a_hidden_builtin_shows_as_selected_under_more_styles(self, qtbot, ctx):
        ctx.config.set("active_profile", "professional")
        pane = WritingStylePane(ctx); pane.refresh()
        assert pane.selected_id() == "professional"
        assert pane.more_styles_is_open() is True

    def test_a_custom_profile_shows_as_selected_under_more_styles(self, qtbot, ctx):
        ctx.profiles.add_profile("my_style", "My style", "Do it my way")
        ctx.config.set("active_profile", "my_style")
        pane = WritingStylePane(ctx); pane.refresh()
        assert pane.selected_id() == "my_style"

    def test_opening_the_pane_never_rewrites_the_active_profile(self, qtbot, ctx):
        ctx.config.set("active_profile", "technical")
        WritingStylePane(ctx).refresh()
        assert ctx.config.get("active_profile") == "technical"

class TestChoosingAStyleAppliesIt:
    def test_clicking_a_row_applies_that_profile_id(self, qtbot, ctx):
        pane = WritingStylePane(ctx); pane.refresh()
        pane.choose("raw")
        assert ctx.applied == [("active_profile", "raw")]
```

- [ ] **Step 2: Run them** — Expected: FAIL, no module `panes.writing_style`.

- [ ] **Step 3: Implement the pane.** Rows are radio-style: a 17px ring, bold title, one `faint` line. The selected row takes the accent border and a 10%-accent fill. "More styles" starts open when the active profile is not a headline id.

- [ ] **Step 4: Run them** — Expected: PASS.

- [ ] **Step 5: Commit** — `feat(ui): writing style pane`

---

### Task 7: Microphone, Shortcuts, Appearance panes

**Files:**
- Create: `src/ui_pyqt6/panes/{microphone,shortcuts,appearance}.py`
- Test: `tests/test_pane_microphone.py`, `tests/test_pane_shortcuts.py`, `tests/test_pane_appearance.py`

**Interfaces:**
- Produces: `MicrophonePane`, `ShortcutsPane`, `AppearancePane` (`Pane` subclasses, ids `microphone`, `shortcuts`, `appearance`).

**Microphone** lists input devices as selectable rows (port the enumeration from `settings_ui._populate_mics`), each with a live level meter driven by the recorder, plus a "System default" row. **Shortcuts** holds push-to-talk, undo hotkey and activation mode (Hold to talk / Press to start, press to stop) — reuse the existing key-capture code from `settings_ui._start_hotkey_capture`. **Appearance** holds the recording badge style (orb / waveform / island) and the theme choice (Follow Windows / Light / Dark).

- [ ] **Step 1: Write the failing tests.** Minimum set:

```python
class TestTheMicrophonePaneSurvivesABadDevice:
    def test_it_says_so_when_the_saved_microphone_is_gone(self, qtbot, ctx):
        ctx.config.set("mic_device_name", "Ghost Mic")
        pane = MicrophonePane(ctx); pane.refresh()
        assert "Ghost Mic" in pane.warning_text()

    def test_no_devices_at_all_is_a_message_not_a_crash(self, qtbot, ctx): ...

class TestChoosingAMicrophoneAppliesBothKeys:
    def test_the_name_and_the_index_are_written(self, qtbot, ctx): ...

class TestTheThemeChoice:
    def test_follow_windows_is_the_default(self, qtbot, ctx): ...
    def test_choosing_dark_applies_it_immediately(self, qtbot, ctx): ...

class TestAModifierOnlyHotkeyIsRejectedForToggleMode:
    def test_it_explains_rather_than_silently_failing(self, qtbot, ctx): ...
```

- [ ] **Step 2: Run them** — Expected: FAIL, modules missing.

- [ ] **Step 3: Implement the three panes.**

- [ ] **Step 4: Run them** — Expected: PASS.

- [ ] **Step 5: Render `microphone` and `shortcuts` to PNG and look at them.** Rows must not clip at 125% display scaling.

- [ ] **Step 6: Commit** — `feat(ui): microphone, shortcuts and appearance panes`

---

### Task 8: Language, General, About panes

**Files:**
- Create: `src/ui_pyqt6/panes/{language,general,about}.py`
- Modify: `src/config.py` (`DEFAULT_CONFIG`)
- Test: `tests/test_pane_language.py`, `tests/test_pane_general.py`, `tests/test_pane_about.py`, `tests/test_config.py`

**General** holds: API key (with the existing validate button, reusing `main._validate_api_key`), start with Windows, always copy to clipboard, show clipboard notice, mute sounds, auto-switch style per app. **About** holds version, licence, the GitHub link and the support link. **Language** holds the nine-language picker.

- [ ] **Step 1: Write the failing tests**

```python
class TestEverySettingHasAHome:
    def test_no_config_key_is_orphaned(self):
        from src.ui_pyqt6.panes import all_panes
        homed = set().union(*(p.OWNS for p in all_panes()))
        unowned = set(DEFAULT_CONFIG) - homed - NOT_USER_FACING
        assert unowned == set()

class TestTheConfigDefaultsMatchTheUI:
    def test_always_copy_and_clipboard_notice_have_defaults(self):
        assert DEFAULT_CONFIG["always_copy"] is True
        assert DEFAULT_CONFIG["clipboard_notice"] is True

class TestTheApiKeyIsNotLeaked:
    def test_the_field_is_masked_until_revealed(self, qtbot, ctx): ...
```

`NOT_USER_FACING` = `{"profiles", "app_profiles", "voice_commands", "mic_device", "llm_model", "whisper_model", "offline_model"}`. Give every `Pane` subclass an `OWNS: frozenset[str]` of the config keys it edits — including the panes from Tasks 6 and 7.

- [ ] **Step 2: Run them** — Expected: FAIL on the missing `OWNS`/defaults.

- [ ] **Step 3: Implement the three panes and add the two config defaults.**

- [ ] **Step 4: Run them** — Expected: PASS.

- [ ] **Step 5: Commit** — `feat(ui): language, general and about panes`

---

### Task 9: Voice commands pane

**Files:**
- Create: `src/ui_pyqt6/panes/voice_commands.py`
- Test: `tests/test_pane_voice_commands.py`

Port the editor currently living in `settings_ui._show_voice_commands` (:592-703) from a modal dialog into a pane: a list of trigger→expansion pairs, add and delete, saved through `ctx.apply("voice_commands", mapping)`.

- [ ] **Step 1: Write the failing tests**

```python
class TestEditingCommands:
    def test_existing_commands_are_listed(self, qtbot, ctx): ...
    def test_adding_a_pair_applies_the_whole_mapping(self, qtbot, ctx): ...
    def test_deleting_a_pair_applies_the_whole_mapping(self, qtbot, ctx): ...
    def test_a_blank_trigger_is_not_saved(self, qtbot, ctx): ...
```

- [ ] **Step 2: Run them** — Expected: FAIL.
- [ ] **Step 3: Implement the pane.**
- [ ] **Step 4: Run them** — Expected: PASS.
- [ ] **Step 5: Commit** — `feat(ui): voice commands pane`

---

### Task 10: History pane

**Files:**
- Create: `src/ui_pyqt6/panes/history.py`
- Test: `tests/test_pane_history.py`

Everything today's `HistoryWindow` does — debounced search, copy, delete, clear all — in the pane layout from `docs/mockups/settings-history.png`: a search field, then one row per entry with a time on the left, the text in the middle, and copy/delete icons on the right.

- [ ] **Step 1: Write the failing tests**

```python
class TestTheHistoryPaneKeepsWhatTheWindowCouldDo:
    def test_entries_are_listed_newest_first(self, qtbot, ctx): ...
    def test_search_filters_the_list(self, qtbot, ctx): ...
    def test_copy_puts_the_text_on_the_clipboard(self, qtbot, ctx): ...
    def test_delete_removes_one_entry(self, qtbot, ctx): ...
    def test_clear_all_asks_first(self, qtbot, ctx): ...

class TestALargeHistoryStaysUsable:
    def test_two_thousand_entries_render_within_a_page(self, qtbot, ctx):
        # the store holds 2000; the pane must not build 2000 widgets at once
        assert len(pane.visible_rows()) <= 100

    def test_a_very_long_entry_does_not_stretch_the_window(self, qtbot, ctx):
        ctx.history.add("x" * 4000, "y" * 4000, "en", 1.0, profile="raw")
        pane.refresh()
        assert pane.sizeHint().width() <= 760
```

- [ ] **Step 2: Run them** — Expected: FAIL.
- [ ] **Step 3: Implement the pane.** Page the list (first 100, more on scroll) and elide long text to two lines.
- [ ] **Step 4: Run them** — Expected: PASS.
- [ ] **Step 5: Commit** — `feat(ui): history pane`

---

### Task 11: Stats pane

**Files:**
- Create: `src/ui_pyqt6/panes/stats.py`
- Test: `tests/test_pane_stats.py`

Three numbers only, large: **words dictated** (`total_words`), **time saved**, **this week** (`this_week`). Time saved is `total_words / 40` minutes — 40 wpm typing against speech — and the pane says so in one `faint` line, so the number is not a mystery.

- [ ] **Step 1: Write the failing tests**

```python
class TestThreeNumbersNotSeven:
    def test_the_pane_shows_exactly_three_figures(self, qtbot, ctx):
        assert len(StatsPane(ctx).figures()) == 3

    def test_time_saved_is_derived_from_words_at_40wpm(self, qtbot, ctx):
        ctx.history.add_many(words=4000)
        assert StatsPane(ctx).figures()["time_saved"] == "1h 40m"

class TestAnEmptyHistory:
    def test_it_shows_zeroes_rather_than_an_error(self, qtbot, ctx): ...
```

- [ ] **Step 2: Run them** — Expected: FAIL.
- [ ] **Step 3: Implement the pane.**
- [ ] **Step 4: Run them** — Expected: PASS.
- [ ] **Step 5: Commit** — `feat(ui): stats pane`

---

### Task 12: Switch over and delete the old windows

**Files:**
- Modify: `src/main.py`, `src/tray_app.py`, `build.spec`
- Delete: `src/ui_pyqt6/settings_ui.py`, `src/ui_pyqt6/history_window.py`, `src/ui_pyqt6/stats_window.py`, `tests/test_settings_ui.py`, `tests/test_theme_widgets.py` (the parts testing deleted widgets), `tests/test_ios_layout.py` if nothing imports `ios_layout` any more
- Test: `tests/test_startup.py`

- [ ] **Step 1: Write the failing tests** in `tests/test_startup.py`

```python
class TestTheAppOpensTheNewWindow:
    def test_settings_opens_the_sidebar_window(self, app):
        app._show_settings()
        assert isinstance(app._settings_window, SettingsWindow)

    def test_the_tray_history_item_opens_the_history_pane(self, app):
        app._show_history()
        assert app._settings_window.current_pane().PANE_ID == "history"

    def test_the_tray_stats_item_opens_the_stats_pane(self, app): ...

class TestTheRailFollowsTheApp:
    def test_recording_turns_the_rail_dot_to_listening(self, app): ...

class TestAUserWithNoApiKeyLandsSomewhereUseful:
    def test_an_unconfigured_start_opens_the_general_pane(self, app):
        app._config.set("api_key", "")
        app._startup_stage_2()
        assert app._settings_window.current_pane().PANE_ID == "general"
```

This is the whole of first-run behaviour until the first-run plan lands: a new
user gets the settings window open on the pane holding the API key, which is
what happens today — not a worse experience, just not yet the better one.

- [ ] **Step 2: Run them** — Expected: FAIL (still the old windows).

- [ ] **Step 3: Rewire `main.py` and `tray_app.py`.** One `SettingsWindow`; `_show_history`/`_show_stats` call `show_pane`. Delete `_on_settings_saved` and the three old modules. Push tray state changes to `SettingsWindow.set_status`.

- [ ] **Step 4: Add the icons to `build.spec`'s `datas`** — `('assets/icons/phosphor', 'assets/icons/phosphor')`.

- [ ] **Step 5: Run the whole suite** — `py -3.13 -m pytest -q`. Expected: all green. Every engine test that passed before this plan must still pass; any that does not is a regression, not a test to delete.

- [ ] **Step 6: Launch Voxel for real** — `py -3.13 -m src.main` — open every pane, screenshot the window in both themes, and look at the screenshots.

- [ ] **Step 7: Commit** — `feat(ui): switch to the sidebar settings window`

---

## After this plan

- The first-run flow (spec §"First run"), as its own plan.
- Isuru still owes a look at 125%/150% display scaling on real hardware.
- Verify in a built `.exe` that the Phosphor SVGs and `faster-whisper` both survive packaging.
