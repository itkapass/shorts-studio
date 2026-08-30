"""
subtitle_engine.py
------------------
MODULE 4 — Word-by-word caption cards

TWO FIXES FROM THE SAMPLE-VIDEO REVIEW:

1. THE HIGHLIGHT THAT WAS NEVER WIRED UP.
   CaptionStyle has always defined `highlight_color` (gold, #FFD700) and
   nothing ever read it. Every caption rendered flat white. That is the single
   highest-value free improvement available here: the moving highlight is what
   makes short-form captions feel alive rather than like a subtitle track, and
   it measurably holds attention because the eye tracks the moving element.
   Cards now carry per-word timing, and the compositor colours whichever word
   is currently being spoken.

2. PUNCTUATION-SAFE GROUPING.
   Cards used to be built by slicing the word list into fixed groups of three,
   which cut across sentence boundaries. A card reading "dollars. High" is
   harder to read than one reading "186,000 dollars." Cards now prefer to break
   at punctuation, so each card is a readable fragment.
   (The stray-space bug in "186 ,000" is fixed upstream in voice_engine.py,
   which no longer splits words on punctuation in the first place.)
"""
from dataclasses import dataclass, field


@dataclass
class CaptionStyle:
    words_per_card:     int   = 3

    font_file:          str   = "assets/fonts/Montserrat-Variable.ttf"
    font_size:          int   = 72
    font_color:         str   = "#FFFFFF"    # words already said / not yet said
    highlight_color:    str   = "#FFD700"    # the word being spoken right now
    stroke_color:       str   = "#000000"
    stroke_width:       int   = 3

    # Layout — YouTube's UI covers the bottom ~20% and right ~15% of a Short,
    # so captions sit at 62% down, horizontally centred, inside 80% of width.
    position_y_ratio:   float = 0.62
    max_width_ratio:    float = 0.80

    scale_on_entry:     float = 1.08
    fade_in_duration:   float = 0.07

    bg_box:             bool  = True
    bg_color:           str   = "#00000066"
    bg_padding:         int   = 18

    # Set False to render flat white (the old behaviour). Kept as a switch
    # because the highlight fights for attention with the character_skit
    # style, which already has a moving face to look at.
    highlight_active_word: bool = True


@dataclass
class CaptionCard:
    """A group of words shown together, with each word's own timing so the
    renderer can highlight the one currently being spoken."""
    words:         list          # list[str]
    start_time:    float
    end_time:      float
    is_hook:       bool = False
    word_times:    list = field(default_factory=list)  # [(start, end), ...]

    @property
    def text(self) -> str:
        return " ".join(self.words)

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time

    def active_index(self, t: float) -> int:
        """Which word is being spoken at time t, or -1 between words."""
        for i, (ws, we) in enumerate(self.word_times):
            if ws <= t < we:
                return i
        return -1


_BREAK_CHARS = ".!?"
_SOFT_BREAK_CHARS = ",;:"


def build_caption_cards(word_timestamps: list, style: CaptionStyle = None) -> list:
    """Groups word timings into caption cards.

    Breaking rules, in priority order:
      1. Always break after sentence-ending punctuation.
      2. Prefer breaking after a comma if the card already has 2+ words.
      3. Otherwise break at words_per_card.
    """
    style = style or CaptionStyle()
    if not word_timestamps:
        return []

    cards, current, first = [], [], True

    def flush():
        nonlocal current, first
        if not current:
            return
        words = [w["word"] for w in current]
        times = [(float(w["start"]), float(w["end"])) for w in current]
        cards.append(CaptionCard(
            words=words,
            start_time=times[0][0],
            end_time=times[-1][1],
            is_hook=first,
            word_times=times,
        ))
        current = []
        first = False

    for w in word_timestamps:
        text = str(w.get("word", "")).strip()
        if not text:
            continue
        current.append(w)

        last_char = text[-1:]
        if last_char in _BREAK_CHARS:
            flush()
        elif last_char in _SOFT_BREAK_CHARS and len(current) >= 2:
            flush()
        elif len(current) >= style.words_per_card:
            flush()

    flush()

    # Close a 30ms gap between adjacent cards so the outgoing card is fully
    # gone before the next appears. Without it the two overlap for a frame and
    # the text visibly smears.
    for i in range(len(cards) - 1):
        cards[i].end_time = min(cards[i].end_time, cards[i + 1].start_time - 0.03)

    print(f"[subtitle_engine] ✓ Generated {len(cards)} caption cards")
    return cards


def get_active_card(cards: list, t: float):
    for card in cards:
        if card.start_time <= t <= card.end_time:
            return card
    return None


def export_srt(cards: list, output_path: str) -> str:
    """Exports an .srt. Useful for accessibility and as a YouTube subtitle
    upload — Shorts are mostly watched muted, so real captions measurably
    help watch time on top of the burned-in ones."""
    def fmt(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"

    lines = []
    for i, card in enumerate(cards, 1):
        lines += [str(i), f"{fmt(card.start_time)} --> {fmt(card.end_time)}", card.text, ""]

    content = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[subtitle_engine] ✓ SRT exported: {output_path}")
    return output_path


if __name__ == "__main__":
    sample = [
        {"word": "Inside", "start": 0.0, "end": 0.38},
        {"word": "this", "start": 0.38, "end": 0.52},
        {"word": "cleanroom,", "start": 0.52, "end": 0.85},
        {"word": "transistors", "start": 0.90, "end": 1.40},
        {"word": "smaller", "start": 1.40, "end": 1.75},
        {"word": "than", "start": 1.75, "end": 1.90},
        {"word": "186,000", "start": 1.90, "end": 2.30},
        {"word": "are", "start": 2.30, "end": 2.45},
        {"word": "built.", "start": 2.45, "end": 3.10},
    ]
    for c in build_caption_cards(sample):
        print(f"[{c.start_time:.2f} -> {c.end_time:.2f}] '{c.text}' hook={c.is_hook}")
