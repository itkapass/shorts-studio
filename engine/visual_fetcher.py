"""
visual_fetcher.py
-----------------
MODULE 3 — Background Video & B-Roll Fetcher

Fetches HD stock footage from Pexels API (free, no cost) for each scene.
Each scene gets its OWN clip based on its unique visual_keyword.
This guarantees visual variety and prevents the "repetitive stock footage" YPP rejection.

To swap providers: Replace pexels_ functions with Pixabay, Coverr, or a custom generator.
The output contract (list of local video file paths) stays the same.
"""

import os
import random
import hashlib
import requests
from pathlib import Path
from engine.config import require, get

# ─── Constants ────────────────────────────────────────────────────────────────

PEXELS_VIDEO_API = "https://api.pexels.com/videos/search"

# YouTube Shorts is 9:16 vertical. We prefer landscape source clips (1920x1080)
# and will rotate/crop them in the compositor. Avoid vertical clips (they crop badly).
PREFERRED_MIN_WIDTH  = 1920
PREFERRED_MIN_HEIGHT = 1080
PREFERRED_ORIENTATION = "landscape"  # Pexels filter

# Fallback: If no good clip found, use a clean tech-themed gradient animation
# (rendered in video_compositor.py) instead of a blank screen
FALLBACK_CLIP_TYPE = "gradient_animation"

# Cache folder: avoid re-downloading the same clip for the same keyword
CLIP_CACHE_DIR = os.path.join(get("OUTPUT_DIR", "output"), "clip_cache")


# ─── Core Functions ────────────────────────────────────────────────────────────

def fetch_clip_for_scene(
    visual_keyword: str,
    duration_needed: float,
    job_id: str = "job",
    scene_number: int = 1
) -> dict:
    """
    Fetches the best matching video clip for a scene's visual keyword.

    Args:
        visual_keyword: Pexels search term (e.g., "silicon wafer semiconductor cleanroom")
        duration_needed: How many seconds this scene needs (clip will be looped if shorter)
        job_id:         Unique job identifier for file naming
        scene_number:   Scene index (for logging)

    Returns:
        {
            "clip_path": "/path/to/downloaded.mp4",
            "source": "pexels" | "cache" | "fallback",
            "duration": 15.3,
            "keyword_used": "silicon wafer semiconductor cleanroom"
        }
    """
    cfg = require(["PEXELS_API_KEY"])
    os.makedirs(CLIP_CACHE_DIR, exist_ok=True)

    # Check cache first (hash the keyword to get a stable filename)
    cache_key = hashlib.md5(visual_keyword.encode()).hexdigest()[:12]
    cached_path = os.path.join(CLIP_CACHE_DIR, f"{cache_key}.mp4")

    if os.path.exists(cached_path):
        print(f"[visual_fetcher] Scene {scene_number}: Using cached clip for '{visual_keyword}'")
        return {
            "clip_path":    cached_path,
            "source":       "cache",
            "keyword_used": visual_keyword,
        }

    # ── Search Pexels API ─────────────────────────────────────────────────────
    print(f"[visual_fetcher] Scene {scene_number}: Searching Pexels for '{visual_keyword}'...")

    headers = {"Authorization": cfg["PEXELS_API_KEY"]}
    params = {
        "query":       visual_keyword,
        "per_page":    10,
        "orientation": PREFERRED_ORIENTATION,
        "size":        "large",  # HD+
    }

    try:
        resp = requests.get(PEXELS_VIDEO_API, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"[visual_fetcher] ⚠ Pexels API error: {e}. Using fallback.")
        return _get_fallback(job_id, scene_number)

    videos = data.get("videos", [])
    if not videos:
        print(f"[visual_fetcher] ⚠ No results for '{visual_keyword}'. Trying broader query...")
        # Try a simplified 1-2 word version of the query
        simple_query = " ".join(visual_keyword.split()[:2])
        params["query"] = simple_query
        try:
            resp = requests.get(PEXELS_VIDEO_API, headers=headers, params=params, timeout=15)
            data = resp.json()
            videos = data.get("videos", [])
        except Exception:
            pass

    if not videos:
        print(f"[visual_fetcher] ⚠ Still no results. Using fallback.")
        return _get_fallback(job_id, scene_number)

    # ── Select Best Clip ──────────────────────────────────────────────────────
    # Prefer clips that are >= duration_needed (no looping), or take the longest available
    clip = _select_best_clip(videos, duration_needed)
    if not clip:
        return _get_fallback(job_id, scene_number)

    # ── Download Clip ─────────────────────────────────────────────────────────
    video_url = clip["url"]
    print(f"[visual_fetcher] ✓ Downloading: {clip['width']}x{clip['height']}px @ {clip['fps']}fps")

    try:
        vid_resp = requests.get(video_url, stream=True, timeout=60)
        vid_resp.raise_for_status()
        with open(cached_path, "wb") as f:
            for chunk in vid_resp.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)
        print(f"[visual_fetcher] ✓ Saved to cache: {cached_path}")
    except Exception as e:
        print(f"[visual_fetcher] ⚠ Download failed: {e}. Using fallback.")
        return _get_fallback(job_id, scene_number)

    return {
        "clip_path":    cached_path,
        "source":       "pexels",
        "keyword_used": visual_keyword,
    }


def fetch_all_scene_clips(scenes_with_times: list, job_id: str) -> list:
    """
    Fetches a unique clip for every scene in the storyboard.
    Returns scenes list with clip_path added to each scene.
    """
    enriched_scenes = []
    used_keywords = set()

    for scene in scenes_with_times:
        keyword = scene["visual_keyword"]

        # If two scenes have the same keyword, add a modifier to vary the clip
        if keyword in used_keywords:
            modifiers = ["close up", "wide shot", "aerial view", "time lapse", "abstract"]
            keyword = f"{keyword} {random.choice(modifiers)}"

        used_keywords.add(scene["visual_keyword"])

        duration_needed = scene.get("time_end", 10) - scene.get("time_start", 0)
        duration_needed = max(duration_needed, 3.0)  # minimum 3 seconds

        clip_info = fetch_clip_for_scene(
            visual_keyword=keyword,
            duration_needed=duration_needed,
            job_id=job_id,
            scene_number=scene["scene_number"]
        )

        enriched_scenes.append({**scene, **clip_info})

    return enriched_scenes


# ─── Internal Helpers ──────────────────────────────────────────────────────────

def _select_best_clip(videos: list, duration_needed: float) -> dict | None:
    """Selects the best video file from Pexels results."""
    candidates = []

    for video in videos:
        for file in video.get("video_files", []):
            w = file.get("width", 0)
            h = file.get("height", 0)
            if w >= PREFERRED_MIN_WIDTH and h >= PREFERRED_MIN_HEIGHT:
                candidates.append({
                    "url":      file["link"],
                    "width":    w,
                    "height":   h,
                    "fps":      file.get("fps", 25),
                    "duration": video.get("duration", 0),
                })

    if not candidates:
        # Loosen requirements — accept any reasonable resolution
        for video in videos:
            for file in video.get("video_files", []):
                if file.get("width", 0) >= 1280:
                    candidates.append({
                        "url":      file["link"],
                        "width":    file["width"],
                        "height":   file.get("height", 720),
                        "fps":      file.get("fps", 25),
                        "duration": video.get("duration", 0),
                    })

    if not candidates:
        return None

    # Prefer clips >= duration_needed (don't need looping)
    long_enough = [c for c in candidates if c["duration"] >= duration_needed]
    if long_enough:
        return random.choice(long_enough)

    # Take the longest available otherwise
    return max(candidates, key=lambda c: c["duration"])


def _get_fallback(job_id: str, scene_number: int) -> dict:
    """Returns a fallback indicator when no clip is found."""
    return {
        "clip_path":    None,
        "source":       FALLBACK_CLIP_TYPE,
        "keyword_used": "fallback",
    }


# ─── Test / Debug ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    result = fetch_clip_for_scene(
        visual_keyword="silicon wafer semiconductor cleanroom",
        duration_needed=8.5,
        job_id="test001",
        scene_number=1
    )
    print(result)
