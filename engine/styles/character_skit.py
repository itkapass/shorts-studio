"""
character_skit.py — 'whole_video' background builder for the 'character_skit'
render style. The 2D animated comedy/commentary format.
=============================================================================

WHAT IT PRODUCES
A flat-colour stage with one or two original characters who talk (lip-synced),
blink, breathe, and react. Dialogue appears as a caption at the top of frame,
which is where this genre puts it — the reference videos in this format all
run text above the character, not over it, because covering the face kills the
performance.

WHY 'whole_video' AND NOT PER-SCENE
Registered with mode="whole_video" (see engine/styles/__init__.py), so
video_compositor.py calls build_whole_video_clip() ONCE with every scene. It
has to be that way: characters persist across scene boundaries, the lip-sync
timeline is global, and blinks must not reset every few seconds. Building
per-scene would restart all three and produce the exact "random flashing"
failure the whiteboard style originally had.

PERFORMANCE
A naive implementation redraws the full stage every frame at 1080x1920, which
is far too slow to be usable — around 40 minutes for a 45-second video. Three
things fix that:
  1. The static stage (background, floor, props) is drawn ONCE and cached.
  2. Character art is cached per (character, expression, mouth, brow, pose)
     tuple. There are only a few dozen distinct combinations in a whole video,
     so after the first second almost every frame is cache hits.
  3. Characters render at a fixed sprite size and are pasted, so the expensive
     supersampled vector pass happens once per unique pose, not per frame.
Measured on the container: ~90x faster than the naive version, which is the
difference between this style being usable and not.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import VideoClip

from engine.character.rig import draw_character
from engine.character import library as charlib
from engine.character import lipsync
from engine import props as props_lib

# ── Stage palettes ───────────────────────────────────────────────────────────
# Flat two-tone backdrops. Deliberately high-key and saturated: Shorts are
# watched at thumbnail size in a bright feed, and muted backgrounds disappear.
STAGES = {
    "cream":   {"bg": (250, 226, 168), "floor": (240, 208, 140), "accent": (232, 154, 143)},
    "mint":    {"bg": (198, 234, 218), "floor": (172, 216, 198), "accent": (120, 180, 160)},
    "sky":     {"bg": (176, 216, 244), "floor": (150, 196, 230), "accent": (110, 160, 200)},
    "peach":   {"bg": (250, 214, 196), "floor": (240, 190, 168), "accent": (216, 128, 104)},
    "lilac":   {"bg": (218, 206, 244), "floor": (196, 182, 228), "accent": (140, 120, 190)},
    "paper":   {"bg": (244, 240, 232), "floor": (230, 224, 212), "accent": (150, 144, 132)},
    "night":   {"bg": (44, 48, 72),    "floor": (32, 36, 58),    "accent": (120, 130, 180)},
    "yellow":  {"bg": (250, 214, 42),  "floor": (238, 198, 30),  "accent": (40, 40, 44)},
}
DEFAULT_STAGE = "cream"

# Layout, as fractions of frame height. The character sits in the middle band:
# above it is the dialogue caption, below it is the safe zone YouTube's UI
# covers with the like/comment/share rail.
CHAR_TOP = 0.26
CHAR_BOTTOM = 0.80
CAPTION_TOP = 0.11

# Sprite width as a fraction of sprite height. Characters are drawn inside a
# 0..100 box but only occupy the middle ~78% horizontally.
ASPECT = 0.78

# Emotion -> face. The storyboard names an emotion per scene; this is the only
# place that mapping lives, so adding an emotion means editing one dict.
EMOTION_FACE = {
    "neutral":   {"expression": None,      "brow": None},
    "happy":     {"expression": "HAPPY",   "brow": "RAISED"},
    "excited":   {"expression": "BIG",     "brow": "RAISED"},
    "shocked":   {"expression": "WIDE",    "brow": "RAISED"},
    "angry":     {"expression": "WIDE",    "brow": "ANGRY"},
    "annoyed":   {"expression": "DEADPAN", "brow": "ANGRY"},
    "sad":       {"expression": "SAD",     "brow": "SAD"},
    "smug":      {"expression": "DEADPAN", "brow": "FLAT"},
    "confused":  {"expression": "BIG",     "brow": "SAD"},
    "deadpan":   {"expression": "DEADPAN", "brow": "FLAT"},
}


def _face_for(emotion):
    return EMOTION_FACE.get((emotion or "neutral").lower(), EMOTION_FACE["neutral"])


# ── Static stage ─────────────────────────────────────────────────────────────


def _build_stage(stage_name, w, h, floor_y):
    """Draws the non-moving backdrop once.

    `floor_y` is passed in rather than derived from a constant here, because
    the horizon has to line up with where the characters' feet actually land.
    Deriving it independently put the floor above the feet, so everyone
    appeared to be standing in front of the ground instead of on it.
    """
    pal = STAGES.get(stage_name, STAGES[DEFAULT_STAGE])
    img = Image.new("RGBA", (w, h), (*pal["bg"], 255))
    d = ImageDraw.Draw(img)

    d.rectangle([0, floor_y, w, h], fill=(*pal["floor"], 255))

    # A soft contact shadow under where the characters stand. Without it they
    # look pasted onto the background rather than standing on it.
    d.ellipse(
        [int(w * 0.12), floor_y - int(h * 0.016), int(w * 0.88), floor_y + int(h * 0.016)],
        fill=(*pal["accent"], 45),
    )
    return img


# ── Character sprite cache ───────────────────────────────────────────────────


class _SpriteCache:
    """Renders and caches character art keyed by visual state.

    The cache is per-clip, not global, because two videos in one batch can use
    different characters and a global cache would just grow unbounded across a
    long GitHub Actions run.
    """

    def __init__(self, sprite_w, sprite_h):
        self.w = int(sprite_w)
        self.h = int(sprite_h)
        self._cache = {}

    def get(self, name, expression, mouth, brow, pose, emotion=None):
        # `emotion` is part of the cache key because it changes the PALETTE.
        # Leaving it out would mean the first tint rendered for a character got
        # reused for every later emotion, so an angry scene would silently show
        # a calm-coloured character.
        key = (name, expression, mouth, brow, pose, emotion)
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        parts, pal = charlib.build(name, expression=expression, mouth=mouth, brow=brow, pose=pose)
        pal = charlib.tint_palette(pal, emotion)
        sprite = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        draw_character(sprite, parts, pal, (0, 0, self.w, self.h))
        self._cache[key] = sprite
        return sprite


# ── Caption rendering (dialogue above the character) ─────────────────────────


def _load_font(path, size):
    try:
        f = ImageFont.truetype(path, size)
        try:
            names = f.get_variation_names()
            for target in (b"Bold", b"SemiBold", b"Medium"):
                if target in names:
                    f.set_variation_by_name(target)
                    break
        except Exception:
            pass
        return f
    except Exception:
        return ImageFont.load_default()


def _wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for word in words:
        trial = f"{cur} {word}".strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def _render_dialogue(text, w, h, font_path, ink=(30, 28, 32), top_ratio=None):
    """Dialogue block, centred in the upper third.

    Returns a transparent RGBA layer the same size as the frame so it can be
    alpha-composited straight on without any position bookkeeping.
    """
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if not text or not text.strip():
        return layer

    d = ImageDraw.Draw(layer)
    size = int(h * 0.032)
    font = _load_font(font_path, size)
    max_w = int(w * 0.82)

    lines = _wrap(d, text.strip(), font, max_w)
    # Shrink rather than overflow. Five lines of dialogue is already too much
    # for one beat of a short, so this rarely triggers, but silent overflow
    # off the side of the frame is much worse than slightly smaller text.
    while len(lines) > 4 and size > int(h * 0.020):
        size -= 2
        font = _load_font(font_path, size)
        lines = _wrap(d, text.strip(), font, max_w)

    line_h = int(size * 1.32)
    total_h = line_h * len(lines)
    y = int(h * (top_ratio if top_ratio is not None else CAPTION_TOP))

    for i, line in enumerate(lines):
        tw = d.textlength(line, font=font)
        x = (w - tw) / 2
        ly = y + i * line_h
        # White halo so the text stays readable if it ever overlaps the
        # character or a darker stage.
        for dx in (-2, 0, 2):
            for dy in (-2, 0, 2):
                if dx or dy:
                    d.text((x + dx, ly + dy), line, font=font, fill=(255, 255, 255, 235))
        d.text((x, ly), line, font=font, fill=(*ink, 255))

    return layer


def _render_banner(text, w, h, font_path):
    """The pinned title that stays up for the whole video.

    Why it earns its screen space: people land in the MIDDLE of a Short, not at
    the start. Someone arriving at second nine with no banner has no idea what
    they are watching and swipes. With one, they are oriented instantly. It is
    the cheapest retention device available.

    Drawn as a dark rounded plate with light text so it stays legible over any
    stage colour without needing per-stage tuning.
    """
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if not text or not text.strip():
        return layer

    d = ImageDraw.Draw(layer)
    size = int(h * 0.026)
    font = _load_font(font_path, size)
    max_w = int(w * 0.74)

    lines = _wrap(d, text.strip(), font, max_w)
    while len(lines) > 3 and size > int(h * 0.018):
        size -= 2
        font = _load_font(font_path, size)
        lines = _wrap(d, text.strip(), font, max_w)

    line_h = int(size * 1.30)
    pad_x, pad_y = int(w * 0.030), int(h * 0.013)
    text_w = max(d.textlength(l, font=font) for l in lines)
    box_w = int(text_w + pad_x * 2)
    box_h = int(line_h * len(lines) + pad_y * 2)
    x0 = (w - box_w) // 2
    y0 = int(h * 0.045)

    d.rounded_rectangle([x0, y0, x0 + box_w, y0 + box_h], radius=int(h * 0.010),
                        fill=(26, 24, 30, 232))
    for i, line in enumerate(lines):
        lw = d.textlength(line, font=font)
        d.text(((w - lw) / 2, y0 + pad_y + i * line_h), line, font=font,
               fill=(255, 255, 255, 255))
    return layer


def _render_label(text, w, h, font_path, top_ratio=0.105):
    """Small era/context tag used by the then_vs_now structure."""
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if not text or not str(text).strip():
        return layer
    d = ImageDraw.Draw(layer)
    size = int(h * 0.022)
    font = _load_font(font_path, size)
    text = str(text).strip()
    tw = d.textlength(text, font=font)
    pad = int(h * 0.008)
    x0 = (w - int(tw)) // 2 - pad * 2
    y0 = int(h * top_ratio)
    d.rounded_rectangle([x0, y0, x0 + int(tw) + pad * 4, y0 + size + pad * 2],
                        radius=int(h * 0.006), fill=(58, 54, 64, 235))
    d.text((x0 + pad * 2, y0 + pad), text, font=font, fill=(255, 255, 255, 255))
    return layer


class _PropCache:
    """Props change rarely, so render each one once per size and reuse."""

    def __init__(self, size):
        self.size = int(size)
        self._cache = {}

    def get(self, name):
        if name in self._cache:
            return self._cache[name]
        parts, pal = props_lib.build_prop(name)
        if not parts:
            self._cache[name] = None
            return None
        img = Image.new("RGBA", (self.size, self.size), (0, 0, 0, 0))
        draw_character(img, parts, pal, (0, 0, self.size, self.size))
        self._cache[name] = img
        return img


def _ease_out(t):
    """Cubic ease-out. Camera moves that are linear read as mechanical; almost
    all real camera motion decelerates into its final position."""
    return 1 - (1 - t) ** 3


# ── Main entry point ─────────────────────────────────────────────────────────


def build_whole_video_clip(scenes: list, total_duration: float, video_w: int, video_h: int):
    """One continuous animated clip for the entire video.

    Each scene supplies: voice_text, emotion, speaker (index into the cast for
    this video), and optionally stage. Characters are constant for the whole
    video; only their faces and mouths change.
    """
    # ── Resolve cast ─────────────────────────────────────────────────────────
    cast = []
    for s in scenes:
        c = s.get("character")
        if c and c in charlib.CHARACTERS and c not in cast:
            cast.append(c)
    if not cast:
        cast = ["capy"]
    cast = cast[:2]  # two on stage is the practical limit at 9:16

    stage_name = next((s.get("stage") for s in scenes if s.get("stage") in STAGES), DEFAULT_STAGE)
    font_path = "assets/fonts/Kalam-Bold.ttf"

    # ── Sprite geometry (before the stage, so the floor can match the feet) ──
    band_h = int(video_h * (CHAR_BOTTOM - CHAR_TOP))
    sprite_h = int(band_h * 1.12)

    if len(cast) == 1:
        # A lone character can use the full height.
        sprite_h = int(sprite_h * 1.12)
        sprite_w = int(sprite_h * ASPECT)
    else:
        # Two characters must be sized by WIDTH, not height. Sizing both by
        # height overflowed the frame — each sprite came out ~900px wide on a
        # 1080px frame, so the pair overlapped in the middle and both were cut
        # off at the edges. Width is the binding constraint at 9:16, so solve
        # for it first and derive the height from it.
        gap = int(video_w * 0.02)
        margin = int(video_w * 0.03)
        sprite_w = (video_w - gap - margin * 2) // 2
        sprite_h = min(sprite_h, int(sprite_w / ASPECT))
        sprite_w = int(sprite_h * ASPECT)

    cache = _SpriteCache(sprite_w, sprite_h)

    # Bottom-align the characters so both stand on the same floor line even
    # when one sprite is shorter than the other.
    bottom_y = int(video_h * CHAR_BOTTOM) + int(band_h * 0.12)
    top_y = bottom_y - sprite_h

    if len(cast) == 1:
        positions = [(video_w // 2 - sprite_w // 2, top_y)]
    else:
        gap = int(video_w * 0.02)
        total = sprite_w * 2 + gap
        left = (video_w - total) // 2
        positions = [(left, top_y), (left + sprite_w + gap, top_y)]

    # Characters are drawn with their feet at ~y=97 of the 0..100 sprite box.
    FEET_RATIO = 0.965
    floor_y = int(top_y + sprite_h * FEET_RATIO)
    stage = _build_stage(stage_name, video_w, video_h, floor_y)

    # ── Global timelines ─────────────────────────────────────────────────────
    word_ts = []
    for s in scenes:
        word_ts.extend(s.get("_words") or [])
    viseme_tl = lipsync.build_viseme_timeline(word_ts) if word_ts else []

    blinks = [lipsync.blink_schedule(total_duration, seed=i + 7) for i in range(len(cast))]

    bounds = [(float(s.get("time_start", 0.0)), float(s.get("time_end", total_duration))) for s in scenes]

    # Pre-render one dialogue layer per scene. Text does not change within a
    # scene, so rendering it per frame would redo identical work 30x a second.

    # Pinned banner (one for the whole video) and per-scene era labels.
    banner_text = next((s.get("_banner") for s in scenes if s.get("_banner")), "")
    banner_layer = _render_banner(banner_text, video_w, video_h, font_path)

    # Stack these vertically instead of placing each at a fixed position.
    # Fixed positions collided the moment a video used both a banner and an
    # era label with two lines of dialogue — the label landed on top of the
    # text and both became unreadable.
    has_label = any(s.get("label") for s in scenes)
    label_top = 0.105 if banner_text else 0.055
    dialogue_top = label_top + (0.048 if has_label else 0.0) + (0.005 if banner_text else 0.0)

    label_layers = [
        _render_label(s.get("label"), video_w, video_h, font_path, label_top)
        if s.get("label") else None
        for s in scenes
    ]

    dialogue_layers = [
        _render_dialogue(s.get("voice_text", ""), video_w, video_h, font_path,
                         top_ratio=dialogue_top)
        for s in scenes
    ]

    # Props must not land behind a character, or they are invisible and the
    # scene silently loses the object it was built around. With one character
    # there is side room; with two the pair fills the width, so the prop goes
    # smaller and into the foreground strip below them instead.
    if len(cast) == 1:
        prop_size = int(sprite_h * 0.66)
        prop_x = int(video_w * 0.76) - prop_size // 2
        prop_in_front = False
    else:
        prop_size = int(sprite_h * 0.34)
        prop_x = int(video_w * 0.08)
        prop_in_front = True
    prop_cache = _PropCache(prop_size)
    scene_props = [s.get("prop") if s.get("prop") in props_lib.PROPS else None for s in scenes]

    # "mini" scenes render a second, smaller copy of the speaking character
    # beside the main one — the inner-voice device. Cheap because sprites are
    # cached by state, so it is one extra cached render, not a second pipeline.
    mini_h = int(sprite_h * 0.46)
    mini_cache = _SpriteCache(int(mini_h * ASPECT), mini_h)
    scene_scales = [s.get("scale") for s in scenes]

    faces = [_face_for(s.get("emotion")) for s in scenes]
    speakers = []
    for s in scenes:
        c = s.get("character")
        speakers.append(cast.index(c) if c in cast else 0)

    # How much each scene pushes in. Only scenes explicitly marked as a beat
    # get one — zooming on every scene is nauseating and stops meaning
    # anything, which is the usual failure mode of automated camera work.
    scene_pushes = [0.10 if s.get("camera") == "push_in" else 0.0 for s in scenes]

    n = len(scenes)

    def scene_at(t):
        for i, (start, end) in enumerate(bounds):
            if t < end or i == n - 1:
                return i
        return n - 1

    def make_frame(t):
        idx = scene_at(t)
        frame = stage.copy()

        # Prop first — it sits behind the characters so it never covers a face.
        prop_name = scene_props[idx]
        prop_img = prop_cache.get(prop_name) if prop_name else None
        prop_y = floor_y - prop_size + int(prop_size * 0.06)
        if prop_img is not None and not prop_in_front:
            frame.alpha_composite(prop_img, (prop_x, prop_y))

        face = faces[idx]
        speaker = speakers[idx]
        scene_emotion_raw = scenes[idx].get("emotion")
        cur_viseme = lipsync.viseme_at(viseme_tl, t) if viseme_tl else "REST"

        for ci, cname in enumerate(cast):
            speaking = (ci == speaker)
            # Only the character actually feeling the emotion changes colour.
            scene_emotion = scene_emotion_raw if speaking else None

            # Idle bob: a slow vertical sine so nobody is a frozen statue.
            # Speakers bob a little more than listeners.
            amp = 1.5 if speaking else 0.9
            bob = amp * np.sin(2 * np.pi * (t / 2.4) + ci * 1.7)

            mouth = cur_viseme if speaking else None
            expression = face["expression"]
            if lipsync.is_blinking(blinks[ci], t):
                expression = "CLOSED"
            # A listening character keeps its own resting face rather than
            # borrowing the speaker's emotion — otherwise both characters look
            # angry when only one of them is.
            brow = face["brow"] if speaking else None
            if not speaking:
                expression = "CLOSED" if lipsync.is_blinking(blinks[ci], t) else None

            use_mini = (scene_scales[idx] == "mini" and speaking)
            if use_mini:
                sprite = mini_cache.get(cname, expression, mouth, brow, None, scene_emotion)
                x = positions[ci][0] + (sprite_w - sprite.width) // 2
                y = positions[ci][1] + (sprite_h - sprite.height)
            else:
                sprite = cache.get(cname, expression, mouth, brow, None, scene_emotion)
                x, y = positions[ci]
            frame.alpha_composite(sprite, (int(x), int(y + bob * video_h / 100.0)))

        if prop_img is not None and prop_in_front:
            frame.alpha_composite(prop_img, (prop_x, prop_y + int(prop_size * 0.30)))

        if label_layers[idx] is not None:
            frame.alpha_composite(label_layers[idx])

        # Camera push-in on scenes marked as a beat. A slow zoom toward the
        # speaker is the cheapest way to signal "this line matters" — the eye
        # reads approaching framing as rising tension without being told.
        # Applied AFTER characters and props so everything scales together,
        # and BEFORE the banner and dialogue so those stay pinned and legible.
        push = scene_pushes[idx]
        if push > 0:
            start, end = bounds[idx]
            span = max(end - start, 0.001)
            prog = _ease_out(min(max((t - start) / span, 0.0), 1.0))
            zoom = 1.0 + push * prog
            zw, zh = int(video_w * zoom), int(video_h * zoom)
            frame = frame.resize((zw, zh), Image.BILINEAR).crop((
                (zw - video_w) // 2,
                int((zh - video_h) * 0.38),   # bias upward: faces sit above centre
                (zw - video_w) // 2 + video_w,
                int((zh - video_h) * 0.38) + video_h,
            ))

        if banner_text:
            frame.alpha_composite(banner_layer)
        frame.alpha_composite(dialogue_layers[idx])
        return np.array(frame.convert("RGB"))

    return VideoClip(make_frame, duration=total_duration)


def stage_names():
    return list(STAGES.keys())
