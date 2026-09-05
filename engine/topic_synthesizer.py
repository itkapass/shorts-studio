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
from engine import api_budget
from engine import daycycle

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
                      rotation_index: int = 0, api_key: str = None, budget=None) -> list:
    """Asks Gemini for `n` new topic ideas inside a persona's domain.

    Returns [] on an ordinary failure — the caller falls back to the persona's
    static seed list, which always exists and always works. Nothing about
    "unlimited topics" is allowed to become "zero topics" because one model
    call had a bad day.

    BUT a quota error is RE-RAISED, not swallowed. This function used to
    catch every exception including 429, which meant that when the daily
    Gemini allowance was gone, topic invention did not report a quota problem
    — it quietly returned [] and the caller silently filled the pool from the
    seed list instead. From the dashboard that looked like "the AI has
    stopped inventing topics" (a content problem) when it was actually "the
    API key is out of quota" (an infrastructure problem). Two completely
    different fixes, and the logs pointed at neither.

    It is also now BUDGET-AWARE. This call is a real Gemini request, and it
    used to be spent without ever being recorded in api_budget — so the
    tracker structurally under-counted, thought it had more room than it did,
    started videos it could not finish, and hit 429s the budget system existed
    to prevent.
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

    # Real videos doing well right now, in this persona's own archetype
    # space — INSPIRATION for angle and framing, never a topic to rename or
    # copy. The model still has to invent its own specific idea through
    # every lens below; this just tells it what kind of thing is landing
    # with an audience at the moment. Best-effort and silent on failure —
    # see trending.topic_inspiration for why this must never block or
    # degrade ordinary topic invention.
    trending_block = ""
    try:
        from engine import trending as trending_mod
        rising = trending_mod.topic_inspiration(persona_key)
        if rising:
            trending_block = (
                "\nREAL VIDEOS GETTING VIEWS RIGHT NOW IN THIS SPACE (inspiration for ANGLE "
                "and FRAMING ONLY — invent your own specific topic; do not rename or lightly "
                "reword any of these):\n" + "\n".join(f"- {t}" for t in rising) + "\n"
            )
    except Exception as e:
        print(f"[topic_synthesizer] \u26a0 Trending inspiration skipped ({e}); continuing without it.")

    user = f"""DOMAIN: {persona['label']}
{persona['description']}
{rules_block}
EXAMPLES OF THE DOMAIN'S SHAPE (do not repeat these, invent NEW ones like them):
{chr(10).join('- ' + s for s in persona['seed_topics'])}
{trending_block}
ALREADY COVERED — do not repeat or closely rephrase any of these:
{avoid_text}

{lens_text}

Invent exactly {n} new topics, one per lens, in order."""

    # Reserve BEFORE calling, spend AFTER — the same contract the video
    # pipeline uses. One call buys up to 20 topics, which is the best-value
    # request in the whole system; it just has to be counted.
    if budget is not None:
        budget.require(1, f"topic synthesis for '{persona_key}'")

    try:
        client, model_name = _get_client(api_key)
        response = _call_model_with_clear_errors(client, model_name, SYNTH_SYSTEM, user, temperature=1.0)
        if budget is not None:
            budget.spend(1)
        ideas = _extract_json_array(response.text)
        # `_provider` rides along on each idea so the insert step below can
        # tag it honestly (persona-auto vs persona-auto-groq) instead of
        # collapsing "genuinely AI-invented" into one badge regardless of
        # WHICH model did the inventing.
        cleaned = [
            {"name": i["name"].strip(), "description": i.get("description", "").strip(),
             "_provider": response.provider}
            for i in ideas if i.get("name")
        ]
        provider_note = " (via the Groq backup — Gemini's daily quota was gone)" if response.provider != "gemini" else ""
        print(f"[topic_synthesizer] \u2713 Proposed {len(cleaned)} new topic(s) for "
              f"'{persona['label']}'{provider_note}")
        return cleaned
    except api_budget.QuotaExhausted:
        raise
    except Exception as e:
        # A 429 that reached here means the call was actually made and
        # rejected. Record the spend (it counted against Google's meter even
        # though it returned nothing) and stop the run rather than papering
        # over it with seed topics.
        if api_budget.is_quota_error(e):
            if budget is not None:
                budget.spend(1)
                budget.hard_stop(str(e)[:200])
            raise api_budget.QuotaExhausted(
                f"Gemini daily quota ran out during topic synthesis for "
                f"'{persona_key}'. Topics were NOT invented this run.\n\n"
                f"Refills in about {daycycle.humanize_until_reset()} (midnight Pacific)."
            ) from e
        print(f"[topic_synthesizer] \u26a0 Could not synthesize topics ({e}); "
              f"falling back to seed topics for this persona.")
        return []


def _no_op_result(persona_key: str, added: int = 0) -> dict:
    """The shared shape for 'nothing happened' returns, so every caller —
    the step-summary writer included — can rely on ensure_persona_topic_pool
    ALWAYS returning this dict shape, never a bare int for some paths and a
    dict for others."""
    persona = personas_mod.get_persona(persona_key)
    return {
        "persona": persona_key, "label": (persona or {}).get("label", persona_key),
        "added": added, "from_gemini": 0, "from_groq": 0, "from_seed": 0, "topics": [],
    }


def ensure_persona_topic_pool(persona_key: str, db, min_pool: int = MIN_POOL_SIZE, api_key: str = None,
                              budget=None) -> dict:
    """Tops up a persona's unused topic pool if it has run low.

    "Unused" means an ACTIVE topic that has never produced a video row yet.

    This deliberately does NOT use the concept ledger to decide what is spent.
    The ledger only records on publish, so a topic that had already generated
    three unreviewed videos still counted as "unused" — which is precisely how
    the same subject got made over and over. Counting actual video rows means
    a topic is spent the moment it produces anything, so each new video
    reaches for a genuinely new subject.

    Returns a dict: {added, from_gemini, from_groq, from_seed, topics: [...]}.
    added=0 is normal, not a failure — it just means the pool was already
    deep enough. Always this same shape (never a bare int) so callers — the
    GitHub Actions step-summary writer in particular — never have to guess
    which kind of value they got back.
    """
    persona = personas_mod.get_persona(persona_key)
    if not persona:
        return _no_op_result(persona_key)

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
            return _no_op_result(persona_key)

        needed = min(min_pool - len(unused), SYNTHESIZE_BATCH)
        print(f"[topic_synthesizer] Pool for '{persona['label']}' is at "
              f"{len(unused)}/{min_pool} fresh topic(s) \u2014 synthesizing {needed} more.")

        return _synthesize_and_insert(persona_key, persona, needed, db, api_key, budget)

    except api_budget.QuotaExhausted:
        # Must escape. Swallowing this here would recreate the exact bug
        # fixed inside synthesize_topics one level up the stack.
        raise
    except Exception as e:
        print(f"[topic_synthesizer] \u26a0 Pool check failed for '{persona_key}': {e}")
        return _no_op_result(persona_key)


def force_add_topics(persona_key: str, count: int, db, api_key: str = None, budget=None) -> dict:
    """The manual, deliberate version of ensure_persona_topic_pool: invents
    exactly `count` new topics for ONE persona right now, regardless of how
    deep its pool already is.

    WHY THIS IS A SEPARATE FUNCTION, NOT A FLAG ON THE AUTOMATIC ONE

    The automatic top-up (above) exists to keep the pool from running dry
    without anyone watching it — its entire logic is "only act if the pool
    is thin." A manual "add N topics for this channel" button means the
    opposite: the person pressing it has already decided they want N new
    ideas right now, on purpose, whether or not the pool is thin. Bolting
    that onto ensure_persona_topic_pool as a "force" flag would mean every
    future reader has to hold both meanings in their head for one function;
    two small, single-purpose functions sharing the actual synthesis logic
    (_synthesize_and_insert) reads more clearly than one function with a
    behavior-flipping flag.

    Capped at SYNTHESIZE_BATCH (20) per call — the same limit the automatic
    path respects, and for the same reason: it is the most Gemini will
    reliably return well-reasoned topics for in one request. Asking for
    more than that returns exactly SYNTHESIZE_BATCH, not a silent partial
    miss — callers should surface that plainly rather than let someone
    wonder where the rest went.
    """
    persona = personas_mod.get_persona(persona_key)
    if not persona:
        return _no_op_result(persona_key)

    count = max(1, min(int(count), SYNTHESIZE_BATCH))
    print(f"[topic_synthesizer] Manual request: {count} new topic(s) for '{persona['label']}', "
          f"regardless of current pool depth.")
    try:
        return _synthesize_and_insert(persona_key, persona, count, db, api_key, budget)
    except api_budget.QuotaExhausted:
        raise
    except Exception as e:
        print(f"[topic_synthesizer] \u26a0 Manual topic add failed for '{persona_key}': {e}")
        return _no_op_result(persona_key)


def _synthesize_and_insert(persona_key: str, persona: dict, needed: int, db,
                           api_key: str = None, budget=None) -> dict:
    """Shared by ensure_persona_topic_pool (automatic, gated by pool depth)
    and force_add_topics (manual, unconditional) — the two differ only in
    how they decide `needed`; everything after that is identical: call the
    model, fall back to seeds if it comes up short, insert, tag honestly.
    """
    ledger = cm.load_ledger(db=db)
    all_topic_names = {
        t["name"].strip().lower()
        for t in (db.table("topics").select("name").execute().data or [])
    }

    rotation = datetime.now(timezone.utc).timetuple().tm_yday
    ideas = synthesize_topics(persona_key, needed, all_topic_names, ledger, rotation,
                              api_key=api_key, budget=budget)

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
    added_from_groq = 0
    added_names = []   # for the GitHub Actions step summary / Telegram digest
    for idx, idea in enumerate(ideas[:needed]):
        key = idea["name"].strip().lower()
        if key in all_topic_names:
            continue
        # Anything past index `gemini_invented_count` is a seed-fallback
        # insertion, not a real model invention — label it honestly.
        # Anything BEFORE it came from a real model call, but which one?
        # `_provider` (set in synthesize_topics) tells us — a topic
        # invented by the Groq backup is just as genuinely new as one
        # from Gemini, but it did not come from the primary model, and
        # this project's whole philosophy is to never blur that
        # distinction behind a single ambiguous badge.
        is_real = idx < gemini_invented_count
        from_groq = is_real and idea.get("_provider") == "groq"
        if is_real:
            added_by = "persona-auto-groq" if from_groq else "persona-auto"
        else:
            added_by = "persona-seed-fallback"
        try:
            db.table("topics").insert({
                "name": idea["name"],
                "description": idea.get("description") or "",
                "persona_key": persona_key,
                "is_active": True,
                "added_by": added_by,
            }).execute()
            all_topic_names.add(key)
            added += 1
            added_from_gemini += 1 if (is_real and not from_groq) else 0
            added_from_groq += 1 if from_groq else 0
            added_names.append({
                "name": idea["name"],
                "source": "groq" if from_groq else ("gemini" if is_real else "seed"),
            })
        except Exception as e:
            print(f"[topic_synthesizer] \u26a0 Could not insert topic {idea['name']!r}: {e}")

    seed_count = added - added_from_gemini - added_from_groq
    if added_from_groq:
        print(f"[topic_synthesizer] \u2713 Added {added} topic(s) to '{persona['label']}' "
              f"({added_from_gemini} from Gemini, {added_from_groq} from the Groq backup "
              f"because Gemini's daily quota was gone, {seed_count} from the seed list).")
    elif seed_count:
        print(f"[topic_synthesizer] \u2713 Added {added} topic(s) to '{persona['label']}' "
              f"({added_from_gemini} genuinely new from Gemini, "
              f"{seed_count} filled in from the seed list because "
              f"Gemini synthesis did not return enough — check the Gemini budget log "
              f"above if this keeps happening).")
    else:
        print(f"[topic_synthesizer] \u2713 Added {added} topic(s) to '{persona['label']}', "
              f"all genuinely invented by Gemini.")

    # Returning a dict (not a bare int) is what lets the workflow print a
    # real "here is exactly what got added" summary instead of just a
    # count — see the Add Topics workflow's step-summary step.
    return {
        "persona": persona_key, "label": persona["label"], "added": added,
        "from_gemini": added_from_gemini, "from_groq": added_from_groq,
        "from_seed": seed_count, "topics": added_names,
    }


def resolve_active_personas(db) -> list:
    """Works out which personas should have topics invented for them.

    BUGFIX — THIS IS WHY CHANNELS 2 AND 3 NEVER GOT TOPICS.

    This used to check three sources in strict priority order and RETURN AT
    THE FIRST ONE THAT MATCHED, with the `auto_topic_personas` setting first
    on the reasoning that "a person set it deliberately". Nobody had set it.
    Migration 002 seeded it:

        SELECT 'auto_topic_personas', 'tech_science_explainer'

    So from the moment the database was created, source 1 always matched with
    exactly one persona, and source 2 — personas attached to enabled channels
    — became unreachable dead code. Adding a Comedy channel and a Tamil
    Quotes channel on the Channels page had literally no effect on topic
    invention, forever, with no error anywhere. The log line
    "Using auto_topic_personas setting: ['tech_science_explainer']" was the
    only symptom, and it read like correct behaviour.

    NOW: sources are UNIONED, not raced.

      - Any persona with an ENABLED channel always gets topics. That is what
        enabling a channel means; a setting should not be able to silently
        cancel it.
      - The `auto_topic_personas` setting ADDS personas on top. It is still
        useful — it is how you generate for a domain before its channel
        exists — it just can no longer subtract.
      - Personas referenced by existing topics are the last-resort fallback
        for a database with neither channels nor a setting.
    """
    selected, sources = {}, {}

    # ── enabled channels (authoritative — cannot be overridden) ──────────
    try:
        channels = db.table("channels").select("persona_key, name").eq("is_enabled", True).execute().data or []
        for c in channels:
            key = c.get("persona_key")
            if key and personas_mod.get_persona(key):
                selected[key] = True
                sources[key] = f"channel '{c.get('name') or key}'"
    except Exception as e:
        print(f"[topic_synthesizer] \u26a0 Could not read channels: {e}")

    # ── explicit setting (additive) ──────────────────────────────────────
    try:
        rows = db.table("settings").select("key, value").eq("key", "auto_topic_personas").execute().data or []
        if rows and (rows[0].get("value") or "").strip():
            for k in rows[0]["value"].split(","):
                k = k.strip()
                if k and personas_mod.get_persona(k) and k not in selected:
                    selected[k] = True
                    sources[k] = "Settings"
    except Exception:
        pass

    # ── last resort: whatever existing topics already point at ───────────
    if not selected:
        try:
            topics = db.table("topics").select("persona_key").eq("is_active", True).execute().data or []
            for t in topics:
                key = t.get("persona_key")
                if key and personas_mod.get_persona(key):
                    selected[key] = True
                    sources[key] = "existing topics"
        except Exception:
            pass

    if not selected:
        print("[topic_synthesizer] No personas configured anywhere \u2014 automatic topic "
              "rotation is OFF. Pick a persona on the Channels page, or set "
              "'auto_topic_personas' in Settings, to turn it on.")
        return []

    result = sorted(selected)
    print(f"[topic_synthesizer] Inventing topics for {len(result)} persona(s):")
    for key in result:
        print(f"[topic_synthesizer]   - {key}  (from {sources[key]})")
    return result


def ensure_all_active_persona_pools(db, min_pool: int = MIN_POOL_SIZE, budget_factory=None) -> dict:
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
        # Each persona spends against ITS OWN channel's budget, matching the
        # key it actually uses. Counting a comedy-key call against the
        # science key's meter would make per-channel keys pointless.
        budget = budget_factory(persona_key) if budget_factory else None
        try:
            results[persona_key] = ensure_persona_topic_pool(
                persona_key, db, min_pool, api_key=api_key, budget=budget)
        except api_budget.QuotaExhausted as e:
            # One persona running dry must not stop the others — they may be
            # on entirely separate Gemini keys with quota to spare.
            print(f"[topic_synthesizer] \u26a0 '{persona_key}' skipped: {e}")
            results[persona_key] = _no_op_result(persona_key)
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
