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

    "Unused" means an ACTIVE topic that has never produced a video row yet.

    This deliberately does NOT use the concept ledger to decide what is spent.
    The ledger only records on publish, so a topic that had already generated
    three unreviewed videos still counted as "unused" — which is precisely how
    the same subject got made over and over. Counting actual video rows means
    a topic is spent the moment it produces anything, so each new video
    reaches for a genuinely new subject.

    Returns how many new topics were added (0 is normal, not a failure — it
    just means the pool was already deep enough).
    """
    persona = personas_mod.get_persona(persona_key)
    if not persona:
        return 0

    try:
        active = (
            db.table("topics").select("id, name")
            .eq("persona_key", persona_key).eq("is_active", True)
            .execute().data
        ) or []

        used_topic_ids = set()
        try:
            vids = db.table("videos").select("topic_id").execute().data or []
            used_topic_ids = {v["topic_id"] for v in vids if v.get("topic_id")}
        except Exception as e:
            print(f"[topic_synthesizer] \u26a0 Could not read video history: {e}")

        unused = [t for t in active if t["id"] not in used_topic_ids]

        if len(unused) >= min_pool:
            return 0

        needed = min(min_pool - len(unused), SYNTHESIZE_BATCH)
        print(f"[topic_synthesizer] Pool for '{persona['label']}' is at "
              f"{len(unused)}/{min_pool} fresh topic(s) \u2014 synthesizing {needed} more.")

        ledger = cm.load_ledger(db=db)
        all_topic_names = {
            t["name"].strip().lower()
            for t in (db.table("topics").select("name").execute().data or [])
        }

        rotation = datetime.now(timezone.utc).timetuple().tm_yday
        ideas = synthesize_topics(persona_key, needed, all_topic_names, ledger, rotation)

        # Fall back to unused seed topics if the model call failed or returned
        # too few — a persona must never go dry because one API call had a bad
        # day. This matters more now that Gemini 503s are common.
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


def resolve_active_personas(db) -> list:
    """Works out which personas should have topics invented for them.

    Checks three sources in order. Relying only on the first one meant this
    entire feature silently never ran for anyone who had not yet set up a
    persona-backed channel — which was the real situation: a handful of old
    topics, no personas anywhere, so the pool top-up did nothing and every
    video was drawn from the same tiny stale list, producing duplicates.

      1. The `auto_topic_personas` setting — an explicit comma-separated list.
         Highest priority because a person set it deliberately.
      2. Personas attached to enabled channels.
      3. Personas already referenced by existing topics.
    """
    try:
        rows = db.table("settings").select("key, value").eq("key", "auto_topic_personas").execute().data or []
        if rows and (rows[0].get("value") or "").strip():
            keys = [k.strip() for k in rows[0]["value"].split(",") if k.strip()]
            valid = [k for k in keys if personas_mod.get_persona(k)]
            if valid:
                print(f"[topic_synthesizer] Using auto_topic_personas setting: {valid}")
                return valid
    except Exception:
        pass

    try:
        channels = db.table("channels").select("persona_key").eq("is_enabled", True).execute().data or []
        from_channels = sorted({c["persona_key"] for c in channels if c.get("persona_key")})
        if from_channels:
            return from_channels
    except Exception as e:
        print(f"[topic_synthesizer] \u26a0 Could not read channels: {e}")

    try:
        topics = db.table("topics").select("persona_key").eq("is_active", True).execute().data or []
        from_topics = sorted({t["persona_key"] for t in topics if t.get("persona_key")})
        if from_topics:
            return from_topics
    except Exception:
        pass

    print("[topic_synthesizer] No personas configured anywhere \u2014 automatic topic "
          "rotation is OFF. Pick a persona on the Channels page, or set "
          "'auto_topic_personas' in Settings, to turn it on.")
    return []


def ensure_all_active_persona_pools(db, min_pool: int = MIN_POOL_SIZE) -> dict:
    """Tops up every persona that should be generating content."""
    return {p: ensure_persona_topic_pool(p, db, min_pool) for p in resolve_active_personas(db)}



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
