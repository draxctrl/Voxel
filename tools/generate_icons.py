"""Draw Voxel's icon set.

The mark is the letter V with the level bars either side of it: the name and
what the app does, in one shape.

Detail that works at 256 pixels does not survive 16, so the artwork is drawn
*per size* rather than once and resampled:

    256 / 128   installer, About        the V with two bars either side
    32 / 48     taskbar, alt-tab        the same, with heavier strokes so
                                        nothing thins out below a pixel
    16          tray, title bar         the V alone - five separate shapes
                                        cannot be told apart across sixteen
                                        pixels, and a crisp letter beats a
                                        crowded smudge

Run it from the repository root:

    py -3.13 tools/generate_icons.py

The files it writes are committed; tests/test_icons.py regenerates them into a
temporary directory and compares, so the committed art and this script can
never quietly drift apart. Nothing in the app imports this module.
"""
from __future__ import annotations

import os
import sys

from PIL import Image, ImageDraw

# --- palette ---------------------------------------------------------------
INDIGO = (0x63, 0x66, 0xF1)
INDIGO_LIGHT = (0x81, 0x8C, 0xF8)
INDIGO_DARK = (0x4F, 0x46, 0xE5)
MARK = (0xFF, 0xFF, 0xFF)
RECORDING_RED = (0xFF, 0x45, 0x3A)

#: Corner radius as a fraction of the tile.
CORNER = 0.24

#: Which artwork each .ico frame is drawn with.
ICO_SIZES: dict[int, str] = {
    16: "flat",
    32: "tight",
    48: "tight",
    64: "tight",
    128: "full",
    256: "full",
}

#: Supersampling for the sizes drawn big and reduced. 16px is drawn at its
#: own scale instead, which is what keeps it legible.
_SS = 8


# --- drawing helpers -------------------------------------------------------

def _cap_line(draw, p0, p1, width: float, colour) -> None:
    """A line with round caps, which ImageDraw does not provide."""
    draw.line([p0, p1], fill=colour, width=max(1, int(round(width))))
    for px, py in (p0, p1):
        draw.ellipse(
            (px - width / 2, py - width / 2, px + width / 2, py + width / 2),
            fill=colour,
        )


def _bar(draw, cx: float, cy: float, height: float, width: float, colour) -> None:
    draw.rounded_rectangle(
        (cx - width / 2, cy - height / 2, cx + width / 2, cy + height / 2),
        radius=width / 2,
        fill=colour,
    )


def _squircle_mask(size: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size - 1, size - 1), radius=CORNER * size, fill=255
    )
    return mask


def _draw_vee(draw, work: int, colour, left: float, right: float,
              top: float, bottom: float, stroke: float) -> None:
    """The V itself, in percentages of the tile."""
    u = work / 100.0
    mid = (left + right) / 2
    _cap_line(draw, (left * u, top * u), (mid * u, bottom * u), stroke * u, colour)
    _cap_line(draw, (right * u, top * u), (mid * u, bottom * u), stroke * u, colour)


def draw_mark(work: int, colour, variant: str) -> Image.Image:
    """The mark on its own, transparent behind it.

    ``full`` and ``tight`` carry the bars; ``flat`` is the V alone.
    """
    layer = Image.new("RGBA", (work, work), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer, "RGBA")
    u = work / 100.0
    fill = tuple(colour) + (255,)

    if variant == "flat":
        # One shape, as heavy as it can be without closing its own mouth.
        _draw_vee(draw, work, fill, 28, 72, 24, 75, 11)
        return layer

    stroke, bar_w = (10, 8) if variant == "full" else (11.5, 9)
    _draw_vee(draw, work, fill, 36, 64, 26, 76, stroke)
    # Taller bar nearest the letter, so the V stays the tallest thing here.
    for x, height in ((25, 30), (13, 17)):
        _bar(draw, x * u, 51 * u, height * u, bar_w * u, fill)
        _bar(draw, (100 - x) * u, 51 * u, height * u, bar_w * u, fill)
    return layer


def draw_tile(size: int, variant: str) -> Image.Image:
    """One icon tile. *variant* is ``full``, ``tight`` or ``flat``."""
    if variant not in ("full", "tight", "flat"):
        raise ValueError(f"unknown variant: {variant}")

    # The flattened variant is still supersampled, just less: drawn straight
    # at 16px the V's diagonals come out as a staircase, and a jagged letter
    # is no better than the mush it replaced. Four is enough to smooth the
    # edges without softening a shape this bold.
    scale = 4 if variant == "flat" else _SS
    work = size * scale

    tile = Image.new("RGBA", (work, work), tuple(INDIGO) + (255,))
    tile = Image.alpha_composite(tile, draw_mark(work, MARK, variant))
    tile.putalpha(_squircle_mask(work))

    if scale != 1:
        tile = tile.resize((size, size), Image.Resampling.LANCZOS)
    return tile


def draw_tray(size: int, state: str) -> Image.Image:
    """A tray icon. The three states must be told apart at a glance.

    Windows scales whatever it is given down to tray size, so these carry the
    flattened mark however large they are drawn: the bars would not survive
    the trip. Colour alone is not enough on a taskbar that may be light or
    dark, so recording also carries a red dot.
    """
    scale = 4
    work = size * scale
    tile_colour = INDIGO_LIGHT if state == "processing" else INDIGO
    if state == "idle":
        tile_colour = INDIGO_DARK

    tile = Image.new("RGBA", (work, work), tuple(tile_colour) + (255,))
    tile = Image.alpha_composite(tile, draw_mark(work, MARK, "flat"))
    tile.putalpha(_squircle_mask(work))

    if state == "recording":
        draw = ImageDraw.Draw(tile)
        r = work * 0.17
        cx = cy = work * 0.76
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=RECORDING_RED + (255,))

    return tile.resize((size, size), Image.Resampling.LANCZOS)


def generate(out_dir: str) -> list[str]:
    """Write every icon asset into *out_dir*. Returns the paths written."""
    os.makedirs(out_dir, exist_ok=True)
    written: list[str] = []

    # Largest first: Pillow's ICO writer drops any requested size larger than
    # the base image, so a 16px base would silently produce a one-frame file.
    frames = [
        draw_tile(size, variant)
        for size, variant in sorted(ICO_SIZES.items(), reverse=True)
    ]
    ico_path = os.path.join(out_dir, "icon.ico")
    # Pillow rebuilds every frame from the first image when given `sizes`, so
    # the per-size artwork is passed as append_images instead.
    frames[0].save(
        ico_path,
        format="ICO",
        sizes=[(s, s) for s in sorted(ICO_SIZES, reverse=True)],
        append_images=frames[1:],
    )
    written.append(ico_path)

    big = draw_tile(512, "full")
    png_path = os.path.join(out_dir, "icon.png")
    big.save(png_path, format="PNG")
    written.append(png_path)

    icns_path = os.path.join(out_dir, "icon.icns")
    # Pillow's ICNS writer wants square power-of-two sources.
    big.save(icns_path, format="ICNS")
    written.append(icns_path)

    for state in ("idle", "recording", "processing"):
        path = os.path.join(out_dir, f"icon_{state}.png")
        draw_tray(64, state).save(path, format="PNG")
        written.append(path)

    return written


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else os.path.join("src", "assets")
    for written_path in generate(target):
        print(f"wrote {written_path}")
