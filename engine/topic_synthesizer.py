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

MIN_POOL_SIZE = 15
SYNTHESIZE_BATCH = 20

SYNTH_SYSTEM = """You are a short-form content strategist inventing new video topics
inside one domain. You do not write scripts — only specific topic ideas someone
could later write a 45-second video about.

You will be given a handful of EXAMPLE topics. Read them once to understand the
domain's tone and register, then STOP referring to them. Your job is to explore
the FULL SPACE the domain description implies, not to write more topics that
resemble the examples. If your ideas would sit comfortably in a list next to the
examples, you have not gone far enough — you have found the boring, adjacent
version of an idea instead of a genuinely different one inside the same domain.

WHAT MAKES A TOPIC WORTH MAKING, IN ORDER OF IMPORTANCE:

1. SPECIFICITY. "Space" is not a topic. "Why astronauts' bones lose density in
   zero gravity, and what they actually do about it" is a topic. If a topic
   could be the title of a whole book, narrow it until it is the title of one
   scene from that book.

2. A CURIOSITY GAP. The topic should create a question in the reader's head
   that they cannot immediately answer, and want to. "How keyboards work" has
   no gap. "Why keyboards are arranged in an order that seems designed to slow
   you down" has one — it implies a surprising reason exists.

3. A REASON A STRANGER WOULD STOP SCROLLING. Not "is this interesting to
   someone who already cares about this domain" but "would someone with zero
   prior interest still stop for this specific detail". Concrete numbers, named
   real things, and surprising mechanisms clear this bar. Vague abstractions do
   not.

4. NOT THE OBVIOUS FIRST THOUGHT. For any subject, there is a version anyone
   would think of in five seconds. Do not write that version. Write the one a
   genuine expert in the domain would bring up that a casual outsider would not
   have thought to ask.

5. GENUINE VARIETY ACROSS THE BATCH. Do not submit five topics that are all the
   same shape wearing different subjects — five "how X works" or five "top facts
   about Y". Vary the kind of question being asked (mechanism, origin, scale,
   misconception, cost, comparison, edge case) across the batch, not just the
   subject matter.

Every idea must:
  - Fit the domain description — do not drift into an unrelated domain.
  - Be genuinely different from every existing topic and seed example given.
  - Be something a single 45-second video could actually cover well, not a
    whole documentary's worth of ground.
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
                      rotation_index: int = 0, api_key: str = None) -> list:
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

    # The persona's own house rules, included here too — not just at script
    # writing. Without this, a rule like "only use REAL existing proverbs,
    # never invent one and call it traditional" never reached the step that
    # actually decides what the topic IS, only the step that writes about a
    # topic already chosen. Some rules have to apply at naming time or not
    # at all.
    house_rules = persona.get("flavor_instructions", "")
    rules_block = f"\nHOUSE RULES FOR THIS DOMAIN:\n{house_rules}\n" if house_rules else ""

    user = f"""DOMAIN: {persona['label']}
{persona['description']}
{rules_block}
EXAMPLES OF THE DOMAIN'S SHAPE (do not repeat these, invent NEW ones like them):
{chr(10).join('- ' + s for s in persona['seed_topics'])}

ALREADY COVERED — do not repeat or closely rephrase any of these:
{avoid_text}

{lens_text}

Invent exactly {n} new topics, one per lens, in order."""

    try:
        client, model_name = _get_client(api_key)
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


def ensure_persona_topic_pool(persona_key: str, db, min_pool: int = MIN_POOL_SIZE, api_key: str = None) -> int:
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
        ideas = synthesize_topics(persona_key, needed, all_topic_names, ledger, rotation, api_key=api_key)

        # Track how many ideas actually came from Gemini vs the static seed
        # list, and TAG THEM DIFFERENTLY. Both used to be inserted under the
        # identical 'persona-auto' label, which quietly hid a real problem:
        # while Gemini's quota was being exhausted elsewhere in the pipeline,
        # every single "synthesized" topic was actually a seed-list fallback,
        # and there was no way to tell from the dashboard. Now the Topic
        # Studio badge shows the difference honestly.
        gemini_invented_count = len(ideas)

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
        added_from_gemini = 0
        for idx, idea in enumerate(ideas[:needed]):
            key = idea["name"].strip().lower()
            if key in all_topic_names:
                continue
            # Anything past index `gemini_invented_count` is a seed-fallback
            # insertion, not a real Gemini invention — label it honestly.
            is_real = idx < gemini_invented_count
            try:
                db.table("topics").insert({
                    "name": idea["name"],
                    "description": idea.get("description") or "",
                    "persona_key": persona_key,
                    "is_active": True,
                    "added_by": "persona-auto" if is_real else "persona-seed-fallback",
                }).execute()
                all_topic_names.add(key)
                added += 1
                added_from_gemini += 1 if is_real else 0
            except Exception as e:
                print(f"[topic_synthesizer] \u26a0 Could not insert topic {idea['name']!r}: {e}")

        if added_from_gemini < added:
            print(f"[topic_synthesizer] \u2713 Added {added} topic(s) to '{persona['label']}' "
                  f"({added_from_gemini} genuinely new from Gemini, "
                  f"{added - added_from_gemini} filled in from the seed list because "
                  f"Gemini synthesis did not return enough — check the Gemini budget log "
                  f"above if this keeps happening).")
        else:
            print(f"[topic_synthesizer] \u2713 Added {added} topic(s) to '{persona['label']}', "
                  f"all genuinely invented by Gemini.")
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
    """Tops up every persona that should be generating content.

    Uses each persona's OWN channel's Gemini key when one is set, so topic
    invention for a channel draws from that channel's own quota pool instead
    of the shared default — the same reasoning as per-channel keys for
    script writing, applied to the step before it.
    """
    from engine import channels as channels_mod
    channels = channels_mod.load_channels(db=db)

    results = {}
    for persona_key in resolve_active_personas(db):
        channel = next((c for c in channels if c.get("persona_key") == persona_key), None)
        api_key = channels_mod.gemini_key_for(channel) if channel else None
        results[persona_key] = ensure_persona_topic_pool(persona_key, db, min_pool, api_key=api_key)
    return results



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
