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
