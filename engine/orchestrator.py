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
from engine import channels as channels_mod
from engine.styles import is_multi_voice
from engine.voice_engine import generate_multi_voice

MAX_VIDEOS_PER_RUN = 5
OUTPUT_DIR = get("OUTPUT_DIR", "output")


def get_supabase() -> Client:
    cfg = require(["SUPABASE_URL", "SUPABASE_SERVICE_KEY"])
    return create_client(cfg["SUPABASE_URL"], cfg["SUPABASE_SERVICE_KEY"])


# ─── Core Pipeline ────────────────────────────────────────────────────────────

def run_generation_pipeline():
    """Main entry point for the scheduled batch. Generates up to
    MAX_VIDEOS_PER_RUN videos and queues them as 'pending'."""
    print(f"\n{'='*60}")
    print(f"[orchestrator] Pipeline started: {datetime.now(timezone.utc).isoformat()}")
    print(f"[orchestrator] Generating up to {MAX_VIDEOS_PER_RUN} video drafts...")
    print(f"{'='*60}\n")

    db = get_supabase()
    settings = _load_settings(db)
    branding = {"channel_name": settings.get("channel_name", "")}
    default_style = settings.get("default_render_style", DEFAULT_STYLE)
    if default_style not in available_styles():
        default_style = DEFAULT_STYLE

    # FIXED: max_videos_daily existed in the settings table and the Admin
    # Panel's Settings page, but nothing ever read it — MAX_VIDEOS_PER_RUN
    # was a hardcoded constant, so changing this in the dashboard did
    # nothing. It's now the actual source of truth (falls back to the
    # constant if unset or invalid).
    try:
        videos_this_run = int(settings.get("max_videos_daily", MAX_VIDEOS_PER_RUN))
    except (TypeError, ValueError):
        videos_this_run = MAX_VIDEOS_PER_RUN
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

    topics = db.table("topics").select("*").eq("is_active", True).execute().data
    tones = db.table("tones").select("*").eq("is_active", True).execute().data

    if not topics:
        print("[orchestrator] \u26a0 No active topics found. Add topics in the Admin Panel.")
        return
    if not tones:
        print("[orchestrator] \u26a0 No active tones found. Add tones in the Admin Panel.")
        return

    print(f"[orchestrator] Found {len(topics)} topics, {len(tones)} tones, "
          f"default style='{default_style}', generating {videos_this_run} this run, "
          f"auto_approve={auto_approve}")

    import random
    random.shuffle(topics)
    random.shuffle(tones)

    # Loaded once for the whole batch rather than per video: it is the same
    # list every time, and re-reading it five times is five needless queries.
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
        archetype = topic.get("archetype") or arch.archetype_names()[i % len(arch.archetype_names())]
        allowed, block_reason = arch.is_combination_allowed(
            f"{topic.get('name','')} {topic.get('description','')}", archetype
        )
        if not allowed:
            print(f"[orchestrator] \u26a0 Skipping: {block_reason}")
            archetype = "informative"

        # The third axis: the SHAPE of the video. Rotated rather than random,
        # because random repeats in visible clumps and three POV videos in a
        # row is exactly what makes a channel look automated.
        structure = topic.get("structure") or narrative.pick_structure(archetype, i)

        render_style = topic.get("render_style") or arch.suggest_style(archetype, default_style)
        if render_style not in available_styles():
            render_style = default_style

        print(f"\n[orchestrator] \u2500\u2500 Video {i+1}/{videos_this_run} \u2500\u2500 Job: {job_id}")
        print(f"[orchestrator]    Topic: {topic['name']} | Tone: {tone['name']}")
        print(f"[orchestrator]    Format: {archetype} | Structure: {structure} | Style: {render_style}")

        attempted += 1
        try:
            storyboard = generate_storyboard(
                topic, tone, num_scenes=5, render_style=render_style,
                archetype=archetype, avoid_list=avoid_list, structure=structure,
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
            # duplicate_check has always run, but only as a FLAG applied after
            # rendering, which stopped auto-approve and nothing else — so a
            # repeat still got fully rendered and still landed in the queue.
            # Checking here means an identical script costs one model call
            # instead of five minutes of render time.
            script_dup = duplicate_check.check_duplicate(storyboard, db=db)
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
                                structure=structure)

            # The concept is added to the in-memory ledger immediately so the
            # NEXT video in this same batch cannot duplicate it. It is only
            # written to the permanent ledger on approval — see
            # concept_memory.record_concept for why that split matters.
            ledger.insert(0, dup["signature"])
            avoid_list = concept_memory.avoid_list_for_prompt(ledger)

            successful += 1
            print(f"[orchestrator] \u2713 Video {i+1} queued for review: {result['video_path']}")

        except Exception as e:
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

    scenes_with_times = get_scene_timestamps(voice_result["word_timestamps"], storyboard["scenes"])

    # Only the stock_footage style needs real B-roll — whiteboard_sketch and
    # quote_card already have everything they need (icons / mood) straight
    # from the storyboard, so skip the Pexels round-trip entirely for them.
    if render_style == "stock_footage":
        scenes_with_clips = fetch_all_scene_clips(scenes_with_times, job_id)
    else:
        scenes_with_clips = scenes_with_times

    caption_style = default_caption_style_for(render_style)
    caption_style.words_per_card = 3
    caption_cards = build_caption_cards(voice_result["word_timestamps"], style=caption_style)
    export_srt(caption_cards, os.path.join(job_output_dir, f"{job_id}.srt"))

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
    }


# ─── Supabase Helpers ─────────────────────────────────────────────────────────

def _load_settings(db: Client) -> dict:
    rows = db.table("settings").select("key, value").execute().data
    return {row["key"]: row["value"] for row in rows} if rows else {}


def _save_and_finalize(db, result, job_id, topic_id, tone_id, render_style, tone_name=None,
                       auto_approve=False, archetype=None, channel_id=None, structure=None):
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
        "category": archetype,
        "channel_id": channel_id,
        "quality_verdict": gates.get("verdict"),
        "status": initial_status,
        "storyboard": json.dumps(result["storyboard"]),
        "flags": flags or None,  # native dict, NOT json.dumps() — see VideoQueue.jsx, which reads this as an object
        "created_at": datetime.now(timezone.utc).isoformat(),
    }).execute()

    storage_module.upload_video(result["video_path"], job_id, db=db)


def _expire_stale_render_jobs(db, max_age_hours: int = 3):
    """Marks jobs that have been 'queued_for_render' too long as failed.

    3 hours is well beyond the longest legitimate render (about 40 minutes for
    a full batch), so anything older is genuinely stuck rather than slow.
    """
    from datetime import datetime, timezone, timedelta
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
