# Voxel iOS Theme Foundation (Part 2A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every Voxel window one iOS-styled look that follows the Windows light/dark setting, built from a single shared stylesheet so the chrome can never drift apart again.

**Architecture:** `theme.py` becomes the only source of colour and style. It exposes two palettes (light and dark) as token dicts, detects the system theme, and builds the stylesheet from a palette on demand rather than as an import-time constant — so a theme change restyles live windows. `settings_ui.py`'s duplicate palette, `_QSS`, `_ArrowComboBox` and `_TickCheckBox` are deleted and imported from `theme.py` instead. Inter and the flag images are bundled as assets, loaded through the existing frozen/dev asset path helper.

**Tech Stack:** Python 3.13, PyQt6 6.10 (Qt 6.10), Inter (SIL OFL), flag-icons SVGs (MIT).

**Spec:** [`docs/superpowers/specs/2026-11-10-voxel-fixes-design.md`](../specs/2026-11-10-voxel-fixes-design.md) — "Part two: the iOS visual redesign".

This plan covers the **theme foundation only**. Deliberately out of scope, each its
own plan: the settings window's re-layout into grouped inset cards (2B), the
recording display styles (2C), and the app icon and tray artwork (2D). After this
plan the app is iOS-*styled* but still laid out as it is today.

## Global Constraints

- Python 3.13 — run everything with `py -3.13`. Test command: `py -3.13 -m pytest -q`, green at the end of every task.
- Qt tests run headless: set `QT_QPA_PLATFORM=offscreen`, following `tests/test_settings_ui.py`.
- **Accent is Voxel indigo, never iOS blue, and switches are indigo, never Apple's green `#34C759`.** `#6366f1`, light `#818cf8`, dark `#4f46e5`.
- Palette values from the spec, exact:
  - Light: bg `#F2F2F7`, card `#FFFFFF`, separator `#D6D6DA`, text `#000000`, secondary `#8E8E93`, switch-off `#E9E9EB`
  - Dark: bg `#000000`, card `#1C1C1E`, separator `#2E2E31`, text `#FFFFFF`, secondary `#8E8E93`, switch-off `#39393D`
- **SF Pro cannot be bundled.** Inter (SIL OFL) is used and must ship with the app, never fetched at runtime.
- Flags are image assets — Windows renders flag emoji as letter pairs.
- Flag choices follow speaker numbers: English→US, Spanish→ES, Portuguese→BR, Chinese→CN. Ten language rows, variants not split.
- No new runtime Python dependencies.
- Assets must be added to `build.spec` and `build_mac.spec`, which enumerate files individually.
- Layout is not restructured in this plan; only colours, fonts, controls and chrome change.

## Review Focus

Failure modes no feature's happy path exercises. Each has a test in the task that owns the code.

1. **The theme registry key is missing or unreadable** (older Windows, locked-down policy) — must pick a sensible default and never crash at startup. *Task 1.*
2. **The bundled font fails to load** (missing from a frozen build, unreadable file) — text must fall back to Segoe UI rather than render in a broken or default-serif face. *Task 3.*
3. **A language has no flag asset** — the row must still render and be selectable, without an icon, rather than raising. *Task 7.*
4. **The Windows theme changes while Voxel is running** — open windows must restyle completely, not end up half light and half dark. *Task 6.*
5. **A dialog opened after a theme change** (FAQ, Voice Commands) — must use the current palette, not one captured at import time, which is what today's module-level `_QSS` constant would do. *Task 6.*

---

### Task 1: Palette tokens and system theme detection

**Files:**
- Modify: `src/ui_pyqt6/theme.py`
- Test: `tests/test_theme.py` (create)

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `LIGHT: dict[str, str]` and `DARK: dict[str, str]` — palette tokens. Keys: `bg`, `card`, `card_alt`, `separator`, `text`, `secondary`, `accent`, `accent_hover`, `accent_pressed`, `switch_off`, `input_bg`, `success`, `error`, `warning`, `scrollbar`, `scrollbar_hover`.
  - `detect_system_theme() -> str` — `"light"` or `"dark"`; `"dark"` on any failure or non-Windows.
  - `palette_for(name: str) -> dict[str, str]` — unknown names return `DARK`.

- [ ] **Step 1: Write the failing tests**

```python
def test_both_palettes_define_the_same_tokens():
    assert set(LIGHT) == set(DARK)

def test_light_palette_matches_the_spec():
    assert LIGHT["bg"] == "#F2F2F7"
    assert LIGHT["card"] == "#FFFFFF"
    assert LIGHT["separator"] == "#D6D6DA"
    assert LIGHT["text"] == "#000000"
    assert LIGHT["secondary"] == "#8E8E93"
    assert LIGHT["switch_off"] == "#E9E9EB"

def test_dark_palette_matches_the_spec():
    assert DARK["bg"] == "#000000"
    assert DARK["card"] == "#1C1C1E"
    assert DARK["separator"] == "#2E2E31"
    assert DARK["text"] == "#FFFFFF"
    assert DARK["switch_off"] == "#39393D"

def test_accent_is_voxel_indigo_in_both_palettes():
    # Never iOS blue, and switches are never Apple green.
    for p in (LIGHT, DARK):
        assert p["accent"] == "#6366f1"
        assert p["accent"] != "#007AFF"
        assert p["switch_off"] != "#34C759"

def test_detect_reads_the_windows_registry(monkeypatch):
    # AppsUseLightTheme == 1 -> light, 0 -> dark
def test_detect_falls_back_to_dark_when_key_missing(monkeypatch):   # Review Focus 1
    # winreg raises FileNotFoundError -> "dark", no exception
def test_detect_falls_back_to_dark_off_windows(monkeypatch):
def test_palette_for_unknown_name_returns_dark():
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3.13 -m pytest tests/test_theme.py -q`
Expected: FAIL — names not defined.

- [ ] **Step 3: Implement the tokens and `detect_system_theme()`**

Read `HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize` value `AppsUseLightTheme` via `winreg`. Wrap the whole read in `try/except Exception` returning `"dark"`. Import `winreg` lazily inside the function so the module imports on macOS.

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -3.13 -m pytest tests/test_theme.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ui_pyqt6/theme.py tests/test_theme.py
git commit -m "feat: add iOS light/dark palette tokens and system theme detection"
```

---

### Task 2: Build the stylesheet from a palette

The one place chrome is defined. Replaces `theme.QSS`, `settings_ui._QSS`, and the hand-rolled scrollbar copies in `history_window.py` and `stats_window.py`.

**Files:**
- Modify: `src/ui_pyqt6/theme.py`
- Test: `tests/test_theme.py`

**Interfaces:**
- Consumes: `LIGHT`/`DARK`, `palette_for` (Task 1).
- Produces: `build_qss(palette: dict[str, str]) -> str`.

- [ ] **Step 1: Write the failing tests**

```python
def test_qss_contains_no_unsubstituted_tokens():
    qss = build_qss(DARK)
    assert "{" not in qss and "}" not in qss.replace("}}", "")  # no stray format braces

def test_qss_uses_the_palette_colours():
    assert DARK["card"] in build_qss(DARK)
    assert LIGHT["card"] in build_qss(LIGHT)

def test_scrollbar_reserves_clearance_from_content():
    # The bar must not sit on top of the cards it scrolls.
    qss = build_qss(DARK)
    assert "QScrollBar:vertical" in qss
    assert "margin" in qss

def test_scrollbar_styles_every_subcontrol():
    # Any subcontrol left unstyled falls back to the native Windows scrollbar.
    qss = build_qss(DARK)
    for part in ("add-line", "sub-line", "add-page", "sub-page"):
        assert part in qss

def test_horizontal_scrollbar_is_styled_too():
    assert "QScrollBar:horizontal" in build_qss(DARK)

def test_combo_popup_matches_the_field_radius():
    qss = build_qss(DARK)
    assert "QComboBox QAbstractItemView" in qss
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3.13 -m pytest tests/test_theme.py -q`
Expected: FAIL — `build_qss` not defined.

- [ ] **Step 3: Implement `build_qss`**

Port the existing `QSS` rules onto palette tokens, and add what is missing: horizontal scrollbar rules, `add-page`/`sub-page` set to `background: none`, a `margin` on the vertical bar giving clearance from content, and a `QComboBox QAbstractItemView` radius matching the field's. Font family is `"Inter", "Segoe UI"` so it degrades if Inter is absent. Delete the old module-level `QSS` constant.

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -3.13 -m pytest tests/test_theme.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ui_pyqt6/theme.py tests/test_theme.py
git commit -m "feat: build one stylesheet from palette tokens, fixing scrollbars app-wide"
```

---

### Task 3: Bundle and load Inter

**Files:**
- Create: `src/assets/fonts/Inter-Regular.ttf`, `Inter-Medium.ttf`, `Inter-SemiBold.ttf`, `OFL.txt`
- Modify: `src/ui_pyqt6/theme.py`, `src/main.py`, `build.spec`, `build_mac.spec`
- Test: `tests/test_theme.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `load_fonts(assets_dir: str) -> bool` — registers the bundled faces with Qt, returns True if at least one loaded. Safe to call more than once.

- [ ] **Step 1: Fetch the fonts**

Download the three static TTFs from the Inter release on GitHub (`rsms/inter`, SIL OFL 1.1) into a scratch directory first, then copy into `src/assets/fonts/`. Commit `OFL.txt` alongside them — the licence requires it. Never fetch at runtime.

- [ ] **Step 2: Write the failing tests**

```python
def test_load_fonts_returns_false_for_a_missing_directory(qapp):   # Review Focus 2
    assert load_fonts("C:/definitely/not/here") is False

def test_load_fonts_registers_inter(qapp):
    from PyQt6.QtGui import QFontDatabase
    assert load_fonts(assets_dir()) is True
    assert "Inter" in QFontDatabase.families()

def test_qss_font_stack_falls_back_to_segoe():
    # If Inter is absent, text must still render in the system UI face.
    assert '"Inter", "Segoe UI"' in build_qss(DARK)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `py -3.13 -m pytest tests/test_theme.py -q`
Expected: FAIL — `load_fonts` not defined.

- [ ] **Step 4: Implement `load_fonts`**

Use `QFontDatabase.addApplicationFont` on each `.ttf` found; return whether any id came back non-negative. Call it from `VoxelApp.__init__` right after the `QApplication` is constructed, passing the existing `_get_assets_dir()`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `py -3.13 -m pytest tests/test_theme.py -q`
Expected: PASS.

- [ ] **Step 6: Add the fonts to both PyInstaller specs**

`build.spec` and `build_mac.spec` list `datas` individually; add the fonts directory so a frozen build ships them.

- [ ] **Step 7: Commit**

```bash
git add src/assets/fonts src/ui_pyqt6/theme.py src/main.py build.spec build_mac.spec tests/
git commit -m "feat: bundle Inter as the SF Pro substitute"
```

---

### Task 4: iOS switch

Replaces the square `TickCheckBox` indicator with an iOS pill switch in Voxel indigo.

**Files:**
- Modify: `src/ui_pyqt6/theme.py`
- Test: `tests/test_theme_widgets.py` (create, headless Qt)

**Interfaces:**
- Consumes: palette tokens (Task 1).
- Produces: `IOSSwitch(QCheckBox)` — a `QCheckBox` subclass, so every existing `setChecked`/`isChecked`/`stateChanged` call site keeps working unchanged. `set_palette(palette: dict[str, str]) -> None` restyles it.

- [ ] **Step 1: Write the failing tests**

```python
def test_switch_is_a_checkbox_so_call_sites_still_work(qapp):
    s = IOSSwitch("Mute sounds")
    assert isinstance(s, QCheckBox)
    s.setChecked(True)
    assert s.isChecked() is True

def test_switch_emits_state_changes(qapp):
    # stateChanged must still fire — _sync_offline_state depends on it.

def test_switch_on_colour_is_indigo_not_apple_green(qapp):
    s = IOSSwitch("x"); s.set_palette(DARK)
    assert s._on_colour().name().lower() == "#6366f1"

def test_switch_reports_a_sensible_size(qapp):
    assert IOSSwitch("x").sizeHint().width() > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3.13 -m pytest tests/test_theme_widgets.py -q`
Expected: FAIL — `IOSSwitch` not defined.

- [ ] **Step 3: Implement `IOSSwitch`**

Subclass `QCheckBox`, hide the native indicator in the stylesheet, and draw the pill and knob in `paintEvent` with `QPainter` antialiasing — track `switch_off` when unchecked, `accent` when checked, white knob. Keep the label text drawn by the base class. Expose `_on_colour()` so the colour is assertable without pixel-reading.

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -3.13 -m pytest tests/test_theme_widgets.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ui_pyqt6/theme.py tests/test_theme_widgets.py
git commit -m "feat: add iOS pill switch in Voxel indigo"
```

---

### Task 5: Dropdown popup that lines up with its field

Today `showPopup` resizes the popup's top-level window to a width computed from the text, ignoring the field's own width and position — which is why the dropdowns read as detached.

**Files:**
- Modify: `src/ui_pyqt6/theme.py`
- Test: `tests/test_theme_widgets.py`

**Interfaces:**
- Consumes: palette tokens.
- Produces: `ArrowComboBox(QComboBox)` — one implementation; `settings_ui._ArrowComboBox` is deleted in Task 6.

- [ ] **Step 1: Write the failing tests**

```python
def test_popup_is_never_narrower_than_the_field(qapp):
    c = ArrowComboBox(); c.addItems(["a", "b"]); c.resize(300, 36)
    assert c._popup_width() >= 300

def test_popup_grows_for_long_items(qapp):
    c = ArrowComboBox(); c.addItem("a" * 120); c.resize(120, 36)
    assert c._popup_width() > 120

def test_popup_width_is_capped_to_stay_usable(qapp):
    c = ArrowComboBox(); c.addItem("x" * 4000); c.resize(120, 36)
    assert c._popup_width() <= 900
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3.13 -m pytest tests/test_theme_widgets.py -q`
Expected: FAIL — `_popup_width` not defined.

- [ ] **Step 3: Implement `ArrowComboBox._popup_width()` and use it in `showPopup`**

Width is `max(field width, widest item + padding)`, capped at 900px. `showPopup` sets the view's minimum width and must **not** move or resize the popup's top-level window — Qt already aligns it to the field. Keep the painted chevron.

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -3.13 -m pytest tests/test_theme_widgets.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ui_pyqt6/theme.py tests/test_theme_widgets.py
git commit -m "fix: align dropdown popups to their field instead of free-floating"
```

---

### Task 6: Delete the duplicate theme and apply the palette app-wide

The anti-goal the spec names: two stylesheet copies that drift apart. This is the task that removes the second one.

**Files:**
- Modify: `src/ui_pyqt6/settings_ui.py` (delete `_BG.._WARNING`, `_QSS`, `_ArrowComboBox`, `_TickCheckBox`; import from `theme`)
- Modify: `src/ui_pyqt6/history_window.py` (delete the hand-rolled scrollbar block), `src/ui_pyqt6/stats_window.py`, `src/ui_pyqt6/splash.py`, `src/ui_pyqt6/recording_overlay.py`
- Modify: `src/main.py`
- Test: `tests/test_theme.py`, `tests/test_settings_ui.py`

**Interfaces:**
- Consumes: `build_qss`, `palette_for`, `detect_system_theme`, `IOSSwitch`, `ArrowComboBox`.
- Produces: `apply_theme(app, theme_name: str | None = None) -> str` in `theme.py` — sets the application stylesheet from the resolved palette and returns the theme name used. `current_palette() -> dict[str, str]` returns the palette last applied, so dialogs built later use it.

- [ ] **Step 1: Write the failing tests**

```python
def test_settings_ui_has_no_private_theme_copy():
    import src.ui_pyqt6.settings_ui as s
    for name in ("_QSS", "_BG", "_CARD", "_ArrowComboBox", "_TickCheckBox"):
        assert not hasattr(s, name), f"{name} is a duplicate of theme.py"

def test_no_module_defines_its_own_scrollbar_rules():
    # One scrollbar, defined once.
    import src.ui_pyqt6.history_window as h, src.ui_pyqt6.stats_window as st
    for mod in (h, st):
        assert "QScrollBar" not in inspect.getsource(mod)

def test_apply_theme_sets_the_application_stylesheet(qapp):
    name = apply_theme(qapp, "light")
    assert name == "light"
    assert LIGHT["card"] in qapp.styleSheet()

def test_current_palette_follows_the_applied_theme(qapp):   # Review Focus 5
    apply_theme(qapp, "light")
    assert current_palette() is LIGHT
    apply_theme(qapp, "dark")
    assert current_palette() is DARK

def test_theme_change_restyles_open_windows(qapp, window):  # Review Focus 4
    apply_theme(qapp, "dark")
    apply_theme(qapp, "light")
    assert LIGHT["card"] in qapp.styleSheet()
    assert DARK["bg"] not in qapp.styleSheet()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3.13 -m pytest tests/test_theme.py tests/test_settings_ui.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement `apply_theme` / `current_palette`, and strip the duplicates**

Set the stylesheet on the `QApplication` so every window and every later dialog inherits it; remove the per-window `setStyleSheet(QSS)` / `setStyleSheet(_QSS)` calls and the per-window scrollbar blocks. In `settings_ui.py` replace `_TickCheckBox` with `IOSSwitch` and `_ArrowComboBox` with `ArrowComboBox`, and keep the module-level names as import aliases **only if** call sites need them — prefer updating the call sites. Replace the removed `_SUBTLE`/`_WARNING` constants with palette lookups.

- [ ] **Step 4: Follow the system theme at startup and when it changes**

Call `apply_theme(self._qapp)` in `VoxelApp.__init__` after `load_fonts`. Connect `QGuiApplication.styleHints().colorSchemeChanged` (Qt 6.5+, and this project is on 6.10) to re-apply; wrap the connection in `try/except AttributeError` so an older Qt simply doesn't live-switch.

- [ ] **Step 5: Run the full suite**

Run: `py -3.13 -m pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/ tests/
git commit -m "refactor: delete the duplicate stylesheet and theme the whole app from one source"
```

---

### Task 7: Language flags

**Files:**
- Create: `src/assets/flags/*.svg` (10 files), `src/assets/flags/LICENSE`
- Create: `src/ui_pyqt6/flags.py`
- Modify: `src/ui_pyqt6/settings_ui.py` (language combo), `build.spec`, `build_mac.spec`
- Test: `tests/test_flags.py` (create)

**Interfaces:**
- Consumes: the assets dir helper.
- Produces:
  - `LANGUAGE_FLAGS: dict[str, str]` — language code to ISO country code: `en→us`, `es→es`, `fr→fr`, `de→de`, `it→it`, `pt→br`, `ja→jp`, `ko→kr`, `zh→cn`; `auto` has no entry.
  - `flag_icon(lang_code: str, assets_dir: str) -> QIcon | None` — `None` when there is no flag for that language or the file is missing.

- [ ] **Step 1: Fetch the flag assets**

Download the 4x3 SVGs for `us, es, fr, de, it, br, jp, kr, cn` from `lipis/flag-icons` (MIT) into a scratch directory, then copy into `src/assets/flags/`. Commit the MIT `LICENSE` beside them.

- [ ] **Step 2: Write the failing tests**

```python
def test_language_to_country_follows_speaker_numbers():
    assert LANGUAGE_FLAGS["en"] == "us"
    assert LANGUAGE_FLAGS["pt"] == "br"
    assert LANGUAGE_FLAGS["zh"] == "cn"
    assert LANGUAGE_FLAGS["es"] == "es"

def test_auto_detect_has_no_flag():
    assert "auto" not in LANGUAGE_FLAGS

def test_every_mapped_language_has_an_asset_file():
    for code in LANGUAGE_FLAGS.values():
        assert (Path(assets_dir()) / "flags" / f"{code}.svg").exists()

def test_flag_icon_returns_an_icon_for_a_known_language(qapp):
    assert flag_icon("en", assets_dir()) is not None

def test_flag_icon_returns_none_for_an_unknown_language(qapp):   # Review Focus 3
    assert flag_icon("xx", assets_dir()) is None

def test_flag_icon_returns_none_when_the_file_is_missing(qapp):  # Review Focus 3
    assert flag_icon("en", "C:/no/such/dir") is None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `py -3.13 -m pytest tests/test_flags.py -q`
Expected: FAIL — module not found.

- [ ] **Step 4: Implement `flags.py` and attach the icons**

`flag_icon` builds a `QIcon` from the SVG path, returning `None` rather than an empty icon when the mapping or file is absent. In `_populate_languages` (the language combo block in `settings_ui.py`), pass the icon to `addItem` when one exists and add the plain text when it doesn't, so a missing asset costs an icon and nothing else. Set the combo's `iconSize` so flags render crisply on high-DPI displays.

- [ ] **Step 5: Run tests to verify they pass**

Run: `py -3.13 -m pytest tests/test_flags.py -q`
Expected: PASS.

- [ ] **Step 6: Add the flags to both PyInstaller specs, then run the full suite**

Run: `py -3.13 -m pytest -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/assets/flags src/ui_pyqt6/flags.py src/ui_pyqt6/settings_ui.py build.spec build_mac.spec tests/
git commit -m "feat: show country flags beside each language"
```

---

### Task 8: See it

Every other task is verified by tests that cannot see colour. This one is the eyes.

**Files:**
- Test: manual, plus `tests/test_startup.py` (existing) must stay green.

- [ ] **Step 1: Launch the app in both themes**

Run with the Windows theme set to dark, then to light, confirming: grouped controls use the card colour, switches are indigo (not green), dropdown popups line up with their fields, scrollbars match in Settings, History, Stats and the FAQ dialog and clear the content, flags appear beside each language, and text renders in Inter.

- [ ] **Step 2: Capture a screenshot of each theme for the owner**

The owner chose "Follow Windows" without seeing it built; they decide whether it is right.

- [ ] **Step 3: Run the full suite one last time**

Run: `py -3.13 -m pytest -q`
Expected: PASS.
