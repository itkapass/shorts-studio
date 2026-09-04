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


if __name__ == "__main__":
    check("Python syntax", _syntax)
    check("Undefined names", _undefined)
    check("Quota day boundary", _day_boundary)
    check("Workflow schedules", _workflows)
    check("Content config", _content_config)
    check("Upload spacing", _spacing)
    check("Topic persona resolution", _persona_union)

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
