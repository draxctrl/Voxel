# Voxel UI rebuild — design

**Date:** 2026-11-11
**Status:** awaiting approval
**Owner:** Isuru (draxctrl)

---

## Why this exists

Voxel is going out publicly, on an already-public GitHub repo, to people who
have never met it and owe it no patience. Isuru's words: *"this one is not good
enough… doesn't look clean and cluttered too."*

Two separate problems hide inside that sentence, and both have to be fixed or
neither is:

1. **It looks cluttered.** Every setting Voxel has lives on one scrolling page.
   Fifteen controls compete for attention and none of them wins.
2. **It doesn't look good.** The current styling is a half-iOS, half-Windows
   mix that reads as unfinished.

There is a third problem nobody reported, because only strangers hit it: Voxel
cannot do anything until the user has a free Groq API key, and a new user has
never heard of Groq. Today they would meet an empty text box on a settings page.
A public launch with that first run loses most of the people who download it.

The reference Isuru gave for the look is **Discord**.

---

## Goals

- A settings window a stranger finds calm and legible on first sight.
- One topic on screen at a time; no scrolling to find a setting.
- A first run that ends with the new user having **already dictated
  something successfully, inside Voxel's own window**.
- Light and dark themes, following the Windows setting by default.
- Screenshots good enough to put at the top of a public README.

## Non-goals

- No change to how Voxel records, transcribes, cleans up or injects text. The
  engine works; this is the surface.
- No installer, website, store listing or release automation. Separate work.
- No change to the floating recording badge. It is the one part that already
  looks right.
- No new product features. Settings that exist today are regrouped and
  renamed, not added to or removed.

## Anti-goals — ways this fails while technically succeeding

- **Hiding the mess behind doors.** Nine sidebar entries holding the same
  eleven jumbled controls is not an improvement. The grouping has to make each
  screen feel complete on its own.
- **Bloating the download.** Voxel is a free tool people try on a whim. See
  "Toolkit" below.
- **Breaking what works.** Roughly 265 of the 375 passing tests cover the
  engine — hotkeys, recording, transcription, config, history. **Those stay
  green throughout.** The other ~110 (`test_settings_ui`, `test_theme`,
  `test_theme_widgets`, `test_ios_layout`) test the code being replaced and
  are expected to be rewritten with it; `test_theme.py` hard-asserts the
  current palette's hex values, so adopting the new one requires editing them.
  A rebuild that regresses the hotkey, the overlay or the transcription path
  has cost more than it gained.
- **Beautiful but mute.** If a stranger cannot tell whether Voxel is working,
  the look does not matter.

---

## Decided — the shape of it

These were settled with Isuru during brainstorming, with mockups he reviewed.
Rendered images live in `docs/mockups/`.

### Layout: a sidebar, like Discord

A fixed left rail (~198px) lists topics in groups; the right pane shows one
topic. Chosen over a single calmer page and over top tabs, both of which Isuru
saw and passed on.

| Group | Entries |
|---|---|
| Dictation | Writing style, Voice commands, Language |
| Your setup | Microphone, Shortcuts, Appearance |
| Your words | History, Stats |
| App | General, About |

Every control that exists today has exactly one home. The four the mockups did
not place: **API key** → General (it is set during first run and rarely touched
again), **Activation mode** (hold / press-to-toggle) → Shortcuts, **recording
badge style** → Appearance, **Voice commands** → its own pane, since it has a
full editor today and nowhere else to live. Per-app profile switching
(`auto_profile`) stays exactly as it is: one toggle on General.

**History and Stats stop being separate windows** and become panes here. That
removes two windows from the app outright.

At the bottom of the rail, permanently visible: a status dot, a word and the
user's **actual** shortcut, read from their config — the mockups show
`Ready · Ctrl + Alt` because that is Isuru's; the shipped default is unchanged
at Ctrl+Shift+Space. The dot mirrors the four states `main.py` already tracks
for the tray: idle, recording, processing, error. "Is this thing on?" is
answered without a click.

### Words

Labels are rewritten into plain English. Decided examples:

| Now | Becomes |
|---|---|
| Dictation Mode | Writing style |
| Raw mode | Exactly what I said |
| Offline mode | Work offline — *"Slower, but nothing leaves this computer"* |

Writing style is presented as three tap-to-choose rows, not a dropdown:
**Grammar only**, **Tidy up**, **Exactly what I said**, each with one line of
explanation.

Voxel has six built-in styles, not three. **Isuru's decision:** the three
everyday ones sit on the pane; *Professional Email*, *Code Comments*,
*Technical Writing* and any custom styles the user has made live behind a
**More styles** link on the same pane. Nothing is deleted and nothing is
silently migrated — a user whose active style is one of the hidden four keeps
it, and the pane shows it as selected under More styles.

### Look

- Dark and light themes, following Windows by default, with an explicit
  override under Appearance.
- Indigo `#6366f1` stays the accent. The Dynamic Island's red dot stays.
- **Phosphor icons** (MIT licensed), bundled as SVG files in the repo — not
  fetched at runtime.
- Dark surfaces, roughly: rail `#16171a`, pane `#1e1f23`, rows `#2a2c32`,
  borders `#32343b`. Light values are the builder's to derive.

### First run — four screens, about a minute

1. **Welcome.** What Voxel does, in one sentence. One button.
2. **Choose how Voxel listens.** Two options: *Fast and accurate* (free Groq
   key, recommended) or *Private — stays on this computer* (local model,
   slower, 145MB download). A "Get my free key" button opens Groq's page; the
   pasted key is **validated against the API immediately**, with a green tick
   on success and a plain-language error on failure.
3. **Microphone.** Devices as rows with live level meters. "Pick the one whose
   bars move when you talk." Proof, not a dropdown.
4. **Try it.** "Hold Ctrl + Alt and say anything." The result lands in a box on
   that screen.

Step 4 is the one worth defending: today a new user's first dictation happens
in some other application, where failure is a mystery. Here, Voxel is holding
the problem and can explain it.

### Toolkit — PyQt6, not a web view

**This is my call, not Isuru's, and it reverses advice I gave him earlier in
the same conversation.** I first recommended rebuilding the windows as an
embedded web page, because Qt's stylesheet engine had fought me all day over
dropdown corners, switch indicators and padding arithmetic.

Checked before committing to it:

- A sidebar with stacked panes, flat rows, SVG icons and custom-painted
  toggles is ordinary PyQt6 work. `QtSvg` and `QStackedWidget` are present.
- The cosmetic fights were mostly the combo-box popup — and this design
  replaces most dropdowns with tap-to-choose rows.
- `PyQt6-WebEngine` would add roughly 200MB to a public download. The lean
  alternative (pywebview on WebView2) means two UI systems with two event
  loops in one process, next to a Qt tray icon and a Qt overlay.

So: same toolkit, no bloat, one event loop, and the existing test suite keeps
protecting the app underneath.

---

### Stats

**Isuru's decision:** three big numbers — words dictated, time saved, and this
week — instead of today's seven-card grid. "Streaks", advertised in the current
settings row, is not implemented in `history.py` and is not being added.

### Saving

There is no Save button. Each control applies when you touch it, and only what
changed is restarted: changing the microphone reopens the audio stream,
changing the shortcut restarts the hotkey listener, and changing a checkbox
does neither. Today a single `_save()` reloads the config, restarts the
listener, rebuilds the injector and reopens the microphone stream all at once —
doing that on every toggle would be unusable. *My call; it is the one change
this design makes to `main.py`'s wiring.*

### The first-run test dictation

Step 4's dictation is **diverted**: it is shown in the box on that screen, and
it is not typed into whatever app is behind Voxel, not pasted, and not written
to History. This is a deliberate, narrow exception to "no change to how Voxel
injects text" — a one-shot hook on the processing path, nothing more. *My
call.* Note that the hotkey listener only starts today once an API key exists,
so the offline path has to start it too or step 4 silently does nothing.

### Who sees the first run

A new `onboarding_complete` flag in the config, not a user-facing setting.
Today "configured" means "has an API key", which would hand the setup wizard to
an offline-only user on every single launch. Anyone upgrading with a working
key is marked complete and never sees it. *My call.*

### Carried over without discussion

- The tray menu's **History** and **Statistics** items open the main window on
  that pane, since those windows no longer exist.
- The History pane keeps everything today's window does: search, copy, delete,
  clear all.
- Phosphor SVGs must be added to `build.spec`'s `datas`, or they vanish from
  packaged builds.
- `always_copy` and `clipboard_notice` are read and written by the UI but are
  missing from `DEFAULT_CONFIG`; add them.
- The window becomes resizable — 980×620 by default, no smaller than 860×560.
  It is `setFixedSize(540, 820)` today, which the new layout cannot use.
- Offline transcription is already in `build.spec`'s `hiddenimports`, so the
  "Private" option should survive packaging. **Verify this in a built `.exe`
  before release** — if it does not, that option is a dead end for exactly the
  stranger this redesign is for.

## Constraints

- Python 3.13 + PyQt6 6.10. Tests: `py -3.13 -m pytest -q` from the repo root.
  There is no virtualenv; plain `python` is a 3.12 without pytest.
- No new heavy dependencies. Phosphor SVGs are static assets.
- Windows is the primary target. `BudgetWhisper-mac/` is a separate copy and
  is **out of scope**.
- The repo is public. No key, token or personal path may enter it.
- MIT licensed; bundled icon assets must stay license-compatible (Phosphor is
  MIT).
- Offscreen Qt in pytest does not draw platform-styled widgets the way real
  Windows does. **Rendering screens to PNG and looking at them** has caught
  what the tests could not, repeatedly, and is expected practice here.

---

## Left to the builder

- Widget-level structure: how the rail, the pane stack and each page are
  composed, and how much of `theme.py` and `ios_layout.py` survives.
- The migration path for `settings_ui.py` (1,202 lines today), and whether
  `history_window.py` and `stats_window.py` become panes by porting or by
  rewrite.
- Light-theme colour values derived from the dark set.
- Where the first-run flow lives and how it is triggered (and skipped on
  subsequent launches).
- Test strategy for the new panes, keeping the existing 375 green.
- Which Phosphor weight (regular vs fill) is used where, beyond the brand mark.

---

## Still open

1. **Shipping.** Whether this UI is the whole job, or whether a public launch
   also needs installer and landing-page work. A separate project either way,
   and not blocking this one.

## Settled during review

- **Mockups in the README:** yes, labelled as the coming release rather than
  as the current app. *Isuru's decision.*
- **Writing styles:** three up front, the rest behind "More styles". *Isuru's
  decision.*
- **Stats:** three big numbers. *Isuru's decision.*
