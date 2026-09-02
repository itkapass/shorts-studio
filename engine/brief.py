"""
brief.py — the model plans the video before it writes it.
=========================================================

THE PROBLEM THIS REPLACES
Topic Studio used to ask you to fill in "Custom Admin Context & Hook Rules" and
"AI Description / Core Prompt" for every topic. That is prompt engineering, by
hand, forever, per topic — and it does not scale past about five topics. It
also makes the quality of every video depend on how well you happened to word
a text box six weeks ago.

THE FIX: TWO STAGES INSTEAD OF ONE
Asking a model to write a good short video in one call gets you the obvious
video. Not a bad one — the obvious one. First idea, first framing, the thing
anyone would think of in five seconds. Every automated channel is full of them,
which is exactly why they all feel the same.

So the work is split:

  STAGE 1 (this file) — think. Generate several angles on the topic, judge them
  against each other, pick the strongest, and write a creative brief: the
  angle, the hook, the specific detail that carries it, what to avoid, and the
  reason someone would watch to the end.

  STAGE 2 (script_generator.py) — write, using that brief.

This is the "let the AI write its own prompt" idea, and it works for a concrete
reason: judging which of five angles is strongest is a much easier task than
producing a strong angle cold. Separating the two lets the model do the easy
task first and hands the hard task a decision that is already made.

WHAT IT COSTS
One extra Gemini call per video. On the free tier that is nothing. It is by
some distance the highest quality-per-cost change available in this project.

SELF-CRITIQUE IS PART OF STAGE 1
The brief prompt requires the model to name the LAZIEST version of the video
and explicitly rule it out. Models default to the obvious framing; making it
identify and reject that framing on paper measurably pushes the output past it.
"""
import json
import re

from engine import archetypes as arch
from engine import narrative
from engine import pulse
from engine import personas as personas_mod


BRIEF_SYSTEM = """You are a short-form video producer. You do not write scripts.
Your only job is to decide what a video should BE, and hand a writer a brief
they cannot get wrong.

You will be given a topic, a content format, and a narrative structure. Do this:

1. Generate FIVE genuinely different angles on the topic. Not five wordings of
   one idea — five different videos.
2. Judge them honestly against each other. The winner is the one where a real
   person, mid-scroll, would stop and stay. Not the most informative. Not the
   most clever. The one that earns the next three seconds.
3. Write the brief for the winner.

RULES FOR JUDGING:
- Specific beats general, always. "Meetings are pointless" is nothing. "The
  meeting where someone reads the slides out loud" is a video.
- If you can guess the ending from the opening, it is a weak angle.
- A fact nobody has heard beats a fact explained well.
- The best angle is usually the second or third thing you thought of. The first
  is what everyone else already made.

YOU MUST ALSO name the laziest, most obvious version of this video and rule it
out explicitly. That is not a formality — whatever you name there is the video
you would have written by default, and naming it is what stops you writing it.

Return ONLY a JSON object. No markdown, no preamble.

{
  "angles_considered": ["five one-line angles you weighed"],
  "chosen_angle": "the winning angle in one sentence",
  "why_this_one": "why it beats the other four, in one sentence",
  "lazy_version_to_avoid": "the obvious video you are deliberately NOT making",
  "hook": "the exact opening line or image, written out",
  "hook_reasoning": "why that stops a scroll",
  "specific_detail": "the one concrete detail, number, or image the video rests on",
  "payoff": "what the viewer gets at the end that they did not have at the start",
  "tone_note": "one line on how it should feel",
  "avoid": ["things that would make this generic"]
}"""


def _extract_json(text: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip())
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in the model's reply")
    return json.loads(cleaned[start:end + 1])


def generate_brief(
    topic: dict,
    archetype: str,
    structure: str,
    use_pulse: bool = True,
    persona_key: str = None,
) -> dict:
    """Produces a creative brief for one video.

    Returns {} on any failure. That is a real fallback, not a placeholder: with
    no brief, script_generator writes from the topic as it always did. The
    video is less sharp, and it still gets made. Nothing here is allowed to
    break a generation run.
    """
    from engine.script_generator import _get_client, _call_model_with_clear_errors

    topic_name = topic.get("name", "")
    topic_desc = topic.get("description", "") or ""

    a = arch.get_archetype(archetype)
    s = narrative.get_structure(structure)

    pulse_items = pulse.fetch_pulse(topic_name, topic_desc, archetype) if use_pulse else []
    pulse_text = pulse.prompt_block(pulse_items, archetype)
    persona_text = personas_mod.flavor_prompt_block(persona_key) if persona_key else ""

    user = f"""TOPIC: {topic_name}
{topic_desc}

CONTENT FORMAT: {a['label']} — {a['blurb']}
How this format works: {a['rules']}

HARD LIMITS FOR THIS FORMAT (a brief that violates these is useless):
{a['guardrails']}

NARRATIVE STRUCTURE: {s['label']} — {s['blurb']}
{s['beats']}
{persona_text}{pulse_text}
Now do the five-angle process and return the brief as JSON."""

    try:
        client, model_name = _get_client()
        response = _call_model_with_clear_errors(client, model_name, BRIEF_SYSTEM, user)
        brief = _extract_json(response.text)

        if not brief.get("chosen_angle"):
            raise ValueError("Brief has no chosen angle")

        brief["_pulse_used"] = [i["headline"] for i in pulse_items]
        brief["_archetype"] = archetype
        brief["_structure"] = structure
        brief["_persona"] = persona_key

        print(f"[brief] \u2713 Angle: {brief['chosen_angle'][:90]}")
        if brief.get("lazy_version_to_avoid"):
            print(f"[brief]   Avoiding: {brief['lazy_version_to_avoid'][:80]}")
        if pulse_items:
            print(f"[brief]   Informed by {len(pulse_items)} current item(s)")
        return brief

    except Exception as e:
        print(f"[brief] \u26a0 Could not generate a brief ({e}). Writing from the topic alone.")
        return {}


def prompt_block(brief: dict) -> str:
    """Formats the brief for the script-writing prompt.

    Phrased as decisions already made, not suggestions. A brief the writer can
    negotiate with is a brief the writer ignores — it will drift straight back
    to the obvious version, which is the entire thing this exists to prevent.
    """
    if not brief:
        return ""

    avoid = brief.get("avoid") or []
    avoid_lines = "\n".join(f"  - {a}" for a in avoid) if avoid else "  - (nothing specific)"

    return f"""

════════════════════════════════════════════════════════════════
THE BRIEF — these decisions are already made. Execute them.
════════════════════════════════════════════════════════════════

ANGLE: {brief.get('chosen_angle', '')}
WHY IT WORKS: {brief.get('why_this_one', '')}

OPEN WITH: {brief.get('hook', '')}
  ({brief.get('hook_reasoning', '')})

THE VIDEO RESTS ON THIS DETAIL: {brief.get('specific_detail', '')}

END ON: {brief.get('payoff', '')}

TONE: {brief.get('tone_note', '')}

DO NOT WRITE THIS VERSION: {brief.get('lazy_version_to_avoid', '')}
  This was considered and rejected. Do not drift back toward it.

ALSO AVOID:
{avoid_lines}

Do not second-guess the angle or substitute your own. The thinking is done.
Your job is to execute it as well as it can possibly be executed.
════════════════════════════════════════════════════════════════
"""


def summarize(brief: dict) -> str:
    if not brief:
        return "no brief (wrote from topic alone)"
    return brief.get("chosen_angle", "")[:120]
