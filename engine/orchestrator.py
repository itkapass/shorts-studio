"""
orchestrator.py
---------------
MAIN — Pipeline Orchestrator

Connects all modules to produce up to MAX_VIDEOS_PER_RUN complete video
drafts per run. Called by GitHub Actions daily cron job (generate.yml).

Flow per video:
  1. Read topics + settings from Supabase
  2. Generate storyboard (script_generator.py) — style-aware: whiteboard_sketch
     scenes get an `icons` list instead of a Pexels `visual_keyword`
  3. Generate voiceover + timestamps (voice_engine.py)
  4. Fetch per-scene B-roll clips (visual_fetcher.py) — stock_footage style only
  5. Build caption cards (subtitle_engine.py)
  6. Mix audio (audio_mixer.py)
  7. Compose & render video (video_compositor.py) — dispatches to the chosen
     render style, see engine/styles/
  8. Upload to Supabase Storage + write "pending" row to DB (engine/storage.py)
  9. Check the new script against the last 30 days for near-duplicates
     (engine/duplicate_check.py) and flag (not silently drop) likely repeats

Does NOT publish to YouTube — that is done by publish_approved.py after you
review and approve videos in the Admin Panel.

NOTE ON MAX_VIDEOS_PER_RUN: this caps how many videos are *generated* per
run. It does NOT need to match YouTube's upload quota (~6/day on the default
10,000-unit budget) — generation never touches the YouTube API. The quota-
aware cap lives in publish_approved.py's PUBLISH_PER_RUN, which governs the
step that actually costs quota.
"""

import os
import uuid
import json
import argparse
import traceback
from datetime import datetime, timezone
from supabase import create_client, Client

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
from engine.script_generator import generate_storyboard, generate_custom_storyboard
from engine.voice_engine import generate_voiceover, get_scene_timestamps
from engine.visual_fetcher import fetch_all_scene_clips
from engine.subtitle_engine import build_caption_cards, CaptionStyle, export_srt
from engine.audio_mixer import mix_audio
from engine.video_compositor import compose_video, default_caption_style_for
from engine.styles import DEFAULT_STYLE, available_styles
from engine import storage_r2 as storage_module
from engine import duplicate_check
from engine import concept_memory
from engine import quality_gates
from engine import alerts
from engine import archetypes as arch
from engine import narrative
from engine import personas as personas_mod
from engine import topic_synthesizer
from engine import api_budget
from engine import backup_provider
from engine import daycycle
from engine import step_summary
from engine import brief as brief_mod
from engine import channels as channels_mod
from engine.styles import is_multi_voice
from engine.voice_engine import generate_multi_voice

MAX_VIDEOS_PER_RUN = 5
OUTPUT_DIR = get("OUTPUT_DIR", "output")


def get_supabase() -> Client:
    cfg = require(["SUPABASE_URL", "SUPABASE_SERVICE_KEY"])
    return create_client(cfg["SUPABASE_URL"], cfg["SUPABASE_SERVICE_KEY"])


# ─── Core Pipeline ────────────────────────────────────────────────────────────

def run_generation_pipeline(manual_count: int = None, skip_topics: bool = False,
                            topics_only: bool = False, persona_key_filter: str = None,
                            topic_id: str = None, topics_for_persona: str = None,
                            topics_count: int = None):
    """Main entry point for generation.

    REWORKED FROM A SINGLE DAILY BATCH TO A SPREAD SCHEDULE.

    Previously one run at 2 AM tried to generate the whole day's videos
    (e.g. 8) in one go. That has two real problems: it looks exactly like
    what YouTube's "mass-produced content" detection watches for — a burst of
    uploads from one source at one moment — and it fails all-or-nothing: if
    Gemini's quota runs out partway through, the rest of the day produces
    nothing until tomorrow.

    Now the workflow itself runs every 2 hours (see generate.yml), and each
    run only tops up toward the day's target rather than trying to hit it in
    one shot. A `videos_generated_<date>` counter (same pattern as the
    Gemini budget counter) tracks how many have been made today across ALL
    of today's runs; each run generates min(PER_RUN_CAP, what's left today).
    Once today's target is reached, later runs exit immediately — that is
    the normal, expected outcome for most runs, not a failure.

    `manual_count`, when given (e.g. `python -m engine.orchestrator --count 5`,
    or the workflow's manual "how many right now" input), bypasses the
    per-run spreading cap for that one run — an explicit human request to
    generate a specific number right now is not the pattern YouTube's
    automation detection cares about; a silent scheduled burst is.
    """
    print(f"\n{'='*60}")
    print(f"[orchestrator] Pipeline started: {datetime.now(timezone.utc).isoformat()}")
    print(f"{'='*60}\n")

    db = get_supabase()
    settings = _load_settings(db)
    branding = {"channel_name": settings.get("channel_name", "")}
    default_style = settings.get("default_render_style", DEFAULT_STYLE)
    if default_style not in available_styles():
        default_style = DEFAULT_STYLE

    try:
        daily_target = int(settings.get("max_videos_daily", MAX_VIDEOS_PER_RUN))
    except (TypeError, ValueError):
        daily_target = MAX_VIDEOS_PER_RUN

    if manual_count is not None:
        videos_this_run = max(1, int(manual_count))
        print(f"[orchestrator] Manual run requested: generating {videos_this_run} now "
              f"(daily target of {daily_target} still applies to scheduled runs).")
    else:
        try:
            per_run = max(1, int(settings.get("videos_per_run") or PER_RUN_SPREAD_CAP))
        except (TypeError, ValueError):
            per_run = PER_RUN_SPREAD_CAP
        made_today = _count_videos_made_today(db)
        remaining_today = max(0, daily_target - made_today)
        videos_this_run = min(remaining_today, per_run)
        print(f"[orchestrator] Daily target {daily_target}, {made_today} made today already, "
              f"{remaining_today} remaining. This run will attempt {videos_this_run}.")

    if topic_id:
        # One exact topic was hand-picked — that IS the request, regardless
        # of manual_count or the daily schedule's usual math.
        videos_this_run = 1

        if videos_this_run < 1:
            print("[orchestrator] Today's target is already met. Nothing to do this run — "
                  "this is normal, not a failure. The next run will check again.")
            return

    auto_approve = str(settings.get("auto_approve", "false")).lower() == "true"

    # Check storage BEFORE rendering anything. A render is 5+ minutes of
    # compute and discovering the bucket is full only at upload time throws
    # all of that away.
    pressure = storage_module.check_storage_pressure(alert_fn=alerts.storage_pressure)
    print(f"[orchestrator] Storage: {pressure['used_mb']} MB / {pressure['limit_mb']} MB "
          f"({pressure['percent']}%) on {pressure['backend']}")
    if pressure["should_pause_renders"]:
        alerts.alert(
            "Generation paused — storage almost full",
            f"Storage is at {pressure['percent']}% ({pressure['used_mb']:.0f} MB of "
            f"{pressure['limit_mb']} MB). No videos were generated this run.\n\n"
            f"Approve, reject or export the videos waiting in the queue and their files "
            f"are freed automatically.",
            severity="critical",
        )
        return

    # Clear out jobs stuck in "Awaiting Render". A row gets that status the
    # moment you save a storyboard, and only leaves it when a render job picks
    # it up. If the render never ran — workflow failed, was cancelled, or was
    # never triggered — the row sits in the queue forever looking like work
    # that is about to happen. Nothing cleaned those up, so they accumulated
    # and had to be deleted by hand.
    _expire_stale_render_jobs(db)

    # One BudgetTracker per Gemini key actually in use this run, not one
    # global tracker. Without this, giving a channel its own key would not
    # help: every video would still increment the SAME shared counter, so
    # three channels would still look like they share one 20/day pool even
    # after being given three separate ones.
    #
    # MOVED UP (was defined below, after topic synthesis had already run).
    # Topic synthesis makes real Gemini calls, so it has to be able to reserve
    # and record them like everything else. While this helper was defined
    # further down, synthesis spent unbudgeted calls first and the tracker
    # started every run already wrong about how much room was left.
    all_channels = channels_mod.load_channels(db=db)
    budgets_by_key: dict = {}

    def budget_for_persona(persona_key):
        channel = next((c for c in all_channels if c.get("persona_key") == persona_key), None)
        api_key = channels_mod.gemini_key_for(channel) if channel else None
        key_id = (channel.get("env_suffix") or "default") if channel else "default"
        if key_id not in budgets_by_key:
            b = api_budget.BudgetTracker(db=db, daily_budget=api_budget.DEFAULT_DAILY_BUDGET, key_id=key_id)
            b.load()
            print(f"[orchestrator] Gemini budget for '{key_id}': {b.spent}/{b.daily_budget} used today.")
            budgets_by_key[key_id] = b
        return budgets_by_key[key_id], api_key

    if topics_for_persona:
        # The manual, targeted version of topic top-up: "invent N topics for
        # THIS channel, right now," regardless of how deep its pool already
        # is. Distinct from the automatic top-up below, which only ever acts
        # when a pool has run thin — see topic_synthesizer.force_add_topics
        # for why these are two functions instead of one with a flag.
        budget, api_key = budget_for_persona(topics_for_persona)
        result = topic_synthesizer.force_add_topics(
            topics_for_persona, topics_count or topic_synthesizer.MIN_POOL_SIZE,
            db, api_key=api_key, budget=budget,
        )
        step_summary.topics_added({topics_for_persona: result})
        if result.get("added"):
            alerts.alert(
                f"{result['added']} topic(s) added to {result.get('label', topics_for_persona)}",
                "\n".join(f"- {t['name']} ({t['source']})" for t in result.get("topics", [])),
                severity="info", force=True,
            )
        return

    # Top up any persona's topic pool that has run low, BEFORE loading topics
    # for this run, so newly synthesized ones are immediately eligible.
    topic_results = {}
    if skip_topics or topic_id:
        print("[orchestrator] Topic top-up skipped for this run "
              + ("(--skip-topics)." if skip_topics else "(a specific topic was hand-picked)."))
    else:
        try:
            topic_results = topic_synthesizer.ensure_all_active_persona_pools(
                db, budget_factory=lambda pk: budget_for_persona(pk)[0])
        except Exception as e:
            print(f"[orchestrator] \u26a0 Persona topic pool check failed (continuing anyway): {e}")

    if topics_only:
        # The "Add Topics" workflow stops here. Topic invention and video
        # generation used to be welded into one run, which meant you could
        # not refill the idea pool without also spending 2 Gemini calls per
        # video and 10 minutes of rendering — and if generation failed, the
        # topics never got added either.
        print("[orchestrator] Topic top-up complete. Stopping here (--topics-only).")
        # Writes exactly which topics got added, for which channel, from
        # which model, onto THIS run's Summary tab — see engine/step_summary.py.
        # This is the direct answer to "how do I know what got added and
        # what they are" without opening the dashboard.
        step_summary.topics_added(topic_results)
        total_added = sum(r.get("added", 0) for r in topic_results.values())
        if total_added:
            alerts.alert(
                f"{total_added} new topic(s) added",
                "\n".join(
                    f"- {r.get('label', k)}: {r.get('added', 0)} added"
                    for k, r in topic_results.items() if r.get("added")
                ),
                severity="info", force=True,
            )
        return

    topics_query = db.table("topics").select("*").eq("is_active", True)
    if persona_key_filter:
        # A manual, targeted run: "generate for THIS channel/persona only,"
        # not whatever the shuffled full pool happens to land on.
        topics_query = topics_query.eq("persona_key", persona_key_filter)
    if topic_id:
        # The most targeted case: one exact topic, chosen by hand in the
        # dashboard rather than left to the pool. persona_key_filter is
        # ignored when this is set — a specific topic already IS a specific
        # persona, filtering by both would only risk an empty result if
        # they ever disagreed.
        topics_query = db.table("topics").select("*").eq("id", topic_id)
    topics = topics_query.execute().data
    tones = db.table("tones").select("*").eq("is_active", True).execute().data

    # Exclude topics that already produced a real video. THIS WAS MISSING
    # ENTIRELY — the query above selects every active topic every single
    # run with no concept of "already used," so once a persona's pool of
    # genuinely fresh ideas ran out, the same handful of topics kept getting
    # reshuffled and re-picked forever. Each repeat still cost a full
    # creative-brief + storyboard Gemini call before concept_memory's
    # duplicate check caught it and threw the attempt away — meaning a
    # real, growing share of the daily Gemini budget was being spent on
    # attempts that were guaranteed to fail before they even started,
    # crowding out genuinely new topics that might otherwise have fit in
    # the same budget.
    #
    # A topic whose only history is a FAILED attempt stays eligible — that
    # failure was Gemini's quota or a 503, not evidence the idea itself was
    # bad, so it deserves a real retry rather than being written off.
    if topics and not topic_id:
        # Skipped entirely when a specific topic_id was hand-picked — if
        # someone deliberately chose exactly this topic, most likely they
        # want it made (or remade) regardless of whether it already
        # produced something, not silently filtered back out.
        topic_ids = [t["id"] for t in topics]
        used_rows = (
            db.table("videos").select("topic_id")
            .in_("topic_id", topic_ids)
            .neq("status", "failed")
            .execute().data
        ) or []
        used_topic_ids = {r["topic_id"] for r in used_rows if r.get("topic_id")}
        if used_topic_ids:
            before = len(topics)
            topics = [t for t in topics if t["id"] not in used_topic_ids]
            print(f"[orchestrator] Excluded {before - len(topics)} already-used topic(s) "
                  f"from selection — {len(topics)} genuinely fresh topic(s) remain.")

    # These two are the quietest failure in the whole system: with nothing
    # active, generation completes "successfully" having produced nothing, and
    # the only trace is one line in a log nobody reads. It has to alert.
    if not topics:
        if topic_id:
            print(f"[orchestrator] Topic id {topic_id} was not found, or is no longer active. "
                  f"Nothing to generate.")
            alerts.alert(
                "Manual video request found no topic",
                f"Topic id {topic_id} was not found or is inactive — nothing was generated.",
                severity="warn",
            )
        elif persona_key_filter:
            label = (personas_mod.get_persona(persona_key_filter) or {}).get("label", persona_key_filter)
            print(f"[orchestrator] No active, unused topics for '{label}'. Nothing to generate. "
                  f"Try 'Add Topics Now' for this channel first.")
            alerts.alert(
                f"No topics available for {label}",
                f"A manual video request for '{label}' found no active, unused topics.\n\n"
                f"Fix: press 'Add Topics Now' for this channel, then try generating again.",
                severity="warn",
            )
        else:
            # These two are the quietest failure in the whole system: with
            # nothing active, generation completes "successfully" having
            # produced nothing, and the only trace is one line in a log
            # nobody reads. It has to alert.
            alerts.alert(
                "No videos generated — every topic is turned off",
                "The daily run found zero ACTIVE topics, so it produced nothing.\n\n"
                "Fix: open your dashboard -> Topic Studio and switch at least one topic "
                "back on. The next scheduled run will pick it up, or run 'Generate Videos' "
                "from the Actions tab to go now.",
                severity="critical",
            )
        return
    if not tones:
        alerts.alert(
            "No videos generated — every tone is turned off",
            "The daily run found zero ACTIVE tones, so it produced nothing.\n\n"
            "Fix: open your dashboard -> Topic Studio -> Tones tab and switch at "
            "least one back on.",
            severity="critical",
        )
        return

    print(f"[orchestrator] Found {len(topics)} topics, {len(tones)} tones, "
          f"default style='{default_style}', generating {videos_this_run} this run, "
          f"auto_approve={auto_approve}")

    import random
    random.shuffle(topics)
    random.shuffle(tones)

    # Loaded once for the whole batch rather than per video: it is the same
    # list every time, and re-reading it five times is five needless queries.
    # Gemini free tier is roughly 20 requests/day. Each video costs ~2 calls
    # (creative brief + storyboard). Check the budget BEFORE starting rather
    # than discovering it via 429s halfway through — a half-spent budget
    # produces a queue full of failures and no videos.
    _default_budget = api_budget.BudgetTracker(
        db=db, daily_budget=settings.get("gemini_daily_budget") or api_budget.DEFAULT_DAILY_BUDGET,
    )
    _default_budget.load()
    cost_each = api_budget.estimate_calls_per_video(use_brief=True, use_ranking=False)
    affordable = _default_budget.remaining // max(cost_each, 1)

    if affordable < 1 and not backup_provider.available():
        # BUGFIX: this used to read `budget.spent`, but the tracker built two
        # lines above is called `_default_budget`; `budget` is only assigned
        # much further down, INSIDE the video loop. Python marks a name local
        # for the whole function the moment it is assigned anywhere in it, so
        # reading it here raised UnboundLocalError — and it raised it inside
        # the quota-exhausted branch, meaning the one situation this branch
        # existed to report cleanly was the exact situation that crashed the
        # workflow with exit code 1. Every red "Generate Video Drafts" run
        # was this single wrong word.
        msg = (
            f"No videos generated: {_default_budget.spent}/{_default_budget.daily_budget} "
            f"of today's Gemini free-tier requests are already spent.\n\n"
            f"The allowance refills in about {daycycle.humanize_until_reset()} "
            f"(midnight Pacific). To fit more videos into it, lower 'Daily video "
            f"generation batch' in Settings, or give each channel its own Gemini "
            f"key from a separate Google account (docs/10). Or add a free Groq "
            f"backup (docs/13) so a day like this doesn't stop generation at all."
        )
        print(f"[orchestrator] {msg}")
        alerts.alert("Gemini daily quota is used up", msg, severity="warn")
        # Exit 0, not a crash. Running out of a free-tier allowance is an
        # expected daily event, not a failure worth a red X in the Actions
        # tab — red should mean "something is broken and needs you".
        return

    if affordable < 1:
        # A backup IS configured. Don't give up before the real call even
        # happens — see api_budget.require()'s docstring for the full story
        # of why this exact check used to make a configured Groq key
        # completely unreachable. Keep going at the schedule's normal pace;
        # every call below will legitimately try Gemini first and only
        # fail over to Groq on a REAL 429, not this local estimate.
        print(f"[orchestrator] Local Gemini budget shows 0 remaining "
              f"({_default_budget.spent}/{_default_budget.daily_budget}), but a Groq "
              f"backup is configured. Proceeding — real calls will fail over as needed.")
    elif affordable < videos_this_run:
        print(f"[orchestrator] Budget allows {affordable} video(s), not {videos_this_run}. "
              f"Generating {affordable} and stopping cleanly.")
        videos_this_run = affordable

    ledger = concept_memory.load_ledger(db=db)
    avoid_list = concept_memory.avoid_list_for_prompt(ledger)
    print(f"[orchestrator] Concept ledger: {len(ledger)} ideas already used.")

    successful, attempted = 0, 0
    gate_rejected, concept_rejected = 0, 0
    errors = []

    for i in range(videos_this_run):
        topic = topics[i % len(topics)]
        tone = tones[i % len(tones)]
        job_id = str(uuid.uuid4())[:8]

        # The archetype decides the KIND of video. A topic can pin one; if it
        # does not, rotate through the allowed set so a channel does not end
        # up publishing the same format every single day.
        # Rotate on the DAY plus the index, not the index alone.
        #
        # This was a real bug: `i` restarts at 0 every run, so with 5 videos a
        # day the rotation only ever reached the first 5 of 10 archetypes.
        # Dark humour, sarcasm, absurd and observational were unreachable —
        # not rare, impossible. Adding the day-of-year advances the starting
        # point every day, so the full set gets used over time.
        #
        # NOTE: datetime is imported at module level ONLY. Re-importing it
        # inside this function made Python treat `datetime` as a local name
        # for the WHOLE function, so the very first line of the function
        # (which prints the start time) crashed with UnboundLocalError before
        # execution ever reached the import. That took down every single
        # generation run. Never shadow a module-level import inside a function.
        day = datetime.now(timezone.utc).timetuple().tm_yday
        all_arch = arch.archetype_names()
        persona_key = topic.get("persona_key")
        persona = personas_mod.get_persona(persona_key) if persona_key else None

        # A persona-tagged topic rotates through ONLY that persona's preferred
        # formats — a comedy-persona topic must never come out as a myth-busting
        # explainer. Topics with no persona keep the original full rotation.
        if persona and persona.get("preferred_archetypes"):
            pool = persona["preferred_archetypes"]
            archetype = topic.get("archetype") or pool[(day + i) % len(pool)]
        else:
            archetype = topic.get("archetype") or all_arch[(day + i) % len(all_arch)]
        allowed, block_reason = arch.is_combination_allowed(
            f"{topic.get('name','')} {topic.get('description','')}", archetype
        )
        if not allowed:
            print(f"[orchestrator] \u26a0 Skipping: {block_reason}")
            archetype = "informative"

        # The third axis: the SHAPE of the video. Rotated rather than random,
        # because random repeats in visible clumps and three POV videos in a
        # row is exactly what makes a channel look automated.
        structure = topic.get("structure") or narrative.pick_structure(archetype, day + i)

        render_style = (
            topic.get("render_style")
            or (persona.get("preferred_render_style") if persona else None)
            or arch.suggest_style(archetype, default_style)
        )
        if render_style not in available_styles():
            render_style = default_style

        print(f"\n[orchestrator] \u2500\u2500 Video {i+1}/{videos_this_run} \u2500\u2500 Job: {job_id}")
        print(f"[orchestrator]    Topic: {topic['name']} | Tone: {tone['name']}")
        print(f"[orchestrator]    Format: {archetype} | Structure: {structure} | Style: {render_style}")

        attempted += 1
        try:
            # Resolve which Gemini key (and therefore which quota pool) this
            # video draws from, based on its persona's channel.
            budget, gemini_key = budget_for_persona(persona_key)

            # Reserve before starting so a video is never begun half-funded.
            budget.require(cost_each, f"video {i+1}")
            # STAGE 1: decide what this video should BE. One extra model call,
            # free on the current tier, and the single biggest quality lever
            # available — it stops the writer defaulting to the obvious video.
            # Each persona knows its own right creativity level — facts need
            # precision (lower), comedy needs surprise (higher). Falls back to
            # the global Settings slider for topics with no persona.
            temperature = (persona.get("default_temperature") if persona else None) \
                          or settings.get("gemini_temperature")

            creative_brief = brief_mod.generate_brief(topic, archetype, structure,
                                                       persona_key=persona_key, api_key=gemini_key)

            # STAGE 2: write it.
            storyboard = generate_storyboard(
                topic, tone, num_scenes=5, render_style=render_style,
                archetype=archetype, avoid_list=avoid_list, structure=structure,
                creative_brief=creative_brief, api_key=gemini_key, temperature=temperature,
            )

            # Reject repeats BEFORE rendering. Checking after would waste the
            # single most expensive step in the pipeline on a video that can
            # never be published.
            dup = concept_memory.check_concept(storyboard, ledger=ledger)
            if dup["is_repeat"]:
                concept_rejected += 1
                print(f"[orchestrator] \u2717 Skipped as repeat ({dup['reason']}, "
                      f"score {dup['score']}) — too close to: {dup['matched_title']!r}")
                continue

            # Second, independent check: near-identical SCRIPT text against
            # every video generated recently, whatever its status.
            #
            # Wrapped in try/except deliberately. This is a SAFETY check, and a
            # safety check that throws is worse than one that is absent: a
            # signature mismatch here previously raised on every single video
            # and killed the entire generation run, so nothing was produced AND
            # nothing was deduplicated. A check that cannot run should degrade
            # to "allow through and say so", never to "destroy the pipeline".
            try:
                script_dup = duplicate_check.check_duplicate(storyboard, db=db)
            except Exception as dup_error:
                print(f"[orchestrator] \u26a0 Script duplicate check failed to run "
                      f"({dup_error}) — continuing without it.")
                script_dup = {"is_duplicate": False}

            if script_dup.get("is_duplicate"):
                concept_rejected += 1
                print(f"[orchestrator] \u2717 Skipped: script is "
                      f"{script_dup['similarity']:.0%} identical to "
                      f"{script_dup['matched_title']!r}")
                continue

            result = _render_pipeline(
                job_id=job_id,
                storyboard=storyboard,
                voice_profile=settings.get("voice_profile", "documentary_male"),
                branding=branding,
                render_style=render_style,
                persona_key=persona_key,
            )

            gates = result.get("quality", {})
            if gates.get("verdict") == "reject":
                gate_rejected += 1
                print(f"[orchestrator] \u2717 Video {i+1} failed quality gates: "
                      f"{quality_gates.summarize(gates)}")
                _log_failure(db, job_id, topic, tone,
                             f"Quality gates rejected: {quality_gates.summarize(gates)}")
                continue

            _save_and_finalize(db, result, job_id, topic.get("id"), tone.get("id"), render_style,
                                auto_approve=auto_approve, archetype=archetype,
                                structure=structure, creative_brief=creative_brief,
                                persona_key=persona_key,
                                topic_label=topic.get("category") or None)

            # The concept is added to the in-memory ledger immediately so the
            # NEXT video in this same batch cannot duplicate it. It is only
            # written to the permanent ledger on approval — see
            # concept_memory.record_concept for why that split matters.
            ledger.insert(0, dup["signature"])
            avoid_list = concept_memory.avoid_list_for_prompt(ledger)

            budget.spend(cost_each)
            _increment_videos_made_today(db)
            successful += 1
            provider = (result.get("storyboard") or {}).get("_provider", "gemini")
            print(f"[orchestrator] \u2713 Video {i+1} queued for review: {result['video_path']} "
                  f"(Gemini budget: {budget.spent}/{budget.daily_budget}, "
                  f"written by: {provider})")

            # Writes exactly what got made — title, channel, format, and
            # which AI actually wrote it — right onto this run's Summary
            # tab. Same "how do I know" answer as the topics step above,
            # for the other half of the pipeline.
            step_summary.video_generated(
                title=result.get("title", "?"),
                persona_label=(persona or {}).get("label", persona_key or "no persona"),
                style=render_style, archetype=archetype, provider=provider,
                job_id=job_id, quality_verdict=(result.get("quality") or {}).get("verdict"),
                voice_engine=(result.get("storyboard") or {}).get("_voice_engine"),
            )
            alerts.alert(
                f"New video ready for review: {result.get('title', '?')}",
                f"Channel: {(persona or {}).get('label', persona_key or 'none')}\n"
                f"Style: {render_style} · Format: {archetype or 'n/a'}\n"
                f"Written by: {provider}"
                + ("  (Groq backup — Gemini's daily quota was gone)" if provider == "groq" else "")
                + f"\nJob ID: {job_id}\n\nOpen the Video Queue -> Pending Review to approve it.",
                severity="info", force=True,
            )

        except api_budget.QuotaExhausted as e:
            # A quota error is a per-DAY condition, not a per-video one.
            # Continuing would guarantee an identical 429 on every remaining
            # video and fill the queue with red — which is exactly what
            # happened before this check existed.
            print(f"[orchestrator] \U0001f6d1 Stopping run: {e}")
            _log_failure(db, job_id, topic, tone, f"Stopped early — Gemini quota: {e}")
            alerts.alert(
                "Generation stopped — Gemini daily quota reached",
                f"{successful} video(s) were generated before the free-tier quota ran out.\n\n"
                f"{e}\n\nThe quota resets at midnight Pacific.",
                severity="warn",
            )
            break

        except Exception as e:
            if api_budget.is_quota_error(e):
                budget.hard_stop(str(e)[:200])
                print(f"[orchestrator] \U0001f6d1 Gemini quota exhausted — stopping the run.")
                # A real, visible row — without this, a quota stop was
                # completely invisible: no failure row, no queue entry,
                # nothing to click on. Exactly the mystery this run created.
                _log_failure(db, job_id, topic, tone,
                             f"Stopped early — Gemini's real daily quota was already used up "
                             f"(likely from earlier attempts today, before quota tracking existed): {e}")
                alerts.alert(
                    "Generation stopped — Gemini daily quota reached",
                    f"{successful} video(s) were generated before the free-tier quota ran out.\n\n"
                    f"The quota resets at midnight Pacific. Lower 'Daily video generation batch' "
                    f"in Settings to fit within it.",
                    severity="warn",
                )
                break

            print(f"[orchestrator] \u2717 Video {i+1} failed: {e}")
            errors.append(f"{topic.get('name','?')}: {str(e)[:160]}")
            traceback.print_exc()
            _log_failure(db, job_id, topic, tone, str(e))

    failed = attempted - successful - gate_rejected - concept_rejected
    print(f"\n{'='*60}")
    print(f"[orchestrator] Done. {successful}/{attempted} generated. "
          f"{gate_rejected} failed quality gates, {concept_rejected} skipped as repeats, "
          f"{failed} errored.")
    print(f"[orchestrator] Open Admin Panel to review and approve videos for publishing.")
    print(f"{'='*60}\n")

    if failed and failed >= max(1, attempted // 2):
        alerts.generation_failed(failed, attempted, errors)

    try:
        pending = len(db.table("videos").select("id").eq("status", "pending").execute().data or [])
    except Exception:
        pending = 0

    alerts.daily_digest({
        "generated": successful, "published": 0, "pending": pending,
        "gate_rejected": gate_rejected, "concept_rejected": concept_rejected,
        "storage_mb": storage_module.usage_mb(),
    })


def generate_video_from_prompt(
    prompt: str,
    tone_name: str = "Curious Explainer",
    tone_desc: str = "Clear, specific, genuinely informative — makes the viewer smarter in 45 seconds",
    hook_style: str = "Surprising Fact / Question",
    voice_profile: str = "documentary_male",
    render_style: str = DEFAULT_STYLE,
    storyboard_override: dict = None,
) -> dict:
    """On-demand generation from a free-form prompt (the --prompt CLI flag,
    and the real path behind the Admin Panel's Create Video page — see
    supabase/functions/generate-storyboard for how the browser reaches this
    safely without exposing the Gemini key client-side)."""
    job_id = str(uuid.uuid4())[:8]
    print(f"\n[orchestrator] \u2500\u2500 On-Demand Custom Video \u2500\u2500 Job: {job_id}")
    print(f"[orchestrator] Prompt: {prompt[:80]}...  Style: {render_style}")

    if render_style not in available_styles():
        render_style = DEFAULT_STYLE

    if storyboard_override:
        storyboard = storyboard_override
    else:
        storyboard = generate_custom_storyboard(
            prompt=prompt, tone_name=tone_name, tone_desc=tone_desc,
            hook_style=hook_style, num_scenes=5, render_style=render_style,
        )

    result = _render_pipeline(
        job_id=job_id, storyboard=storyboard, voice_profile=voice_profile,
        branding=None, render_style=render_style,
    )

    try:
        db = get_supabase()
        _save_and_finalize(db, result, job_id, None, None, render_style, tone_name=tone_name)
        print(f"[orchestrator] \u2713 Custom video saved to Supabase video queue: Job {job_id}")
    except Exception as e:
        print(f"[orchestrator] Note: Supabase save skipped or failed ({e})")

    return result


# ─── Shared Single-Video Renderer (used by both entry points above) ──────────

def _render_pipeline(
    job_id: str,
    storyboard: dict,
    voice_profile: str,
    branding: dict,
    render_style: str,
    persona_key: str = None,
) -> dict:
    """Everything after 'we have a storyboard' — voiceover, timing, visuals,
    captions, audio mix, and final composition. Previously duplicated almost
    verbatim between the scheduled-batch path and the custom-prompt path;
    now there's exactly one place this logic lives."""
    job_output_dir = os.path.join(OUTPUT_DIR, job_id)
    os.makedirs(job_output_dir, exist_ok=True)

    with open(os.path.join(job_output_dir, "storyboard.json"), "w") as f:
        json.dump(storyboard, f, indent=2)

    full_script = " ".join(s["voice_text"] for s in storyboard["scenes"])

    if is_multi_voice(render_style):
        # character_skit gives each character its own voice and synthesises
        # one clip per speaker turn. Running it through the single-narrator
        # path would have both characters sharing one voice, which makes a
        # two-hander unreadable.
        voice_result = generate_multi_voice(
            scenes=storyboard["scenes"], output_dir=job_output_dir,
            job_id=job_id, default_voice=voice_profile,
        )
    else:
        voice_result = generate_voiceover(
            full_script=full_script, voice_profile=voice_profile,
            output_dir=job_output_dir, job_id=job_id,
        )
    total_duration = voice_result["duration_seconds"]
    # Honest tag: which TTS engine actually spoke this video. edge-tts gives
    # exact per-word timing; its fallbacks (Piper, gTTS) estimate it. This
    # rides through to quality_gates (flags a "warn" for review) and the
    # dashboard, the same way _provider tags which AI wrote the script.
    storyboard["_voice_engine"] = voice_result.get("engine", "unknown")

    scenes_with_times = get_scene_timestamps(voice_result["word_timestamps"], storyboard["scenes"])

    # Only the stock_footage style needs real B-roll — whiteboard_sketch and
    # quote_card already have everything they need (icons / mood) straight
    # from the storyboard, so skip the Pexels round-trip entirely for them.
    if render_style == "stock_footage":
        scenes_with_clips = fetch_all_scene_clips(scenes_with_times, job_id)
        # Fold each scene's actual visual source (pexels / cache / ai_generated
        # / fallback) back into the storyboard that gets saved, not just the
        # transient render-time list. Without this, an AI-generated backup
        # visual (see engine/backup_visuals.py) rendered correctly but left no
        # trace anywhere a human could see WHICH scenes it touched — the same
        # kind of silent-provider gap already fixed for the script (Gemini vs
        # Groq) and the voice (edge-tts vs its fallbacks).
        for sb_scene, rendered_scene in zip(storyboard.get("scenes", []), scenes_with_clips):
            sb_scene["_visual_source"] = rendered_scene.get("source")
    else:
        scenes_with_clips = scenes_with_times

    caption_style = default_caption_style_for(render_style, persona_key)
    caption_style.words_per_card = 3
    caption_cards = build_caption_cards(voice_result["word_timestamps"], style=caption_style)
    srt_path = os.path.join(job_output_dir, f"{job_id}.srt")
    export_srt(caption_cards, srt_path)
    # Read back the content (not just the path) so it can ride along in the
    # video row and get uploaded as a REAL YouTube caption track at publish
    # time. Without this, subtitle_engine's own docstring promise — "useful
    # ... as a YouTube subtitle upload" — was never actually kept: the file
    # was written, then discarded when the render job's runner was torn
    # down, since generate and publish run on separate GitHub Actions jobs
    # with no shared filesystem.
    try:
        with open(srt_path, "r", encoding="utf-8") as f:
            captions_srt = f.read()
    except Exception as e:
        print(f"[orchestrator] \u26a0 Could not read back the SRT for storage ({e}); "
              f"burned-in captions are unaffected, only the real-caption upload will be skipped.")
        captions_srt = None

    mixed_audio_path = os.path.join(job_output_dir, f"{job_id}_mixed.mp3")
    mix_audio(
        voiceover_path=voice_result["audio_path"],
        word_timestamps=voice_result["word_timestamps"],
        scene_timestamps=scenes_with_clips,
        total_duration=total_duration,
        output_path=mixed_audio_path,
    )

    video_path = os.path.join(job_output_dir, f"{job_id}_final.mp4")
    compose_video(
        scenes_with_clips=scenes_with_clips,
        mixed_audio_path=mixed_audio_path,
        caption_cards=caption_cards,
        total_duration=total_duration,
        output_path=video_path,
        caption_style=caption_style,
        branding=branding,
        render_style=render_style,
    )

    # Automated QC on the finished file. This is what keeps human review
    # worth doing: only videos that are mechanically sound reach the queue,
    # so the person reviewing is judging whether it is GOOD, not whether it
    # is broken.
    gates = quality_gates.run_gates(video_path, storyboard)
    print(f"[orchestrator] Quality gates: {gates['verdict']} — {quality_gates.summarize(gates)}")

    return {
        "job_id": job_id, "video_path": video_path,
        "title": storyboard["video_title"], "description": storyboard["description"],
        "hashtags": storyboard["hashtags"], "duration": total_duration,
        "storyboard": storyboard,
        "quality": gates,
        "captions_srt": captions_srt,
    }


# ─── Supabase Helpers ─────────────────────────────────────────────────────────

def _load_settings(db: Client) -> dict:
    rows = db.table("settings").select("key, value").execute().data
    return {row["key"]: row["value"] for row in rows} if rows else {}


def _save_and_finalize(db, result, job_id, topic_id, tone_id, render_style, tone_name=None,
                       auto_approve=False, archetype=None, channel_id=None, structure=None,
                       creative_brief=None, persona_key=None, topic_label=None):
    """Saves the video row, uploads the rendered file to Storage (this used
    to only happen inside a separate GitHub Actions YAML step — see
    engine/storage.py's docstring), and flags likely near-duplicates instead
    of silently queuing them as if they were fresh content."""
    dup = duplicate_check.check_duplicate(result["storyboard"])
    flags = {}
    if dup.get("is_duplicate"):
        flags["possible_duplicate"] = True
        flags["similarity"] = dup["similarity"]
        flags["similar_to"] = dup["matched_title"]
        print(f"[orchestrator] \u26a0 Similar to a recent video ({dup['similarity']*100:.0f}% match: "
              f"'{dup['matched_title']}') — queuing anyway, flagged for review.")

    # FIXED: auto_approve existed in settings/Admin Panel but nothing read
    # it — every video always started 'pending' regardless of this toggle.
    gates = result.get("quality") or {}
    if gates.get("verdict") == "warn":
        flags["quality_warnings"] = gates.get("warnings", [])

    # auto_approve is respected, but it never overrides a duplicate flag or a
    # quality warning. Auto-approving a flagged video is precisely how a
    # channel ends up publishing the thing that gets it reviewed.
    safe_to_auto = (
        auto_approve
        and not flags.get("possible_duplicate")
        and gates.get("verdict") != "warn"
    )
    initial_status = "approved" if safe_to_auto else "pending"

    db.table("videos").insert({
        "job_id": job_id,
        "title": result["title"],
        "description": result["description"],
        "hashtags": result["hashtags"],
        "duration": result["duration"],
        "topic_id": topic_id,
        "tone_id": tone_id,
        "tone_name": tone_name,
        "render_style": render_style,
        "archetype": archetype,
        "structure": structure,
        "creative_brief": creative_brief or None,
        "pulse_context": (creative_brief or {}).get("_pulse_used") or None,
        "persona_key": persona_key,
        "category": archetype,          # content FORMAT — used by channels.py routing
        # BUGFIX: this used to be `topic.get("category")`, but no variable
        # named `topic` exists in this function — it receives `topic_id`, an
        # integer. That is a NameError on EVERY video insert, raised only
        # after the full render had already finished, so five minutes of
        # compute was thrown away and the video never reached the queue.
        # It stayed invisible because the quota bugs above stopped every run
        # before it ever got as far as a successful render.
        "topic_label": topic_label,  # YOUR grouping tag, e.g. "office"
        "channel_id": channel_id,
        "quality_verdict": gates.get("verdict"),
        "status": initial_status,
        "storyboard": json.dumps(result["storyboard"]),
        "captions_srt": result.get("captions_srt"),
        "flags": flags or None,  # native dict, NOT json.dumps() — see VideoQueue.jsx, which reads this as an object
        "created_at": datetime.now(timezone.utc).isoformat(),
    }).execute()

    storage_module.upload_video(result["video_path"], job_id, db=db)


# A single automatic run never renders more than this many videos.
#
# ONE, not two. Rendering is by far the heaviest step in the pipeline —
# ffmpeg, text-to-speech and Whisper captioning on a free shared runner —
# and doing two in one job doubles how long that job holds a runner and
# doubles what is thrown away if it times out. Six small runs recover from
# a failure far better than three big ones: lose a run, lose one video.
#
# Override in Settings -> "Videos per run" if you have a paid Gemini key
# and want to move faster.
PER_RUN_SPREAD_CAP = 1


def _count_videos_made_today(db) -> int:
    """How many videos have already been generated today, across every run.

    Persisted the same way as the Gemini budget counter: a settings row keyed
    by the PACIFIC date, incremented after each success. This is what lets
    generation be split across many small runs through the day instead of one
    big batch — each run can tell how much of today's target is already done.

    Keyed on the same day boundary as the Gemini budget on purpose: the two
    numbers are compared against each other in the logs ("0 made today" vs
    "20/20 spent"), and comparing counters that roll over at different times
    is how the original bug hid for so long.
    """
    key = f"videos_made_{daycycle.quota_day()}"
    try:
        rows = db.table("settings").select("value").eq("key", key).execute().data
        return int(rows[0]["value"]) if rows else 0
    except Exception:
        return 0


def _increment_videos_made_today(db, by: int = 1):
    key = f"videos_made_{daycycle.quota_day()}"
    try:
        existing = db.table("settings").select("key, value").eq("key", key).execute().data
        if existing:
            new_val = int(existing[0].get("value") or 0) + by
            db.table("settings").update({"value": str(new_val)}).eq("key", key).execute()
        else:
            db.table("settings").insert({"key": key, "value": str(by)}).execute()
    except Exception as e:
        print(f"[orchestrator] \u26a0 Could not update today's video count: {e}")


def _expire_stale_render_jobs(db, max_age_hours: int = 3):
    """Marks jobs that have been 'queued_for_render' too long as failed.

    3 hours is well beyond the longest legitimate render (about 40 minutes for
    a full batch), so anything older is genuinely stuck rather than slow.

    timedelta is imported here because it is not needed at module level;
    datetime and timezone are NOT re-imported — doing so would shadow the
    module-level names and break this function the same way it broke
    run_generation_pipeline.
    """
    from datetime import timedelta
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=max_age_hours)).isoformat()
        stale = (
            db.table("videos").select("id, job_id")
            .eq("status", "queued_for_render")
            .lt("created_at", cutoff)
            .execute().data
        ) or []
        if not stale:
            return
        for row in stale:
            db.table("videos").update({
                "status": "failed",
                "error_log": (
                    f"Stuck in 'Awaiting Render' for over {max_age_hours} hours. "
                    "The render job never ran or did not finish — check the Actions tab. "
                    "Re-create it from Create Video if you still want this one."
                ),
            }).eq("id", row["id"]).execute()
        print(f"[orchestrator] Cleared {len(stale)} stale 'Awaiting Render' job(s).")
    except Exception as e:
        print(f"[orchestrator] \u26a0 Could not clear stale render jobs: {e}")


def _log_failure(db: Client, job_id: str, topic: dict, tone: dict, error: str):
    try:
        db.table("videos").insert({
            "job_id": job_id,
            "title": f"[FAILED] {topic['name']} + {tone['name']}",
            "status": "failed",
            "error_log": error,
            "topic_id": topic.get("id"),
            "tone_id": tone.get("id"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
    except Exception:
        pass  # Don't let logging failures crash the whole run


def render_existing_job(job_id: str) -> dict:
    """Renders a video for a job_id that already has a storyboard saved in
    Supabase (status should be 'queued_for_render') — used by the Admin
    Panel's Create Video page: generation (via the generate-storyboard edge
    function, which the browser can safely call) and rendering (which needs
    ffmpeg/TTS/Whisper — real compute, not something a browser or a light
    edge function can do) are different steps. This is what "Copy Render
    Command" actually runs; it renders the SPECIFIC storyboard you reviewed
    and possibly edited in the browser, not a freshly regenerated one."""
    db = get_supabase()
    row = db.table("videos").select("*").eq("job_id", job_id).single().execute().data
    if not row:
        raise ValueError(f"No video found with job_id={job_id}")

    storyboard = row["storyboard"] if isinstance(row["storyboard"], dict) else json.loads(row["storyboard"])
    render_style = row.get("render_style") or DEFAULT_STYLE
    if render_style not in available_styles():
        render_style = DEFAULT_STYLE

    print(f"[orchestrator] \u2500\u2500 Rendering existing job {job_id} \u2500\u2500 style={render_style}")
    result = _render_pipeline(
        job_id=job_id, storyboard=storyboard, voice_profile="documentary_male",
        branding=None, render_style=render_style,
    )

    db.table("videos").update({
        "duration": result["duration"],
        "status": "pending",  # now actually rendered — ready for real human review
    }).eq("job_id", job_id).execute()
    storage_module.upload_video(result["video_path"], job_id, db=db)

    print(f"[orchestrator] \u2713 Job {job_id} rendered and uploaded — check the Video Queue.")
    return result


# ─── Entry Point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse as _argparse
    _p = _argparse.ArgumentParser(description="Run the generation pipeline")
    _p.add_argument("--count", type=int, default=None,
                     help="Generate this many videos right now, bypassing the "
                          "spread-across-the-day cap (a deliberate manual run).")
    _p.add_argument("--topics-only", action="store_true",
                     help="Only invent new topics, then stop. No storyboards, "
                          "no rendering. Costs 1 Gemini call per persona.")
    _p.add_argument("--skip-topics", action="store_true",
                     help="Generate videos from the existing topic pool without "
                          "inventing new ones. Saves Gemini calls.")
    _p.add_argument("--persona", type=str, default=None,
                     help="Restrict generation to one persona/channel's topics only.")
    _p.add_argument("--topic-id", type=str, default=None,
                     help="Generate exactly one video for this specific topic id, "
                          "bypassing pool selection and the daily schedule's count.")
    _p.add_argument("--topics-for", type=str, default=None,
                     help="Invent topics for exactly one persona right now, regardless "
                          "of current pool depth, then stop (no rendering). Pair with "
                          "--topics-count.")
    _p.add_argument("--topics-count", type=int, default=None,
                     help="How many topics to invent with --topics-for (default: 15).")
    _args, _ = _p.parse_known_args()
    if _args.topics_for:
        run_generation_pipeline(topics_for_persona=_args.topics_for, topics_count=_args.topics_count)
        raise SystemExit(0)
    if _args.topics_only:
        run_generation_pipeline(topics_only=True)
        raise SystemExit(0)
    if _args.count is not None or _args.skip_topics or _args.persona or _args.topic_id:
        run_generation_pipeline(manual_count=_args.count, skip_topics=_args.skip_topics,
                                persona_key_filter=_args.persona, topic_id=_args.topic_id)
        raise SystemExit(0)
    parser = argparse.ArgumentParser(description="AI Video Pipeline Orchestrator")
    parser.add_argument("--prompt", type=str, help="Generate AND render a custom video for a specific prompt (regenerates the storyboard from scratch)")
    parser.add_argument("--render-job", type=str, help="Render a specific job_id that already has a storyboard saved (e.g. from the Admin Panel's Create Video page)")
    parser.add_argument("--tone", type=str, default="Curious Explainer", help="Tone style (only used with --prompt)")
    parser.add_argument("--voice", type=str, default="documentary_male", help="Voice profile (only used with --prompt)")
    parser.add_argument("--style", type=str, default=DEFAULT_STYLE, choices=available_styles(),
                         help="Render style for this video (only used with --prompt)")
    args = parser.parse_args()

    if args.render_job:
        render_existing_job(args.render_job)
    elif args.prompt:
        generate_video_from_prompt(args.prompt, tone_name=args.tone, voice_profile=args.voice, render_style=args.style)
    else:
        run_generation_pipeline()
