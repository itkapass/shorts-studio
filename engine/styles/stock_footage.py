"""
stock_footage.py — background-clip builder for the 'stock_footage' render
style (the original plan for this project). Pexels b-roll cropped to 9:16
with a Ken Burns zoom, or an animated gradient fallback when no clip was
found / provided.

NOTE ON A FIXED BUG: the previous version of this cropping step called
moviepy.video.fx.resize.resize(), which internally does
    Image.fromarray(pic).resize(newsize, Image.ANTIALIAS)
Pillow >= 10.0 removed Image.ANTIALIAS entirely, so with this project's own
pinned moviepy==1.0.3 + an unpinned Pillow, that call raised:
    AttributeError: module 'PIL.Image' has no attribute 'ANTIALIAS'
on literally every scene with real footage. Confirmed by reproducing it in
a clean venv. Fixed two ways: requirements.txt now pins Pillow<10, AND (belt
and suspenders, in case something transitively re-upgrades Pillow later)
this module resizes frames itself with Image.LANCZOS — the same safe
resampling filter _apply_ken_burns already used correctly — instead of
calling moviepy's resize fx at all.
"""
import os
import numpy as np
from PIL import Image, ImageDraw
from moviepy.editor import VideoFileClip, ImageClip

# Belt-and-suspenders shim: ANTIALIAS was just the old name for LANCZOS.
# If anything else in the dependency tree still references it, this keeps
# it from crashing instead of silently masking a real incompatibility.
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.LANCZOS


def build_background_clip(scene: dict, duration: float, video_w: int, video_h: int):
    clip_path = scene.get("clip_path")

    if clip_path and os.path.exists(clip_path):
        try:
            clip = VideoFileClip(clip_path, audio=False)

            if clip.duration < duration:
                from moviepy.video.fx.loop import loop
                clip = loop(clip, duration=duration + 0.1)

            clip = clip.subclip(0, duration)
            clip = _crop_to_portrait(clip, video_w, video_h)
            clip = _apply_ken_burns(clip, duration)
            return clip

        except Exception as e:
            print(f"[stock_footage] \u26a0 Could not load clip: {e}. Using gradient fallback.")

    return _make_gradient_bg(duration, scene, video_w, video_h)


def _crop_to_portrait(clip: VideoFileClip, video_w: int, video_h: int) -> VideoFileClip:
    """Scale-to-cover + center-crop to target portrait size, frame-by-frame
    with PIL directly (see module docstring for why we don't call moviepy's
    own resize fx here)."""
    orig_w, orig_h = clip.size
    scale = video_h / orig_h
    new_w, new_h = max(int(orig_w * scale), video_w), video_h
    left = (new_w - video_w) // 2

    def resize_and_crop(get_frame, t):
        frame = get_frame(t)
        img = Image.fromarray(frame).resize((new_w, new_h), Image.LANCZOS)
        img = img.crop((left, 0, left + video_w, video_h))
        return np.array(img)

    return clip.fl(resize_and_crop, apply_to=["mask", "video"])


def _apply_ken_burns(clip, duration: float):
    """Subtle slow-zoom effect to add motion to static footage."""
    start_scale, end_scale = 1.0, 1.08

    def zoom(get_frame, t):
        frame = get_frame(t)
        progress = t / max(duration, 0.001)
        scale = start_scale + (end_scale - start_scale) * progress
        h, w = frame.shape[:2]
        new_h, new_w = int(h * scale), int(w * scale)
        img = Image.fromarray(frame).resize((new_w, new_h), Image.LANCZOS)
        left, top = (new_w - w) // 2, (new_h - h) // 2
        img = img.crop((left, top, left + w, top + h))
        return np.array(img)

    return clip.fl(zoom, apply_to=["mask", "video"])


def _make_gradient_bg(duration: float, scene: dict, video_w: int, video_h: int) -> ImageClip:
    """Animated-in-name (static image held for the scene) gradient fallback,
    used when no Pexels clip was found for a scene's keyword."""
    img = Image.new("RGB", (video_w, video_h))
    draw = ImageDraw.Draw(img)

    moods = {
        "dark":     [(8, 8, 15),   (20, 20, 45)],
        "dramatic": [(15, 0, 25),  (5, 25, 50)],
        "bright":   [(20, 30, 60), (10, 50, 80)],
        "neutral":  [(10, 12, 20), (25, 28, 50)],
    }
    color_top, color_bot = moods.get(scene.get("visual_mood", "dark"), moods["dark"])

    for y in range(video_h):
        t = y / video_h
        r = int(color_top[0] + (color_bot[0] - color_top[0]) * t)
        g = int(color_top[1] + (color_bot[1] - color_top[1]) * t)
        b = int(color_top[2] + (color_bot[2] - color_top[2]) * t)
        draw.line([(0, y), (video_w, y)], fill=(r, g, b))

    return ImageClip(np.array(img)).set_duration(duration)
