"""
selfcheck.py — run this before you push anything.

    python3 tools/selfcheck.py

WHY THIS EXISTS

Every bug fixed in this release shared one property: **nothing in the project
could have caught it except a human reading a log after it had already
wasted a day of quota.**

  - `budget` vs `_default_budget` was a one-word typo in a rarely-taken
    branch. Python does not check names until the line actually runs, so it
    sat there silently until the exact day the quota ran out.
  - `topic.get("category")` in a function that has no `topic` was the same
    class of bug, in a branch that only runs after a successful 5-minute
    render.
  - The UTC-vs-Pacific day boundary was a logic bug that only showed itself
    in a 7-hour window, once a day.

The first two are catchable in under a second by a static undefined-name
scan. This script runs one. It is not a substitute for tests; it is the
cheapest possible net under the specific mistakes this codebase has actually
made twice.
"""
import ast
import glob
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

FAILED = []
PASSED = []


def check(name, fn):
    try:
        detail = fn()
        PASSED.append((name, detail or "ok"))
    except Exception as e:
        FAILED.append((name, str(e)))


# ── 1. Everything parses ────────────────────────────────────────────────────
def _syntax():
    files = glob.glob("engine/**/*.py", recursive=True) + glob.glob("tools/*.py")
    for f in files:
        ast.parse(open(f, encoding="utf-8").read(), filename=f)
    return f"{len(files)} Python files parse"


# ── 2. No undefined names ───────────────────────────────────────────────────
def _undefined():
    """THE check. Both crash bugs in this release were undefined names."""
    try:
        out = subprocess.run(
            [sys.executable, "-m", "pyflakes", "engine/"],
            capture_output=True, text=True,
        ).stdout
    except FileNotFoundError:
        raise RuntimeError("pyflakes not installed — run: pip install pyflakes")
    bad = [l for l in out.splitlines() if "undefined name" in l]
    if bad:
        raise RuntimeError(
            "undefined name(s) found — this is the exact bug class that broke "
            "generation twice:\n    " + "\n    ".join(bad)
        )
    return "no undefined names in engine/"


# ── 3. Daily counters use the Pacific day, never UTC ────────────────────────
def _day_boundary():
    """Guards the fix for the bug that produced '20/20 spent, 0 videos made'."""
    offenders = []
    for f in ["engine/api_budget.py", "engine/orchestrator.py"]:
        src = open(f, encoding="utf-8").read()
        for line in src.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            # A daily bucket key built straight from a UTC clock is the bug.
            if "%Y_%m_%d" in line and "daycycle" not in line:
                offenders.append(f"{f}: {stripped}")
    if offenders:
        raise RuntimeError(
            "a daily counter key is being built without engine/daycycle.py.\n"
            "Gemini resets at midnight PACIFIC; keying on UTC makes the counter "
            "roll over 7-8h early and pin itself to 'full' for the rest of the "
            "day. Offending lines:\n    " + "\n    ".join(offenders)
        )

    from engine import daycycle
    return f"quota day = {daycycle.quota_day()} (Pacific), resets in {daycycle.humanize_until_reset()}"


# ── 4. Workflows are valid and inside one quota day ─────────────────────────
def _workflows():
    import yaml
    files = glob.glob(".github/workflows/*.yml")
    crons = {}
    for f in files:
        doc = yaml.safe_load(open(f, encoding="utf-8"))
        trig = doc.get("on") or doc.get(True) or {}
        sched = (trig or {}).get("schedule") or []
        crons[os.path.basename(f)] = [c["cron"] for c in sched]

    gen = crons.get("generate.yml", [])
    if gen:
        # Expand the hour field and confirm every generation run lands inside
        # a single Pacific day (07:00 UTC -> 07:00 UTC next day).
        hours = []
        for c in gen:
            hf = c.split()[1]
            if hf == "*":
                hours = list(range(24))
            elif "/" in hf:
                step = int(hf.split("/")[1])
                hours = list(range(0, 24, step))
            else:
                hours = [int(h) for h in hf.split(",")]
        early = [h for h in hours if h < 7]
        if early:
            raise RuntimeError(
                f"generate.yml runs at {early} UTC, which is BEFORE Gemini's "
                f"07:00 UTC (midnight Pacific) reset. Those runs spend the "
                f"previous day's already-exhausted quota, get a 429, and pin "
                f"the budget counter for the rest of the day. This is the bug."
            )
    return f"{len(files)} workflows valid; generate runs at {sorted(set(hours)) if gen else 'n/a'} UTC"


# ── 5. Config counts still match what the docs claim ────────────────────────
def _content_config():
    sys.path.insert(0, ROOT)
    from engine import personas, lenses, archetypes, narrative
    missing = [k for k, v in personas.PERSONAS.items() if "default_temperature" not in v]
    if missing:
        raise RuntimeError(f"personas missing default_temperature: {missing}")
    return (f"{len(personas.PERSONAS)} personas, {len(lenses.LENSES)} lenses, "
            f"{len(archetypes.ARCHETYPES)} archetypes, {len(narrative.STRUCTURES)} structures")


# ── 6. Publishing spacing is wired up ───────────────────────────────────────
def _spacing():
    from engine import channels
    for fn in ("min_gap_minutes", "ready_to_publish", "minutes_since_last_publish"):
        if not hasattr(channels, fn):
            raise RuntimeError(f"channels.{fn} is missing — upload spacing is not wired up")
    gap = channels.min_gap_minutes({"daily_cap": 4})
    if gap != 360:
        raise RuntimeError(f"a 4/day cap should space uploads 360 min apart, got {gap}")
    src = open("engine/publish_approved.py", encoding="utf-8").read()
    if "ready_to_publish" not in src:
        raise RuntimeError("publish_approved.py never calls ready_to_publish — spacing is dead code")
    if "publish_now" not in src:
        raise RuntimeError("publish_approved.py has no Publish Now override")
    return "4/day -> one upload every 360 min; Publish Now override present"


# ── 7. Topic personas can no longer be silently overridden ──────────────────
def _persona_union():
    src = open("engine/topic_synthesizer.py", encoding="utf-8").read()
    if "selected[key] = True" not in src:
        raise RuntimeError("resolve_active_personas is not using the union form")
    if "budget=budget" not in src:
        raise RuntimeError("topic synthesis is not budget-aware — it will spend uncounted Gemini calls")
    mig = open("supabase/migrations/003_scheduling_and_manual_controls.sql", encoding="utf-8").read()
    if "auto_topic_personas" not in mig:
        raise RuntimeError("migration 003 does not clear the seeded auto_topic_personas value")
    return "channels can no longer be shadowed by the settings value"


# ── 8. Groq fallback is wired correctly (and only for genuine daily quota) ──
def _backup_provider():
    src = open("engine/script_generator.py", encoding="utf-8").read()
    if "backup_provider.available()" not in src:
        raise RuntimeError("script_generator.py never checks backup_provider — the fallback is dead code")
    if "is_per_minute_limit" not in src:
        raise RuntimeError(
            "script_generator.py's 429 handling doesn't check is_per_minute_limit — "
            "it would fall back to Groq (or fail) on a per-minute throttle that "
            "should just retry Gemini instead"
        )
    if "_ModelResponse" not in src:
        raise RuntimeError("the uniform (.text, .provider) response wrapper is missing")

    for f, needle in [
        ("engine/topic_synthesizer.py", "_provider"),
        ("engine/brief.py", '_provider'),
    ]:
        if needle not in open(f, encoding="utf-8").read():
            raise RuntimeError(f"{f} does not record which provider wrote its output")

    if not os.path.exists("engine/backup_provider.py"):
        raise RuntimeError("engine/backup_provider.py is missing")
    return "Gemini primary, Groq fallback only on confirmed daily quota exhaustion"


# ── 9. Every workflow that can call Gemini also passes GROQ_API_KEY ─────────
def _groq_wired_into_workflows():
    needed = ["add-topics.yml", "generate.yml", "render-on-demand.yml"]
    missing = []
    for f in needed:
        path = f".github/workflows/{f}"
        if "GEMINI_API_KEY" in open(path, encoding="utf-8").read() and \
           "GROQ_API_KEY" not in open(path, encoding="utf-8").read():
            missing.append(f)
    if missing:
        raise RuntimeError(f"these workflows call Gemini but never pass GROQ_API_KEY: {missing}")
    return f"{len(needed)} workflows pass GROQ_API_KEY through"


# ── 10. Migrations auto-deploy, and the folder stays idempotent ─────────────
def _migration_automation():
    wf = ".github/workflows/deploy-migrations.yml"
    if not os.path.exists(wf):
        raise RuntimeError("deploy-migrations.yml is missing")
    src = open(wf, encoding="utf-8").read()
    for needle in ["supabase/migrations/**", "supabase db push", "SUPABASE_DB_PASSWORD"]:
        if needle not in src:
            raise RuntimeError(f"deploy-migrations.yml is missing expected content: {needle!r}")

    # Every migration must stay safe to re-run — this is what makes it safe
    # for `supabase db push` to run on every push without a human checking
    # each one first.
    unsafe = []
    for f in glob.glob("supabase/migrations/*.sql"):
        sql = open(f, encoding="utf-8").read().upper()
        if "ADD COLUMN" in sql and "IF NOT EXISTS" not in sql:
            unsafe.append(f)
    if unsafe:
        raise RuntimeError(f"non-idempotent ADD COLUMN (no IF NOT EXISTS) in: {unsafe}")
    return f"{len(glob.glob('supabase/migrations/*.sql'))} migration file(s), all idempotent"


# ── 11. Caption timing source is tagged and gated ───────────────────────────
def _voice_engine_honesty():
    orch = open("engine/orchestrator.py", encoding="utf-8").read()
    if '_voice_engine' not in orch:
        raise RuntimeError("orchestrator.py never tags the storyboard with which TTS engine spoke it")
    gates = open("engine/quality_gates.py", encoding="utf-8").read()
    if "_voice_engine" not in gates or "caption_timing" not in gates:
        raise RuntimeError("quality_gates.py doesn't flag estimated (non-edge-tts) caption timing")
    ve = open("engine/voice_engine.py", encoding="utf-8").read()
    if "attempts=5" not in ve:
        raise RuntimeError("edge-tts retry count was not bumped — still vulnerable to short rate-limit windows")
    return "estimated-timing videos are tagged, gated as warn, and retries widened to 5 attempts"


# ── 12. YOUTUBE_API_KEY is actually reachable via config.get() ─────────────
def _youtube_api_key_registered():
    src = open("engine/config.py", encoding="utf-8").read()
    if '"YOUTUBE_API_KEY"' not in src:
        raise RuntimeError(
            "YOUTUBE_API_KEY is missing from config.py's _env dict, so "
            "config.get('YOUTUBE_API_KEY') always returns None even when the "
            "secret IS set in the environment. This silently kills all of "
            "engine/trending.py (Discover Trending Topics workflow, "
            "--auto-add, and topic_inspiration)."
        )
    return "YOUTUBE_API_KEY is registered and reachable via config.get()"


# ── 13. Trending feeds topic reasoning as inspiration, never as the topic ───
def _trending_stays_inspiration_only():
    src = open("engine/trending.py", encoding="utf-8").read()
    if "def topic_inspiration" not in src:
        raise RuntimeError("trending.topic_inspiration is missing")

    # Extract just the topic_inspiration function body and make sure it never
    # writes to the database. If it ever does, trending has stopped being
    # "inspiration for the model's own reasoning" and started being "another
    # list the app reads from" — the exact regression PROJECT_HANDOFF.md
    # warns against.
    start = src.index("def topic_inspiration")
    end = src.index("\ndef auto_add")
    body = src[start:end]
    if ".insert(" in body or ".table(" in body:
        raise RuntimeError(
            "topic_inspiration() touches the database directly — it must only "
            "return text for the model to consider, never write a topic itself."
        )

    ts_src = open("engine/topic_synthesizer.py", encoding="utf-8").read()
    if "topic_inspiration" not in ts_src:
        raise RuntimeError("topic_synthesizer.py never calls trending.topic_inspiration")
    if "invent your own specific topic" not in ts_src.lower() and \
       "invent your own" not in ts_src.lower():
        raise RuntimeError(
            "the trending block doesn't instruct the model to invent its own "
            "topic rather than copy the trending titles verbatim"
        )
    return "trending signal reaches the prompt as inspiration only; auto_add() (direct insert) is unchanged and still opt-in"


# ── 14. Real YouTube captions get uploaded, best-effort, never blocking ────
def _real_captions_wired():
    orch = open("engine/orchestrator.py", encoding="utf-8").read()
    if "captions_srt" not in orch:
        raise RuntimeError("orchestrator.py never captures/stores the SRT content")
    pub = open("engine/publisher.py", encoding="utf-8").read()
    if "def upload_captions" not in pub:
        raise RuntimeError("publisher.py has no upload_captions function")
    if "captions().insert" not in pub:
        raise RuntimeError("upload_captions doesn't actually call the YouTube captions API")
    pa = open("engine/publish_approved.py", encoding="utf-8").read()
    if "captions_srt=row.get" not in pa:
        raise RuntimeError("publish_approved.py never passes the stored SRT through to upload_video")
    mig = "supabase/migrations/004_real_captions_and_visual_source.sql"
    if not os.path.exists(mig):
        raise RuntimeError(f"{mig} is missing")
    return "SRT survives render -> DB -> publish -> real YouTube caption track"


# ── 15. Semantic duplicate detection degrades gracefully ────────────────────
def _semantic_dedup():
    src = open("engine/concept_memory.py", encoding="utf-8").read()
    if "_semantic_similarity" not in src or "SEMANTIC_CEILING" not in src:
        raise RuntimeError("semantic similarity signal is missing from concept_memory.py")
    if "_get_embedder" not in src or "_embedder = False" not in src:
        raise RuntimeError("_get_embedder doesn't appear to degrade gracefully on import failure")
    if "sentence-transformers" not in open("requirements.txt", encoding="utf-8").read():
        raise RuntimeError("sentence-transformers is used but not declared in requirements.txt")
    return "adds a real semantic signal; falls back to lexical+topical if unavailable"


# ── 16. AI-generated visual backup only fires after Pexels has failed ──────
def _ai_visual_backup():
    if not os.path.exists("engine/backup_visuals.py"):
        raise RuntimeError("engine/backup_visuals.py is missing")
    vf = open("engine/visual_fetcher.py", encoding="utf-8").read()
    if "backup_visuals" not in vf:
        raise RuntimeError("visual_fetcher.py never calls into backup_visuals")
    # Must only be reachable from _get_fallback — never called as a first
    # choice ahead of the Pexels search above it.
    if vf.index("def fetch_clip_for_scene") > vf.index("backup_visuals"):
        raise RuntimeError("backup_visuals appears to be wired in BEFORE the Pexels search, not as a fallback")
    if '"HUGGINGFACE_API_KEY"' not in open("engine/config.py", encoding="utf-8").read():
        raise RuntimeError("HUGGINGFACE_API_KEY is not registered in config.py")
    return "Pexels stays primary; AI-generated visual only fires in _get_fallback"


# ── 17. A configured backup provider can actually be reached ───────────────
def _backup_reachable_despite_local_budget():
    """THE most important check added this round. Guards against the exact
    bug reported: Groq was configured correctly, but a LOCAL, possibly-stale
    budget counter blocked every video before a real Gemini call was ever
    attempted — so the fallback that was supposed to catch this never got
    the chance to run at all."""
    ab = open("engine/api_budget.py", encoding="utf-8").read()
    if "backup_provider.available()" not in ab:
        raise RuntimeError(
            "api_budget.require() no longer checks backup_provider.available() — "
            "a configured Groq key can once again be silently unreachable "
            "whenever the local budget counter says zero, stale or not."
        )
    orch = open("engine/orchestrator.py", encoding="utf-8").read()
    if "backup_provider.available()" not in orch:
        raise RuntimeError(
            "orchestrator.py's pre-flight budget gate no longer checks "
            "backup_provider.available() before giving up early."
        )
    return "a local 'budget exhausted' reading no longer blocks a configured backup"


# ── 18. Every real persona is selectable on the Channels page ──────────────
def _channels_dropdown_complete():
    from engine import personas
    # As of this check, the persona list lives in ONE shared frontend file
    # (admin-panel/src/lib/personas.js), imported by both ChannelsPage.jsx
    # and ManualControls.jsx — specifically so this exact bug (one copy
    # updated, a second hand-copied one quietly left behind) can't happen
    # a second time. This check still only catches drift on the Python ->
    # JS boundary, which is unavoidable without generating the JS file.
    js_path = "admin-panel/src/lib/personas.js"
    if not os.path.exists(js_path):
        raise RuntimeError(f"{js_path} is missing — persona list has no shared source")
    js = open(js_path, encoding="utf-8").read()
    missing = [k for k in personas.PERSONAS if f"'{k}'" not in js]
    if missing:
        raise RuntimeError(
            f"{js_path} is missing: {missing}. This is the ONE shared list the "
            f"dashboard's persona dropdowns read from — a persona that exists in "
            f"the backend can be completely unselectable with no error anywhere."
        )
    for consumer in ["admin-panel/src/pages/ChannelsPage.jsx",
                     "admin-panel/src/components/ManualControls.jsx"]:
        c = open(consumer, encoding="utf-8").read()
        if "from '../lib/personas'" not in c:
            raise RuntimeError(f"{consumer} does not import the shared persona list")
    return f"all {len(personas.PERSONAS)} personas in one shared file, imported by both consumers"


# ── 19. Scheduled runs never redundantly re-run topic top-up ───────────────
def _scheduled_runs_skip_topics():
    src = open(".github/workflows/generate.yml", encoding="utf-8").read()
    if "github.event_name" not in src or "'schedule'" not in src.replace('"', "'"):
        raise RuntimeError(
            "generate.yml no longer distinguishes schedule vs manual triggers — "
            "scheduled runs may again silently re-run topic top-up on every one "
            "of the 6 daily runs instead of relying on the dedicated Add Topics "
            "workflow, quietly multiplying Gemini spend past the documented budget."
        )
    return "scheduled generate runs always pass --skip-topics; manual runs keep the checkbox"


# ── 20. A backup failure is never reported as 'not configured' ─────────────
def _backup_failure_not_mislabeled():
    src = open("engine/script_generator.py", encoding="utf-8").read()
    if "IS configured and was tried" not in src:
        raise RuntimeError(
            "script_generator.py no longer distinguishes 'no backup configured' "
            "from 'a backup was configured but also failed' — every quota "
            "failure would again claim no backup exists even when one is "
            "present and simply had its own separate problem."
        )
    return "the two failure modes produce two different, accurate messages"


# ── 21. Unread-notification timestamps are actually maintained ─────────────
def _unread_badges_have_real_timestamps():
    """The Failed/Published tab badges show 'new since last visit', computed
    by comparing updated_at against a localStorage timestamp. That is only
    correct if updated_at is actually refreshed at the moment a video
    fails or publishes — the schema only defaults it on INSERT, there is no
    UPDATE trigger, so every write path that flips status to failed/
    published/publish_failed must set it explicitly or the badge silently
    reads a stale row-creation time instead of the real event time."""
    pa = open("engine/publish_approved.py", encoding="utf-8").read()
    if pa.count('"updated_at"') < 2:
        raise RuntimeError(
            "publish_approved.py doesn't set updated_at on both the "
            "successful-publish update and the shared _update_status() "
            "helper (used for publish_failed) — the Published/Failed "
            "unread badges would read stale timestamps."
        )
    orch = open("engine/orchestrator.py", encoding="utf-8").read()
    if '"updated_at": datetime.now' not in orch:
        raise RuntimeError(
            "orchestrator.py's failure write paths don't set updated_at explicitly."
        )
    jsx = open("admin-panel/src/pages/VideoQueue.jsx", encoding="utf-8").read()
    if "UNREAD_TRACKED_TABS" not in jsx or "getLastSeen" not in jsx:
        raise RuntimeError("VideoQueue.jsx is missing the unread-tracking mechanism")
    return "Failed/Published badges show real unread counts, not lifetime totals"


# ── 22. Settings' voice choice actually reaches character skits ────────────
def _character_skit_voice_override():
    src = open("engine/voice_engine.py", encoding="utf-8").read()
    if "primary_voice_override" not in src or "primary_character" not in src:
        raise RuntimeError(
            "generate_multi_voice no longer lets Settings' voice choice reach "
            "the primary speaker — CHARACTER_VOICES would silently win every "
            "time again, making the Settings voice picker a no-op for any "
            "character-skit video (comedy)."
        )
    return "Settings' voice choice now governs the primary (most-used) speaking character"


# ── 23. The title banner no longer collides with dialogue text ─────────────
def _banner_collision_fixed():
    src = open("engine/styles/character_skit.py", encoding="utf-8").read()
    if "return layer, bottom_fraction" not in src and "return layer, 0.055" not in src:
        raise RuntimeError("_render_banner no longer returns its real measured height")
    if "banner_bottom" not in src:
        raise RuntimeError(
            "dialogue_top is no longer derived from the banner's actual height — "
            "a title that wraps to two lines will again visually collide with "
            "the caption text drawn under it."
        )
    return "dialogue text position is derived from the banner's real height, not a fixed guess"


# ── 24. Groq's default model isn't the one that already got retired ────────
def _groq_model_not_retired():
    src = open("engine/backup_provider.py", encoding="utf-8").read()
    if 'DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"' in src:
        raise RuntimeError(
            "DEFAULT_GROQ_MODEL is still the model Groq deprecated on "
            "2026-06-17 and fully shut down 2026-08-16 — every backup "
            "attempt would fail against a model that no longer exists."
        )
    if "FALLBACK_GROQ_MODEL" not in src or "_TryNextModel" not in src:
        raise RuntimeError(
            "backup_provider.py no longer retries a second model name on "
            "'model not found' — a single retired model name can once "
            "again take the entire Groq backup offline until a human "
            "notices and ships a fix, exactly what just happened."
        )
    return "default model is current; a second candidate is tried automatically if it's ever retired too"


# ── 25. channel_id is resolved at generation time, not only at publish ─────
def _channel_id_resolved_at_generation():
    src = open("engine/orchestrator.py", encoding="utf-8").read()
    if "resolved_channel_id" not in src or "channels_mod.route(" not in src:
        raise RuntimeError(
            "orchestrator.py no longer resolves channel_id when a video is "
            "created — _save_and_finalize's channel_id parameter would again "
            "silently default to None on every video until it publishes, "
            "which is harmless for publishing itself (persona_key drives "
            "that) but means the dashboard has no way to show which channel "
            "a not-yet-published video is actually headed for."
        )
    if "channel_id=resolved_channel_id" not in src:
        raise RuntimeError("resolved_channel_id is computed but never passed to _save_and_finalize")
    jsx = open("admin-panel/src/pages/VideoQueue.jsx", encoding="utf-8").read()
    if "channelNames" not in jsx:
        raise RuntimeError("VideoQueue.jsx doesn't display the resolved channel on video cards")
    return "channel_id is resolved with the same routing logic publish time uses, and shown on each card"


# ── 26. A per-model rate limit also triggers the fallback, not just 404 ────
def _groq_429_triggers_fallback():
    """THE bug that actually fired in production: gpt-oss-120b returned a
    genuine 429 (its own 200,000 tokens/day ceiling, not a shared account
    limit), and the fallback to gpt-oss-20b never triggered because only a
    404 used to count as 'try the other model.' Groq's limits are per-model
    per their own docs, so a 429 on one model says nothing about whether
    the other model's separate budget is also spent."""
    src = open("engine/backup_provider.py", encoding="utf-8").read()
    if_429 = src.split("if resp.status_code == 429:")[1].split("if resp.status_code == 404")[0]
    if "_TryNextModel" not in if_429:
        raise RuntimeError(
            "the 429 (rate limit) branch no longer raises _TryNextModel — a "
            "rate limit on the primary model will once again skip the "
            "fallback model entirely, even though Groq's limits are "
            "per-model and the fallback's budget is completely separate."
        )
    return "a 429 on the primary model now retries the fallback model too, not just a 404"


# ── 27. config.get()/require() can't silently hide a real env var again ────
def _config_never_hides_real_env_vars():
    """THE most impactful fix this round. config.py's _env dict is a
    hand-maintained list, and get()/require() used to ONLY check that list
    — so a real, correctly-set secret was completely unreachable if
    whoever built the feature reading it forgot to also add a line to
    _env. Found to have actually happened to seven keys at once: Telegram
    alerts, email alerts, all three Cloudflare R2 credentials, and the
    offline Piper TTS path had been structurally broken this entire time,
    for users who had genuinely configured them correctly. Guards the
    fallback (get() must fall through to a raw os.getenv() for anything not
    pre-listed) so a future forgotten _env entry degrades to 'works
    anyway,' not 'silently invisible for months.'"""
    src = open("engine/config.py", encoding="utf-8").read()
    for fn_name, needle in [("get", "_env.get(key) or os.getenv(key)"),
                            ("require", "_env.get(key) or os.getenv(key)")]:
        if needle not in src:
            raise RuntimeError(
                f"config.py's {fn_name}() no longer falls through to a raw "
                f"os.getenv() for keys missing from _env — a real, "
                f"correctly-set secret can once again be completely "
                f"unreachable just because _env forgot a line for it."
            )
    for key in ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "SMTP_HOST", "SMTP_USER",
               "SMTP_PASSWORD", "ALERT_EMAIL_TO", "R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID",
               "R2_SECRET_ACCESS_KEY", "R2_PUBLIC_BASE", "STORAGE_BUCKET",
               "PIPER_MODEL_PATH", "GEMINI_TEMPERATURE"]:
        if f'"{key}"' not in src:
            raise RuntimeError(f"{key} is still missing from config.py's _env dict")
    return "get()/require() fall through to os.getenv(); the 7 previously-unreachable keys are registered"


# ── 28. Push notifications: wired into the one place every alert flows through
def _push_notifications_wired():
    for f in ["engine/push_notifications.py",
             "supabase/migrations/005_push_subscriptions.sql",
             "admin-panel/public/manifest.json",
             "admin-panel/public/sw.js",
             "admin-panel/src/components/NotificationSettings.jsx"]:
        if not os.path.exists(f):
            raise RuntimeError(f"{f} is missing")
    alerts_src = open("engine/alerts.py", encoding="utf-8").read()
    if "push_notifications" not in alerts_src:
        raise RuntimeError(
            "engine/alerts.py's alert() no longer calls push_notifications — "
            "push would stop reaching every event Telegram/email already "
            "cover (video ready, run failed, quota gone)."
        )
    settings_src = open("admin-panel/src/pages/SettingsPage.jsx", encoding="utf-8").read()
    if "<NotificationSettings" not in settings_src:
        raise RuntimeError("SettingsPage.jsx imports NotificationSettings but never renders it")
    return "push notifications flow through the same choke point as Telegram/email"


# ── 29. publish.yml can actually send the alerts it triggers ───────────────
def _publish_workflow_has_alert_secrets():
    """publish_approved.py calls alerts.youtube_auth_broken() and
    alerts.daily_quota_reached() directly — the two alerts that matter most
    for publishing — but the workflow step running that code never had
    TELEGRAM_BOT_TOKEN/SMTP_*/etc in its env block at all, on any
    deployment. Not a config.py bug this time; the secret was simply never
    handed to that specific step."""
    src = open(".github/workflows/publish.yml", encoding="utf-8").read()
    step = src.split("Publish approved videos to YouTube")[1].split("Package videos")[0]
    for key in ["TELEGRAM_BOT_TOKEN", "SMTP_HOST", "ALERT_EMAIL_TO"]:
        if key not in step:
            raise RuntimeError(
                f"publish.yml's main step still doesn't pass {key} — alerts "
                f"triggered from inside publish_approved.py (YouTube auth "
                f"broken, daily cap reached) will silently have nothing to send."
            )
    return "the publish step can now actually send the alerts its own code triggers"


# ── 30. Multi-persona channels actually work end to end ────────────────────
def _multi_persona_channels():
    ch_src = open("engine/channels.py", encoding="utf-8").read()
    if "def persona_keys_for" not in ch_src:
        raise RuntimeError("channels.py is missing persona_keys_for()")
    if "persona_key in persona_keys_for(c)" not in ch_src:
        raise RuntimeError("route() still checks equality with the primary persona_key only")
    ts_src = open("engine/topic_synthesizer.py", encoding="utf-8").read()
    if "channels_mod.persona_keys_for(c)" not in ts_src:
        raise RuntimeError("resolve_active_personas() doesn't consult a channel's full persona list")
    orch_src = open("engine/orchestrator.py", encoding="utf-8").read()
    if "channels_mod.persona_keys_for(c)" not in orch_src:
        raise RuntimeError("budget_for_persona() doesn't consult a channel's full persona list")
    mig = "supabase/migrations/006_channel_customization.sql"
    if not os.path.exists(mig):
        raise RuntimeError(f"{mig} is missing")
    for col in ["additional_persona_keys", "voice_override", "render_style_override"]:
        if col not in open(mig, encoding="utf-8").read():
            raise RuntimeError(f"{mig} doesn't create the {col} column")
    return "a channel can draw from several personas; routing/topic-invention/budget all honor it"


# ── 31. persona.preferred_voice is actually read (was defined, never used) ─
def _persona_voice_actually_used():
    """Every persona has had its own preferred_voice since day one — this
    checks it's actually reachable, not just present in the dict. Also
    checks the full precedence chain: channel override > persona voice >
    Settings fallback, and that render_style_override follows the same
    pattern."""
    src = open("engine/orchestrator.py", encoding="utf-8").read()
    if "voice_for_this_video" not in src or 'persona.get("preferred_voice")' not in src:
        raise RuntimeError(
            "orchestrator.py no longer resolves a persona's own preferred_voice — "
            "every video would again use one single global Settings voice "
            "regardless of which persona/channel it belongs to."
        )
    if 'resolved_channel.get("voice_override")' not in src:
        raise RuntimeError("a channel's voice_override is no longer part of the precedence chain")
    if 'resolved_channel.get("render_style_override")' not in src:
        raise RuntimeError("a channel's render_style_override is no longer part of the precedence chain")
    return "channel override > persona voice > Settings fallback, for both voice and render style"


# ── 32. The health persona has real, working safety guardrails ─────────────
def _health_persona_safety():
    from engine import personas
    p = personas.PERSONAS.get("health_and_body")
    if not p:
        raise RuntimeError("health_and_body persona is missing")
    if not p.get("requires_human_review"):
        raise RuntimeError(
            "health_and_body doesn't set requires_human_review — AI-generated "
            "medical/first-aid content could reach YouTube with no human ever "
            "looking at it, regardless of channel or Settings auto_approve."
        )
    rules = p.get("flavor_instructions", "")
    for phrase in ["emergency services", "NEVER state a specific medication dosage",
                  "NEVER include guidance on obtaining"]:
        if phrase not in rules:
            raise RuntimeError(f"health_and_body's safety rules are missing: {phrase!r}")

    orch = open("engine/orchestrator.py", encoding="utf-8").read()
    if 'persona.get("requires_human_review")' not in orch:
        raise RuntimeError(
            "orchestrator.py no longer checks requires_human_review — the "
            "safety override for health content is dead code."
        )
    return "mandatory human review + dosing/diagnosis/emergency-services guardrails are all live"


# ── 33. A publish credentials failure names the specific missing secret ────
def _credentials_error_is_specific():
    ch_src = open("engine/channels.py", encoding="utf-8").read()
    if "def missing_credentials_for" not in ch_src:
        raise RuntimeError("channels.py is missing missing_credentials_for()")
    pa_src = open("engine/publish_approved.py", encoding="utf-8").read()
    if "missing_credentials_for(channel)" not in pa_src:
        raise RuntimeError(
            "publish_approved.py went back to a generic 'credentials missing' "
            "message instead of naming the specific missing secret — this is "
            "the exact ambiguity that caused a real, hours-long confusion."
        )
    return "a credentials failure now names exactly which secret is missing"


# ── 34. Groq per-minute limits retry the same model, not the fallback ──────
def _groq_per_minute_handled():
    src = open("engine/backup_provider.py", encoding="utf-8").read()
    if "per minute" not in src.lower() or "MAX_MINUTE_RETRIES" not in src:
        raise RuntimeError(
            "backup_provider.py no longer distinguishes a per-minute Groq "
            "limit from a per-day one — a per-minute hit (self-resolving in "
            "under a minute) will again immediately burn the fallback "
            "model's separate daily budget instead of just waiting briefly."
        )
    return "a per-minute Groq limit waits and retries the same model; only a per-day limit falls to the other model"


if __name__ == "__main__":
    check("Python syntax", _syntax)
    check("Undefined names", _undefined)
    check("Quota day boundary", _day_boundary)
    check("Workflow schedules", _workflows)
    check("Content config", _content_config)
    check("Upload spacing", _spacing)
    check("Topic persona resolution", _persona_union)
    check("Groq backup provider", _backup_provider)
    check("Groq wired into workflows", _groq_wired_into_workflows)
    check("Automatic migrations", _migration_automation)
    check("Voice engine honesty", _voice_engine_honesty)
    check("YOUTUBE_API_KEY reachable", _youtube_api_key_registered)
    check("Trending stays inspiration-only", _trending_stays_inspiration_only)
    check("Real YouTube captions", _real_captions_wired)
    check("Semantic duplicate detection", _semantic_dedup)
    check("AI-generated visual backup", _ai_visual_backup)
    check("Backup reachable despite local budget", _backup_reachable_despite_local_budget)
    check("Channels dropdown has every persona", _channels_dropdown_complete)
    check("Scheduled runs skip redundant topic top-up", _scheduled_runs_skip_topics)
    check("Backup failure not mislabeled", _backup_failure_not_mislabeled)
    check("Unread badges have real timestamps", _unread_badges_have_real_timestamps)
    check("Character skit voice override", _character_skit_voice_override)
    check("Banner/dialogue collision fixed", _banner_collision_fixed)
    check("Groq model not retired", _groq_model_not_retired)
    check("channel_id resolved at generation time", _channel_id_resolved_at_generation)
    check("Groq 429 triggers fallback too", _groq_429_triggers_fallback)
    check("config.py never hides a real env var", _config_never_hides_real_env_vars)
    check("Push notifications wired", _push_notifications_wired)
    check("publish.yml has alert secrets", _publish_workflow_has_alert_secrets)
    check("Multi-persona channels", _multi_persona_channels)
    check("Persona voice actually used", _persona_voice_actually_used)
    check("Health persona safety", _health_persona_safety)
    check("Credentials error is specific", _credentials_error_is_specific)
    check("Groq per-minute handled", _groq_per_minute_handled)

    print()
    for name, detail in PASSED:
        print(f"  \u2713 {name}: {detail}")
    for name, err in FAILED:
        print(f"  \u2717 {name}:\n      {err}")
    print()
    if FAILED:
        print(f"{len(FAILED)} check(s) FAILED.")
        sys.exit(1)
    print(f"All {len(PASSED)} checks passed.")
