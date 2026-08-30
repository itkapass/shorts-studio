"""
lipsync.py — turns spoken words into mouth shapes over time.
============================================================

APPROACH, AND WHY NOT THE OBVIOUS ONE
The obvious approach is amplitude-driven: read the waveform, open the mouth
when it is loud. It is one line of numpy and it looks wrong, because loudness
and mouth shape are only loosely related — "shhh" is quiet with a wide mouth,
"b" is a loud burst with a closed one. The mouth ends up pulsing on the beat
of the audio rather than on the speech, which reads as a puppet, not a talker.

This instead does grapheme-to-viseme mapping. We already know the exact words
and their exact start/end times (voice_engine.py gets those from the TTS engine
itself, not from transcribing audio back). So each word is split into its
letters, each letter maps to one of six mouth shapes, and the shapes are laid
out evenly across that word's own time span. The result tracks the actual
phonetics, costs nothing, needs no model, and cannot drift out of sync because
it is anchored to the same timestamps the captions use.

It is not phonetically perfect — English spelling is not phonetic, so "though"
gets mapped naively. That does not matter at 30fps on a phone screen: what the
eye checks is whether the mouth moves in step with the voice and closes when
the voice stops. Both hold here.

CO-ARTICULATION
Real mouths do not snap between shapes; they blend. `_smooth` inserts a REST
between shapes that are far apart in openness, and holds shapes for a minimum
number of frames so the mouth never strobes on fast syllables.
"""
from .library import VISEME_ORDER

# Letter -> viseme. Consonants that visibly close the lips matter most; the
# rest resolve to a neutral small opening.
_LETTER_VISEME = {
    "a": "AA", "e": "EE", "i": "EE", "o": "OO", "u": "OO", "y": "EE",
    "m": "MBP", "b": "MBP", "p": "MBP",
    "f": "EE", "v": "EE",
    "w": "OO", "r": "OO", "q": "OO",
    "l": "AA", "d": "EE", "t": "EE", "n": "EE", "s": "EE", "z": "EE",
    "c": "EE", "k": "EE", "g": "EE", "h": "AA", "j": "EE", "x": "EE",
}

# How open each viseme is (0 = shut). Used to decide when a blend is needed.
_OPENNESS = {"REST": 0.0, "MBP": 0.0, "EE": 0.3, "OO": 0.5, "AA": 0.8, "OH": 1.0}

MIN_HOLD_FRAMES = 2      # a shape must survive at least this long
FPS_ASSUMED = 30


def visemes_for_word(word: str) -> list:
    """Reduces a word to the sequence of mouth shapes worth showing.

    Runs of the same shape collapse (the mouth does not re-form for "ss"), and
    the sequence is capped so a long word does not machine-gun through twelve
    shapes in half a second.
    """
    seq = []
    for ch in word.lower():
        v = _LETTER_VISEME.get(ch)
        if not v:
            continue
        if seq and seq[-1] == v:
            continue
        seq.append(v)
    if not seq:
        return ["AA"]
    # An open vowel somewhere in the word makes speech read as speech. If a
    # word mapped entirely to closed/narrow shapes, force one open frame.
    if all(_OPENNESS[v] < 0.4 for v in seq):
        seq[len(seq) // 2] = "AA"
    return seq[:6]


def build_viseme_timeline(word_timestamps: list, fps: int = FPS_ASSUMED) -> list:
    """Builds a list of (start_seconds, end_seconds, viseme) covering the whole
    narration, including closed-mouth gaps between words.

    word_timestamps: [{"word": str, "start": float, "end": float}, ...]
    """
    if not word_timestamps:
        return []

    frame = 1.0 / max(fps, 1)
    min_hold = MIN_HOLD_FRAMES * frame
    out = []
    prev_end = 0.0

    for w in word_timestamps:
        start = float(w.get("start", 0.0))
        end = float(w.get("end", start))
        text = str(w.get("word", "")).strip()

        # Silence between words: mouth shuts. This is the single biggest cue
        # that sells the sync — a mouth that keeps moving through pauses reads
        # as broken instantly, even to someone not paying attention.
        if start - prev_end > 0.08:
            out.append((prev_end, start, "REST"))

        span = max(end - start, frame)
        seq = visemes_for_word(text)

        # If the word is too short to show every shape at minimum hold, drop
        # shapes rather than flashing them for one frame.
        max_shapes = max(int(span / min_hold), 1)
        if len(seq) > max_shapes:
            step = len(seq) / max_shapes
            seq = [seq[int(i * step)] for i in range(max_shapes)]

        slice_len = span / len(seq)
        for i, v in enumerate(seq):
            out.append((start + i * slice_len, start + (i + 1) * slice_len, v))

        prev_end = end

    out.append((prev_end, prev_end + 1.0, "REST"))
    return _smooth(out, frame)


def _smooth(timeline: list, frame: float) -> list:
    """Inserts brief transitional shapes between jumps that are too large.

    Going straight from a shut mouth (MBP) to a wide one (OH) in one frame
    pops. A single intermediate frame removes that without anyone consciously
    noticing it is there.
    """
    if len(timeline) < 2:
        return timeline
    out = [timeline[0]]
    for cur in timeline[1:]:
        prev = out[-1]
        jump = abs(_OPENNESS.get(cur[2], 0.4) - _OPENNESS.get(prev[2], 0.4))
        gap = cur[0] - prev[1]
        if jump > 0.6 and gap < frame and (cur[1] - cur[0]) > 2 * frame:
            mid = "EE" if _OPENNESS.get(cur[2], 0) > _OPENNESS.get(prev[2], 0) else "EE"
            out.append((cur[0], cur[0] + frame, mid))
            out.append((cur[0] + frame, cur[1], cur[2]))
        else:
            out.append(cur)
    return out


def viseme_at(timeline: list, t: float, default: str = "REST") -> str:
    """Looks up the mouth shape at time t.

    Linear scan is deliberate: a 45-second video has a few hundred entries and
    this is called once per frame, so the total cost is trivial and the code
    stays obvious. If this ever runs on multi-minute videos, replace with
    bisect on a precomputed start-time list.
    """
    for start, end, v in timeline:
        if start <= t < end:
            return v
    return default


def blink_schedule(total_duration: float, seed: int = 0) -> list:
    """Returns (start, end) windows where the eyes should be shut.

    A character that never blinks looks dead, and one that blinks on a fixed
    metronome looks mechanical. Humans blink roughly every 2-6 seconds, so
    this jitters the interval deterministically off `seed` — same character in
    the same video always blinks identically, which keeps renders reproducible.
    """
    import random
    rnd = random.Random(seed or 1)
    out = []
    t = rnd.uniform(1.0, 2.5)
    while t < total_duration:
        out.append((t, t + 0.12))
        t += rnd.uniform(2.0, 6.0)
    return out


def is_blinking(schedule: list, t: float) -> bool:
    for start, end in schedule:
        if start <= t < end:
            return True
    return False
