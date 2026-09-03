"""
quote_card.py — background-clip builder for the 'quote_card' render style.

Two looks live here now:
  "dark" family   — the original slow-drifting gradient, thin corner accents.
  "elite" (default) — a warm paper backdrop with a soft diagonal light beam
                       and procedural leaf-shadow silhouettes, plus a thin
                       divider-and-dot mark at a fixed height.

WHY "elite" EXISTS
Built directly off a reference account (quotes in Tamil, minimal aesthetic:
cream paper, plant-shadow, thin divider, small serif meaning-line) that pulled
enormous engagement — one post at 1.3M views from a small account. The old
"dark" look was flagged elsewhere in this project as the boring, flat option;
this is the fix, and it's fully procedural — no photo, no texture file, so
there's nothing to license and nothing that can go missing.

The divider-and-dot graphic is baked into the BACKGROUND at a fixed height
rather than drawn by the caption system, because the caption system draws
per-word timed cards wherever position_y_ratio says to — it has no idea a
divider is supposed to sit above it. Baking it into the background is the
simple way to get the "headline / divider / meaning" structure from the
reference without a deeper rework of how every style shares one caption
pipeline.

Public entry point matches the other styles' shape:
    build_background_clip(scene, duration, video_w, video_h) -> moviepy clip
"""
import math
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from moviepy.editor import VideoClip

MOODS = {
    "dark":     [(10, 10, 18), (28, 22, 46)],
    "dramatic": [(18, 4, 28), (6, 30, 58)],
    "bright":   [(24, 34, 64), (12, 56, 88)],
    "neutral":  [(12, 14, 22), (30, 32, 56)],
    # Warm paper tones for the "elite" look — sampled close to the reference.
    "elite":    [(240, 231, 214), (214, 197, 168)],
}

# Where the divider mark sits, as a fraction of frame height. Captions render
# at position_y_ratio (0.62 by default) — keeping the divider well above that,
# with a comfortable gap, is what lets both read as one deliberate layout
# instead of overlapping by accident.
DIVIDER_Y_RATIO = 0.46


def _gradient_frame(w, h, top, bot, drift):
    img = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = min(max(y / h + drift, 0.0), 1.0)
        r = int(top[0] + (bot[0] - top[0]) * t)
        g = int(top[1] + (bot[1] - top[1]) * t)
        b = int(top[2] + (bot[2] - top[2]) * t)
        draw.line([(0, y), (w, y)], fill=(r, g, b))
    return img


def _leaf(draw, cx, cy, length, angle_deg, width_ratio=0.34, fill=(0, 0, 0, 34)):
    """One procedural leaf silhouette: two mirrored arcs meeting at a point
    at each end, rotated to `angle_deg`. Cheap to draw, reads instantly as
    foliage at the soft opacity used here — nobody examines a background
    shadow closely enough to need more than a plausible silhouette."""
    n = 20
    pts = []
    for i in range(n + 1):
        t = i / n
        x = (t - 0.5) * length
        y = -math.sin(t * math.pi) * (length * width_ratio / 2)
        pts.append((x, y))
    for i in range(n, -1, -1):
        t = i / n
        x = (t - 0.5) * length
        y = math.sin(t * math.pi) * (length * width_ratio / 2)
        pts.append((x, y))

    a = math.radians(angle_deg)
    ca, sa = math.cos(a), math.sin(a)
    rotated = [(cx + x * ca - y * sa, cy + x * sa + y * ca) for x, y in pts]
    draw.polygon(rotated, fill=fill)
    # A simple centre vein sells the leaf read at a glance.
    mid0 = (cx - (length / 2) * ca, cy - (length / 2) * sa)
    mid1 = (cx + (length / 2) * ca, cy + (length / 2) * sa)
    draw.line([mid0, mid1], fill=(fill[0], fill[1], fill[2], min(255, fill[3] + 20)), width=2)


def _elite_paper_frame(w, h, top, bot, drift, seed):
    """Warm gradient + a soft diagonal light beam + a scattered plant-shadow
    cluster in one corner. `seed` keeps the leaf layout identical across every
    frame of one video (regenerating it per frame would make the shadows
    crawl, which reads as a bug, not ambience)."""
    base = _gradient_frame(w, h, top, bot, drift).convert("RGBA")

    # Soft diagonal light: a wide, heavily blurred white band, screened on
    # top. Cheap and reads as window light without any real light simulation.
    light = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ld = ImageDraw.Draw(light)
    band_w = int(w * 0.55)
    ld.polygon(
        [(-band_w, 0), (0, 0), (int(w * 0.55), h), (int(w * 0.55) - band_w, h)],
        fill=(255, 250, 240, 46),
    )
    light = light.filter(ImageFilter.GaussianBlur(60))
    base.alpha_composite(light)

    # Leaf-shadow cluster, top-left and bottom-right corners like the
    # reference. Positions are seeded so they stay put across the whole clip.
    rnd = random.Random(seed)
    shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    for corner_x, corner_y in ((w * 0.12, h * 0.10), (w * 0.88, h * 0.90)):
        for _ in range(5):
            ox = corner_x + rnd.uniform(-w * 0.05, w * 0.05)
            oy = corner_y + rnd.uniform(-h * 0.03, h * 0.03)
            length = rnd.uniform(w * 0.14, w * 0.24)
            angle = rnd.uniform(0, 360)
            _leaf(sd, ox, oy, length, angle, fill=(60, 52, 38, 30))
    shadow = shadow.filter(ImageFilter.GaussianBlur(3))
    base.alpha_composite(shadow)

    return base.convert("RGB")


def _draw_divider(img_rgb, w, h):
    """Thin horizontal rule with a centred dot, at DIVIDER_Y_RATIO. Matches
    the reference's line-and-dot mark that separates headline from meaning."""
    draw = ImageDraw.Draw(img_rgb)
    y = int(h * DIVIDER_Y_RATIO)
    half = int(w * 0.09)
    ink = (60, 52, 40)
    draw.line([(w // 2 - half, y), (w // 2 + half, y)], fill=ink, width=2)
    r = 3
    draw.ellipse([w // 2 - r, y - r, w // 2 + r, y + r], fill=ink)
    return img_rgb


def build_background_clip(scene: dict, duration: float, video_w: int, video_h: int):
    mood = scene.get("visual_mood", "elite")
    top, bot = MOODS.get(mood, MOODS["elite"])
    seed = scene.get("scene_number", 1) * 97 + 13

    if mood == "elite":
        # Drawn once — this background barely needs to move, and redrawing a
        # blurred composite every frame is the expensive part of this style.
        # A held frame with only a faint gradient drift reads as calm and
        # deliberate, which suits the aesthetic far better than motion would.
        still = _elite_paper_frame(video_w, video_h, top, bot, 0.0, seed)
        still = _draw_divider(still, video_w, video_h)
        still_arr = np.array(still)

        def make_frame(t):
            return still_arr

        return VideoClip(make_frame, duration=duration)

    def make_frame(t):
        drift = (t / max(duration, 0.001)) * 0.15
        img = _gradient_frame(video_w, video_h, top, bot, drift)
        return np.array(img)

    return VideoClip(make_frame, duration=duration)
