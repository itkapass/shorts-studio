"""
video_compositor.py
-------------------
MODULE 6 — Final Video Assembly Engine

The heart of the pipeline. Combines all elements into the final 9:16 YouTube Shorts video:
  1. Background clips (per-scene) — pluggable render style, see engine/styles/
  2. Voiceover + mixed audio (from audio_mixer.py)
  3. Dynamic word-by-word captions (from subtitle_engine.py)
  4. Optional: channel watermark / branding
  5. Gradient/whiteboard/quote-card fallback backgrounds handled by the style module

Output: 1080x1920 MP4 at 30fps — the exact spec for YouTube Shorts.

RENDER STYLES: this file no longer hardcodes "Pexels footage" as the only
visual. `compose_video(..., render_style=...)` picks a background builder
from engine.styles.STYLES (stock_footage / whiteboard_sketch / quote_card).
Each style module owns everything about *how a scene looks*; this file only
owns assembly (background + captions + branding + audio + encode), which is
identical across styles.

FIXED: branding used to render via MoviePy's TextClip, which shells out to
ImageMagick — not installed in this project's Dockerfile or GitHub Actions
workflow, so the watermark silently never appeared (caught by its own
try/except). Now rendered with the same PIL path the captions already use,
so there's one fewer system dependency to manage.
"""

import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    ImageClip, AudioFileClip, CompositeVideoClip,
)
from engine.subtitle_engine import CaptionCard, CaptionStyle
from engine.styles import get_style, DEFAULT_STYLE

# Belt-and-suspenders: see engine/styles/stock_footage.py for the full story
# on why this matters with this project's pinned moviepy==1.0.3.
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.LANCZOS


# ─── Video Spec Constants (YouTube Shorts) ─────────────────────────────────────
VIDEO_WIDTH  = 1080
VIDEO_HEIGHT = 1920
FPS = 30
CODEC = "libx264"
AUDIO_CODEC = "aac"
VIDEO_BITRATE = "4000k"

CAPTION_CENTER_Y = int(VIDEO_HEIGHT * 0.62)  # Default caption position (62% down)


# ─── Core Function ─────────────────────────────────────────────────────────────

def compose_video(
    scenes_with_clips: list[dict],
    mixed_audio_path: str,
    caption_cards: list[CaptionCard],
    total_duration: float,
    output_path: str,
    caption_style: CaptionStyle = None,
    branding: dict = None,
    render_style: str = DEFAULT_STYLE,
) -> str:
    """
    Assembles the final YouTube Shorts video.

    Args:
        scenes_with_clips:  Scenes enriched with time_start/time_end, plus
                             whatever the chosen style needs (clip_path for
                             stock_footage, icons for whiteboard_sketch, ...)
        mixed_audio_path:   Path to the final mixed audio file
        caption_cards:      List of CaptionCard objects for subtitle overlay
        total_duration:     Total video length in seconds
        output_path:        Where to save the final .mp4
        caption_style:      CaptionStyle config (uses style-aware defaults if None)
        branding:           Optional {"channel_name": "...", "logo_path": "..."}
        render_style:       One of engine.styles.available_styles()

    Returns:
        output_path of the rendered video.
    """
    style = get_style(render_style)
    if caption_style is None:
        caption_style = default_caption_style_for(render_style)

    print(f"[video_compositor] Starting composition: {total_duration:.1f}s video, "
          f"{len(scenes_with_clips)} scenes, style='{render_style}'")

    # ── Step 1: Build per-scene background clips (style-specific) ─────────────
    background_clips = []
    for scene in scenes_with_clips:
        scene_start = scene.get("time_start", 0)
        scene_end   = scene.get("time_end", total_duration)
        scene_dur   = max(scene_end - scene_start, 0.5)

        bg_clip = style["build_background_clip"](scene, scene_dur, VIDEO_WIDTH, VIDEO_HEIGHT)
        bg_clip = bg_clip.set_start(scene_start)
        background_clips.append(bg_clip)

    # ── Step 2: Build caption overlay (style-agnostic) ────────────────────────
    caption_clips = _build_caption_clips(caption_cards, caption_style, total_duration)

    # ── Step 3: Branding / Watermark (style-agnostic) ─────────────────────────
    branding_clips = []
    if branding:
        branding_clips = _build_branding(branding, total_duration)

    # ── Step 4: Composite everything ──────────────────────────────────────────
    all_clips = background_clips + caption_clips + branding_clips
    final_video = CompositeVideoClip(all_clips, size=(VIDEO_WIDTH, VIDEO_HEIGHT))
    final_video = final_video.set_duration(total_duration)

    # ── Step 5: Attach audio ───────────────────────────────────────────────────
    if os.path.exists(mixed_audio_path):
        audio = AudioFileClip(mixed_audio_path).set_duration(total_duration)
        final_video = final_video.set_audio(audio)
    else:
        print(f"[video_compositor] \u26a0 Audio file not found: {mixed_audio_path}")

    # ── Step 6: Render to file ─────────────────────────────────────────────────
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    print(f"[video_compositor] Rendering {VIDEO_WIDTH}x{VIDEO_HEIGHT}@{FPS}fps → {output_path}")

    final_video.write_videofile(
        output_path,
        fps=FPS,
        codec=CODEC,
        audio_codec=AUDIO_CODEC,
        bitrate=VIDEO_BITRATE,
        preset="fast",
        threads=4,
        logger="bar",
    )

    final_video.close()
    print(f"[video_compositor] \u2713 Video rendered: {output_path}")
    return output_path


def default_caption_style_for(render_style: str) -> CaptionStyle:
    """Each render style gets caption defaults that actually match its look.
    Still just a CaptionStyle — callers can override any field before passing
    it to compose_video()."""
    if render_style == "whiteboard_sketch":
        return CaptionStyle(
            font_file="assets/fonts/Kalam-Bold.ttf",
            font_size=64,
            font_color="#1E1E22",     # dark ink, readable on the paper background
            highlight_color="#C0392B",
            stroke_color="#FFFFFF",
            stroke_width=0,
            bg_box=False,             # no box — this style relies on the paper bg for contrast
        )
    if render_style == "quote_card":
        return CaptionStyle(
            font_file="assets/fonts/Montserrat-Variable.ttf",
            font_size=76,
            font_color="#FFFFFF",
            highlight_color="#FFD700",
            stroke_color="#000000",
            stroke_width=2,
            bg_box=False,
        )
    return CaptionStyle()  # stock_footage default (white-on-black-box Montserrat)


# ─── Caption Overlay Builder (style-agnostic) ──────────────────────────────────

def _build_caption_clips(
    cards: list[CaptionCard],
    style: CaptionStyle,
    total_duration: float
) -> list:
    """Builds MoviePy text clips for each caption card."""
    clips = []
    font_path = style.font_file

    if not os.path.exists(font_path):
        print(f"[video_compositor] \u26a0 Font not found: {font_path}. Falling back to default caption font.")
        font_path = "assets/fonts/Montserrat-Variable.ttf" if os.path.exists("assets/fonts/Montserrat-Variable.ttf") else ""

    for card in cards:
        if not card.text.strip():
            continue

        duration = max(card.duration, 0.1)
        text_img = _render_text_card(card.text, style, font_path)
        text_clip = (
            ImageClip(text_img)
            .set_duration(duration)
            .set_start(card.start_time)
            .set_position(("center", CAPTION_CENTER_Y - text_img.shape[0] // 2))
        )
        text_clip = text_clip.fadein(style.fade_in_duration)
        clips.append(text_clip)

    print(f"[video_compositor] \u2713 Built {len(clips)} caption clips")
    return clips


def _load_font(font_path: str, font_size: int):
    """Loads a font, selecting the ExtraBold named instance if it's the
    bundled Montserrat variable font (avoids depending on a separate static
    -ExtraBold.ttf file that used to be fetched from a third party at
    runtime — see assets/fonts/README.md)."""
    font = ImageFont.truetype(font_path, font_size)
    try:
        names = font.get_variation_names()
        target = b"ExtraBold" if b"ExtraBold" in names else (b"Bold" if b"Bold" in names else None)
        if target:
            font.set_variation_by_name(target)
    except Exception:
        pass  # Not a variable font (e.g. Kalam-Bold.ttf) — nothing to do.
    return font


def _render_text_card(text: str, style: CaptionStyle, font_path: str) -> np.ndarray:
    """Renders text to a numpy RGBA image array using PIL for max quality."""
    font_size = style.font_size
    max_w = int(VIDEO_WIDTH * style.max_width_ratio)
    padding = style.bg_padding

    try:
        font = _load_font(font_path, font_size) if font_path else ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()

    dummy_img = Image.new("RGBA", (VIDEO_WIDTH, 200))
    dummy_draw = ImageDraw.Draw(dummy_img)
    bbox = dummy_draw.textbbox((0, 0), text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]

    while text_w > max_w and font_size > 30:
        font_size -= 4
        try:
            font = _load_font(font_path, font_size) if font_path else ImageFont.load_default()
        except Exception:
            break
        bbox = dummy_draw.textbbox((0, 0), text, font=font)
        text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]

    img_w, img_h = text_w + padding * 2, text_h + padding * 2
    img = Image.new("RGBA", (max(img_w, 1), max(img_h, 1)), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if style.bg_box:
        bg_color = _hex_to_rgba(style.bg_color)
        draw.rounded_rectangle([(0, 0), (img_w, img_h)], radius=14, fill=bg_color)

    if style.stroke_width > 0:
        stroke = style.stroke_width
        stroke_color = _hex_to_rgb(style.stroke_color)
        for dx in range(-stroke, stroke + 1):
            for dy in range(-stroke, stroke + 1):
                if dx != 0 or dy != 0:
                    draw.text((padding + dx, padding + dy), text, font=font, fill=(*stroke_color, 255))

    text_color = _hex_to_rgb(style.font_color)
    draw.text((padding, padding), text, font=font, fill=(*text_color, 255))

    return np.array(img)


def _hex_to_rgb(hex_color: str) -> tuple:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _hex_to_rgba(hex_color: str) -> tuple:
    h = hex_color.lstrip("#")
    if len(h) == 8:
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4, 6))
    return (*_hex_to_rgb(hex_color), 100)


# ─── Branding (style-agnostic, PIL-only — no ImageMagick dependency) ──────────

def _build_branding(branding: dict, total_duration: float) -> list:
    """Adds a subtle channel-name watermark in the top-left corner.

    Previously used MoviePy's TextClip, which shells out to ImageMagick.
    Neither the Dockerfile nor generate.yml installed it, so this failed
    silently (caught by its own try/except) on every render. Rendering with
    PIL directly — the same approach the captions already use — removes
    that dependency entirely.
    """
    channel_name = (branding or {}).get("channel_name", "")
    if not channel_name:
        return []

    try:
        font_path = "assets/fonts/Montserrat-Variable.ttf"
        font = _load_font(font_path, 32) if os.path.exists(font_path) else ImageFont.load_default()

        text = f"@{channel_name}"
        dummy = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
        bbox = dummy.textbbox((0, 0), text, font=font)
        w, h = bbox[2] - bbox[0] + 8, bbox[3] - bbox[1] + 8

        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx or dy:
                    draw.text((4 + dx, 4 + dy), text, font=font, fill=(0, 0, 0, 255))
        draw.text((4, 4), text, font=font, fill=(255, 255, 255, 255))

        clip = (
            ImageClip(np.array(img))
            .set_opacity(0.6)
            .set_duration(total_duration)
            .set_position((40, 80))
        )
        return [clip]
    except Exception as e:
        print(f"[video_compositor] \u26a0 Branding clip failed: {e}")
        return []
