"""
subtitle_engine.py
------------------
MODULE 4 — Dynamic Word-by-Word Caption Renderer

Generates animated "Hormozi-style" captions: 3 words pop on screen at a time,
perfectly synced to audio timestamps from Whisper.

This runs as a pre-render step and produces a list of subtitle "frames" 
that video_compositor.py draws on top of the background video.

Design: Single responsibility — only handles text grouping and style. 
        No video/audio code here.
"""

from dataclasses import dataclass, field
from engine.config import get


# ─── Caption Style Config ─────────────────────────────────────────────────────
# These are the defaults. Admin Panel can override via Supabase settings.

@dataclass
class CaptionStyle:
    # Words grouped per caption card (3 is the sweet spot for Shorts)
    words_per_card:     int   = 3

    # Font settings (font file must exist in assets/fonts/).
    # Montserrat-Variable.ttf is bundled directly in this repo (OFL-licensed,
    # from Google Fonts) — no more runtime download from a third-party GitHub
    # mirror, and no dependency on a "-ExtraBold" static file that doesn't
    # exist in the current Google Fonts release. See engine/video_compositor.py
    # _load_font(), which selects the ExtraBold named instance from it.
    font_file:          str   = "assets/fonts/Montserrat-Variable.ttf"
    font_size:          int   = 72
    font_color:         str   = "#FFFFFF"    # Primary word color (white)
    highlight_color:    str   = "#FFD700"    # Current-word highlight (gold)
    stroke_color:       str   = "#000000"    # Text outline (black) for readability
    stroke_width:       int   = 3

    # Layout — safe zone for YouTube Shorts
    # YouTube covers: bottom 20% (UI elements), right 15% (like/comment buttons)
    # We place captions in the center 60% horizontally, 45-75% vertically
    position_y_ratio:   float = 0.62        # 62% down the screen
    max_width_ratio:    float = 0.80        # Use 80% of video width max

    # Animation
    scale_on_entry:     float = 1.08        # Slight scale-up on each new card (pop effect)
    fade_in_duration:   float = 0.07        # Seconds for fade-in on each card

    # Background box behind text (improves readability)
    bg_box:             bool  = True
    bg_color:           str   = "#00000066"  # Semi-transparent black (RGBA hex)
    bg_padding:         int   = 18          # px padding around text


@dataclass
class CaptionCard:
    """A single caption card to be displayed on screen."""
    words:         list[str]        # The words in this card
    start_time:    float            # When to show (seconds from start of audio)
    end_time:      float            # When to hide
    is_hook:       bool = False     # First card gets slightly different styling

    @property
    def text(self) -> str:
        return " ".join(self.words)

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


# ─── Core Function ─────────────────────────────────────────────────────────────

def build_caption_cards(
    word_timestamps: list[dict],
    style: CaptionStyle = None
) -> list[CaptionCard]:
    """
    Groups word-level timestamps into timed caption cards.

    Args:
        word_timestamps: Output from voice_engine.generate_voiceover()
            [{"word": "Inside", "start": 0.0, "end": 0.38}, ...]
        style: CaptionStyle config. Uses defaults if None.

    Returns:
        List of CaptionCard objects ready for video_compositor.py
    """
    if style is None:
        style = CaptionStyle()

    if not word_timestamps:
        return []

    cards = []
    words_per_card = style.words_per_card
    is_first_card = True

    # Group words into batches of N
    for i in range(0, len(word_timestamps), words_per_card):
        batch = word_timestamps[i: i + words_per_card]

        words = [w["word"] for w in batch if w.get("word", "").strip()]
        if not words:
            continue

        start_time = batch[0]["start"]
        end_time   = batch[-1]["end"]

        # Tiny gap between cards to prevent visual blur
        if cards:
            cards[-1] = CaptionCard(
                words=cards[-1].words,
                start_time=cards[-1].start_time,
                end_time=min(cards[-1].end_time, start_time - 0.03),
                is_hook=cards[-1].is_hook
            )

        cards.append(CaptionCard(
            words=words,
            start_time=start_time,
            end_time=end_time,
            is_hook=is_first_card,
        ))
        is_first_card = False

    print(f"[subtitle_engine] ✓ Generated {len(cards)} caption cards")
    return cards


def get_active_card(cards: list[CaptionCard], t: float) -> CaptionCard | None:
    """
    Returns the caption card that should be displayed at time t (seconds).
    Used by the video compositor during frame-by-frame rendering.
    """
    for card in cards:
        if card.start_time <= t <= card.end_time:
            return card
    return None


def export_srt(cards: list[CaptionCard], output_path: str) -> str:
    """
    Exports caption cards as a .srt subtitle file.
    Useful for accessibility and as a bonus YouTube subtitle upload.
    """
    def fmt_time(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"

    lines = []
    for i, card in enumerate(cards, 1):
        lines.append(str(i))
        lines.append(f"{fmt_time(card.start_time)} --> {fmt_time(card.end_time)}")
        lines.append(card.text)
        lines.append("")

    content = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"[subtitle_engine] ✓ SRT exported: {output_path}")
    return output_path


# ─── Test / Debug ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Simulate word timestamps from Whisper
    sample_words = [
        {"word": "Inside", "start": 0.0, "end": 0.38},
        {"word": "this", "start": 0.38, "end": 0.52},
        {"word": "cleanroom,", "start": 0.52, "end": 0.85},
        {"word": "transistors", "start": 0.90, "end": 1.40},
        {"word": "smaller", "start": 1.40, "end": 1.75},
        {"word": "than", "start": 1.75, "end": 1.90},
        {"word": "DNA", "start": 1.90, "end": 2.30},
        {"word": "are", "start": 2.30, "end": 2.45},
        {"word": "being", "start": 2.45, "end": 2.65},
        {"word": "built.", "start": 2.65, "end": 3.10},
    ]

    cards = build_caption_cards(sample_words)
    for c in cards:
        print(f"[{c.start_time:.2f}s → {c.end_time:.2f}s] '{c.text}' (hook={c.is_hook})")

    export_srt(cards, "output/test_captions.srt")
