# Recording Display Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the decorative sine-wave overlay with three user-selectable recording displays — Orb (default), Waveform pill, Dynamic Island — every one of them driven by the real microphone level, and let the user pick between them in Settings with live animated previews.

**Architecture:** `MicRecorder` gains a cheap rolling level updated once per captured chunk, so reading it is O(1) however long the recording runs. A new `src/ui_pyqt6/recording_styles.py` holds the three display widgets behind one interface (`set_level`, `set_state`, `set_elapsed`, `set_mic_text`). `RecordingOverlay` keeps its thread-safe public API unchanged and becomes a host: it builds the configured style, polls the level provider at 60fps, and positions itself. Settings gains a picker whose three thumbnails animate from a synthetic level so the user sees what they are choosing.

**Tech Stack:** Python 3.13, PyQt6 6.10, PyAudio, pytest (headless via `QT_QPA_PLATFORM=offscreen`).

**Spec:** `docs/superpowers/specs/2026-11-10-voxel-fixes-design.md` — Part two, "Recording display: three styles, user-selectable" and "The recording animation must be driven by real audio".

## Global Constraints

- Accent is Voxel indigo `#6366f1` / `#818cf8` / `#4f46e5`. The Dynamic Island's recording dot is red `#ff453a` — the one deliberate exception.
- **Only the glow responds to voice level.** The orb's frosted disc and mic glyph stay fixed; a mic that wobbles with volume reads as nervous.
- The overlay floats over other apps, so it keeps its dark treatment in both themes.
- `RecordingOverlay`'s public methods (`show_recording`, `show_processing`, `hide`, `show_clipboard_notice`, `set_mic_text`, `show`) stay thread-safe and keep their signatures: `main.py` calls them from a worker thread.
- The overlay window must stay translucent — the application stylesheet reaches it, so `QWidget { background: transparent; }` and `WA_TranslucentBackground` are not optional.
- A level provider that raises or returns nothing must not stop the animation or the recording.

## Review Focus

1. **Level provider called from the GUI thread while the capture thread writes** — the rolling level is written by the PyAudio loop and read by a 60fps timer. Pinned in Task 1.
2. **A style name in config that no longer exists** (hand-edited, or a downgrade) must fall back to the default rather than crash the overlay on the first dictation. Pinned in Task 3.
3. **Silence must look like silence** — at zero level the display must visibly differ from loud speech, which is the whole point of the change. Pinned in Tasks 2 and 4.
4. **The overlay is reused across dictations**: state left over from a previous recording (elapsed text, mic warning, level) must not leak into the next one. Pinned in Task 4.
5. **Thumbnails must not keep animating when Settings is closed**, or a hidden window burns 60fps forever. Pinned in Task 5.

---

### Task 1: A cheap, live microphone level

**Files:**
- Modify: `src/mic_recorder.py`
- Test: `tests/test_mic_recorder.py`

**Interfaces:**
- Produces: `MicRecorder.current_level() -> float` in `0.0..1.0`, and module constant `LEVEL_FULL_SCALE_RMS = 4000.0`.

- [ ] **Step 1: Write the failing tests**

```python
class TestCurrentLevel:
    def test_silence_reads_zero(self):            # no frames captured yet
    def test_a_loud_chunk_reads_high(self):       # feed a full-scale chunk -> > 0.8
    def test_a_quiet_chunk_reads_low(self):       # feed a near-silent chunk -> < 0.1
    def test_it_does_not_rescan_the_whole_recording(self):
        """get_rms() sums every buffered frame, so it gets slower the longer you
        talk. The display reads this 60 times a second and must not."""
        # 10 chunks vs 1000 chunks: the call count of the unpack helper is the
        # same, because only the newest chunk is measured.
    def test_level_decays_rather_than_snapping_to_zero(self):
        """A bar chart that snaps to zero between syllables flickers."""
```

- [ ] **Step 2: Run them and watch them fail**

Run: `py -3.13 -m pytest tests/test_mic_recorder.py -k CurrentLevel -q`
Expected: FAIL — `AttributeError: 'MicRecorder' object has no attribute 'current_level'`

- [ ] **Step 3: Implement it**

In the capture loop, after each chunk is appended, compute that chunk's RMS
only and fold it into `self._level` with asymmetric smoothing (fast attack,
slow decay: `level = max(new, level * 0.82)`), under the existing lock.
`current_level()` reads it under the lock and returns it clamped to `0..1`
after dividing by `LEVEL_FULL_SCALE_RMS`. `get_rms()` is left alone — it is
still the right measure for the end-of-recording silence check.

- [ ] **Step 4: Run them and watch them pass**, then the file: `py -3.13 -m pytest tests/test_mic_recorder.py -q` → PASS

- [ ] **Step 5: Commit**

```bash
git add src/mic_recorder.py tests/test_mic_recorder.py
git commit -m "feat: track a cheap rolling microphone level"
```

---

### Task 2: The three display widgets

**Files:**
- Create: `src/ui_pyqt6/recording_styles.py`
- Test: `tests/test_recording_styles.py`

**Interfaces:**
- Produces:
  - `RECORDING_STYLES: dict[str, str]` — id → human label: `orb` → "Orb", `waveform` → "Waveform", `island` → "Dynamic Island". `DEFAULT_STYLE = "orb"`.
  - `build_display(style_id: str, parent=None) -> RecordingDisplay` — unknown id falls back to `DEFAULT_STYLE`.
  - `RecordingDisplay(QWidget)` base with `set_level(float)`, `set_state(str)` (`recording` / `processing` / `clipboard`), `set_elapsed(str)`, `set_mic_text(str)`, `advance(float)` (animation phase), and `preferred_size() -> QSize`.
  - `OrbDisplay`, `WaveformDisplay`, `IslandDisplay`.

- [ ] **Step 1: Write the failing tests**

```python
class TestStyleRegistry:
    def test_every_style_builds(self):           # each id in RECORDING_STYLES
    def test_an_unknown_style_falls_back_to_the_default(self):
    def test_the_default_is_the_orb(self):

class TestLevelDrivesTheDrawing:
    """The old waveform animated identically whether you shouted or said
    nothing. For each style, loud must not look like silent."""
    def test_loud_and_silent_render_differently(self, style):   # parametrised over all three

class TestOrbGlyphIsSteady:
    def test_the_disc_and_mic_do_not_move_with_level(self):
        """Spec: only the glow responds. Pixels in the disc's centre are
        identical at level 0.0 and level 1.0."""

class TestIslandDotStaysRed:
    def test_recording_dot_is_red_not_indigo(self):
```

- [ ] **Step 2: Run them and watch them fail**

Run: `py -3.13 -m pytest tests/test_recording_styles.py -q`
Expected: FAIL — module does not exist

- [ ] **Step 3: Implement the three widgets**

All three paint themselves on a translucent window and keep their dark
treatment in both themes.

- **OrbDisplay** — indigo radial glow whose radius and opacity follow level and
  drift with `advance()`; a frosted centre disc (semi-transparent white over
  the glow, so it bleeds faintly through); a mic glyph filled with a vertical
  `#FFFFFF` → `#F4F4F7` at 45% → `#B9B9C4` gradient with a soft drop shadow;
  elapsed timer centred beneath the orb, mic text beneath that.
- **WaveformDisplay** — the existing frosted pill and bar geometry, but each
  bar's height comes from a rolling history of levels rather than summed sine
  waves; inline timer.
- **IslandDisplay** — compact near-black pill that breathes with level; red
  recording dot; inline timer.

- [ ] **Step 4: Run them and watch them pass**: `py -3.13 -m pytest tests/test_recording_styles.py -q` → PASS

- [ ] **Step 5: Render all three to PNG at level 0.05 and 0.9 and look at them.**

- [ ] **Step 6: Commit**

```bash
git add src/ui_pyqt6/recording_styles.py tests/test_recording_styles.py
git commit -m "feat: three level-driven recording displays"
```

---

### Task 3: The overlay hosts a style

**Files:**
- Modify: `src/ui_pyqt6/recording_overlay.py`, `src/main.py`, `src/config.py`
- Test: `tests/test_recording_overlay.py`

**Interfaces:**
- Consumes: `build_display`, `DEFAULT_STYLE`, `MicRecorder.current_level`.
- Produces: `RecordingOverlay(style: str = DEFAULT_STYLE, level_provider: Callable[[], float] | None = None)`, property `style`, method `set_style(style_id)`. Config key `recording_style`, default `orb`.

- [ ] **Step 1: Write the failing tests**

```python
class TestOverlayHostsAStyle:
    def test_it_builds_the_configured_style(self):
    def test_an_unknown_configured_style_still_shows_something(self):
        """A hand-edited or downgraded config must not break every dictation."""
    def test_the_level_provider_feeds_the_display(self):
    def test_a_failing_level_provider_does_not_stop_the_animation(self):
        """A provider that raises must cost a frame, never the recording."""
    def test_the_window_stays_translucent_for_every_style(self):   # the sentinel-pixel probe
```

- [ ] **Step 2: Run them and watch them fail.**

- [ ] **Step 3: Rewrite the overlay as a host**

Keep `_OverlaySignals` and every public method exactly as they are. `_build_ui`
builds `self._display = build_display(style)`; the 60fps timer reads
`level_provider()` inside a `try` and calls `self._display.set_level(...)` then
`advance()`. Elapsed and mic text are forwarded to the display. `main.py`
passes `style=config.get("recording_style", DEFAULT_STYLE)` and
`level_provider=self._recorder.current_level`, and re-reads the style after
Settings saves.

- [ ] **Step 4: Run them and watch them pass**, then the whole suite.

- [ ] **Step 5: Commit**

```bash
git add src/ui_pyqt6/recording_overlay.py src/main.py src/config.py tests/test_recording_overlay.py
git commit -m "feat: drive the recording overlay with the real mic level"
```

---

### Task 4: Nothing leaks between dictations

**Files:**
- Modify: `src/ui_pyqt6/recording_overlay.py`
- Test: `tests/test_recording_overlay.py`

- [ ] **Step 1: Write the failing tests**

```python
class TestOverlayResetsBetweenDictations:
    def test_elapsed_restarts_at_zero(self):
    def test_the_level_is_cleared_so_the_orb_does_not_open_mid_shout(self):
    def test_the_mic_warning_survives_but_the_clipboard_notice_does_not(self):
        """set_mic_text is a persistent warning; "Paste with Ctrl+V" is not."""
    def test_timers_stop_when_hidden(self):
        """A hidden overlay animating at 60fps burns a core for nothing."""
```

- [ ] **Step 2: Run, watch fail. Step 3: Fix. Step 4: Run, watch pass.**

- [ ] **Step 5: Commit**

```bash
git add src/ui_pyqt6/recording_overlay.py tests/test_recording_overlay.py
git commit -m "fix: reset overlay state between dictations"
```

---

### Task 5: The picker with live previews

**Files:**
- Modify: `src/ui_pyqt6/settings_ui.py`
- Test: `tests/test_settings_ui.py`

**Interfaces:**
- Consumes: `RECORDING_STYLES`, `build_display`, and `GroupCard`/`SettingsRow` from the settings layout.
- Produces: `SettingsWindow._style_picker` with `selected() -> str`; `_save` writes `recording_style`.

- [ ] **Step 1: Write the failing tests**

```python
class TestRecordingStylePicker:
    def test_it_offers_every_style(self):
    def test_it_starts_on_the_configured_style(self):
    def test_choosing_one_saves_it(self):
    def test_the_previews_animate_only_while_the_window_is_visible(self):
    def test_the_previews_do_not_touch_the_microphone(self):
        """A preview that opened the mic would fight the recorder for it."""
```

- [ ] **Step 2: Run, watch fail.**

- [ ] **Step 3: Implement the picker** — three selectable thumbnails in the
RECORDING group, each hosting a real display widget fed a synthetic level
(a slow sine), started on `showEvent` and stopped on `hideEvent`/`closeEvent`.

- [ ] **Step 4: Run, watch pass; then the whole suite.**

- [ ] **Step 5: Render Settings in both themes and look at the picker.**

- [ ] **Step 6: Commit**

```bash
git add src/ui_pyqt6/settings_ui.py tests/test_settings_ui.py
git commit -m "feat: let the user choose a recording display"
```
