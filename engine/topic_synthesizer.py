"""
topic_synthesizer.py — the part that makes a persona actually endless.
======================================================================

WHAT THIS DOES
Given a persona (see personas.py), asks Gemini to invent new, SPECIFIC topics
inside that domain — ones that are not the seed examples, are not already in
your topic list, and are not near-duplicates of anything in the concept
ledger. It then inserts the winners as real, active topics.

This is what "unlimited different content based on that" actually means in
practice: you write the domain description once, and from then on the app
keeps finding new specific angles inside it on its own, the same way you would
if you sat down and brainstormed fifty video ideas about DevOps — except it
does that every time the pool runs low, forever, without you doing it.

TOPIC =/= VIDEO
A synthesized topic is still just a topic. It goes through the exact same
pipeline as one you typed by hand: brief.py picks the best angle, pulse.py
checks for current relevance, the archetype's guardrails apply, quality gates
check the render, concept_memory blocks anything too similar. Synthesizing the
subject does not skip a single safety step downstream — it only removes the
one step that was pure repetitive typing.

WHY THIS RUNS ON A POOL, NOT PER VIDEO
Calling this before every single video would be one more model call per video
for no benefit — a topic invented five minutes ago is exactly as good as one
invented today. Instead, each persona keeps a small pool of unused topics
(default 5) and only tops it up when it runs low. That is one extra call every
few days per persona, not one extra call per video.
"""
import json
import re
from datetime import datetime, timezone

from engine import personas as personas_mod
from engine import concept_memory as cm
from engine import lenses as lenses_mod

MIN_POOL_SIZE = 5
SYNTHESIZE_BATCH = 6

SYNTH_SYSTEM = """You invent specific YouTube Shorts topics inside one content
domain. You do not write scripts — only short, specific topic ideas someone
could later write a 45-second video about.

A good topic here is NARROW and CONCRETE, not a broad umbrella. "Space" is not
a topic. "Why astronauts' bones lose density in zero gravity, and what they do
about it" is a topic.

Every idea must:
  - Fit the domain description exactly — do not drift into an adjacent domain.
  - Be genuinely different from every existing topic and seed example given —
    not a reword of one, a different specific subject entirely.
  - Be something a single 45-second video could actually cover well.
  - Avoid anything requiring a real named living person as its subject.

Return ONLY a JSON array, no markdown, no preamble:
[
  {"name": "the topic, phrased as a specific video idea", "description": "one sentence on the angle"}
]"""


def _extract_json_array(text: str) -> list:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip())
    start, end = cleaned.find("["), cleaned.rfind("]")
    if start == -1 or end == -1:
        raise ValueError("No JSON array found in the model's reply")
    return json.loads(cleaned[start:end + 1])


def synthesize_topics(persona_key: str, n: int, existing_names: set, ledger: list,
                      rotation_index: int = 0) -> list:
    """Asks Gemini for `n` new topic ideas inside a persona's domain.

    Returns [] on any failure — the caller falls back to the persona's static
    seed list, which always exists and always works. Nothing about "unlimited
    topics" is allowed to become "zero topics" if a model call fails.
    """
    from engine.script_generator import _get_client, _call_model_with_clear_errors

    persona = personas_mod.get_persona(persona_key)
    if not persona:
        return []

    avoid = sorted(existing_names)[:80] + [r.get("title", "") for r in ledger[:40]]
    avoid_text = "\n".join(f"- {a}" for a in avoid if a) or "(nothing yet)"

    # Assign each requested topic a DIFFERENT kind of question. Without this,
    # every batch converges on "how does X work" — see engine/lenses.py.
    chosen_lenses = lenses_mod.pick_lenses(persona_key, n, rotation_index)
    lens_text = lenses_mod.prompt_block(chosen_lenses)

    user = f"""DOMAIN: {persona['label']}
{persona['description']}

EXAMPLES OF THE DOMAIN'S SHAPE (do not repeat these, invent NEW ones like them):
{chr(10).join('- ' + s for s in persona['seed_topics'])}

ALREADY COVERED — do not repeat or closely rephrase any of these:
{avoid_text}

{lens_text}

Invent exactly {n} new topics, one per lens, in order."""

    try:
        client, model_name = _get_client()
        response = _call_model_with_clear_errors(client, model_name, SYNTH_SYSTEM, user, temperature=1.0)
        ideas = _extract_json_array(response.text)
        cleaned = [
            {"name": i["name"].strip(), "description": i.get("description", "").strip()}
            for i in ideas if i.get("name")
        ]
        print(f"[topic_synthesizer] \u2713 Proposed {len(cleaned)} new topic(s) for '{persona['label']}'")
        return cleaned
    except Exception as e:
        print(f"[topic_synthesizer] \u26a0 Could not synthesize topics ({e}); "
              f"falling back to seed topics for this persona.")
        return []


def ensure_persona_topic_pool(persona_key: str, db, min_pool: int = MIN_POOL_SIZE) -> int:
    """Tops up a persona's unused topic pool if it has run low.

    "Unused" means active and not yet reflected in the concept ledger — a
    topic that already produced a published video is not pool depth, it is
    history. Returns how many new topics were added (0 is a normal result,
    not a failure — it just means the pool was already full enough).
    """
    persona = personas_mod.get_persona(persona_key)
    if not persona:
        return 0

    try:
        active = (
            db.table("topics").select("name")
            .eq("persona_key", persona_key).eq("is_active", True)
            .execute().data
        ) or []
        active_names = {t["name"].strip().lower() for t in active}

        ledger = cm.load_ledger(db=db)
        used_names = {r.get("title", "").strip().lower() for r in ledger}
        unused_pool = active_names - used_names

        if len(unused_pool) >= min_pool:
            return 0

        needed = min(min_pool - len(unused_pool), SYNTHESIZE_BATCH)
        print(f"[topic_synthesizer] Pool for '{persona['label']}' is at "
              f"{len(unused_pool)}/{min_pool} — synthesizing {needed} more.")

        all_topic_names = {
            t["name"].strip().lower()
            for t in (db.table("topics").select("name").execute().data or [])
        }
        # Rotate the lens starting point by day so consecutive days don't
        # always lead with the same kind of question.
        rotation = datetime.now(timezone.utc).timetuple().tm_yday
        ideas = synthesize_topics(persona_key, needed, all_topic_names, ledger, rotation)

        # Fall back to unused seed topics if the model call failed or returned
        # too few — the persona must never go dry just because one API call
        # had a bad day.
        if len(ideas) < needed:
            for seed in persona["seed_topics"]:
                if seed.strip().lower() not in all_topic_names:
                    ideas.append({"name": seed, "description": ""})
                if len(ideas) >= needed:
                    break

        added = 0
        for idea in ideas[:needed]:
            key = idea["name"].strip().lower()
            if key in all_topic_names:
                continue
            try:
                db.table("topics").insert({
                    "name": idea["name"],
                    "description": idea.get("description") or "",
                    "persona_key": persona_key,
                    "is_active": True,
                    "added_by": "persona-auto",
                }).execute()
                all_topic_names.add(key)
                added += 1
            except Exception as e:
                print(f"[topic_synthesizer] \u26a0 Could not insert topic {idea['name']!r}: {e}")

        print(f"[topic_synthesizer] \u2713 Added {added} topic(s) to '{persona['label']}'.")
        return added

    except Exception as e:
        print(f"[topic_synthesizer] \u26a0 Pool check failed for '{persona_key}': {e}")
        return 0


def ensure_all_active_persona_pools(db, min_pool: int = MIN_POOL_SIZE) -> dict:
    """Tops up every persona that at least one enabled channel actually uses.

    Only personas with a real channel behind them get topics synthesized —
    there is no point inventing videos for a domain nobody is publishing to.
    """
    try:
        channels = db.table("channels").select("persona_key").eq("is_enabled", True).execute().data or []
        active_personas = {c["persona_key"] for c in channels if c.get("persona_key")}
    except Exception as e:
        print(f"[topic_synthesizer] \u26a0 Could not read channels: {e}")
        return {}

    return {p: ensure_persona_topic_pool(p, db, min_pool) for p in active_personas}


if __name__ == "__main__":
    import argparse
    from engine.config import get

    p = argparse.ArgumentParser(description="Preview or run persona topic synthesis")
    p.add_argument("persona", choices=personas_mod.persona_keys())
    p.add_argument("--n", type=int, default=5)
    p.add_argument("--apply", action="store_true", help="Actually insert topics (default: preview only)")
    args = p.parse_args()

    if args.apply:
        from supabase import create_client
        db = create_client(get("SUPABASE_URL"), get("SUPABASE_SERVICE_KEY"))
        ensure_persona_topic_pool(args.persona, db, min_pool=999)  # force a full top-up
    else:
        ideas = synthesize_topics(args.persona, args.n, set(), [])
        for i in ideas:
            print(f"  - {i['name']}")
        print("\nPreview only. Add --apply to actually insert these as topics.")
