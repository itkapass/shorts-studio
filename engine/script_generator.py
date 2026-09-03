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

from engine.config import require, get
from engine.styles.icon_library import available_icon_names
from engine import archetypes as arch
from engine import model_registry
from engine.character import library as charlib
from engine import narrative
from engine import brief as brief_mod
from engine import props as props_lib

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
# 429 is deliberately NOT here. 503/500 mean "the model is busy right now" and
# a retry very often succeeds. 429 RESOURCE_EXHAUSTED means the DAILY free-tier
# allowance is gone — retrying cannot help today, and each retry still counts
# against the quota. Treating them the same meant a single quota error burned
# four more calls from a budget that was already empty.
RETRYABLE_CODES = {503, 500}
MAX_RETRIES = 4
RETRY_BACKOFF_SECONDS = 3  # doubles each attempt: 3s, 6s, 12s, 24s


def _get_client(api_key: str = None):
    """Returns (client, model_name).

    `api_key`, when given, overrides the global GEMINI_API_KEY. This is what
    makes per-channel Gemini keys work: each Google account gets its own
    independent free-tier quota (~20 requests/day), so a channel with its own
    key is not competing with every other channel for the same 20 requests.
    Get one free at aistudio.google.com with a different Google account, then
    set GEMINI_API_KEY_<SUFFIX> the same way YOUTUBE_CLIENT_ID_<SUFFIX>
    already works for multi-channel YouTube credentials (see docs/07).

    NOTE — this project previously used the `google.generativeai` package,
    which — as of testing this fix — prints: 'All support for the
    `google.generativeai` package has ended. Please switch to the
    `google.genai` package as soon as possible.' That's not just a stale
    model string, the whole SDK reached end-of-life. Migrated to `google.genai`
    (the current package) here.
    """
    key = api_key
    if not key:
        cfg = require(["GEMINI_API_KEY"])
        key = cfg["GEMINI_API_KEY"]
    client = genai.Client(api_key=key)
    # Model names are discovered from Google's live model list rather than
    # hardcoded. Google retires Gemini names on a ~4-6 month cycle and this
    # project already got 404'd once by a pinned name; asking the API what
    # exists right now means that failure mode is gone for good.
    # Setting GEMINI_MODEL still pins a specific name and skips discovery.
    model_name = model_registry.choose_text_model(key) or DEFAULT_GEMINI_MODEL
    return client, model_name


def _call_model_with_clear_errors(client, model_name, system_prompt, user_prompt, temperature=None):
    """Calls Gemini and retries transient failures.

    TEMPERATURE, EXPLAINED (you asked to learn real AI-engineering concepts —
    this is one of the core ones):

    It controls how much the model is allowed to gamble on a less-likely next
    word instead of always taking the safest one.

      0.0  -> always picks the single most probable word. Deterministic,
             same input gives the same output every time. Reads as flat and
             generic, because "most probable" is also "most expected".
      0.9  -> (the default here) frequently takes a less-obvious but still
             sensible word. This is what makes two videos on the same topic
             come out differently phrased, which is exactly what a comedy or
             hook-writing task needs — the obvious phrasing is rarely the
             funniest one.
      1.5+ -> gambles often enough that output starts breaking: odd word
             choices, sentences that technically parse but read as strange.

    0.9 is deliberately high for this app because retrieval-style tasks
    (get me a correct fact) want low temperature, but WRITING tasks (make me
    a hook nobody else would write) want higher temperature. You can change
    it in Settings and watch the difference yourself — that live feedback
    loop is the fastest way to actually understand what the number does.
    """
    temperature = 0.9 if temperature is None else float(temperature)
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return client.models.generate_content(
                model=model_name,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    temperature=temperature,
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
            if code == 429:
                raise RuntimeError(
                    f"Gemini daily quota exhausted (429 RESOURCE_EXHAUSTED).\n\n"
                    f"The free tier allows a limited number of requests per day and today's "
                    f"allowance is gone. It resets at midnight Pacific.\n\n"
                    f"To fit more videos into the daily allowance, lower 'Daily video "
                    f"generation batch' in Settings. Each video costs about 2 requests.\n\n"
                    f"Original error: {e}"
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

def _build_system_prompt(render_style: str, num_scenes: int, archetype: str = None,
                         avoid_list: str = "", structure: str = None,
                         creative_brief: dict = None) -> str:
    if render_style == "character_skit":
        cast_lines = "\n".join(
            f'   - "{k}" = {v["label"]}: {v["desc"]}' for k, v in charlib.CHARACTERS.items()
        )
        preferred = charlib.cast_for_archetype(archetype or "")
        visual_field = (
            '"character": "which character speaks this line — one of: '
            + ", ".join(charlib.CHARACTERS.keys()) + '",\n      '
            '"emotion": "neutral|happy|excited|shocked|angry|annoyed|sad|smug|confused|deadpan"'
        )
        visual_rule = (
            "5. VISUALS: this is a 2D animated character skit. There is no footage and no icons — "
            "the performance carries it.\n"
            f"   Available characters:\n{cast_lines}\n"
            f"   For this format, prefer: {' or '.join(preferred)}.\n"
            "   Use ONE character for a monologue, or TWO for a conversation — never more than "
            "two, they will not fit on a vertical screen.\n"
            "   If you use two, alternate them so it reads as an exchange, and give the second "
            "one an actual point of view rather than just reacting.\n"
            "   Set an emotion per scene; it drives the eyes and eyebrows, so vary it or the "
            "character looks frozen.\n"
            "   voice_text IS the spoken dialogue and also appears on screen, so write it as "
            "something a person would actually say out loud.\n"
            "6. PROPS: give a scene a \"prop\" when an object makes the idea VISIBLE. A "
            "character standing next to the thing they are talking about is a scene; a "
            "character alone on an empty stage is a talking head. Pick for MEANING, not for "
            "words literally mentioned in the line.\n"
            f"{props_lib.prompt_vocabulary()}\n"
            "   Omit the field entirely when no object helps. An irrelevant prop is worse "
            "than none.\n"
            "7. CAMERA: set \"camera\": \"push_in\" on AT MOST ONE scene — the single most "
            "important line, usually the turn or the punchline. It slowly zooms toward the "
            "speaker. Using it on more than one scene makes it meaningless and nauseating."
        )
    elif render_style == "whiteboard_sketch":
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
        '"label": "Optional small on-screen tag, e.g. a year. Only for then_vs_now."',
    ]))

    archetype_block = arch.prompt_block(archetype) if archetype else ""
    brief_block = brief_mod.prompt_block(creative_brief) if creative_brief else ""
    structure_block = (
        "\n\n" + narrative.prompt_block(structure, num_scenes) if structure else ""
    )
    avoid_block = (
        f"\n\nALREADY MADE — DO NOT REPEAT ANY OF THESE IDEAS, or anything that is "
        f"the same subject from a slightly different angle:\n{avoid_list}\n"
        f"If your idea overlaps with one of these, pick a genuinely different one. "
        f"Repeating a subject is the single fastest way to get a channel flagged "
        f"for mass-produced content."
        if avoid_list else ""
    )

    return f"""
You are an experienced short-form video scriptwriter for YouTube Shorts. Your
goal is genuine viewer retention: specific, well-earned writing that rewards
someone for watching to the end — not filler, and not hollow engagement bait.

{brief_block}{archetype_block}{structure_block}{avoid_block}

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
  "concept": "One sentence naming the specific idea of this video, for duplicate checking",
  "banner": "Optional. One short line pinned on screen for the WHOLE video (under 60 chars). Only if the structure asks for it.",
  "scenes": [
    {{
      {scene_fields}
    }}
  ]
}}
""".strip()


def generate_storyboard(topic: dict, tone: dict, num_scenes: int = 5,
                        render_style: str = "stock_footage",
                        archetype: str = None, avoid_list: str = "",
                        structure: str = None, creative_brief: dict = None,
                        api_key: str = None, temperature: float = None) -> dict:
    """Generates a complete video storyboard from a topic/tone config row.

    `archetype` decides the KIND of video (unknown-fact, myth-bust, dark
    humour...) and pulls in that format's writing rules and content limits.
    `avoid_list` is the concept ledger, so the model can see what has already
    been made and pick something genuinely new.
    """
    prompt = f"Topic: {topic.get('name')} — {topic.get('description', '')}\nExtra Context: {topic.get('custom_context', '')}"

    archetype = archetype or topic.get("archetype") or arch.DEFAULT_ARCHETYPE
    ok, reason = arch.is_combination_allowed(
        f"{topic.get('name','')} {topic.get('description','')}", archetype
    )
    if not ok:
        # Refuse the pairing rather than softening it. Asking for a joke about
        # a famine and then hoping the guardrails catch it is the wrong order:
        # the reliable fix is to never make the request.
        raise ValueError(f"Blocked topic/format combination: {reason}")

    return generate_custom_storyboard(
        prompt=prompt,
        tone_name=tone.get("name", "High Impact"),
        tone_desc=tone.get("description", "Engaging and punchy"),
        num_scenes=num_scenes,
        render_style=render_style,
        archetype=archetype,
        avoid_list=avoid_list,
        structure=structure,
        creative_brief=creative_brief,
        api_key=api_key,
        temperature=temperature,
    )


def generate_custom_storyboard(
    prompt: str,
    tone_name: str = "Curious Explainer",
    tone_desc: str = "Clear, specific, genuinely informative — makes the viewer smarter in 45 seconds",
    hook_style: str = "Surprising Fact / Question",
    num_scenes: int = 5,
    render_style: str = "stock_footage",
    archetype: str = None,
    avoid_list: str = "",
    structure: str = None,
    creative_brief: dict = None,
    api_key: str = None,
    temperature: float = None,
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

    client, model_name = _get_client(api_key)
    system_prompt = _build_system_prompt(render_style, num_scenes, archetype, avoid_list,
                                        structure, creative_brief)
    # An explicit caller-supplied temperature (usually a persona's own
    # default_temperature) wins; otherwise fall back to the global env/
    # Settings value, same as before this parameter existed.
    if temperature is None:
        env_temp = get("GEMINI_TEMPERATURE")
        temperature = float(env_temp) if env_temp else None
    else:
        temperature = float(temperature)

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
          f"(tone='{tone_name}', style='{render_style}', archetype='{archetype or 'none'}')")

    response = _call_model_with_clear_errors(client, model_name, system_prompt, user_prompt, temperature)

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

        if render_style == "character_skit":
            # Fall back rather than fail: an unrecognised character name is a
            # cosmetic mistake, and killing a finished storyboard over it
            # would waste a full model call.
            preferred = charlib.cast_for_archetype(archetype or "")
            if scene.get("character") not in charlib.CHARACTERS:
                scene["character"] = preferred[0]
            valid_emotions = {
                "neutral", "happy", "excited", "shocked", "angry",
                "annoyed", "sad", "smug", "confused", "deadpan",
            }
            if scene.get("emotion") not in valid_emotions:
                scene["emotion"] = "neutral"
        elif render_style == "whiteboard_sketch":
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

    storyboard["render_style"] = render_style
    storyboard["archetype"] = archetype or ""
    storyboard["structure"] = structure or ""

    # The banner is a video-level field but the renderer walks scenes, so copy
    # it down. Doing it here rather than in the renderer means every consumer
    # (export, preview, admin panel) sees the same thing.
    banner = (storyboard.get("banner") or "").strip()
    if banner:
        for sc in storyboard["scenes"]:
            sc["_banner"] = banner

    if structure:
        for warning in narrative.validate(storyboard, structure):
            print(f"[script_generator] \u26a0 Structure note: {warning}")
    storyboard.setdefault("concept", storyboard.get("hook_concept", ""))

    if render_style == "character_skit":
        # Two characters is the hard ceiling at 9:16. If the model used more,
        # remap the extras onto the two most-used ones rather than dropping
        # scenes — losing a scene silently changes the whole script's timing.
        used = []
        for sc in storyboard["scenes"]:
            if sc["character"] not in used:
                used.append(sc["character"])
        if len(used) > 2:
            keep = used[:2]
            for sc in storyboard["scenes"]:
                if sc["character"] not in keep:
                    sc["character"] = keep[len(keep) - 1]
            print(f"[script_generator] \u26a0 Model used {len(used)} characters; "
                  f"remapped onto {keep}.")

    print(f"[script_generator] \u2713 Storyboard generated: '{storyboard['video_title']}'")
    return storyboard


# ─── Visual relevance ranking ────────────────────────────────────────────────

def rank_visual_candidates(scene_text: str, keyword: str, candidates: list, api_key: str = None) -> list:
    """Given several stock clips, returns their indices best-match-first.

    Called by visual_fetcher for every scene with more than one candidate. It
    exists because reviewing real output found a data-centre video illustrated
    with a derelict warehouse and a supercomputer scene illustrated with a
    Spanish emergency-stop button — Pexels returned loosely-matching results
    and the old code picked at RANDOM from them.

    One cheap text call, no image analysis, comfortably inside the free tier.
    Returns [] on any failure so the caller keeps the original order.
    """
    if not candidates:
        return []
    try:
        client, model_name = _get_client(api_key)
    except Exception:
        return []

    listing = "\n".join(
        f"{i}. {c.get('description') or 'untitled clip'} "
        f"({c.get('width')}x{c.get('height')}, {c.get('duration')}s)"
        for i, c in enumerate(candidates)
    )
    system = (
        "You match stock footage to narration. Given a line of narration and a numbered list of "
        "available clips, return the clip indices ordered best match first.\n"
        "A good match shows the actual physical subject the narration is about. Reject clips that "
        "merely share a keyword, generic lifestyle or portrait footage, and anything whose "
        "on-screen text is in a language that would confuse an English viewer.\n"
        'Reply with ONLY a JSON array of integers, e.g. [2,0,1]. No other text.'
    )
    user = f"NARRATION: {scene_text}\nSEARCH TERM USED: {keyword}\n\nCLIPS:\n{listing}"

    try:
        response = _call_model_with_clear_errors(client, model_name, system, user)
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", response.text.strip())
        order = json.loads(raw)
        if isinstance(order, list) and all(isinstance(i, int) for i in order):
            return order
    except Exception as e:
        print(f"[script_generator] \u26a0 Visual ranking failed ({e}); keeping search order.")
    return []


# ─── Test / Debug ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    test_prompt = "how EUV lithography carves transistors smaller than a virus"
    result = generate_custom_storyboard(test_prompt, render_style="whiteboard_sketch")
    print(json.dumps(result, indent=2))
