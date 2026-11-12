# Voxel: correctness fixes, two grammar modes, and UI consistency pass

**Date:** 2026-11-10
**Status:** approved scope, pending plan

## Intent and why

Voxel works, but several features either do nothing, do something
unpredictable, or look like they belong to a different application. The owner
hit all of these in real use. The thread running through every item is
**trust**: a setting that silently has no effect, a hotkey that undoes
something random, or a mic selection that quietly points at a different device
all teach the user not to believe the UI. This pass makes the app honest about
what it is doing, and makes the chrome look like one product.

This is maintenance on an existing app, not a redesign. The stack stays
Python 3.13 + PyQt6 + Groq (Whisper + Llama), packaged with PyInstaller.

## Goals

1. Microphone selection survives plugging in other audio devices.
2. Dictation Mode visibly and actually affects output.
3. Two new, distinct grammar modes.
4. Remove the undo hotkey entirely.
5. One scrollbar design across the whole app, never touching content.
6. Dropdown popups read as part of the field they belong to.
7. Country flags beside each language.
8. A toggle (press-to-start / press-to-stop) alternative to push-to-talk.

## Non-goals

- No redesign of the settings window *layout* or the colour palette. Its
  styling **source** is being unified (see below), but the arrangement of
  controls and the colours themselves stay as they are.
- No change to the transcription or cleanup provider.
- No new packaging, installer, or CI work.
- No macOS-specific work beyond keeping existing parity intact.

## Anti-goals (would make this a failure even if it technically works)

- A fix that makes a setting *appear* to work while it is still ignored.
- Replacing the blind `Ctrl+Z` undo with a different unpredictable action.
- Flags that render as letter pairs or empty boxes on Windows.
- Per-window stylesheet copies that drift apart again later.

## Constraints

- **Windows cannot render flag emoji.** Segoe UI Emoji omits regional
  indicator sequences, so `🇺🇸` renders as "US". Flags must be image assets.
- PyAudio device indices are not stable identifiers; they renumber whenever
  devices are added or removed.
- Qt quirk: setting a stylesheet on a child `QScrollArea` causes unspecified
  scrollbar subcontrols to fall back to the native Windows style. This is the
  direct cause of two of the mismatched scrollbars.
- The app is a tray app; the settings window is constructed once and reused,
  so anything populated in `__init__` must also be refreshable.

## The decisions already made

These were decided by the owner and are not open for the builder to revisit.

### Undo hotkey: removed

Today `_on_undo_press` ([src/main.py:338](../../../src/main.py)) sends a blind
`Ctrl+Z` to whatever window happens to be focused and restores the previous
clipboard, valid once and within 60 seconds, with no check that focus is still
the app it pasted into. The owner found this unpredictable and chose removal
over repair.

Remove: the `_undo_listener` and `_start_undo_listener`, `_on_undo_press`, the
undo state (`_last_injection`, `_last_injection_time`, `_undo_lock`), the
`undo_hotkey` config key, the settings row and its capture button, and the FAQ
entry. `InjectionResult.old_clipboard` stays — `TextInjector` still uses it to
restore the clipboard after pasting.

### Two new grammar modes, kept separate

The owner wants **both** of these as distinct, separately selectable modes,
not one blended mode:

- **Grammar only (keep my words)** — fixes grammar, tense, agreement,
  spelling and punctuation. Keeps filler words, slang and sentence structure
  exactly as spoken. The most literal mode available that is not raw.
- **Grammar + tidy up** — fixes grammar *and* removes filler words so the
  result reads cleanly.

Both are built-in profiles in `ProfileManager.BUILTIN_PROFILES`. Both keep the
existing no-censorship rule that every current profile carries.

### Language flags: bundled image assets

Real flag images, not emoji and not hand-drawn Qt painting. Fetch a small set
of permissively licensed (MIT or public domain) flag assets into
`src/assets/flags/`, one per language in the existing list, and attach them as
`QIcon`s on the language combo items. Record the source and licence in the
repo. The assets must be included in the PyInstaller build and resolved
through the existing frozen/dev asset path helper.

### Styling: one shared source, duplicate deleted

`settings_ui.py` currently holds a **second complete copy** of the theme — its
own palette constants (`_BG`, `_CARD`, …), its own `_QSS`, and its own
`_ArrowComboBox` and `_TickCheckBox` classes that duplicate the ones in
`theme.py`. Every dropdown the user actually interacts with comes from that
copy; `theme.ArrowComboBox` is dead code.

The duplicate is deleted and `settings_ui.py` imports from `theme.py`. This is
the only option under which the scrollbar and dropdown fixes cannot silently
drift apart again, which the anti-goals require. The tradeoff accepted
knowingly: this restyles a 1,300-line window, so every control in it must be
checked visually afterwards, not just the ones named in this document.

### Dictation modes: consolidated, not merely extended

Adding two grammar modes to the existing six would produce eight modes with
heavy overlap. Instead the list is reworked so each mode is clearly distinct,
folding in the ones that overlap (notably `default` and `casual`, which the
grammar modes largely subsume).

Requirements:
- The user's currently selected mode must be carried over automatically;
  nobody should open Settings to find their mode gone.
- `active_profile` **and** `app_profiles` values are keyed by profile id, so
  both need migrating when ids disappear.
- History rows store the display *name* at the time of dictation. Past rows
  keep their original labels and are not rewritten.
- The `raw` mode and its `__RAW__` sentinel stay.

### Missing microphone: warn, but keep working

When the saved device cannot be found, Voxel falls back to the default input
device **and tells the user it did so**, rather than today's silent switch.
Dictation continues to work. The warning must reach the user at the moment it
matters (not only inside Settings), using the existing tray/overlay channels,
and Settings should also show which device is actually in use.

### Language flags: one row per language

Flags follow speaker numbers rather than country of origin: English → United
States, Spanish → Spain, Portuguese → Brazil, Chinese → China. The list stays
at its current ten entries; variants are not split into separate rows, since
Whisper treats them as the same language. (My call — the owner deferred it.)

### Activation mode: a setting, builder's call on presentation

Push-to-talk stays the default. A new mode lets the user press the hotkey once
to start and press it again to stop. This is a choice between two activation
styles for the *same* configured hotkey, not a second hotkey. (My call, as the
owner described the behaviour but not the UI.)

## What needs fixing, and why it is broken

### 1. Microphone selection does not survive new devices

`mic_device` is stored as a PyAudio integer index
([src/main.py:84](../../../src/main.py),
[src/mic_recorder.py:25](../../../src/mic_recorder.py)). Indices renumber when
any audio device is plugged in or removed, so the saved number then refers to
a different microphone. Compounding it, `MicRecorder.__init__` catches the
failure and silently falls back to the system default device.

Fix direction: persist the device **name** as the identifier (keeping the index
only as a fast-path hint), resolve the name to a live index when opening the
stream, and surface it in the UI when the chosen device cannot be found rather
than silently recording from something else. Keep backward compatibility with
configs that currently hold a bare integer.

### 2. Dictation Mode does not take effect

Three independent causes:

- **Offline mode silently disables it.** `_process_audio` skips cleanup
  entirely when `offline_mode` is set
  ([src/main.py:299](../../../src/main.py)), so the dropdown does nothing and
  nothing says so. The UI must make this visible.
- **Auto-switch per app is sticky.** When a focused app has a profile mapping
  the cleaner prompt is switched, but there is no `else` branch restoring the
  user's chosen profile ([src/main.py:282-294](../../../src/main.py)). After
  one match, every later dictation keeps that profile regardless of app.
- **The prompts barely differ.** All five built-ins are variations of the same
  "dictation cleanup assistant" text, so switching modes produces nearly
  identical output. They need to be genuinely differentiated to be worth
  having.

### 3. Dropdown popups look detached

`showPopup` computes a width from item text and then resizes the popup's
top-level window to it, ignoring the field's own width and screen position.
The popup also uses 6px corners and its own padding against the closed field's
8px. Result: a floating panel that does not line up with the control.

The live copy of this code is **`settings_ui._ArrowComboBox`**, not
`theme.ArrowComboBox` ([src/ui_pyqt6/theme.py:261-272](../../../src/ui_pyqt6/theme.py)),
which is dead. Both are removed in favour of one implementation.

Fix direction: the popup should align to the field and be at least as wide as
it, only growing when content genuinely requires it, with corner radius,
border and background matching the field.

### 4. Four different scrollbars, all touching content

- [src/ui_pyqt6/theme.py:229-247](../../../src/ui_pyqt6/theme.py) — the shared
  style; has no `add-page`/`sub-page` rules and reserves no gap.
- [src/ui_pyqt6/history_window.py:217-243](../../../src/ui_pyqt6/history_window.py)
  — a near-duplicate applied directly to the scroll area and its scrollbar.
- [src/ui_pyqt6/stats_window.py:132](../../../src/ui_pyqt6/stats_window.py) —
  `QScrollArea { border: none; }`, which triggers the Qt fallback to the
  **native Windows scrollbar**.
- The FAQ dialog and the Voice Commands dialog in
  [src/ui_pyqt6/settings_ui.py](../../../src/ui_pyqt6/settings_ui.py) — these
  set `settings_ui._QSS`, which contains **no scrollbar or scroll-area rules
  at all**, so they go native regardless of the `border: none` override.

Fix direction: one canonical scrollbar definition in `theme.py`, covering
vertical and horizontal, including the page/groove subcontrols so nothing
falls back to native. Every window uses it; the per-window copies are deleted.
Content must clear the scrollbar — cards in History and Stats should not sit
under it.

### 5. Toggle activation mode

`HotkeyListener` is built around press/release with a `min_hold_duration` tap
filter and a polling thread that watches for physically released keys
([src/hotkey_listener.py](../../../src/hotkey_listener.py)). Toggle mode needs
the press to flip recording state and the release to be ignored, which means
the tap filter and the release-poll safety net must not fire in that mode. The
existing `MAX_RECORDING_DURATION` cap must still apply, since in toggle mode a
user can walk away while recording.

## Part two: the iOS visual redesign

Added mid-brainstorm by the owner, after the fix list above was already
settled. It is deliberately recorded as a second part because it **overrides**
the original non-goal "no change to the colour palette", and because it
reorders the work: the cosmetic items from Part one (scrollbars, dropdowns,
language flags) are built *inside* the new look rather than being styled twice.

Behavioural fixes (microphone, dictation modes, removing undo, toggle-to-talk)
are independent of appearance and come first.

### Theme: iOS, following Windows light/dark

Both an iOS light and an iOS dark theme, switching automatically with the
Windows system setting. Structure follows iOS rather than merely recolouring:
grouped inset cards with rounded corners, section headers in small uppercase
grey, values right-aligned with a chevron, and iOS-style switches replacing the
square checkboxes.

| Role | Light | Dark |
|---|---|---|
| Window background | `#F2F2F7` | `#000000` |
| Card / group | `#FFFFFF` | `#1C1C1E` |
| Separator | `#D6D6DA` | `#2E2E31` |
| Primary text | `#000000` | `#FFFFFF` |
| Secondary text | `#8E8E93` | `#8E8E93` |
| Switch (off) | `#E9E9EB` | `#39393D` |

**Accent is Voxel indigo, not iOS blue** — explicitly chosen by the owner,
including for switches, which use indigo rather than Apple's green `#34C759`.
Indigo `#6366f1`, light `#818cf8`, dark `#4f46e5`.

**Typography:** SF Pro cannot legally be bundled. Inter (SIL OFL) is used
instead and must be shipped with the app, not fetched at runtime.

### Recording display: three styles, user-selectable

The owner asked that all three designed styles ship as a setting rather than
one being chosen and the rest discarded. They share one input, so the
incremental cost is drawing code only.

1. **Orb** — *default*. Indigo radial glow that swells and drifts, with a
   **frosted glass** centre disc (the glow bleeds faintly through) holding a
   mic glyph drawn in a white→grey vertical gradient, brightest at the top,
   with a soft drop shadow. A small elapsed timer sits beneath the orb.
2. **Waveform pill** — frosted pill, live indigo bars, inline timer.
3. **Dynamic Island** — compact black pill that breathes and expands. Its
   recording dot stays red, the one deliberate exception to the indigo rule.

The settings picker shows **live animated thumbnails** of each style.

**Only the glow responds to voice level; the disc and mic glyph stay fixed.** A
mic that wobbles with volume reads as nervous rather than responsive.

### The recording animation must be driven by real audio

`_WaveformWidget._bar_height`
([src/ui_pyqt6/recording_overlay.py:114-127](../../../src/ui_pyqt6/recording_overlay.py))
is three summed sine waves advanced by a timer. It is **decorative** — it
animates identically whether the user shouts or says nothing, which makes the
app appear to be listening when it may not be. `MicRecorder.get_rms()` already
exists and is never used for display.

All three styles must be driven by live microphone level. Note that `get_rms()`
currently sums every buffered frame on each call, so it grows more expensive
the longer a recording runs — it needs a cheap rolling measure for per-frame UI
updates.

### App icon: dark squircle with glowing orb, size-specific artwork

The icon is the recording orb: a dark squircle, indigo glow, light mic. Chosen
for coherence — the app's icon and its recording animation are the same object.

Because a soft glow turns to mush at small sizes, the `.ico` ships **different
artwork per size**, not one image scaled:

| Size | Used for | Artwork |
|---|---|---|
| 256 / 512 | installer, About | Full glow with soft falloff |
| 32 / 48 | taskbar, alt-tab | Tightened glow, brighter core, heavier mic stroke |
| 16 | tray, title bar | Glow flattened to a solid indigo disc, mic only |

Tray icons continue to vary by state (idle, recording, processing). The macOS
`.icns` and the installer artwork need regenerating to match.

### Preserved alternative: flat indigo squircle

**The owner liked this and wants the option to switch to it later.** Recorded
here so it can be rebuilt without redoing the exploration:

> A squircle filled with a top-lit indigo gradient
> (`#8b8ff5` → `#6366f1` at 46% → `#4338ca`), a white highlight over the top
> 46% at ~22% opacity, and the same white→grey mic glyph
> (`#ffffff` → `#f4f4f7` at 45% → `#b9b9c4`) centred on top with a soft drop
> shadow. Corner radius ≈ 27% of the tile.

Its advantage is legibility: the solid indigo block stays recognisable at 16px
where the glow version needs its simplified variant. It is a drop-in
replacement — same glyph, same palette, only the tile treatment differs.

## Calls made during review

Settled without the owner, recorded so they can be checked:

- **Auto-profile is restructured, not patched.** Two bugs sit beside the
  missing `else` in `_process_audio`: `is_raw_profile` and the `profile=` label
  written to History both derive from `get_active_profile()` rather than the
  app-switched profile. So mapping an app to Raw does nothing, and History
  mislabels auto-switched dictations. The block resolves one *effective
  profile* per dictation instead of mutating the cleaner's prompt in place.
- **`__RAW__` stays.** The stale test that asserts every built-in prompt
  contains `{raw_transcript}` is fixed by exempting the sentinel and not
  hardcoding profile counts, rather than by restructuring Raw.
- **Toggle state lives in `VoxelApp`,** not `HotkeyListener`. The
  `MAX_RECORDING_DURATION` timer currently calls `_on_hotkey_release` directly
  and leaves the listener's `_is_held` stale, so the auto-stop path must reset
  the activation state too. Modifier-only hotkeys are not offered with toggle
  mode, since every Ctrl+Shift press would flip recording.
- **`BudgetWhisper-mac/` is treated as dead.** It is a stale fork (no
  `profiles.py`, `theme.py` or `history.py`; `main.py` is 297 lines against
  497) while `.github/workflows/build-mac.yml` builds from the main `src/` via
  `build_mac.spec`. It is left untouched; only `build_mac.spec` gains the flag
  assets.
- **The settings window may grow in height** if removing the undo row does not
  free enough space for the activation-mode control and the offline-mode note.
  Compressing sections is not acceptable; that is the ruled-out redesign.
- **`requirements.txt` is corrected as part of this work.** It omits PyQt6,
  which the whole UI depends on, while still listing `customtkinter` and
  `pystray`, which nothing imports. `pytest` is added as a dev dependency so
  the suite is runnable at all.
- **Pre-existing test breakage is fixed, not inherited.** Baseline before any
  change: 88 passing, 3 failing, and `tests/test_mic_recorder.py` failing to
  import because it references `SAMPLE_RATE` (renamed to
  `TARGET_SAMPLE_RATE`). All of it is repaired here so "the suite passes" is a
  meaningful gate.

## Still left to the builder

- Whether the mic identifier becomes a small structured value or a plain name
  string, and the shape of the config migration.
- Exact prompt wording for the consolidated built-in profiles, and the final
  mode list, subject to the distinctness requirement above.
- How "Dictation Mode has no effect in Offline mode" is surfaced (disabling the
  control, an inline note, or both).
- Presentation of the activation-mode setting.
- Which flag asset set is used, provided the licence is MIT or public domain.
- Whether the combo box keeps custom painting or moves to a styled arrow.
- Test coverage choices, following the existing `tests/` conventions.

## Verification expectations

The existing test suite must pass. Beyond that, the items that are *behavioural*
rather than cosmetic deserve tests: mic resolution by name across renumbered
indices and config migration, the auto-profile restore path, toggle activation
state transitions, and profile prompt selection. The cosmetic items (scrollbars,
popup alignment, flags) are verified by running the app and looking at them;
they should not be claimed as done on the basis of code reading alone.
