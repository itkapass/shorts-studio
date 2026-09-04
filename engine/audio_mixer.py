"""
audio_mixer.py
--------------
MODULE 5 — Audio Mixer (Voiceover + Background Music + Sound FX)

Mixes three audio layers into one final audio track:
1. Voiceover (from voice_engine.py)  — primary layer
2. Background music (from assets/music/) — auto-ducked under voiceover
3. Sound FX (scene transitions)      — layered at correct timestamps

Audio Ducking:
  - When voice is speaking: music plays at 15% volume
  - During pauses (>0.3s silence): music rises to 35% volume
  - Smooth volume ramp over 0.2s to prevent jarring cuts

To swap audio engine: Replace moviepy AudioFileClip usage with pydub or ffmpeg-python.
"""

import os
import random
from pathlib import Path
from moviepy.editor import AudioFileClip, CompositeAudioClip
from moviepy.audio.AudioClip import AudioClip
import numpy as np
from engine.config import get


# ─── Volume Constants ──────────────────────────────────────────────────────────
MUSIC_VOLUME_UNDER_VOICE = 0.12   # 12% when narration is speaking
MUSIC_VOLUME_DURING_PAUSE = 0.32  # 32% during natural pauses
SFX_VOLUME = 0.55                  # Sound effects volume
FADE_DURATION = 0.25              # Seconds to ramp volume up/down

# Minimum silence duration (seconds) before music rises
MIN_PAUSE_DURATION = 0.35


# ─── Core Function ─────────────────────────────────────────────────────────────

def mix_audio(
    voiceover_path: str,
    word_timestamps: list[dict],
    scene_timestamps: list[dict],
    total_duration: float,
    output_path: str,
    music_style: str = "ambient_tech",
) -> str:
    """
    Mixes voiceover + background music + SFX into a final audio file.

    Args:
        voiceover_path:   Path to the TTS audio file (.mp3)
        word_timestamps:  Word-level timestamps (edge-tts ground truth when
                          available, else estimated — see voice_engine.py)
                          used for ducking calculations
        scene_timestamps: Scene timing data (for placing SFX on transitions)
        total_duration:   Total video duration in seconds
        output_path:      Path for the output mixed audio file (.mp3)
        music_style:      Key for selecting music track type

    Returns:
        output_path (string) of the mixed audio file.
    """
    print(f"[audio_mixer] Mixing audio: {total_duration:.1f}s video...")

    # ── Load voiceover ─────────────────────────────────────────────────────────
    voice = AudioFileClip(voiceover_path)

    # ── Select & Load Background Music ────────────────────────────────────────
    music_clip = _load_music_track(music_style, total_duration)

    # ── Apply Audio Ducking to Music ──────────────────────────────────────────
    if music_clip:
        ducked_music = _apply_ducking(music_clip, word_timestamps, total_duration)
    else:
        ducked_music = None

    # ── Load & Place Sound Effects ─────────────────────────────────────────────
    sfx_clips = _load_sfx_clips(scene_timestamps)

    # ── Composite All Layers ───────────────────────────────────────────────────
    audio_layers = [voice]
    if ducked_music:
        audio_layers.append(ducked_music)
    audio_layers.extend(sfx_clips)

    final_audio = CompositeAudioClip(audio_layers)
    final_audio = final_audio.set_duration(total_duration)

    # ── Add fade in/out to entire mix ─────────────────────────────────────────
    final_audio = final_audio.audio_fadein(0.3).audio_fadeout(0.5)

    # ── Export ─────────────────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    final_audio.write_audiofile(output_path, fps=44100, nbytes=2, logger=None)

    # Cleanup
    voice.close()
    if music_clip:
        music_clip.close()
    final_audio.close()

    print(f"[audio_mixer] ✓ Mixed audio saved: {output_path}")
    return output_path


# ─── Internal Helpers ──────────────────────────────────────────────────────────

def _load_music_track(style: str, duration: float) -> AudioFileClip | None:
    """Picks a random music track from the assets/music/ directory."""
    music_dir = os.path.join(get("ASSETS_DIR", "assets"), "music")

    if not os.path.isdir(music_dir):
        print(f"[audio_mixer] ⚠ No music directory found at: {music_dir}")
        return None

    # Find all mp3 files
    tracks = list(Path(music_dir).glob("*.mp3")) + list(Path(music_dir).glob("*.wav"))
    if not tracks:
        print(f"[audio_mixer] ⚠ No music tracks found. Add .mp3 files to assets/music/")
        return None

    track_path = str(random.choice(tracks))
    print(f"[audio_mixer] Using music track: {os.path.basename(track_path)}")

    try:
        music = AudioFileClip(track_path)
        # Loop if track is shorter than video
        if music.duration < duration:
            loops = int(np.ceil(duration / music.duration))
            from moviepy.audio.fx.audio_loop import audio_loop
            music = audio_loop(music, nloops=loops)
        music = music.subclip(0, duration)
        return music
    except Exception as e:
        print(f"[audio_mixer] ⚠ Could not load music: {e}")
        return None


def _apply_ducking(
    music: AudioFileClip,
    word_timestamps: list[dict],
    total_duration: float
) -> AudioFileClip:
    """
    Returns music clip with volume ducked based on speech activity.

    FIXED: this used to be a hard step function — FADE_DURATION was defined
    at module level but never referenced anywhere, so volume jumped
    instantly between the two levels at every word boundary despite the
    docstring's promise of a "smooth ramp." It also only sampled t[0] for
    an entire audio processing chunk, applying one flat volume across the
    whole chunk, which could add an audible stepping artifact on top of
    that. Both are fixed here: a smoothed volume envelope is precomputed
    once (using FADE_DURATION as the actual ramp width, via convolution
    with a Hann window — no hard edges left in the signal), and it's
    applied per-sample across each chunk rather than per-chunk.
    """
    if not word_timestamps:
        return music.volumex(MUSIC_VOLUME_UNDER_VOICE)

    speaking_ranges = [(w["start"], w["end"]) for w in word_timestamps]

    dt = 0.02  # 50 Hz envelope resolution — smooth enough for audio, cheap to compute
    n_samples = max(int(total_duration / dt) + 2, 2)
    times = np.linspace(0, total_duration, n_samples)

    raw = np.zeros(n_samples)
    for start, end in speaking_ranges:
        raw[(times >= start - 0.05) & (times <= end + 0.05)] = 1.0

    kernel_half_width = max(int(FADE_DURATION / dt), 1)
    kernel = np.hanning(kernel_half_width * 2 + 1)
    kernel = kernel / kernel.sum()
    smoothed = np.clip(np.convolve(raw, kernel, mode="same"), 0.0, 1.0)

    envelope = MUSIC_VOLUME_DURING_PAUSE + (MUSIC_VOLUME_UNDER_VOICE - MUSIC_VOLUME_DURING_PAUSE) * smoothed

    def volume_at(t_scalar):
        idx = int(np.clip(t_scalar / dt, 0, n_samples - 1))
        return envelope[idx]

    def make_volume_array(get_frame, t):
        frame = get_frame(t)
        if np.isscalar(t):
            return frame * volume_at(t)
        vols = np.array([volume_at(tt) for tt in t])
        if frame.ndim == 2:  # stereo frames: (n_samples, n_channels)
            vols = vols[:, None]
        return frame * vols

    return music.fl(make_volume_array, keep_duration=True)


def _load_sfx_clips(scene_timestamps: list[dict]) -> list:
    """Loads and positions sound effects at scene transition points."""
    sfx_dir = os.path.join(get("ASSETS_DIR", "assets"), "sfx")
    sfx_clips = []

    if not os.path.isdir(sfx_dir):
        return sfx_clips

    for scene in scene_timestamps:
        sfx_name = scene.get("sfx", "none")
        if sfx_name == "none":
            continue

        sfx_path = os.path.join(sfx_dir, f"{sfx_name}.mp3")
        if not os.path.exists(sfx_path):
            print(f"[audio_mixer] ⚠ SFX not found: {sfx_path} (skipping)")
            continue

        try:
            sfx = AudioFileClip(sfx_path)
            sfx = sfx.volumex(SFX_VOLUME)
            # Play SFX at the start of each scene transition
            scene_start = scene.get("time_start", 0)
            sfx = sfx.set_start(scene_start)
            sfx_clips.append(sfx)
        except Exception as e:
            print(f"[audio_mixer] ⚠ Could not load SFX '{sfx_name}': {e}")

    return sfx_clips


# ─── Test / Debug ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # This requires actual audio files to test
    # Run voice_engine.py first to generate test001_voice.mp3
    print("[audio_mixer] Module loaded. Run via orchestrator.py for full test.")
