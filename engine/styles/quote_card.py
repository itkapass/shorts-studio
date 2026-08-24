"""
quote_card.py — background-clip builder for the 'quote_card' render style.

The minimal option: a slow-drifting gradient with thin corner accents, no
stock footage and no icons, so the big word-by-word captions do all the
talking. Mirrors the black-background quote-card look from the sibling
Instagram project, brought into motion for video.

Public entry point matches the other styles' shape:
    build_background_clip(scene, duration, video_w, video_h) -> moviepy clip
"""
import numpy as np
from PIL import Image, ImageDraw
from moviepy.editor import VideoClip

MOODS = {
    "dark":     [(10, 10, 18), (28, 22, 46)],
    "dramatic": [(18, 4, 28), (6, 30, 58)],
    "bright":   [(24, 34, 64), (12, 56, 88)],
    "neutral":  [(12, 14, 22), (30, 32, 56)],
}


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


def build_background_clip(scene: dict, duration: float, video_w: int, video_h: int):
    mood = scene.get("visual_mood", "dark")
    top, bot = MOODS.get(mood, MOODS["dark"])

    def make_frame(t):
        drift = 0.08 * np.sin(2 * np.pi * (t / max(duration, 1.0)) * 0.5)
        img = _gradient_frame(video_w, video_h, top, bot, drift)
        draw = ImageDraw.Draw(img)
        margin, ln = 70, 46
        for cx, cy, dx, dy in (
            (margin, margin, 1, 1), (video_w - margin, margin, -1, 1),
            (margin, video_h - margin, 1, -1), (video_w - margin, video_h - margin, -1, -1),
        ):
            draw.line([(cx, cy), (cx + ln * dx, cy)], fill=(255, 255, 255), width=2)
            draw.line([(cx, cy), (cx, cy + ln * dy)], fill=(255, 255, 255), width=2)
        return np.array(img)

    return VideoClip(make_frame, duration=duration)
