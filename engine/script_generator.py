"""
script_generator.py
-------------------
MODULE 1 — AI Script & Storyboard Generator

Uses Google Gemini to generate a structured, N-scene video storyboard.
Style-aware: stock_footage scenes get a Pexels visual_keyword; whiteboard_sketch
scenes get an `icons` list drawn from engine.styles.icon_library's vocabulary;
quote_card scenes need neither (just voice_text + visual_mood).

FIXED (see PROJECT review notes):
- Model was hardcoded to "gemini-1.5-flash", a generation now behind even
  gemini-2.0 (retired) and gemini-2.5 (scheduled to retire Oct 2026) — very
  likely already returning 404s. Now reads GEMINI_MODEL from the environment
  with a current default, and raises a clear, actionable error (pointing at
  the env var and the deprecations page) instead of a bare SDK traceback when
  a model name stops working — this WILL happen again; model names on a
  ~4-6 month deprecation cycle is a known, documented property of this API.
- estimated_cpm was in the v2 schema as an LLM-invented number with no basis
  in real ad-auction data, and the Trending Radar / Create Video admin pages
  displayed it as if it were a forecast. Removed from the schema entirely —
  don't fabricate financial numbers and present them as data.
- The "monetization_cta" default was literally "Comment Trigger & Follow for
  Wealth Breakdowns" — textbook engagement bait ("comment X and I'll DM
  you..."), which YouTube's spam/engagement-bait policies discourage. Default
  CTA guidance now asks for a genuine, specific reason to keep watching /
  subscribe rather than a bare engagement-farming instruction. Still fully
  overridable per call if you want a different CTA style.
- Missing-field handling used to silently default EVERY field (including
  voice_text — the one field a scene cannot function without) to an empty
  string. That's a silent content bug, not resilience: an empty voice_text
  scene contributes nothing to the narration and nobody finds out until they
  watch the finished video. voice_text now fails loudly again; cosmetic
  fields (transition, sfx) still get safe defaults.
"""

import json
import re
import time
from google import genai
from google.genai import types, errors
from engine.config import require, get
from engine.styles.icon_library import available_icon_names

# gemini-1.5-flash (the previous hardcoded value) is almost certainly
# retired by now — Google moved the Flash line through 2.0 -> 2.5 -> 3.x,
# shutting down predecessors as it goes. Override via GEMINI_MODEL without
# touching code. Check https://ai.google.dev/gemini-api/docs/models for the
# current lineup and https://ai.google.dev/gemini-api/docs/deprecations
# before assuming this default still resolves.
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"

# HTTP codes worth retrying: transient server-side conditions that usually
# clear up within seconds (confirmed in practice — "503 UNAVAILABLE...
# currently experiencing high demand" killed every single video in a batch
# with zero retries before this fix, even though it's explicitly described
# as temporary). NOT retried: 404 (bad/deprecated model name), 400 (bad
# request), 403 (bad API key) — retrying those just wastes time on
# something a retry can't fix.
RETRYABLE_CODES = {503, 500, 429}
MAX_RETRIES = 4
RETRY_BACKOFF_SECONDS = 3  # doubles each attempt: 3s, 6s, 12s, 24s


def _get_client():
    """Returns (client, model_name). NOTE: this project previously used the
    `google.generativeai` package, which — as of testing this fix — prints:
        'All support for the `google.generativeai` package has ended.
         Please switch to the `google.genai` package as soon as possible.'
    That's not just a stale model string, it's the whole SDK reaching
    end-of-life. Migrated to `google.genai` (the current package) here."""
    cfg = require(["GEMINI_API_KEY"])
    client = genai.Client(api_key=cfg["GEMINI_API_KEY"])
    model_name = get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    return client, model_name


def _call_model_with_clear_errors(client, model_name, system_prompt, user_prompt):
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return client.models.generate_content(
                model=model_name,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    temperature=0.9,
                    top_p=0.95,
                ),
            )
        except errors.APIError as e:
            last_error = e
            code = getattr(e, "code", None)
            if code == 404 or "not found" in str(e).lower() or "deprecated" in str(e).lower():
                raise RuntimeError(
                    f"Gemini model call failed, likely because the model name is no longer "
                    f"available: {e}\n"
                    f"Fix: set GEMINI_MODEL to a currently-supported model name. Check "
                    f"https://ai.google.dev/gemini-api/docs/models for the current lineup. "
                    f"This project's default is '{model_name}'."
                ) from e
            if code in RETRYABLE_CODES and attempt < MAX_RETRIES:
                wait = RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1))
                print(f"[script_generator] \u26a0 Gemini returned {code} (attempt {attempt}/{MAX_RETRIES}), "
                      f"this is usually temporary — retrying in {wait}s...")
                time.sleep(wait)
                continue
            raise
    raise last_error


# ─── Prompt Templates ────────────────────────────────────────────────────────

def _build_system_prompt(render_style: str, num_scenes: int) -> str:
    if render_style == "whiteboard_sketch":
        visual_field = (
            f'"icons": ["1 to 3 icon names from this exact list — nothing else: '
            f'{", ".join(available_icon_names())}"]'
        )
        visual_rule = (
            "5. VISUALS: this is a hand-drawn whiteboard-explainer video. Each scene shows "
            "1-3 simple line icons drawn from the fixed vocabulary provided — pick the ones "
            "that best represent the scene's idea. Do not invent icon names."
        )
    elif render_style == "quote_card":
        visual_field = ""
        visual_rule = (
            "5. VISUALS: this is a minimal text-only quote-card video (no footage, no icons) — "
            "the words themselves have to carry all the weight. Write with that in mind: vivid, "
            "quotable, rhythmic language."
        )
    else:  # stock_footage
        visual_field = (
            '"visual_keyword": "Specific stock footage search phrase (e.g. '
            '\'silicon wafer cleanroom glow\', \'server room blue light corridor\')"'
        )
        visual_rule = (
            "5. VISUALS: stock footage sites only have real footage of real, physical things — "
            "machines, wires, factories, hardware, environments. They do NOT have footage of "
            "abstract ideas (a 'concept', a 'mechanism', 'data flowing', 'the internet'). For "
            "every scene, name a concrete, physical, filmable subject — if the sentence is about "
            "something abstract, pick the closest real object/place/action a camera could "
            "actually point at (e.g. for 'the algorithm decides' use 'server rack blinking "
            "lights close up', not 'algorithm decision visualization'). Never describe a person "
            "wearing/modeling equipment (goggles, lab coats, gloves) as the main subject — stock "
            "sites return generic portrait/lifestyle photography for those, not the technical "
            "subject you actually want. Prefer machines, objects, and environments over people."
        )

    scene_fields = ',\n      '.join(filter(None, [
        '"scene_number": 1',
        '"voice_text": "The exact words spoken in this scene."',
        visual_field,
        '"visual_mood": "dark|bright|neutral|dramatic"',
        '"sfx": "none|whoosh|digital_pop|riser|glitch|impact"',
        '"transition": "cut|fade|zoom_in|zoom_out"',
    ]))

    return f"""
You are an experienced short-form video scriptwriter for YouTube Shorts. Your
goal is genuine viewer retention: specific, well-earned writing that rewards
someone for watching to the end — not filler, and not hollow engagement bait.

RULES:
1. TOTAL NARRATION: 40-50 seconds read aloud (roughly 110-140 spoken words
   total across all {num_scenes} scenes).
2. SCENE 1 (THE HOOK - first 3 seconds): a genuinely surprising, specific
   fact or question related to the topic. Never "Hello guys" or "In this
   video". The hook has to be TRUE and be something the rest of the video
   actually delivers on — don't promise a twist you don't pay off.
3. PACING: every scene is punchy (1-2 sentences max). Cut every unnecessary word.
4. ENDING (scene {num_scenes}): end with a clear, honest reason to keep
   engaging — a specific follow-up question, what part 2 will cover, or why
   subscribing matters for THIS channel. Do not use empty engagement-bait
   instructions like "comment X and I'll DM you" — YouTube's spam policies
   discourage this, and it reads as hollow to viewers anyway.
{visual_rule}
6. Do not state invented statistics or claims about real, named companies or
   people as fact unless they're well-established public knowledge — a
   confident-sounding wrong number about a real company is a real
   misinformation risk at automated scale, not a minor detail.

OUTPUT FORMAT (strict JSON, no extra markdown or commentary):
{{
  "video_title": "Clear, specific, honest title (under 65 chars, include #Shorts)",
  "description": "1-2 sentence description with relevant keywords",
  "hashtags": ["#Shorts", "...9 more specific, relevant tags"],
  "hook_concept": "Brief explanation of why scene 1 hooks the viewer",
  "scenes": [
    {{
      {scene_fields}
    }}
  ]
}}
""".strip()


def generate_storyboard(topic: dict, tone: dict, num_scenes: int = 5, render_style: str = "stock_footage") -> dict:
    """Generates a complete video storyboard from a topic/tone config row."""
    prompt = f"Topic: {topic.get('name')} — {topic.get('description', '')}\nExtra Context: {topic.get('custom_context', '')}"
    return generate_custom_storyboard(
        prompt=prompt,
        tone_name=tone.get("name", "High Impact"),
        tone_desc=tone.get("description", "Engaging and punchy"),
        num_scenes=num_scenes,
        render_style=render_style,
    )


def generate_custom_storyboard(
    prompt: str,
    tone_name: str = "Curious Explainer",
    tone_desc: str = "Clear, specific, genuinely informative — makes the viewer smarter in 45 seconds",
    hook_style: str = "Surprising Fact / Question",
    num_scenes: int = 5,
    render_style: str = "stock_footage",
) -> dict:
    """Generates a video storyboard from any free-form prompt.

    Args:
        prompt: Free-form subject, e.g. "how EUV lithography actually works"
        tone_name / tone_desc: Voice/style for the writing
        hook_style: Guidance for the opening scene's hook
        num_scenes: Total scenes (default 5)
        render_style: "stock_footage" | "whiteboard_sketch" | "quote_card" —
            changes what visual field scenes are asked for (see
            _build_system_prompt). Unknown values fall back to stock_footage.
    """
    from engine.styles import available_styles
    if render_style not in available_styles():
        render_style = "stock_footage"

    client, model_name = _get_client()
    system_prompt = _build_system_prompt(render_style, num_scenes)

    user_prompt = f"""
SUBJECT:
{prompt}

STYLE & TONE:
{tone_name} — {tone_desc}

HOOK REQUIREMENT (Scene 1):
{hook_style}

NUMBER OF SCENES: {num_scenes}

Generate a {num_scenes}-scene storyboard adhering strictly to the JSON schema.
"""

    print(f"[script_generator] Generating storyboard for: '{prompt[:50]}...' "
          f"(tone='{tone_name}', style='{render_style}')")

    response = _call_model_with_clear_errors(client, model_name, system_prompt, user_prompt)

    try:
        raw = response.text.strip()
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        storyboard = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Gemini returned invalid JSON: {e}\nRaw output:\n{response.text[:500]}")

    # ── Validate top-level keys ────────────────────────────────────────────
    for key in ["video_title", "description", "hashtags", "scenes"]:
        if key not in storyboard:
            raise ValueError(f"Storyboard missing required key: '{key}'")

    if len(storyboard["scenes"]) != num_scenes:
        print(f"[script_generator] \u26a0 Expected {num_scenes} scenes, got "
              f"{len(storyboard['scenes'])} — using what came back rather than failing outright.")

    # ── Validate each scene ─────────────────────────────────────────────────
    # voice_text is the one field a scene cannot silently do without — an
    # empty one means that scene contributes nothing to the narration, with
    # no error and no way to notice except by watching the finished video.
    for i, scene in enumerate(storyboard["scenes"]):
        if not scene.get("voice_text", "").strip():
            raise ValueError(f"Scene {i+1} has no voice_text — refusing to silently ship a mute scene.")

        scene.setdefault("transition", "cut")
        scene.setdefault("sfx", "none")
        scene.setdefault("visual_mood", "neutral")

        if render_style == "whiteboard_sketch":
            icons = [ic for ic in scene.get("icons", []) if ic in available_icon_names()]
            scene["icons"] = icons or ["lightbulb"]
        elif render_style == "stock_footage" and not scene.get("visual_keyword", "").strip():
            # Better than an empty search query (which visual_fetcher would
            # have to guess at) — fall back to something on-topic instead.
            scene["visual_keyword"] = f"{scene.get('visual_mood', 'neutral')} abstract technology background"

    if "#Shorts" not in storyboard["hashtags"]:
        storyboard["hashtags"].insert(0, "#Shorts")
    if "#Shorts" not in storyboard["video_title"]:
        storyboard["video_title"] += " #Shorts"

    print(f"[script_generator] \u2713 Storyboard generated: '{storyboard['video_title']}'")
    return storyboard


# ─── Test / Debug ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    test_prompt = "how EUV lithography carves transistors smaller than a virus"
    result = generate_custom_storyboard(test_prompt, render_style="whiteboard_sketch")
    print(json.dumps(result, indent=2))
