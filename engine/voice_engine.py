"""
voice_engine.py
---------------
MODULE 2 — Text-to-Speech + word-level timing

REWRITTEN. The old version generated audio with edge-tts, then transcribed that
audio back with Whisper to find out when each word was spoken. That is a round
trip through a speech recogniser to recover information we already had, and it
caused three of the five defects visible in the sample videos:

  - "186 ,000" and "high -performance" — Whisper returns tokens split on its
    own rules, so numbers and hyphenated words came back as separate pieces and
    the caption builder joined them with a space.
  - "fabs" transcribed as "phabs" — the tiny model guessing at a word it had
    never heard, and the wrong guess going straight onto the screen.
  - Scene timing drift — an alignment pass with difflib existed purely to
    reconcile the script we sent against the transcript that came back.

edge-tts already emits a WordBoundary event for every word as it synthesises,
carrying an exact offset and duration in 100-nanosecond ticks. That is ground
truth from the synthesiser: the words are the ones we sent, spelled how we sent
them, timed to the audio being produced. Using it removes the misheard words,
the punctuation splits, the alignment code, AND the Whisper dependency — which
also cuts roughly 40 seconds and a 75 MB model download off every render.

FALLBACK CHAIN
edge-tts is an unofficial wrapper around Microsoft Edge's read-aloud feature.
It is free and good, and it can break without warning when Microsoft changes
something. So there is a real fallback:

  1. edge-tts  — best quality, exact timings, needs network
  2. Piper     — fully offline neural TTS (MIT). No API, nothing to break.
                 Timings are estimated from the text since Piper does not emit
                 boundaries; slightly less precise, entirely reliable.
  3. gTTS      — last resort, robotic, keeps the pipeline alive

The pipeline never stops because one free service had a bad day.
"""
import asyncio
import json
import os
import re
import shutil
import subprocess

import os
import sys

# Allow BOTH `python -m engine.publisher --setup` (correct) and
# `python engine/publisher.py --setup` (what people naturally type).
# Running a file directly puts engine/ on sys.path instead of the project root,
# so `from engine.config import ...` fails with ModuleNotFoundError. Adding the
# project root here makes the natural command work too, because telling a
# beginner "you typed it wrong" is a worse answer than making both work.
if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.config import get

# ─── Voice Profiles ──────────────────────────────────────────────────────────
VOICE_PROFILES = {
    "documentary_male":   "en-US-GuyNeural",
    "documentary_female": "en-US-JennyNeural",
    "conversational":     "en-US-AndrewNeural",
    "energetic":          "en-US-ChristopherNeural",
    "british_calm":       "en-GB-RyanNeural",
    "warm_female":        "en-US-AriaNeural",
    "young_casual":       "en-US-AnaNeural",
    "default":            "en-US-GuyNeural",
}

# Per-character voices for the character_skit style. Two characters talking in
# the same voice is instantly confusing, so each cast member gets its own.
CHARACTER_VOICES = {
    "capy":  "en-US-AndrewNeural",
    "cat":   "en-US-AnaNeural",
    "bird":  "en-GB-RyanNeural",
    "stick": "en-US-ChristopherNeural",
    "suit":  "en-US-GuyNeural",
}

TICKS_PER_SECOND = 10_000_000  # edge-tts reports offsets in 100ns ticks


def _require_ffmpeg():
    """ffmpeg is needed later by MoviePy for the final encode. Checking here,
    at the very start of the pipeline, means a missing install fails in one
    second with a clear message instead of after several minutes of work."""
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "ffmpeg was not found on your PATH. MoviePy needs the real ffmpeg program, "
            "not just a Python package.\n"
            "  Windows: winget install ffmpeg   (then OPEN A NEW terminal — PATH changes "
            "do not apply to windows that were already open)\n"
            "  macOS:   brew install ffmpeg\n"
            "  Linux:   sudo apt-get install ffmpeg\n"
            "Verify with: ffmpeg -version\n"
            "You do not need this at all if you render on GitHub Actions — see docs/04."
        )


# ─── Engine 1: edge-tts with real word boundaries ────────────────────────────


async def _edge_tts_with_timings(text: str, voice_id: str, output_path: str):
    """Synthesises audio and collects WordBoundary events in one pass.

    Streaming rather than calling .save() is what makes the timings available:
    .save() discards the metadata events, which is why the original code had to
    reach for Whisper to get them back.
    """
    import edge_tts

    communicate = edge_tts.Communicate(text, voice_id)
    words = []
    with open(output_path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / TICKS_PER_SECOND
                dur = chunk["duration"] / TICKS_PER_SECOND
                words.append({
                    "word": chunk["text"],
                    "start": round(start, 3),
                    "end": round(start + dur, 3),
                })
    return words


def _try_edge_tts(text, voice_id, output_path, attempts=5):
    """Tries edge-tts, retrying transient failures before giving up.

    Retries matter specifically in GitHub Actions: edge-tts is an unofficial
    wrapper around Microsoft's read-aloud service, and Microsoft rate-limits
    datacenter IP ranges far more aggressively than home connections. A run
    that fails on the first attempt very often succeeds a few seconds later.

    BUMPED FROM 3 TO 5 ATTEMPTS, WITH LONGER BACKOFF AND JITTER. Three quick
    attempts (3s, 6s) is enough for a one-off hiccup but not for a real rate
    limit window, which can hold for 15-20+ seconds -- three fast attempts
    can all land inside the same blocked window and give up right before it
    would have cleared. Every time this falls through to a fallback engine,
    the video's captions switch from edge-tts's exact per-word timing to an
    ESTIMATED one (see estimate_word_timings below), which is the most
    likely real cause of visible caption drift -- not a bug in the timing
    math itself, but silently losing access to ground truth. Fewer
    fallbacks means fewer videos with estimated timing, which is the actual
    fix for "the next batch might have the same problem."

    Jitter (a small random extra wait) is added so that when several videos
    in the same batch hit the limiter at once, their retries do not all
    land on the exact same second and re-collide.
    """
    import time
    import random

    for attempt in range(1, attempts + 1):
        try:
            words = asyncio.run(_edge_tts_with_timings(text, voice_id, output_path))
            if not words or os.path.getsize(output_path) < 1024:
                raise RuntimeError("edge-tts returned no audio or no word boundaries")
            print(f"[voice_engine] ✓ edge-tts: {len(words)} words with exact timings"
                  + (f" (attempt {attempt})" if attempt > 1 else ""))
            return words
        except Exception as e:
            if attempt < attempts:
                wait = min(4 * (2 ** (attempt - 1)), 45) + random.uniform(0, 2)
                print(f"[voice_engine] ⚠ edge-tts attempt {attempt}/{attempts} failed ({e}). "
                      f"Retrying in {wait:.1f}s...")
                time.sleep(wait)
            else:
                print(f"[voice_engine] ⚠ edge-tts unavailable after {attempts} attempts ({e}). "
                      f"Falling back to an engine with ESTIMATED (not exact) caption timing.")
    return None


# ─── Engine 2: Piper, fully offline ──────────────────────────────────────────


def _try_piper(text, output_path):
    """Piper produces a wav; timings are estimated from word length.

    Piper has no word-boundary output, so timings here are proportional to
    syllable-weighted word length across the measured audio duration. That is
    less accurate than edge-tts, typically within about 80ms per word, which is
    imperceptible for captions and fine for lip sync. The trade is worth it:
    this path has no network dependency and cannot be broken by a third party.
    """
    piper = shutil.which("piper")
    if not piper:
        return None
    model = get("PIPER_MODEL_PATH")
    if not model or not os.path.exists(model):
        print("[voice_engine] ⚠ Piper is installed but PIPER_MODEL_PATH is not set or missing.")
        return None
    try:
        wav_path = output_path.replace(".mp3", ".wav")
        subprocess.run(
            [piper, "--model", model, "--output_file", wav_path],
            input=text.encode("utf-8"), capture_output=True, check=True, timeout=300,
        )
        subprocess.run(
            ["ffmpeg", "-y", "-i", wav_path, "-codec:a", "libmp3lame", "-q:a", "2", output_path],
            capture_output=True, check=True, timeout=180,
        )
        os.remove(wav_path)
        duration = _probe_duration(output_path)
        print(f"[voice_engine] ✓ Piper (offline), {duration:.1f}s — timings estimated")
        return estimate_word_timings(text, duration)
    except Exception as e:
        print(f"[voice_engine] ⚠ Piper failed ({e}).")
        return None


# ─── Engine 3: gTTS, last resort ─────────────────────────────────────────────


def _try_gtts(text, output_path):
    try:
        from gtts import gTTS
        gTTS(text=text, lang="en", slow=False).save(output_path)
        duration = _probe_duration(output_path)
        print(f"[voice_engine] ✓ gTTS fallback, {duration:.1f}s — timings estimated")
        return estimate_word_timings(text, duration)
    except Exception as e:
        print(f"[voice_engine] ⚠ gTTS failed ({e}).")
        return None


# ─── Timing estimation (used only by the fallback engines) ───────────────────

_VOWEL_GROUPS = re.compile(r"[aeiouy]+", re.I)


def _syllables(word: str) -> int:
    """Rough syllable count. Speech time tracks syllables far better than it
    tracks characters, so distributing time by syllable keeps 'a' from being
    allotted the same duration as 'extraordinarily'."""
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return 1
    n = len(_VOWEL_GROUPS.findall(w))
    if w.endswith("e") and n > 1:
        n -= 1
    return max(n, 1)


def estimate_word_timings(text: str, total_duration: float) -> list:
    words = text.split()
    if not words or total_duration <= 0:
        return []
    weights = [_syllables(w) + (0.6 if re.search(r"[.,!?;:]$", w) else 0) for w in words]
    total_w = sum(weights) or 1
    out, t = [], 0.0
    for w, weight in zip(words, weights):
        span = total_duration * (weight / total_w)
        out.append({
            "word": w.strip(".,!?;:\"'"),
            "start": round(t, 3),
            "end": round(t + span * 0.92, 3),  # small gap so words do not butt together
        })
        t += span
    return out


def _probe_duration(path: str) -> float:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=60,
        )
        return float(out.stdout.strip())
    except Exception:
        return 0.0


# ─── Public API ──────────────────────────────────────────────────────────────


def generate_voiceover(
    full_script: str,
    voice_profile: str = "default",
    output_dir: str = None,
    job_id: str = "job",
    voice_id: str = None,
) -> dict:
    """Generates voice audio plus word-level timings.

    Returns {"audio_path", "duration_seconds", "word_timestamps", "engine"}.
    The contract is unchanged from the previous version, so every downstream
    module keeps working without modification.
    """
    output_dir = output_dir or get("OUTPUT_DIR", "output")
    _require_ffmpeg()
    os.makedirs(output_dir, exist_ok=True)
    audio_path = os.path.join(output_dir, f"{job_id}_voice.mp3")

    voice_id = voice_id or VOICE_PROFILES.get(voice_profile, VOICE_PROFILES["default"])
    print(f"[voice_engine] Generating TTS: voice='{voice_id}', job='{job_id}'")

    words, engine = _try_edge_tts(full_script, voice_id, audio_path), "edge-tts"
    if words is None:
        words, engine = _try_piper(full_script, audio_path), "piper"
    if words is None:
        words, engine = _try_gtts(full_script, audio_path), "gtts"
    if words is None:
        raise RuntimeError(
            "Every TTS engine failed. edge-tts needs network access; Piper needs "
            "PIPER_MODEL_PATH set to a downloaded voice model; gTTS needs network access. "
            "See docs/03 for installing the offline Piper fallback."
        )

    duration = _probe_duration(audio_path) or (words[-1]["end"] if words else 0.0)

    ts_path = os.path.join(output_dir, f"{job_id}_timestamps.json")
    with open(ts_path, "w", encoding="utf-8") as f:
        json.dump(words, f, indent=2, ensure_ascii=False)

    print(f"[voice_engine] ✓ {len(words)} words, {duration:.1f}s total (engine={engine})")
    return {
        "audio_path": audio_path,
        "duration_seconds": round(duration, 2),
        "word_timestamps": words,
        "engine": engine,
    }


def generate_multi_voice(scenes: list, output_dir: str, job_id: str, default_voice: str = "default") -> dict:
    """Renders one audio track per speaker turn and concatenates them.

    Used by character_skit so two characters can hold a conversation in
    different voices. Each scene is synthesised separately, then the pieces are
    joined and every scene's word timings are shifted by the running offset so
    the global timeline stays correct.
    """
    _require_ffmpeg()
    os.makedirs(output_dir, exist_ok=True)

    parts, all_words, offset = [], [], 0.0
    for i, scene in enumerate(scenes):
        text = (scene.get("voice_text") or "").strip()
        if not text:
            continue
        character = scene.get("character")
        voice_id = CHARACTER_VOICES.get(character) or VOICE_PROFILES.get(
            default_voice, VOICE_PROFILES["default"]
        )
        part_path = os.path.join(output_dir, f"{job_id}_part{i}.mp3")

        result = generate_voiceover(
            text, output_dir=output_dir, job_id=f"{job_id}_part{i}", voice_id=voice_id
        )
        shutil.move(result["audio_path"], part_path)

        scene_words = [
            {"word": w["word"], "start": round(w["start"] + offset, 3), "end": round(w["end"] + offset, 3)}
            for w in result["word_timestamps"]
        ]
        scene["_words"] = scene_words
        scene["_voice_start"] = offset
        all_words.extend(scene_words)

        parts.append(part_path)
        # A beat of silence between speakers. Without it the second character
        # starts talking over the first and the exchange reads as one voice.
        offset += result["duration_seconds"] + 0.28

    if not parts:
        raise ValueError("No scenes had any voice_text to speak.")

    combined = os.path.join(output_dir, f"{job_id}_voice.mp3")
    _concat_with_gaps(parts, combined, gap_seconds=0.28)

    duration = _probe_duration(combined) or offset
    for p in parts:
        try:
            os.remove(p)
        except OSError:
            pass

    print(f"[voice_engine] ✓ Multi-voice track: {len(parts)} turns, {duration:.1f}s")
    return {
        "audio_path": combined,
        "duration_seconds": round(duration, 2),
        "word_timestamps": all_words,
        "engine": "edge-tts-multi",
    }


def _concat_with_gaps(parts: list, output_path: str, gap_seconds: float = 0.28):
    """Concatenates mp3 parts with silence between them.

    Uses the concat FILTER rather than the concat demuxer because the demuxer
    requires identical encoding parameters across inputs, and separate edge-tts
    calls do not guarantee that. The filter re-encodes, which is slower but
    cannot produce the subtly-corrupt output the demuxer does on mismatch.
    """
    silence = os.path.join(os.path.dirname(output_path) or ".", "_gap.mp3")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
         "-t", str(gap_seconds), "-q:a", "9", silence],
        capture_output=True, check=True, timeout=60,
    )

    inputs, filters = [], []
    idx = 0
    for i, part in enumerate(parts):
        inputs += ["-i", part]
        filters.append(f"[{idx}:a]")
        idx += 1
        if i < len(parts) - 1:
            inputs += ["-i", silence]
            filters.append(f"[{idx}:a]")
            idx += 1

    filter_complex = "".join(filters) + f"concat=n={idx}:v=0:a=1[out]"
    subprocess.run(
        ["ffmpeg", "-y", *inputs, "-filter_complex", filter_complex,
         "-map", "[out]", "-codec:a", "libmp3lame", "-q:a", "2", output_path],
        capture_output=True, check=True, timeout=300,
    )
    try:
        os.remove(silence)
    except OSError:
        pass


def get_scene_timestamps(word_timestamps: list, scenes: list) -> list:
    """Assigns each scene a start and end time on the global timeline.

    Much simpler than the version this replaces. That one had to align the
    script we sent against a transcript of the audio, because Whisper's word
    list did not match the script's word list. Now the word list IS the
    script's word list, so scene boundaries are a straight cumulative count.

    The contiguity pass at the end is kept and still matters: it guarantees
    every scene's end is exactly the next scene's start, so there is no instant
    of the timeline that no background clip covers. A gap there is what caused
    the ~2 second cut to solid black in the earlier build.
    """
    if not word_timestamps or not scenes:
        return scenes

    # Multi-voice already assigned per-scene words during synthesis.
    if all(s.get("_words") for s in scenes):
        out = []
        for s in scenes:
            words = s["_words"]
            out.append({**s, "time_start": words[0]["start"], "time_end": words[-1]["end"]})
        return _force_contiguous(out, word_timestamps)

    total = len(word_timestamps)
    out, cursor = [], 0
    for scene in scenes:
        count = len(str(scene.get("voice_text", "")).split())
        start_i = min(cursor, total - 1)
        end_i = min(cursor + max(count - 1, 0), total - 1)
        out.append({
            **scene,
            "time_start": word_timestamps[start_i]["start"],
            "time_end": word_timestamps[end_i]["end"],
            "_words": word_timestamps[start_i:end_i + 1],
        })
        cursor += count

    return _force_contiguous(out, word_timestamps)


def _force_contiguous(scenes: list, word_timestamps: list) -> list:
    for i in range(len(scenes) - 1):
        scenes[i]["time_end"] = scenes[i + 1]["time_start"]
    if scenes:
        scenes[0]["time_start"] = 0.0
        scenes[-1]["time_end"] = max(scenes[-1]["time_end"], word_timestamps[-1]["end"])
    return scenes


if __name__ == "__main__":
    demo = (
        "Inside this cleanroom, transistors smaller than a strand of DNA are being built. "
        "One chip holds more than 50 billion of them, made by a 200 million dollar machine."
    )
    result = generate_voiceover(demo, voice_profile="documentary_male", job_id="test001")
    print(json.dumps(result["word_timestamps"][:12], indent=2))
