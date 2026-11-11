"""Draw Voxel's icon set.

The icon is the recording orb: a dark squircle, an indigo glow, a light mic.
The app's icon and its recording animation are deliberately the same object.

A soft glow turns to mush when it is scaled down, so the artwork is drawn
*per size* rather than once and resampled:

    256 / 512   installer, About        full glow with soft falloff
    32 / 48     taskbar, alt-tab        tightened glow, brighter core,
                                        heavier mic stroke
    16          tray, title bar         glow flattened to a solid indigo disc

Run it from the repository root:

    py -3.13 tools/generate_icons.py

The files it writes are committed; tests/test_icons.py regenerates them into a
temporary directory and compares, so the committed art and this script can
never quietly drift apart. Nothing in the app imports this module.
"""
from __future__ import annotations

import os
import sys

from PIL import Image, ImageDraw, ImageFilter

# --- palette ---------------------------------------------------------------
INDIGO = (0x63, 0x66, 0xF1)
INDIGO_LIGHT = (0x81, 0x8C, 0xF8)
INDIGO_DARK = (0x4F, 0x46, 0xE5)
TILE_TOP = (0x23, 0x23, 0x30)
TILE_BOTTOM = (0x0B, 0x0B, 0x12)
MIC_TOP = (0xFF, 0xFF, 0xFF)
MIC_MID = (0xF4, 0xF4, 0xF7)
MIC_BOTTOM = (0xB9, 0xB9, 0xC4)

#: Corner radius as a fraction of the tile. The preserved flat-indigo
#: alternative in the spec uses 0.27; the dark squircle sits a little tighter.
CORNER = 0.22

#: Which artwork each .ico frame is drawn with.
ICO_SIZES: dict[int, str] = {
    16: "flat",
    32: "tight",
    48: "tight",
    64: "tight",
    128: "full",
    256: "full",
}

#: Supersampling factor for the sizes that are drawn big and reduced. 16px is
#: drawn at its own scale instead, which is what keeps it legible.
_SS = 4


def _lerp(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def _vertical_gradient(size: int, stops: list[tuple[float, tuple[int, int, int]]]) -> Image.Image:
    """A top-to-bottom gradient image, *stops* given as (position, colour)."""
    grad = Image.new("RGB", (1, size))
    pixels = grad.load()
    for y in range(size):
        t = y / max(1, size - 1)
        lower = stops[0]
        upper = stops[-1]
        for i in range(len(stops) - 1):
            if stops[i][0] <= t <= stops[i + 1][0]:
                lower, upper = stops[i], stops[i + 1]
                break
        span = max(1e-6, upper[0] - lower[0])
        pixels[0, y] = _lerp(lower[1], upper[1], (t - lower[0]) / span)
    return grad.resize((size, size))


def _squircle_mask(size: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size - 1, size - 1), radius=int(size * CORNER), fill=255
    )
    return mask


def _glow(size: int, radius_frac: float, peak_alpha: int, softness: float) -> Image.Image:
    """A radial indigo glow on a transparent tile."""
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(glow)
    cx = cy = size / 2
    max_r = size * radius_frac
    steps = max(8, int(max_r))
    for i in range(steps, 0, -1):
        t = i / steps
        alpha = int(peak_alpha * ((1 - t) ** softness))
        if alpha <= 0:
            continue
        colour = _lerp(INDIGO_DARK, INDIGO_LIGHT, (1 - t) ** 0.7)
        r = max_r * t
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=colour + (alpha,))
    return glow


def _mic_mask(size: int, stroke_scale: float = 1.0, simplified: bool = False) -> Image.Image:
    """A microphone silhouette, white on black, sized for *size* pixels.

    *simplified* drops the cradle arc, which is thinner than one pixel at tray
    size and only turns the glyph to mush.
    """
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    cx = size / 2
    unit = size / 100.0

    body_w = 20 * unit * stroke_scale
    body_h = 34 * unit
    body_top = 24 * unit
    if simplified:
        body_w = 30 * unit
        body_h = 56 * unit
        body_top = 22 * unit
    draw.rounded_rectangle(
        (cx - body_w / 2, body_top, cx + body_w / 2, body_top + body_h),
        radius=body_w / 2,
        fill=255,
    )

    if simplified:
        # At 16px the cradle and stem are thinner than a pixel and merge into a
        # blob. The capsule alone still reads as a microphone.
        return mask

    # Cradle: an arc under the body.
    arc_r = 18 * unit
    arc_w = max(1, int(round(5 * unit * stroke_scale)))
    arc_cy = body_top + body_h - 6 * unit
    draw.arc(
        (cx - arc_r, arc_cy - arc_r, cx + arc_r, arc_cy + arc_r),
        start=20,
        end=160,
        fill=255,
        width=arc_w,
    )

    # Stem.
    stem_w = max(1, int(round(5 * unit * stroke_scale)))
    stem_top = arc_cy + arc_r - arc_w / 2
    draw.rounded_rectangle(
        (cx - stem_w / 2, stem_top, cx + stem_w / 2, stem_top + 9 * unit),
        radius=stem_w / 2,
        fill=255,
    )
    return mask


def _mic_layer(size: int, stroke_scale: float = 1.0, simplified: bool = False) -> Image.Image:
    """The mic glyph, filled with the white-to-grey gradient."""
    gradient = _vertical_gradient(
        size, [(0.0, MIC_TOP), (0.45, MIC_MID), (1.0, MIC_BOTTOM)]
    ).convert("RGBA")
    gradient.putalpha(_mic_mask(size, stroke_scale, simplified))
    return gradient


def draw_tile(size: int, variant: str) -> Image.Image:
    """One icon tile. *variant* is ``full``, ``tight`` or ``flat``."""
    if variant not in ("full", "tight", "flat"):
        raise ValueError(f"unknown variant: {variant}")

    # The flattened variant is drawn at its final size: supersampling a tiny
    # icon just blurs the detail it exists to preserve.
    scale = 1 if variant == "flat" else _SS
    work = size * scale

    tile = _vertical_gradient(work, [(0.0, TILE_TOP), (1.0, TILE_BOTTOM)]).convert("RGBA")

    if variant == "full":
        glow = _glow(work, 0.52, 255, softness=1.15)
        glow = glow.filter(ImageFilter.GaussianBlur(work * 0.045))
        mic_scale, mic_box = 1.0, 0.54
    elif variant == "tight":
        # Tighter and harder: at 32-48px a soft falloff is just grey mush.
        glow = _glow(work, 0.38, 255, softness=0.55)
        glow = glow.filter(ImageFilter.GaussianBlur(work * 0.012))
        mic_scale, mic_box = 1.3, 0.56
    else:
        # Flattened: a solid indigo disc, and the mic carries the meaning.
        glow = Image.new("RGBA", (work, work), (0, 0, 0, 0))
        r = work * 0.42
        ImageDraw.Draw(glow).ellipse(
            (work / 2 - r, work / 2 - r, work / 2 + r, work / 2 + r),
            fill=INDIGO + (255,),
        )
        mic_scale, mic_box = 1.0, 0.66

    tile = Image.alpha_composite(tile, glow)

    mic_size = max(8, int(work * mic_box))
    mic = _mic_layer(mic_size, mic_scale, simplified=(variant == "flat"))
    offset = (work - mic_size) // 2
    tile.paste(mic, (offset, offset), mic)

    tile.putalpha(_squircle_mask(work))
    if scale != 1:
        tile = tile.resize((size, size), Image.Resampling.LANCZOS)
    return tile


def draw_tray(size: int, state: str) -> Image.Image:
    """A tray icon. The three states must be told apart at a glance.

    Colour alone is not enough at 16px on a taskbar that may be light or dark,
    so recording also carries a red dot — the same signal the Dynamic Island
    display uses — and processing is drawn as a ring rather than a filled disc.
    """
    scale = 4
    work = size * scale
    img = Image.new("RGBA", (work, work), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    r = work * 0.46
    box = (work / 2 - r, work / 2 - r, work / 2 + r, work / 2 + r)

    if state == "recording":
        draw.ellipse(box, fill=INDIGO + (235,))
    elif state == "processing":
        # A ring, not a disc: "working on it" rather than "listening".
        draw.ellipse(box, fill=INDIGO_LIGHT + (235,))
        inner = work * 0.33
        draw.ellipse(
            (work / 2 - inner, work / 2 - inner, work / 2 + inner, work / 2 + inner),
            fill=(0, 0, 0, 0),
        )
    else:
        draw.ellipse(box, fill=(0x55, 0x55, 0x66, 150))

    mic_size = int(work * 0.54)
    mic = _mic_layer(mic_size, 1.2)
    offset = (work - mic_size) // 2
    img.paste(mic, (offset, offset), mic)

    if state == "recording":
        dot_r = work * 0.15
        cx = work * 0.78
        cy = work * 0.78
        draw = ImageDraw.Draw(img)
        draw.ellipse(
            (cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r),
            fill=(0xFF, 0x45, 0x3A, 255),
        )

    return img.resize((size, size), Image.Resampling.LANCZOS)


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
