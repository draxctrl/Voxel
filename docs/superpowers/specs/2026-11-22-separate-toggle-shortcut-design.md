# Separate shortcuts for push-to-talk and press-to-start

## Why

Isuru wants both ways of dictating available at once, each on its own key,
instead of choosing one mode in settings and switching back and forth.

Today Voxel stores a single key and "How it activates" only changes what
that key does. Set K under hold-to-talk, switch to press-to-start, and K is
now the only key - push-to-talk is gone. And with Ctrl + Alt as the key,
switching to press-to-start was refused with an error (fixed separately by
the clean-tap change).

## What changes

- **Shortcuts pane:** two shortcut rows, each with its own Change button:
  - *Push to talk* - hold these keys and speak (existing `hotkey`).
  - *Press to start, press to stop* - tap once to begin, tap again when done
    (new `toggle_hotkey`).
  The "How it activates" choice is removed: both are always on.
- **Either can be turned off** (a "Turn off" button next to Change; the row
  then reads "Not set"). Turning off the last one that is set is refused,
  so dictation can never end up with no key.
- **The same key for both is refused** with the orange warning, and the
  previous key is kept.
- **New key starts off.** `toggle_hotkey` defaults to empty ("Not set"), so
  nobody's existing setup changes until they choose a key.
- **Upgrade:** someone who had "Press to start, press to stop" selected has
  their key moved to the new row and push-to-talk turned off - the key keeps
  behaving as it did. `activation_mode` is then dropped.
- **Pressing either key while a recording is running stops it and types the
  text**, whichever key started it.
- **Keys that share modifiers coexist.** Ctrl + Alt as push-to-talk and
  Ctrl + Alt + Space as press-to-start must both work: if another key is
  pressed while a modifier-only push-to-talk combo is held, that recording is
  cancelled silently (this also stops Ctrl + Alt + Del starting a dictation).
  A modifier-only press-to-start key fires on a clean tap (already built).
- Splash and sidebar status show the push-to-talk key, or the press-to-start
  key when push-to-talk is off.

## Approaches

1. **Two listeners, one per key (chosen).** The existing `HotkeyListener`
   already does both behaviours and is tested; the app runs one in hold mode
   and one in toggle mode. Least new code.
2. One listener that watches both keys. A rewrite of tested code for no
   visible gain.

## Not in scope

More than two shortcuts; per-app shortcuts; changing the first-run screens
beyond naming the right key.
