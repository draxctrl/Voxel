"""The app icon, its per-size artwork, and the tray state icons."""
import os

import pytest
from PIL import Image

ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "src", "assets")


def _bytes(img) -> bytes:
    return img.convert("RGBA").tobytes()


def _difference(a, b) -> float:
    """Mean per-channel difference between two same-sized images, 0..255."""
    a = a.convert("RGBA")
    b = b.convert("RGBA").resize(a.size, Image.Resampling.LANCZOS)
    pa, pb = a.tobytes(), b.tobytes()
    return sum(abs(x - y) for x, y in zip(pa, pb)) / len(pa)


class TestTileArtwork:
    def test_a_tile_comes_back_at_the_size_asked_for(self):
        from tools.generate_icons import draw_tile
        for size in (16, 48, 256):
            img = draw_tile(size, "full" if size > 48 else "tight")
            assert img.size == (size, size)
            assert img.mode == "RGBA"

    def test_the_flattened_variant_drops_the_bars(self):
        """The whole point of per-size artwork: five separate shapes cannot
        be told apart across sixteen pixels, so the small frame is the V
        alone. full and tight are the same drawing with heavier strokes,
        which is all 32px needs once there is no glow to turn to mush."""
        from tools.generate_icons import draw_tile
        full = draw_tile(64, "full")
        tight = draw_tile(64, "tight")
        flat = draw_tile(64, "flat")
        assert _difference(full, flat) > 6, "the flat variant still has bars"
        assert _difference(tight, flat) > 6, "the flat variant still has bars"
        assert _difference(full, tight) > 0.5, "tight is not drawn any heavier"

    def test_the_small_frame_keeps_one_bar_and_drops_the_other(self):
        """The outer bar survives so the tray still reads as the same logo;
        the inner one goes, because at 16px it cannot be told from the V.
        Measured in the two bands where each bar sits."""
        from tools.generate_icons import draw_tile

        def ink(variant: str, x0: int, x1: int) -> int:
            img = draw_tile(128, variant).convert("RGBA")
            return sum(
                1
                for y in range(48, 80)
                for x in range(x0, x1)
                if img.getpixel((x, y))[0] > 200
            )

        outer, inner = (6, 20), (26, 40)
        assert ink("full", *outer) > 15, "the full mark lost its outer bar"
        assert ink("full", *inner) > 15, "the full mark lost its inner bar"
        assert ink("flat", *outer) > 15, "the small frame lost its bars entirely"
        assert ink("flat", *inner) == 0, "the small frame kept the inner bar"

    def test_drawing_is_deterministic(self):
        """The committed art is checked against the generator, so the
        generator may not wander between runs."""
        from tools.generate_icons import draw_tile
        assert _bytes(draw_tile(64, "full")) == _bytes(draw_tile(64, "full"))


class TestTheIcoFile:
    def _frames(self):
        path = os.path.join(ASSETS, "icon.ico")
        img = Image.open(path)
        frames = {}
        for size in sorted(img.info["sizes"]):
            img.size = size
            img.load()
            frames[size[0]] = img.copy()
        return frames

    def test_it_carries_every_size_windows_asks_for(self):
        assert set(self._frames()) >= {16, 32, 48, 256}

    def test_the_sixteen_px_frame_is_not_the_big_one_scaled_down(self):
        """The reason for per-size artwork. 32px keeps the bars - without a
        glow the mark survives the reduction - but 16px is drawn as the V
        alone, so it must not look like a shrunken 256."""
        frames = self._frames()
        assert _difference(frames[16], frames[256]) > 6, (
            "the 16px frame looks like a scaled copy of the 256px one"
        )

    def test_the_sixteen_px_frame_is_a_light_mark_on_a_coloured_tile(self):
        """At tray size it still has to read as Voxel, which needs the mark
        and the tile to be far apart in brightness - whatever the tile's
        colour. Measured, rather than assumed from the palette."""
        frame = self._frames()[16].convert("RGBA")
        tile = frame.getpixel((8, 2))          # above the V, inside the tile
        column = [frame.getpixel((8, y)) for y in range(4, 14)]
        brightest = max(sum(p[:3]) / 3 for p in column)
        tile_brightness = sum(tile[:3]) / 3
        assert brightest > 200, "there is no light mark in the middle"
        assert brightest - tile_brightness > 60, (
            "the mark is too close in brightness to the tile behind it"
        )

    def test_the_committed_icon_matches_what_the_generator_produces(self, tmp_path):
        """Art and generator cannot drift apart without this failing."""
        from tools.generate_icons import generate
        generate(str(tmp_path))
        with open(os.path.join(ASSETS, "icon.ico"), "rb") as f:
            committed = f.read()
        with open(os.path.join(str(tmp_path), "icon.ico"), "rb") as f:
            fresh = f.read()
        assert committed == fresh, "src/assets/icon.ico is out of date — rerun tools/generate_icons.py"


class TestTrayIcons:
    @pytest.mark.parametrize("state", ["idle", "recording", "processing"])
    def test_each_state_has_an_icon(self, state):
        img = Image.open(os.path.join(ASSETS, f"icon_{state}.png"))
        assert img.size == (64, 64)
        assert img.mode == "RGBA"

    def test_the_states_are_told_apart_at_a_glance(self):
        """Three near-identical greys in the tray tell the user nothing."""
        imgs = {
            state: Image.open(os.path.join(ASSETS, f"icon_{state}.png"))
            for state in ("idle", "recording", "processing")
        }
        pairs = [("idle", "recording"), ("idle", "processing"), ("recording", "processing")]
        for a, b in pairs:
            assert _difference(imgs[a], imgs[b]) > 5, f"{a} and {b} look the same"

    def test_a_missing_icon_file_does_not_stop_the_tray(self):
        from unittest.mock import MagicMock, patch
        from src.tray_app import TrayApp
        with patch("src.tray_app.Image.open", side_effect=OSError("gone")):
            tray = TrayApp.__new__(TrayApp)
            tray._assets_dir = ASSETS
            tray._icons = {}
            TrayApp._load_icons(tray)
        assert set(tray._icons) >= {"idle", "recording", "processing"}


class TestMacIcon:
    def test_the_icns_the_mac_build_references_exists(self):
        """build_mac.spec names src/assets/icon.icns; it was never created."""
        path = os.path.join(ASSETS, "icon.icns")
        assert os.path.isfile(path)
        assert Image.open(path).size[0] >= 128


class TestPackagingShipsEverything:
    def _spec(self, name):
        root = os.path.dirname(ASSETS.rstrip(os.sep))
        with open(os.path.join(os.path.dirname(root), name), encoding="utf-8") as f:
            return f.read()

    @pytest.mark.parametrize("spec_name", ["build.spec", "build_mac.spec"])
    def test_every_generated_asset_is_bundled(self, spec_name, tmp_path):
        from tools.generate_icons import generate
        spec = self._spec(spec_name)
        for path in generate(str(tmp_path)):
            name = os.path.basename(path)
            if name == "icon.icns" and spec_name == "build.spec":
                continue  # macOS-only artwork
            assert name in spec, f"{name} is not bundled by {spec_name}"
