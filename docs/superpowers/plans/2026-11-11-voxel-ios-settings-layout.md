# iOS Grouped Settings Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the settings window from a flat stack of label/control pairs into iOS grouped inset cards: uppercase grey section headers, white (or `#1C1C1E`) rounded cards, one row per setting with its control right-aligned, hairline separators between rows, and chevron disclosure rows for the screens that open elsewhere.

**Architecture:** Three reusable widgets in a new `src/ui_pyqt6/ios_layout.py` (`GroupCard`, `SettingsRow`, `DisclosureRow`) plus a `section_header()` helper, styled from `theme.py`'s palette like everything else. `SettingsWindow._build_ui` is rewritten to compose them; every existing widget attribute (`_api_key_edit`, `_profile_combo`, `_mic_combo`, `_lang_combo`, the switches) keeps its name so `_save`, `_populate_mics`, `_populate_profiles`, `_sync_offline_state` and the hotkey capture code are untouched. Content goes inside a `QScrollArea` so the card structure can grow taller than the window without truncating anything.

**Tech Stack:** Python 3.13, PyQt6 6.10, pytest (headless via `QT_QPA_PLATFORM=offscreen`).

**Spec:** `docs/superpowers/specs/2026-11-10-voxel-fixes-design.md` — Part two, "Theme: iOS, following Windows light/dark".

## Global Constraints

- Palette tokens come from `theme.current_palette()`; no colour literal outside `theme.py` except pure white `#FFFFFF` on an accent fill.
- Accent is Voxel indigo `#6366f1` (hover `#818cf8`, pressed `#4f46e5`), never iOS blue or Apple green.
- Card `#FFFFFF` light / `#1C1C1E` dark; separator `#D6D6DA` / `#2E2E31`; secondary text `#8E8E93` both themes.
- Font stack stays `theme.FONT_STACK`.
- Every top-level window exposes `_restyle()` and is re-styled by `apply_theme`.
- The app must not crash from a missing asset: a missing flag, font or icon costs a picture only.
- No setting may be removed or lose its tooltip in the relayout.

## Review Focus

1. **Window too short for the cards** — grouped cards are taller than the flat stack; if the content exceeds 820px the user must still be able to reach Save. Pinned in Task 4.
2. **Theme switch while the window is open** — cards and separators are styled by object name through the application stylesheet, but `DisclosureRow` draws its chevron by hand and must read the live palette at paint time, not construction. Pinned in Task 2.
3. **A row whose control is wider than its column** — long mic names and the "not connected" suffix must elide rather than push the row wider than the card. Pinned in Task 2.
4. **Offline mode still has to disable Dictation Mode** — the control moves into a row, and its subtitle label (`_profile_sub`) is the thing `_sync_offline_state` rewrites. Pinned in Task 3.
5. **Switch rows lose their tooltips** — the switch text moves to the row title, so the tooltip must move with it or the explanation disappears. Pinned in Task 3.

---

### Task 1: The group card and row widgets

**Files:**
- Create: `src/ui_pyqt6/ios_layout.py`
- Test: `tests/test_ios_layout.py`

**Interfaces:**
- Consumes: `theme.current_palette()`.
- Produces:
  - `section_header(text: str) -> QLabel` — objectName `group_header`, text upper-cased.
  - `GroupCard(parent=None)` with `add_row(widget: QWidget) -> None`, objectName `group_card`; inserts a 1px `QFrame` objectName `row_separator` before every row but the first.
  - `SettingsRow(title: str, control: QWidget | None = None, subtitle: str | None = None, parent=None)` with attributes `title_label`, `subtitle_label` (None when no subtitle), `control`.
  - `ROW_HEIGHT = 44`, `CARD_RADIUS = 12`, `SEPARATOR_INSET = 16`.

- [ ] **Step 1: Write the failing tests**

```python
class TestSectionHeader:
    def test_text_is_upper_cased(self, qapp):
        assert section_header("Recording").text() == "RECORDING"

    def test_object_name_lets_the_stylesheet_reach_it(self, qapp):
        assert section_header("Recording").objectName() == "group_header"


class TestGroupCard:
    def test_first_row_gets_no_separator_above_it(self, qapp):
        card = GroupCard()
        card.add_row(SettingsRow("One"))
        assert _separators(card) == 0

    def test_each_later_row_is_separated_from_the_one_before(self, qapp):
        card = GroupCard()
        for n in ("One", "Two", "Three"):
            card.add_row(SettingsRow(n))
        assert _separators(card) == 2

    def test_separators_are_inset_so_they_do_not_touch_the_left_edge(self, qapp):
        card = GroupCard()
        card.add_row(SettingsRow("One"))
        card.add_row(SettingsRow("Two"))
        sep = [c for c in card.findChildren(QFrame) if c.objectName() == "row_separator"][0]
        assert sep.contentsMargins().left() == SEPARATOR_INSET


class TestSettingsRow:
    def test_title_is_shown(self, qapp):
        assert SettingsRow("Microphone").title_label.text() == "Microphone"

    def test_no_subtitle_means_no_subtitle_label(self, qapp):
        assert SettingsRow("Microphone").subtitle_label is None

    def test_subtitle_is_secondary_styled(self, qapp):
        row = SettingsRow("Mode", subtitle="How your words are cleaned up")
        assert row.subtitle_label.objectName() == "row_sub"

    def test_the_control_is_reparented_into_the_row(self, qapp):
        combo = QComboBox()
        row = SettingsRow("Language", control=combo)
        assert combo.parent() is row
```

`_separators(card)` is a module-level test helper counting children whose
objectName is `row_separator`.

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/test_ios_layout.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.ui_pyqt6.ios_layout'`

- [ ] **Step 3: Implement `ios_layout.py`**

`GroupCard` is a `QFrame` with a zero-spacing `QVBoxLayout` and no contents
margins. `SettingsRow` is a `QWidget` with a horizontal layout: title (plus
subtitle beneath it in a vertical sub-layout when given) on the left, stretch,
then the control right-aligned; minimum height `ROW_HEIGHT`, margins
`(16, 8, 16, 8)`.

- [ ] **Step 4: Run them to verify they pass**

Run: `python -m pytest tests/test_ios_layout.py -q`
Expected: PASS

- [ ] **Step 5: Add the card styling to `theme.build_qss`**

New rules, in the one stylesheet: `QFrame#group_card` (card fill, radius
`CARD_RADIUS`), `QFrame#row_separator` (separator fill, 1px max/min height),
`QLabel#group_header` (secondary, 11px, 600 weight, 0.6px letter-spacing),
`QLabel#row_title` (text, 13px), `QLabel#row_sub` (secondary, 11px).

- [ ] **Step 6: Write and run the test that the card colour follows the theme**

```python
def test_card_rule_uses_the_palette_card_colour():
    for name in ("light", "dark"):
        p = palette_for(name)
        assert f"background-color: {p['card']}" in build_qss(p)
```

Run: `python -m pytest tests/test_theme.py -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/ui_pyqt6/ios_layout.py tests/test_ios_layout.py src/ui_pyqt6/theme.py tests/test_theme.py
git commit -m "feat: add iOS grouped card and row widgets"
```

---

### Task 2: The disclosure row

**Files:**
- Modify: `src/ui_pyqt6/ios_layout.py`
- Test: `tests/test_ios_layout.py`

**Interfaces:**
- Consumes: `SettingsRow` from Task 1, `theme.current_palette()`.
- Produces: `DisclosureRow(title: str, value: str = "", subtitle: str | None = None, parent=None)`, a `SettingsRow` subclass with signal `clicked = pyqtSignal()`, method `set_value(text: str)`, attribute `value_label`, and a hand-painted chevron. `CHEVRON_WIDTH = 18`.

- [ ] **Step 1: Write the failing tests**

```python
class TestDisclosureRow:
    def test_clicking_it_emits_clicked(self, qapp):
        row = DisclosureRow("History")
        seen = []
        row.clicked.connect(lambda: seen.append(True))
        QTest.mouseClick(row, Qt.MouseButton.LeftButton)
        assert seen == [True]

    def test_the_value_is_shown_on_the_right(self, qapp):
        row = DisclosureRow("Language", value="English")
        assert row.value_label.text() == "English"

    def test_set_value_updates_it(self, qapp):
        row = DisclosureRow("Language", value="English")
        row.set_value("Spanish")
        assert row.value_label.text() == "Spanish"

    def test_a_long_value_is_elided_rather_than_widening_the_row(self, qapp):
        row = DisclosureRow("Microphone")
        row.setFixedWidth(320)
        row.set_value("Microphone Array (Realtek(R) Audio) — not connected")
        row.show()
        assert row.value_label.width() <= 320

    def test_the_chevron_follows_the_live_palette(self, qapp):
        """Built once, repainted on theme change: the chevron must read the
        palette when it paints, not when it was constructed."""
        row = DisclosureRow("History")
        apply_theme(qapp, "dark")
        dark = _chevron_pixels(row)
        apply_theme(qapp, "light")
        light = _chevron_pixels(row)
        assert dark != light
```

`_chevron_pixels(row)` renders the row to a `QPixmap` and returns the set of
distinct colour names in the right-hand `CHEVRON_WIDTH` columns.

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/test_ios_layout.py -k Disclosure -q`
Expected: FAIL — `NameError`/`ImportError` on `DisclosureRow`

- [ ] **Step 3: Implement `DisclosureRow`**

`value_label` is a right-aligned `QLabel` with objectName `row_value`;
`set_value` elides with `QFontMetrics.elidedText` against the label's own width
before setting the text. `mouseReleaseEvent` emits `clicked` for a left button
inside the row. `paintEvent` calls `super().paintEvent` then draws the chevron
with a 1.8px round-capped pen in `current_palette()['secondary']`, mirroring
`ArrowComboBox.paintEvent`. Cursor is `PointingHandCursor`.

- [ ] **Step 4: Run them to verify they pass**

Run: `python -m pytest tests/test_ios_layout.py -q`
Expected: PASS

- [ ] **Step 5: Add `QLabel#row_value` to `theme.build_qss`** (secondary colour, 13px).

- [ ] **Step 6: Commit**

```bash
git add src/ui_pyqt6/ios_layout.py tests/test_ios_layout.py src/ui_pyqt6/theme.py
git commit -m "feat: add a chevron disclosure row"
```

---

### Task 3: Rebuild the settings window from cards

**Files:**
- Modify: `src/ui_pyqt6/settings_ui.py` (`_build_ui`, `_restyle`, `_sync_offline_state`; delete `_add_section`)
- Modify: `tests/test_settings_ui.py` (replace `TestLayoutFitsItsContent`, whose two tests assert the old flat geometry)
- Test: `tests/test_settings_ui.py`

**Interfaces:**
- Consumes: `GroupCard`, `SettingsRow`, `DisclosureRow`, `section_header` from Tasks 1–2.
- Produces: `SettingsWindow` with unchanged public API and unchanged widget attribute names, plus `_groups: dict[str, GroupCard]` keyed by header text.

The four groups, in order, with every current setting placed exactly once:

| Header | Rows |
|---|---|
| `TRANSCRIPTION` | API Key (`_api_key_edit` + Verify button, full-width row), Language (`_lang_combo`), Dictation Mode (`_profile_combo`, subtitle `_profile_sub`), Voice Commands (disclosure → `_show_voice_commands`), Offline mode (`_offline_check`) |
| `RECORDING` | Hotkey (`_hotkey_edit` + `_capture_btn`), Activation (`_activation_combo`), Microphone (`_mic_combo`) |
| `BEHAVIOUR` | Mute sounds, Run at login, Always copy to clipboard, Show clipboard notice, Auto-switch profile per app |
| `YOUR DATA` | History (disclosure → `_open_history`), Stats (disclosure → `_open_stats`), Help & FAQ (disclosure → `_show_help`) |

The header keeps the app title and subtitle and loses its three buttons, which
are now rows. `_voice_cmd_btn`, `_history_btn`, `_stats_btn` and `_help_btn` are
deleted along with them. Switches are constructed with empty text; the row
title carries the wording and the row carries the tooltip.

- [ ] **Step 1: Write the failing tests**

```python
class TestGroupedLayout:
    def test_every_setting_lives_in_a_group(self, window):
        assert set(window._groups) == {"TRANSCRIPTION", "RECORDING", "BEHAVIOUR", "YOUR DATA"}

    def test_controls_are_inside_their_card(self, window):
        assert window._mic_combo.isAncestorOf is not None
        assert _card_of(window, window._mic_combo) is window._groups["RECORDING"]
        assert _card_of(window, window._profile_combo) is window._groups["TRANSCRIPTION"]
        assert _card_of(window, window._mute_check) is window._groups["BEHAVIOUR"]

    def test_switch_rows_keep_their_explanation(self, window):
        """The switch text moved to the row title; the tooltip must move too."""
        row = _row_of(window, window._mute_check)
        assert "chime" in row.toolTip()

    def test_no_switch_carries_its_own_duplicate_label(self, window):
        for switch in window.findChildren(IOSSwitch):
            assert switch.text() == ""

    def test_the_old_header_buttons_are_gone(self, window):
        for attr in ("_history_btn", "_stats_btn", "_help_btn", "_voice_cmd_btn"):
            assert not hasattr(window, attr)
```

`_card_of` / `_row_of` walk `parent()` upwards to the first `GroupCard` /
`SettingsRow`.

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/test_settings_ui.py -k GroupedLayout -q`
Expected: FAIL — `AttributeError: 'SettingsWindow' object has no attribute '_groups'`

- [ ] **Step 3: Rewrite `_build_ui` to compose the groups**

Root layout: header (title, subtitle), the four `section_header` + `GroupCard`
pairs with 18px between groups and 6px between a header and its card, the Save
button, the footer. `_restyle` keeps styling only what the stylesheet cannot
reach. `_add_section` is deleted; `_profile_sub` becomes the Dictation Mode
row's `subtitle_label`.

- [ ] **Step 4: Run the new tests, then the whole settings file**

Run: `python -m pytest tests/test_settings_ui.py -q`
Expected: PASS for `TestGroupedLayout`; `TestLayoutFitsItsContent` fails on the
old geometry — delete those two tests, since the layout they describe is the one
this task replaces, and the new tests cover what matters.

- [ ] **Step 5: Verify the disclosure rows still open their windows**

```python
class TestDisclosureRowsAreWired:
    def test_history_row_calls_the_history_callback(self, qapp, tmp_path):
        seen = []
        w = SettingsWindow(config=..., on_save=lambda: None, on_history=lambda: seen.append(1))
        _row_titled(w, "History").clicked.emit()
        assert seen == [1]
```

Run: `python -m pytest tests/test_settings_ui.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/ui_pyqt6/settings_ui.py tests/test_settings_ui.py
git commit -m "feat: rebuild settings as iOS grouped inset cards"
```

---

### Task 4: Make the window survive its own content

**Files:**
- Modify: `src/ui_pyqt6/settings_ui.py` (`_build_ui`)
- Test: `tests/test_settings_ui.py`

**Interfaces:**
- Consumes: the grouped layout from Task 3.
- Produces: `SettingsWindow._scroll` (a `QScrollArea`), with Save and the footer outside it so they are always reachable.

- [ ] **Step 1: Write the failing tests**

```python
class TestContentIsReachable:
    def test_the_groups_scroll(self, window):
        assert window._scroll is not None
        assert window._scroll.widgetResizable() is True

    def test_save_is_outside_the_scroll_area(self, window):
        """Save must never scroll out of reach."""
        assert not window._scroll.isAncestorOf(window._save_btn)

    def test_nothing_is_cut_off_at_the_window_height(self, window):
        window.show()
        content = window._scroll.widget().sizeHint().height()
        assert window._scroll.verticalScrollBar().maximum() == max(
            0, content - window._scroll.viewport().height()
        )

    def test_there_is_no_horizontal_scrollbar(self, window):
        window.show()
        assert window._scroll.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/test_settings_ui.py -k ContentIsReachable -q`
Expected: FAIL — no `_scroll` attribute

- [ ] **Step 3: Wrap the groups in a `QScrollArea`**

Header, Save and footer stay in the window's root layout; the groups move into
a container widget inside `_scroll`. Horizontal scrolling off; vertical as
needed. The scrollbar is already styled app-wide with its gutter, so the groups
need right padding of `SCROLLBAR_THICKNESS + SCROLLBAR_GUTTER` only.

- [ ] **Step 4: Run them to verify they pass**

Run: `python -m pytest tests/test_settings_ui.py -q`
Expected: PASS

- [ ] **Step 5: Run the whole suite**

Run: `python -m pytest -q`
Expected: PASS, no new failures

- [ ] **Step 6: Render the window in both themes and look at it**

Render `SettingsWindow` to PNG at 540×820 under `light` and `dark` and inspect
both: cards are filled and separated, no row clipped, no stranded dark-on-dark
or light-on-light text, the Save button and footer visible without scrolling.

- [ ] **Step 7: Commit**

```bash
git add src/ui_pyqt6/settings_ui.py tests/test_settings_ui.py
git commit -m "feat: scroll the settings groups so nothing is unreachable"
```
