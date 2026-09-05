"""
backup_visuals.py — a free, on-topic image when Pexels genuinely has nothing.
==============================================================================

WHY THIS EXISTS

Pexels' free catalog is real footage of real things, which is exactly why
it sometimes has nothing that matches a specific scene. When that happens
today, visual_fetcher._get_fallback() returns clip_path=None, and
video_compositor falls back to a flat gradient — no relevant image at all.
That gap is also where the closest-but-wrong clips come from: a search for
"AI altering the technological landscape" has no literal stock footage, so
the best match Pexels can offer is something merely keyword-adjacent (a
metal grate, a generic server room) — technically related, visibly
unrelated once you're watching it.

Hugging Face hosts free, serverless text-to-image inference for open models
(Stable Diffusion / FLUX variants) — no card required. This module asks it
for an image built from the SAME visual_keyword and scene text already
being used to search Pexels, so when it's used, what's on screen actually
matches what's being said, rather than settling for the nearest real thing
that happens to share a keyword.

THIS IS A FALLBACK, NOT A REPLACEMENT FOR PEXELS
Real footage still looks more like a documentary than an AI image does, and
that is the intended look for the stock_footage style. Pexels is tried
first on every single scene, exactly as before. This is only ever reached
after Pexels has already failed — a bad search, no results, a download
error — so on a normal day, for a well-covered topic, nothing here runs at
all.

THIS IS A SAFETY NET LIKE THE GROQ ONE, SAME SHAPE
  - Silent no-op if HUGGINGFACE_API_KEY is not set — nothing about today's
    behavior changes for anyone who doesn't configure it.
  - Every clip built this way is honestly tagged source="ai_generated" in
    the same field that already distinguishes "pexels" from "cache" from
    "fallback" — nothing pretends to be real stock footage.
  - Best-effort: any failure (rate limit, cold model, network) falls
    through to the exact same flat-gradient fallback that existed before
    this file did. A slow or unavailable free image API must never be the
    reason a video doesn't get made.

HONEST LIMITS
  - Hugging Face's free serverless tier has no published, fixed rate limit
    — it flexes with overall platform load, and a "cold" model can take
    30-60+ seconds to wake up on its first request of the day. This is why
    the timeout below is generous and why every failure degrades quietly
    rather than blocking the render.
  - This generates a STILL image, not a moving clip. That is not a
    compromise for this specific style: stock_footage.py already applies
    its own slow Ken Burns zoom to whatever clip it receives, so a still
    image gets the same subtle motion a real stock clip would.
"""
import os
import subprocess
import requests

HF_INFERENCE_URL = "https://api-inference.huggingface.co/models/{model}"

# FLUX.1-schnell is Apache-2.0 and specifically built for FEW-STEP, fast
# generation — a much better fit for a background render job on the free
# tier than a full-quality, many-step model that risks the request timing
# out before an image ever comes back. Override with HUGGINGFACE_IMAGE_MODEL
# if this is ever retired or you'd rather trade speed for quality.
DEFAULT_MODEL = "black-forest-labs/FLUX.1-schnell"

TIMEOUT_SECONDS = 90  # generous: a cold model genuinely can take this long


def available() -> bool:
    from engine.config import get
    return bool(get("HUGGINGFACE_API_KEY"))


def _build_prompt(visual_keyword: str, scene_text: str) -> str:
    """Turns the same search text already sent to Pexels into an image
    prompt. Deliberately plain and literal rather than stylistically
    embellished — the goal is accuracy to the scene, not artistic flair
    that could drift from what the script actually says."""
    base = visual_keyword.strip() or scene_text.strip()[:100]
    return (
        f"{base}, cinematic photograph, realistic, high detail, natural lighting, "
        f"documentary style, no text, no watermark, no logos"
    )


def generate_scene_visual(visual_keyword: str, scene_text: str, duration_needed: float,
                          output_mp4_path: str) -> bool:
    """Generates an on-topic still image and turns it into a short video
    file at output_mp4_path, so it can flow through the EXACT SAME path a
    downloaded Pexels clip already uses — no changes needed anywhere else
    in the render pipeline. Returns True on success, False on any failure
    (never raises — this must always be safe to call speculatively).
    """
    from engine.config import get
    api_key = get("HUGGINGFACE_API_KEY")
    if not api_key:
        return False

    model = get("HUGGINGFACE_IMAGE_MODEL") or DEFAULT_MODEL
    prompt = _build_prompt(visual_keyword, scene_text)
    png_path = output_mp4_path.replace(".mp4", ".png")

    try:
        print(f"[backup_visuals] Asking Hugging Face ({model}) for: {prompt[:80]}...")
        resp = requests.post(
            HF_INFERENCE_URL.format(model=model),
            headers={
                "Authorization": f"Bearer {api_key}",
                # Waits server-side for a cold model to finish loading instead
                # of immediately returning a 503 — worth the extra wait time
                # here since this whole path only runs when Pexels already
                # failed and there is nothing better to show instead.
                "X-Wait-For-Model": "true",
            },
            json={"inputs": prompt},
            timeout=TIMEOUT_SECONDS,
        )
    except requests.RequestException as e:
        print(f"[backup_visuals] \u26a0 Request failed ({e}). Using the gradient fallback instead.")
        return False

    if not resp.ok or not resp.headers.get("content-type", "").startswith("image/"):
        print(f"[backup_visuals] \u26a0 Hugging Face returned {resp.status_code} "
              f"(not an image). Using the gradient fallback instead.")
        return False

    try:
        with open(png_path, "wb") as f:
            f.write(resp.content)
    except Exception as e:
        print(f"[backup_visuals] \u26a0 Could not save the generated image ({e}).")
        return False

    # Turn the still into a short video so it can be treated exactly like a
    # downloaded Pexels clip everywhere downstream — build_background_clip
    # already knows how to load, crop, and Ken-Burns-zoom any video file at
    # clip_path; it never needs to know this one started as a still image.
    hold_seconds = max(duration_needed + 0.5, 1.0)
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-loop", "1", "-i", png_path, "-t", str(hold_seconds),
             "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,"
                    "crop=1920:1080", "-pix_fmt", "yuv420p", "-r", "30", output_mp4_path],
            check=True, capture_output=True, timeout=30,
        )
    except Exception as e:
        print(f"[backup_visuals] \u26a0 Could not convert the image to video ({e}).")
        return False
    finally:
        if os.path.exists(png_path):
            os.remove(png_path)

    print(f"[backup_visuals] \u2713 Generated an on-topic visual for: {visual_keyword}")
    return True
