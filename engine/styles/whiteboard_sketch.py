"""
whiteboard_sketch.py — background-clip builder for the 'whiteboard_sketch'
render style.

Instead of Pexels stock footage, each scene draws 1-3 icons (chosen by
script_generator.py from icon_library.ICONS) onto a paper-textured
background, with a deterministic hand-drawn jitter and a progressive
"being drawn" reveal synced to the scene's on-screen time. No external
image/video assets — everything here is generated at render time from
plain coordinate data, so there's nothing to license or fetch.

Public entry point matches the stock_footage style's shape:
    build_background_clip(scene, duration, video_w, video_h) -> moviepy clip
so video_compositor.py can dispatch to either style interchangeably.
"""
import random
import numpy as np
from PIL import Image, ImageDraw
from moviepy.editor import VideoClip

from .icon_library import get_icon_strokes

PAPER_BG = (250, 248, 240)   # warm off-white "paper"
DOT_COLOR = (225, 222, 208)  # faint grid dots
INK = (32, 32, 38)           # "marker" color


def _paper_texture(w, h, seed=0):
    """Deterministic light dot-grid texture — cheap to build once per scene
    and reused as the base for every frame (only the icons animate)."""
    img = Image.new("RGB", (w, h), PAPER_BG)
    draw = ImageDraw.Draw(img)
    rnd = random.Random(seed)
    step = 46
    for y in range(0, h, step):
        for x in range(0, w, step):
            jx, jy = rnd.randint(-3, 3), rnd.randint(-3, 3)
            draw.ellipse([x + jx - 1, y + jy - 1, x + jx + 1, y + jy + 1], fill=DOT_COLOR)
    return img


def _jitter_stroke(pts, seed, amount=1.6):
    """Small deterministic per-point jitter. Same seed -> same wobble on
    every frame, so the line looks hand-drawn but doesn't shimmer/vibrate."""
    rnd = random.Random(seed)
    return [(x + rnd.uniform(-amount, amount), y + rnd.uniform(-amount, amount)) for (x, y) in pts]


def _stroke_length(pts):
    return sum(
        ((pts[i + 1][0] - pts[i][0]) ** 2 + (pts[i + 1][1] - pts[i][1]) ** 2) ** 0.5
        for i in range(len(pts) - 1)
    )


def _partial_stroke(pts, progress):
    """Subset of pts drawn up to `progress` (0..1) along arc length, with the
    final segment interpolated so the reveal is smooth, not stair-stepped."""
    if progress >= 1:
        return pts
    if progress <= 0 or len(pts) < 2:
        return pts[:1] if progress > 0 else []
    target = _stroke_length(pts) * progress
    out = [pts[0]]
    acc = 0.0
    for i in range(len(pts) - 1):
        seg = ((pts[i + 1][0] - pts[i][0]) ** 2 + (pts[i + 1][1] - pts[i][1]) ** 2) ** 0.5
        if acc + seg >= target:
            t = (target - acc) / seg if seg > 1e-6 else 0
            out.append((pts[i][0] + (pts[i + 1][0] - pts[i][0]) * t,
                        pts[i][1] + (pts[i + 1][1] - pts[i][1]) * t))
            return out
        acc += seg
        out.append(pts[i + 1])
    return out


def _draw_icon(draw, name, cx, cy, size, progress, seed):
    """Draws one icon centered at (cx, cy) inside a `size`x`size` box, with
    strokes revealed in sequence (not all at once) as `progress` climbs 0->1."""
    strokes = get_icon_strokes(name)
    n = len(strokes) or 1
    for i, stroke in enumerate(strokes):
        stroke_progress = min(max((progress * n) - i, 0.0), 1.0)
        if stroke_progress <= 0:
            continue
        scaled = [(cx + (p[0] - 50) / 100 * size, cy + (p[1] - 50) / 100 * size) for p in stroke]
        jittered = _jitter_stroke(scaled, seed=seed * 97 + i)
        partial = _partial_stroke(jittered, stroke_progress)
        if len(partial) == 1:
            r = max(size * 0.012, 2)
            x, y = partial[0]
            draw.ellipse([x - r, y - r, x + r, y + r], fill=INK)
        elif len(partial) >= 2:
            width = max(int(size * 0.018), 3)
            draw.line(partial, fill=INK, width=width, joint="curve")


_LAYOUTS = {
    1: [(0.50, 0.42)],
    2: [(0.30, 0.42), (0.70, 0.42)],
    3: [(0.50, 0.26), (0.28, 0.50), (0.72, 0.50)],
}


def build_background_clip(scene: dict, duration: float, video_w: int, video_h: int):
    """
    scene["icons"]: list[str] of icon names chosen by script_generator.py from
    icon_library.available_icon_names(). Unknown/missing names fall back to a
    plain circle (see icon_library.get_icon_strokes) rather than crashing.
    """
    icons = [i for i in (scene.get("icons") or []) if i] or ["lightbulb"]
    icons = icons[:3]

    seed_source = scene.get("voice_text", "") + "|" + "|".join(icons)
    base_seed = abs(hash(seed_source)) % 100000
    box = min(video_w, video_h) * 0.30
    positions = _LAYOUTS[len(icons)]
    base = _paper_texture(video_w, video_h, seed=base_seed)

    def make_frame(t):
        img = base.copy()
        draw = ImageDraw.Draw(img)
        reveal_window = max(duration * 0.55, 0.4)  # draw-on finishes at ~55% of scene, then holds
        progress = min(t / reveal_window, 1.0)
        for icon_name, (px, py) in zip(icons, positions):
            cx, cy = video_w * px, video_h * py
            icon_seed = (abs(hash(icon_name)) % 10000) + int(cx)
            _draw_icon(draw, icon_name, cx, cy, box, progress, seed=icon_seed)
        return np.array(img)

    return VideoClip(make_frame, duration=duration)
