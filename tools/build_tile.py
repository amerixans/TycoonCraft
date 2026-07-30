#!/usr/bin/env python3
"""Draw public/tile.gif — the front-page tile.

    pip install pillow
    python3 tools/build_tile.py

The tile is the app's whole first impression and the only thing on the front page
that is ours, so it shows the actual mechanic: two things drift together, spark,
and a third thing appears between them.

Three constraints from the microapp guide, and the reasons they matter:

* **2:1, 600x300.** The grid forces the ratio and crops anything else.
* **Under ~300 KB.** Three tiles load at once on the front page.
* **Subject in the upper two-thirds.** The bottom ~30% is covered by a dark
  gradient and the app's name.

Keeping it small comes down to three things, and skipping any one of them is the
difference between 170 KB and 3 MB:

1. **Move one region.** The background is byte-identical between frames, so GIF
   stores only the changed rectangle.
2. **One shared palette, dithering off.** Quantising each frame separately makes
   the "identical" background pixels differ slightly, which defeats the delta
   encoding completely.
3. **Loop seamlessly.** Every moving value is a function of sin/cos over the
   frame index, so the last frame flows into the first with no jump.

No fonts and no emoji: font availability differs per machine, and a tile that
renders differently on the droplet than on a laptop is not reproducible. Every
glyph here is drawn from primitives.
"""

from __future__ import annotations

import math
import os

from PIL import Image, ImageDraw, ImageFilter

W, H = 600, 300
FRAMES = 48
FRAME_MS = 60

# Kept in step with :root in public/src/style.css -- the tile is the app's first
# impression, so a tile in the old palette next to a repalletted app reads as a
# stale cache rather than as a choice.
BG_TOP = (16, 22, 31)
BG_BOT = (23, 31, 43)
GRID = (255, 255, 255, 8)
PANEL = (39, 51, 66)
PANEL_EDGE = (78, 97, 122)
ACCENT = (46, 211, 176)          # verdigris
GOLD = (255, 210, 74)
CLAY_C = (245, 128, 60)          # tier 5 orange, warm against the cool base
WATER_C = (75, 163, 245)         # tier 3 blue
TEXT = (233, 239, 246)
DIM = (147, 165, 186)

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "public", "tile.gif")

# Subject sits high: the bottom third is covered by the homepage's gradient and
# the app name, so anything drawn down there is wasted.
CY = 118


def background() -> Image.Image:
    """Built once and reused byte-for-byte. This is the whole compression trick."""
    base = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(base)
    for y in range(H):
        t = y / (H - 1)
        draw.line(
            [(0, y), (W, y)],
            fill=tuple(round(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOT)),
        )

    # Workbench grid, matching the one in the app's own bench surface.
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for x in range(0, W, 28):
        od.line([(x, 0), (x, H)], fill=GRID)
    for y in range(0, H, 28):
        od.line([(0, y), (W, y)], fill=GRID)
    base = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")

    # Kiln glow from below, echoing the app's background.
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([W * 0.15, H * 0.72, W * 0.85, H * 1.5], fill=(245, 128, 60, 44))
    glow = glow.filter(ImageFilter.GaussianBlur(34))
    base = Image.alpha_composite(base.convert("RGBA"), glow)

    # Soft vignette so the tile sits on the dark page instead of ending abruptly.
    # Kept gentle -- the first pass darkened the corners so hard that the cards
    # lost their edges.
    vig = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vig).ellipse([-150, -130, W + 150, H + 130], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(46))
    dark = Image.new("RGBA", (W, H), (8, 11, 17, 255))
    base = Image.composite(base, dark, vig)

    return base.convert("RGB")


def rounded(draw: ImageDraw.ImageDraw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def card(layer: Image.Image, cx: float, cy: float, accent, glyph: str,
         scale: float = 1.0, alpha: int = 255) -> None:
    """One item card. `glyph` picks a primitive drawing, not a font character."""
    w, h = 116 * scale, 62 * scale
    box = [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]

    card_img = Image.new("RGBA", (int(w) + 8, int(h) + 8), (0, 0, 0, 0))
    cd = ImageDraw.Draw(card_img)
    inner = [4, 4, w + 3, h + 3]
    rounded(cd, inner, int(10 * scale), (*PANEL, alpha), (*PANEL_EDGE, alpha), 2)
    # A one-pixel top highlight: cheap, and it is what makes the card read as a
    # raised object rather than a flat rectangle.
    cd.line([(4 + 9 * scale, 5), (w - 5 * scale, 5)], fill=(255, 255, 255, alpha // 6))
    # Tier stripe down the left edge -- the same colour language as the app, and
    # wide enough to survive palette quantisation at thumbnail size.
    cd.rounded_rectangle([4, 4, 4 + 8 * scale, h + 3], radius=int(3 * scale),
                         fill=(*accent, alpha))

    gx, gy = 4 + 30 * scale, 4 + h / 2
    r = 13 * scale
    if glyph == "clay":
        cd.ellipse([gx - r, gy - r, gx + r, gy + r], fill=(*CLAY_C, alpha))
        cd.ellipse([gx - r * 0.5, gy - r * 0.7, gx + r * 0.1, gy - r * 0.1],
                   fill=(190, 138, 100, alpha))
    elif glyph == "water":
        cd.ellipse([gx - r * 0.9, gy - r * 0.45, gx + r * 0.9, gy + r], fill=(*WATER_C, alpha))
        cd.polygon([(gx, gy - r * 1.35), (gx - r * 0.9, gy + r * 0.2),
                    (gx + r * 0.9, gy + r * 0.2)], fill=(*WATER_C, alpha))
        cd.ellipse([gx - r * 0.5, gy - r * 0.1, gx - r * 0.1, gy + r * 0.4],
                   fill=(178, 208, 232, alpha))
    else:  # the result: a fired brick
        cd.polygon([(gx - r, gy + r * 0.6), (gx + r * 0.55, gy + r * 0.6),
                    (gx + r, gy - r * 0.1), (gx - r * 0.55, gy - r * 0.1)],
                   fill=(*ACCENT, alpha))
        cd.polygon([(gx - r * 0.55, gy - r * 0.1), (gx + r, gy - r * 0.1),
                    (gx + r, gy - r * 0.75), (gx - r * 0.55, gy - r * 0.75)],
                   fill=(226, 138, 77, alpha))

    # Name bars: two lines of "text" as flat rectangles. Deliberately abstract --
    # it reads as a label at tile size and needs no font.
    bx = 4 + 52 * scale
    cd.rounded_rectangle([bx, gy - 11 * scale, bx + 46 * scale, gy - 3 * scale],
                         radius=int(3 * scale), fill=(*TEXT, min(alpha, 225)))
    cd.rounded_rectangle([bx, gy + 2 * scale, bx + 30 * scale, gy + 8 * scale],
                         radius=int(3 * scale), fill=(*DIM, min(alpha, 180)))

    layer.alpha_composite(card_img, (int(box[0]) - 4, int(box[1]) - 4))


def sparks(layer: Image.Image, cx: float, cy: float, progress: float) -> None:
    """Radial burst. `progress` 0..1 across the flash; fades as it expands."""
    if progress <= 0 or progress >= 1:
        return
    d = ImageDraw.Draw(layer)
    count = 26
    for i in range(count):
        angle = (2 * math.pi * i) / count + progress * 0.7
        dist = 16 + progress * 96
        x = cx + math.cos(angle) * dist
        y = cy + math.sin(angle) * dist * 0.7
        r = max(0.8, 5.0 * (1 - progress))
        a = int(255 * (1 - progress) ** 1.2)
        colour = GOLD if i % 3 else ACCENT
        d.ellipse([x - r, y - r, x + r, y + r], fill=(*colour, a))


def build() -> None:
    bg = background()
    frames: list[Image.Image] = []

    for k in range(FRAMES):
        phase = k / FRAMES                      # 0..1, wraps
        # Cards drift in and back out. cos gives a smooth there-and-back that is
        # periodic by construction, so the loop cannot jump.
        closeness = (1 - math.cos(2 * math.pi * phase)) / 2      # 0 -> 1 -> 0
        # Minimum spread of 62 leaves the two 116px-wide cards just short of
        # touching. Letting them overlap, plus a third card on top, turned the
        # key frame into an unreadable blob.
        spread = 172 - 110 * closeness
        bob = math.sin(2 * math.pi * phase * 2) * 3

        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))

        # The result exists only at the closest approach, and the two sources
        # fade out *completely* as it lands -- never three cards at once.
        result_alpha = max(0.0, (closeness - 0.80) / 0.20)
        card_alpha = int(255 * (1 - result_alpha))

        if card_alpha > 4:
            card(layer, W / 2 - spread, CY + bob, CLAY_C, "clay", 1.0, card_alpha)
            card(layer, W / 2 + spread, CY - bob, WATER_C, "water", 1.0, card_alpha)

        if result_alpha > 0:
            # Sparks lead the card in: brightest at the handover, gone once the
            # result has settled.
            sparks(layer, W / 2, CY, 1 - result_alpha)
            pop = 0.74 + 0.26 * result_alpha     # scales up as it lands
            card(layer, W / 2, CY, ACCENT, "brick", pop, int(255 * result_alpha))

        frames.append(Image.alpha_composite(bg.convert("RGBA"), layer).convert("RGB"))

    # One palette for every frame. Quantising per-frame would perturb the
    # supposedly-identical background pixels and destroy the delta encoding.
    #
    # The palette has to be derived from *all* frames, not one of them. Taking it
    # from the middle frame -- where the water card has faded out to make room for
    # the result -- left blue out of the palette entirely, so the water card came
    # out the same tan as the clay one.
    montage = Image.new("RGB", (W, H * 4))
    for slot, index in enumerate((0, FRAMES // 4, FRAMES // 2, 3 * FRAMES // 4)):
        montage.paste(frames[index], (0, H * slot))
    master = montage.quantize(colors=160, method=Image.MEDIANCUT)

    paletted = [f.quantize(palette=master, dither=Image.Dither.NONE) for f in frames]

    paletted[0].save(
        OUT,
        save_all=True,
        append_images=paletted[1:],
        duration=FRAME_MS,
        loop=0,
        optimize=True,
        disposal=1,
    )

    size = os.path.getsize(OUT)
    print(f"wrote {OUT}")
    print(f"  {W}x{H}, {FRAMES} frames, {size / 1024:.0f} KB")
    if size > 300 * 1024:
        raise SystemExit(
            f"tile is {size / 1024:.0f} KB, over the ~300 KB budget — "
            f"reduce FRAMES or the palette size"
        )


if __name__ == "__main__":
    build()
