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
    ImageClip, AudioFileClip, CompositeVideoClip, ColorClip,
)
from engine.subtitle_engine import CaptionCard, CaptionStyle
from engine.styles import get_style, DEFAULT_STYLE

# Belt-and-suspenders: see engine/styles/stock_footage.py for the full story
# on why this matters with this project's pinned moviepy==1.0.3.
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.LANCZOS

# Used only as an emergency base layer (see compose_video Step 1) — matches
# each style's general palette so it's inconspicuous in the rare case it's
# ever visible at all.
_FALLBACK_COLOR = {
    "stock_footage": (10, 10, 18),
    "whiteboard_sketch": (250, 248, 240),
    "quote_card": (10, 10, 18),
}


# ─── Video Spec Constants (YouTube Shorts) ─────────────────────────────────────
VIDEO_WIDTH  = 1080
VIDEO_HEIGHT = 1920
FPS = 30
CODEC = "libx264"
AUDIO_CODEC = "aac"
VIDEO_BITRATE = "4000k"

CAPTION_CENTER_Y = int(VIDEO_HEIGHT * 0.62)  # Default caption position (62% down)
CROSSFADE_DURATION = 0.4  # seconds — dissolve between scenes instead of a hard cut


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

    # ── Step 1 & 2: Build the background(s) — branches on style mode ──────────
    # Two genuinely different needs here: stock_footage/quote_card each
    # scene is independent, so they're built one at a time and crossfaded
    # together. whiteboard_sketch's connected diagram needs to see every
    # scene at once (to lay out and progressively reveal one continuous
    # drawing) — see engine/styles/whiteboard_sketch.py — so it gets built
    # as a single whole-video clip instead of a per-scene loop.
    if style.get("mode") == "whole_video":
        background_clips = [
            style["build_whole_video_clip"](scenes_with_clips, total_duration, VIDEO_WIDTH, VIDEO_HEIGHT)
        ]
    else:
        # Defense-in-depth base layer: get_scene_timestamps() forces scenes
        # to be perfectly contiguous (see engine/voice_engine.py), which is
        # the real fix for a black-hole bug found in real generated output
        # (a ~2s gap between scenes exposed CompositeVideoClip's default
        # black canvas, with the caption still playing right through it).
        # This is the second line of defense: if any future change
        # reintroduces a coverage gap, the worst case is a plain color for
        # a moment instead of a black hole. Deliberately a flat static
        # color, not the full style renderer again — this sits fully
        # hidden under real content in the normal case.
        base_color = _FALLBACK_COLOR.get(render_style, (15, 15, 20))
        background_clips = [ColorClip(size=(VIDEO_WIDTH, VIDEO_HEIGHT), color=base_color).set_duration(total_duration)]

        # FIXED: scenes used to cut instantly from one background to the
        # next — part of what read as "uneven, not in a flow." Adjacent
        # scenes now overlap by CROSSFADE_DURATION and the incoming one
        # fades in over that overlap, so cuts dissolve instead of popping.
        n_scenes = len(scenes_with_clips)
        pad = CROSSFADE_DURATION / 2

        for i, scene in enumerate(scenes_with_clips):
            scene_start = scene.get("time_start", 0)
            scene_end   = scene.get("time_end", total_duration)

            lead_pad  = pad if i > 0 else 0.0
            trail_pad = pad if i < n_scenes - 1 else 0.0
            effective_start = max(scene_start - lead_pad, 0.0)
            effective_dur = max((scene_end + trail_pad) - effective_start, 0.5)

            bg_clip = style["build_background_clip"](scene, effective_dur, VIDEO_WIDTH, VIDEO_HEIGHT)
            bg_clip = bg_clip.set_start(effective_start)
            if i > 0:
                bg_clip = bg_clip.crossfadein(CROSSFADE_DURATION)
            background_clips.append(bg_clip)

    # ── Step 3: Build caption overlay (style-agnostic) ────────────────────────
    caption_clips = _build_caption_clips(caption_cards, caption_style, total_duration)

    # ── Step 4: Branding / Watermark (style-agnostic) ─────────────────────────
    branding_clips = []
    if branding:
        branding_clips = _build_branding(branding, total_duration)

    # ── Step 5: Composite everything ──────────────────────────────────────────
    all_clips = background_clips + caption_clips + branding_clips
    final_video = CompositeVideoClip(all_clips, size=(VIDEO_WIDTH, VIDEO_HEIGHT))
    final_video = final_video.set_duration(total_duration)

    # ── Step 6: Attach audio ───────────────────────────────────────────────────
    if os.path.exists(mixed_audio_path):
        audio = AudioFileClip(mixed_audio_path).set_duration(total_duration)
        final_video = final_video.set_audio(audio)
    else:
        print(f"[video_compositor] \u26a0 Audio file not found: {mixed_audio_path}")

    # ── Step 7: Render to file ─────────────────────────────────────────────────
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


def default_caption_style_for(render_style: str, persona_key: str = None) -> CaptionStyle:
    """Each render style gets caption defaults that actually match its look.
    Still just a CaptionStyle — callers can override any field before passing
    it to compose_video().

    persona_key is checked first for a persona-specific override. Right now
    that means exactly one thing: the motivation/discipline persona turns on
    word-size emphasis, because that persona's whole brief is "a flat text
    card is the failure mode here" — the emphasised word is the visual answer
    to that, not an across-the-board feature everything gets by default.
    """
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

    style = CaptionStyle()  # stock_footage default (white-on-black-box Montserrat)
    if persona_key == "motivation_and_discipline":
        style.emphasis_pop = True
    return style


# ─── Caption Overlay Builder (style-agnostic) ──────────────────────────────────

def _build_caption_clips(
    cards: list[CaptionCard],
    style: CaptionStyle,
    total_duration: float
) -> list:
    """Builds MoviePy text clips for each caption card.

    FIXED — THE HIGHLIGHT THAT NEVER RENDERED. CaptionStyle has always defined
    `highlight_color` and nothing ever read it, so every caption came out flat
    white. Cards now carry per-word timings, so each card is split into one
    sub-clip per word, and the sub-clip covering a word's speaking window
    renders that word in the highlight colour.

    Splitting per word rather than animating one clip is deliberate: MoviePy
    1.0.3 has no per-frame text redraw that is not brutally slow, and a card
    only has 2-4 words, so this is a handful of extra static images per card
    rather than a per-frame render. A 45-second video ends up around 150 small
    ImageClips, which composites fine.
    """
    clips = []
    font_path = style.font_file

    if not os.path.exists(font_path):
        print(f"[video_compositor] \u26a0 Font not found: {font_path}. Falling back to default caption font.")
        font_path = "assets/fonts/Montserrat-Variable.ttf" if os.path.exists("assets/fonts/Montserrat-Variable.ttf") else ""

    for card in cards:
        if not card.text.strip():
            continue

        duration = max(card.duration, 0.1)

        if not style.highlight_active_word or not card.word_times:
            emphasis = card.emphasis_mask() if style.emphasis_pop else None
            img = _render_text_card(card.words, -1, style, font_path, emphasis)
            clips.append(
                ImageClip(img)
                .set_duration(duration)
                .set_start(card.start_time)
                .set_position(("center", CAPTION_CENTER_Y - img.shape[0] // 2))
                .fadein(style.fade_in_duration)
            )
            continue

        # One sub-clip per word, each covering that word's speaking window.
        # The card's own bounds clamp the ends so highlights never bleed past
        # the card or leave a gap where no caption is on screen at all.
        segments = []
        for i, (ws, we) in enumerate(card.word_times):
            seg_start = max(ws, card.start_time)
            seg_end = min(we, card.end_time)
            if seg_end > seg_start:
                segments.append((seg_start, seg_end, i))

        # Fill any silence between words by extending the previous highlight,
        # rather than dropping back to flat text for a few frames (which reads
        # as a flicker).
        filled = []
        for idx, (s, e, wi) in enumerate(segments):
            nxt = segments[idx + 1][0] if idx + 1 < len(segments) else card.end_time
            filled.append((s, max(e, min(nxt, card.end_time)), wi))

        if filled and filled[0][0] > card.start_time:
            filled.insert(0, (card.start_time, filled[0][0], -1))

        for si, (s, e, wi) in enumerate(filled):
            emphasis = card.emphasis_mask() if style.emphasis_pop else None
            img = _render_text_card(card.words, wi, style, font_path, emphasis)
            clip = (
                ImageClip(img)
                .set_duration(max(e - s, 0.02))
                .set_start(s)
                .set_position(("center", CAPTION_CENTER_Y - img.shape[0] // 2))
            )
            if si == 0:
                clip = clip.fadein(style.fade_in_duration)
            clips.append(clip)

    print(f"[video_compositor] \u2713 Built {len(clips)} caption clips "
          f"({'word highlight ON' if style.highlight_active_word else 'flat'})")
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


def _render_text_card(words, active_index: int, style: CaptionStyle, font_path: str,
                       emphasis_mask: list = None) -> np.ndarray:
    """Renders one caption card, colouring `active_index` in the highlight
    colour and optionally rendering one word larger per `emphasis_mask`.

    Words are measured and drawn individually rather than as one string,
    because PIL can only apply a single fill per draw.text() call. Measuring
    each word separately is also what lets the highlight sit exactly under the
    right word instead of being approximated from a character offset, and it
    is what makes a size-varying emphasised word possible at all — a single
    draw.text() call has exactly one font size for the whole string.

    Emphasis vertical placement is per-word CENTRED within the card's row
    height rather than baseline-matched against the other words. True
    baseline alignment across two different font sizes needs font ascent
    metrics PIL does not expose cleanly across platforms; centring is a
    simpler calculation that still reads correctly as "this word is bigger",
    which is the entire visual point.
    """
    if isinstance(words, str):
        words = words.split()
    if not words:
        return np.zeros((1, 1, 4), dtype=np.uint8)

    emphasis_mask = emphasis_mask or [False] * len(words)
    font_size = style.font_size
    emphasis_size = int(font_size * getattr(style, "emphasis_scale", 1.35))
    max_w = int(VIDEO_WIDTH * style.max_width_ratio)
    padding = style.bg_padding

    font_cache = {}

    def load(size):
        if size not in font_cache:
            try:
                font_cache[size] = _load_font(font_path, size) if font_path else ImageFont.load_default()
            except Exception:
                font_cache[size] = ImageFont.load_default()
        return font_cache[size]

    measure = ImageDraw.Draw(Image.new("RGBA", (8, 8)))

    def word_font(i):
        return load(emphasis_size) if emphasis_mask[i] else load(font_size)

    def layout():
        space = measure.textlength(" ", font=load(font_size))
        widths = [measure.textlength(w, font=word_font(i)) for i, w in enumerate(words)]
        return widths, space, sum(widths) + space * (len(words) - 1)

    widths, space_w, total_w = layout()
    # Shrink to fit rather than overflowing off the side of the frame. Shrinks
    # both sizes together so the emphasis word stays proportionally bigger.
    while total_w > max_w and font_size > 24:
        font_size -= 4
        emphasis_size = int(font_size * getattr(style, "emphasis_scale", 1.35))
        widths, space_w, total_w = layout()

    word_boxes = [measure.textbbox((0, 0), w, font=word_font(i)) for i, w in enumerate(words)]
    row_h = max(b[3] - b[1] for b in word_boxes)

    img_w = int(total_w + padding * 2)
    img_h = int(row_h + padding * 2)
    img = Image.new("RGBA", (max(img_w, 1), max(img_h, 1)), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if style.bg_box:
        draw.rounded_rectangle([(0, 0), (img_w, img_h)], radius=14, fill=_hex_to_rgba(style.bg_color))

    base_color = (*_hex_to_rgb(style.font_color), 255)
    hi_color = (*_hex_to_rgb(style.highlight_color), 255)
    stroke_color = (*_hex_to_rgb(style.stroke_color), 255)

    x = float(padding)
    for i, word in enumerate(words):
        f = word_font(i)
        bbox = word_boxes[i]
        word_h = bbox[3] - bbox[1]
        y = padding + (row_h - word_h) / 2.0 - bbox[1]

        if style.stroke_width > 0:
            s = style.stroke_width

            for dx in range(-s, s + 1):
                for dy in range(-s, s + 1):
                    if dx or dy:
                        draw.text((x + dx, y + dy), word, font=f, fill=stroke_color)
        draw.text((x, y), word, font=f, fill=hi_color if i == active_index else base_color)
        x += widths[i] + space_w

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
