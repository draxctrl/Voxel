# App Icon Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Voxel the recording orb as its icon — a dark squircle with an indigo glow and a light mic — with artwork drawn per size rather than one image scaled, plus matching tray state icons and a macOS `.icns` (which `build_mac.spec` already references and which does not exist).

**Architecture:** One generator, `tools/generate_icons.py`, draws every asset with Pillow from a single description of the artwork, and writes them into `src/assets/`. The generated files are committed — the build must not depend on regenerating art — and a test regenerates into a temp directory and compares, so the committed assets can never silently drift from the generator.

**Tech Stack:** Python 3.13, Pillow 12, pytest.

**Spec:** `docs/superpowers/specs/2026-11-10-voxel-fixes-design.md` — Part two, "App icon: dark squircle with glowing orb, size-specific artwork", and "Preserved alternative: flat indigo squircle".

## Global Constraints

- Indigo `#6366f1`, light `#818cf8`, dark `#4f46e5`. Mic glyph `#ffffff` → `#f4f4f7` at 45% → `#b9b9c4`.
- Corner radius ≈ 22% of the tile for the dark squircle (the preserved flat alternative uses 27%).
- Per-size artwork, as the spec's table sets out: 256/512 full glow with soft falloff; 32/48 tightened glow, brighter core, heavier mic stroke; 16 glow flattened to a solid indigo disc, mic only.
- The generator must be deterministic: running it twice produces byte-identical files.
- Nothing in the app may import `tools/` at runtime.

## Review Focus

1. **A `.ico` whose small frames are just the big one scaled** — the entire point of the spec's table. Pinned in Task 2.
2. **The 16px frame must still read as Voxel** at tray size: a mic silhouette, not a smudge. Pinned in Task 2.
3. **Tray state must be distinguishable at a glance** — idle, recording and processing cannot be three near-identical greys. Pinned in Task 3.
4. **A missing or unreadable icon must not stop the app**, which is why `tray_app.py` already falls back to a grey square. Pinned in Task 3.
5. **The packaging specs must list every asset they load**, or the frozen build looks fine on this machine and ships without them. Pinned in Task 4.

---

### Task 1: The artwork generator

**Files:**
- Create: `tools/generate_icons.py`
- Test: `tests/test_icons.py`

**Interfaces:**
- Produces:
  - `draw_tile(size: int, variant: str) -> Image.Image` — `variant` in `full` / `tight` / `flat`.
  - `draw_tray(size: int, state: str) -> Image.Image` — `state` in `idle` / `recording` / `processing`.
  - `ICO_SIZES: dict[int, str]` — size → variant.
  - `generate(out_dir: str) -> list[str]` — writes every asset, returns the paths.

- [ ] **Step 1: Write the failing tests** — `draw_tile` returns the requested size in RGBA; the three variants differ from one another at the same size; `draw_tile` is deterministic (two calls give identical bytes).

- [ ] **Step 2: Run them, watch them fail** (`ModuleNotFoundError: tools.generate_icons`).

- [ ] **Step 3: Implement it.** Large sizes are drawn supersampled ×4 and reduced with LANCZOS; 16px is drawn at its own scale so the glow becomes a solid disc rather than mush.

- [ ] **Step 4: Run them, watch them pass.**

- [ ] **Step 5: Commit.**

---

### Task 2: The .ico and the big PNG

**Files:**
- Modify: `tools/generate_icons.py`; regenerate `src/assets/icon.ico`, add `src/assets/icon.png` (512)
- Test: `tests/test_icons.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_the_ico_carries_every_size_windows_asks_for():      # 16,32,48,64,128,256
def test_the_small_frames_are_not_the_big_one_scaled_down():
    """The whole reason for per-size artwork: a soft glow turns to mush."""
def test_the_sixteen_px_frame_still_has_a_light_mic_on_a_dark_tile():
def test_the_committed_icon_matches_what_the_generator_produces():
    """Regenerate into a temp dir and compare bytes, so the art and the
    generator cannot drift apart."""
```

- [ ] **Steps 2-4: fail, implement, pass.** Then look at every frame rendered side by side.

- [ ] **Step 5: Commit.**

---

### Task 3: Tray state icons and the .icns

**Files:**
- Modify: `tools/generate_icons.py`; regenerate `icon_idle.png`, `icon_recording.png`, `icon_processing.png`; add `src/assets/icon.icns`
- Test: `tests/test_icons.py`

- [ ] **Step 1: Write the failing tests** — the three tray icons are 64×64 RGBA and visibly different from each other (a per-pixel difference above a threshold, not merely non-identical bytes); `icon.icns` exists and opens; `tray_app` still falls back when a file is missing.

- [ ] **Steps 2-4: fail, implement, pass.**

- [ ] **Step 5: Commit.**

---

### Task 4: Packaging knows about all of it

**Files:**
- Modify: `build.spec`, `build_mac.spec`
- Test: `tests/test_icons.py`

- [ ] **Step 1: Write the failing test** — every file `generate()` writes is named in `build.spec`, and in `build_mac.spec` (which already references `icon.icns`).

- [ ] **Steps 2-4: fail, implement, pass; then run the whole suite.**

- [ ] **Step 5: Commit.**
