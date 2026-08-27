"""
voice_engine.py
---------------
MODULE 2 — Text-to-Speech + Word-Level Timestamp Generator

Uses Edge-TTS (Microsoft Neural Voices, $0 cost) to:
1. Generate high-quality voiceover audio (.mp3)
2. Generate a word-level subtitle file (.srt) via OpenAI Whisper (tiny model, offline, free)

To swap the voice engine: replace the edge_tts section with any other TTS API.
The output contract (audio_path + word_timestamps) stays the same for all downstream modules.
"""

import asyncio
import difflib
import json
import os
import shutil
import tempfile
from pathlib import Path

import edge_tts
import whisper

from engine.config import get


def _require_ffmpeg():
    """Whisper (and moviepy, later in the pipeline) both shell out to the
    ffmpeg binary — not the ffmpeg-python or edge-tts Python packages, an
    actual system executable on PATH. Missing it is one of the single most
    common local setup failures for this kind of project, especially on
    Windows, where it doesn't come preinstalled the way it typically does
    in Docker/CI Linux images (this project's own Dockerfile and GitHub
    Actions workflows install it explicitly for exactly that reason).

    Without this check, a missing ffmpeg surfaces ~20 seconds later as a
    bare `FileNotFoundError: [WinError 2] The system cannot find the file
    specified` from deep inside Whisper's internals — technically correct,
    not remotely obvious what it means. This fails immediately, before
    spending time on TTS + downloading the Whisper model, with a message
    that says what to actually do about it.
    """
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "ffmpeg was not found on your system PATH. Both Whisper (for caption timing) and "
            "MoviePy (for final rendering) need the real ffmpeg program installed, not just a "
            "Python package.\n"
            "Windows: winget install ffmpeg   (then OPEN A NEW terminal — PATH changes don't "
            "apply to already-open ones)\n"
            "macOS:   brew install ffmpeg\n"
            "Linux:   sudo apt-get install ffmpeg\n"
            "Verify with: ffmpeg -version   — see docs/02_FREE_AI_API_KEYS.md."
        )

# ─── Voice Profiles ──────────────────────────────────────────────────────────
# These map "voice_profile" names (set in Admin Panel) to Edge-TTS voice IDs.
# Full list: https://github.com/rany2/edge-tts#voices

VOICE_PROFILES = {
    "documentary_male":   "en-US-GuyNeural",           # Deep, authoritative narrator
    "documentary_female": "en-US-JennyNeural",         # Clear, professional narrator
    "conversational":     "en-US-AndrewNeural",        # Natural, friendly explainer
    "energetic":          "en-US-ChristopherNeural",   # Upbeat, fast-paced
    "british_calm":       "en-GB-RyanNeural",          # British accent, calm & intelligent
    "default":            "en-US-GuyNeural",
}

# Whisper model size: "tiny" runs offline in <1s on CPU, accurate enough for captions
WHISPER_MODEL_SIZE = "tiny"

# ─── Core Functions ───────────────────────────────────────────────────────────

async def _generate_tts_async(text: str, voice_id: str, output_path: str):
    """Internal async TTS generation using edge-tts."""
    communicate = edge_tts.Communicate(text, voice_id)
    await communicate.save(output_path)


def generate_voiceover(
    full_script: str,
    voice_profile: str = "default",
    output_dir: str = None,
    job_id: str = "job"
) -> dict:
    """
    Generates voice audio and word-level timestamps from the full video script.

    Args:
        full_script: The concatenated voice_text from all scenes.
        voice_profile: Key from VOICE_PROFILES dict (set in Admin Panel).
        output_dir: Directory to save audio file. Uses config OUTPUT_DIR if None.
        job_id: Unique identifier for this video job (used for file naming).

    Returns:
        {
            "audio_path": "/path/to/audio.mp3",
            "duration_seconds": 47.3,
            "word_timestamps": [
                {"word": "Inside", "start": 0.0, "end": 0.38},
                ...
            ]
        }
    """
    if output_dir is None:
        output_dir = get("OUTPUT_DIR", "output")

    _require_ffmpeg()
    
    os.makedirs(output_dir, exist_ok=True)
    audio_path = os.path.join(output_dir, f"{job_id}_voice.mp3")

    # ── Step 1: Generate TTS Audio ────────────────────────────────────────────
    voice_id = VOICE_PROFILES.get(voice_profile, VOICE_PROFILES["default"])
    print(f"[voice_engine] Generating TTS: voice='{voice_id}', job='{job_id}'")
    
    asyncio.run(_generate_tts_async(full_script, voice_id, audio_path))
    print(f"[voice_engine] ✓ Audio saved: {audio_path}")

    # ── Step 2: Generate Word-Level Timestamps via Whisper ────────────────────
    print(f"[voice_engine] Running Whisper transcription for timestamps...")
    model = whisper.load_model(WHISPER_MODEL_SIZE)
    
    result = model.transcribe(
        audio_path,
        word_timestamps=True,
        language="en",
        fp16=False,  # CPU mode — no GPU required
    )

    # Extract flat list of word timestamps from Whisper segments
    word_timestamps = []
    total_duration = 0.0
    
    for segment in result.get("segments", []):
        total_duration = max(total_duration, segment.get("end", 0))
        for word_data in segment.get("words", []):
            word_timestamps.append({
                "word":  word_data.get("word", "").strip(),
                "start": round(word_data.get("start", 0), 3),
                "end":   round(word_data.get("end", 0), 3),
            })

    # Save timestamps as JSON alongside audio (useful for debugging)
    ts_path = os.path.join(output_dir, f"{job_id}_timestamps.json")
    with open(ts_path, "w") as f:
        json.dump(word_timestamps, f, indent=2)

    print(f"[voice_engine] ✓ Timestamps generated: {len(word_timestamps)} words, {total_duration:.1f}s total")

    return {
        "audio_path":       audio_path,
        "duration_seconds": round(total_duration, 2),
        "word_timestamps":  word_timestamps,
    }


def get_scene_timestamps(word_timestamps: list, scenes: list) -> list:
    """
    Maps word-level timestamps to scenes.

    FIXED: this used to assume scene N's position in the ORIGINAL script text
    (by character count) maps proportionally onto WHISPER's returned word
    list — i.e. it assumed Whisper transcribes with the exact same word
    count and character-density as the original script. It usually doesn't:
    numbers, contractions, and mispronounced technical terms all make
    Whisper's word count drift from a naive split of the source text, and
    that drift compounds scene-to-scene, so later scenes could land
    noticeably off — visual cuts happening slightly before/after what's
    actually being said, or occasionally a small black-frame gap between
    scenes.

    Now uses difflib to actually align the expected script's words against
    what Whisper transcribed, and only falls back to proportional guessing
    for the (usually small) stretches where no confident alignment exists —
    e.g. right where Whisper genuinely dropped or added a word.
    """
    if not word_timestamps:
        return scenes

    total_words = len(word_timestamps)

    def _norm(w: str) -> str:
        return w.strip().lower().strip(".,!?;:\"'\u2014\u2013")

    whisper_words = [_norm(w.get("word", "")) for w in word_timestamps]

    scene_word_lists = [scene["voice_text"].split() for scene in scenes]
    scene_word_counts = [len(w) for w in scene_word_lists]
    expected_words = [_norm(w) for words in scene_word_lists for w in words]

    matcher = difflib.SequenceMatcher(a=expected_words, b=whisper_words, autojunk=False)
    expected_to_whisper = {}
    for block in matcher.get_matching_blocks():
        for i in range(block.size):
            expected_to_whisper[block.a + i] = block.b + i

    n_expected = max(len(expected_words), 1)

    def nearest_whisper_index(expected_idx: int) -> int:
        for radius in range(0, n_expected + 1):
            for cand in (expected_idx - radius, expected_idx + radius):
                if cand in expected_to_whisper:
                    return min(max(expected_to_whisper[cand] + (expected_idx - cand), 0), total_words - 1)
        return min(int((expected_idx / n_expected) * total_words), total_words - 1)  # last-resort fallback

    scenes_enriched = []
    cursor = 0
    for scene, word_count in zip(scenes, scene_word_counts):
        start_idx = cursor
        end_idx = cursor + max(word_count - 1, 0)
        cursor += word_count

        word_start_idx = min(max(nearest_whisper_index(start_idx), 0), total_words - 1)
        word_end_idx = min(max(nearest_whisper_index(end_idx), word_start_idx), total_words - 1)

        scenes_enriched.append({
            **scene,
            "time_start": word_timestamps[word_start_idx]["start"],
            "time_end":   word_timestamps[word_end_idx]["end"],
        })

    # FIXED: confirmed by inspecting rendered output frame-by-frame — even
    # with real alignment (above) instead of pure proportional guessing,
    # adjacent scenes' independently-computed boundaries don't always touch
    # exactly. The result wasn't a crash or an obviously-wrong cut; it was a
    # ~2 second hole where NO background clip was scheduled at all.
    # CompositeVideoClip's canvas for time no clip covers is solid black,
    # and captions are timed separately from scene boundaries (directly off
    # word timestamps), so the caption kept playing right through it —
    # which is exactly what made it look like a clean, silent cut to a
    # black screen mid-sentence instead of an obvious glitch. Force perfect
    # contiguity as a final pass: every scene's end IS the next scene's
    # start, full stop, so there is no time position any background clip
    # doesn't cover.
    for i in range(len(scenes_enriched) - 1):
        scenes_enriched[i]["time_end"] = scenes_enriched[i + 1]["time_start"]
    if scenes_enriched:
        scenes_enriched[-1]["time_end"] = max(
            scenes_enriched[-1]["time_end"], word_timestamps[-1]["end"]
        )

    return scenes_enriched


# ─── Test / Debug ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    test_script = (
        "Inside this cleanroom, transistors smaller than a strand of DNA are being born. "
        "One single chip holds more than 50 billion of them. "
        "The machine that makes this possible costs 200 million dollars. "
        "It uses extreme ultraviolet light — the same wavelength as X-rays — "
        "focused to a dot one thousand times thinner than a human hair. "
        "And there are only a handful of them on the entire planet."
    )

    result = generate_voiceover(test_script, voice_profile="documentary_male", job_id="test001")
    print(json.dumps(result, indent=2, default=str))
