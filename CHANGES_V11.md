# v11 — Why quota kept running out, and a misleading error message fixed

No new migration.

## Bug 1: scheduled runs were quietly spending 2-3x more than budgeted

Every scheduled Generate Video run (6×/day) was ALSO re-checking and
topping up every active persona's topic pool — not just the dedicated
Add Topics workflow that was supposed to be the only place this cost.

Root cause: the code checked `inputs.skip_topics` to decide whether to
skip it, but that value is only ever populated on a manual
`workflow_dispatch` run. On a `schedule` (cron) trigger, it's always empty
— regardless of the input's declared default — so the skip silently never
applied to any of the 6 daily automatic runs.

With 3 channels now active, that's up to 3 extra Gemini calls, 6 times a
day, on top of the 12 already budgeted for videos. That alone can push a
normal day well past the 20-request free allowance — before any manual
testing, before anything else.

**Fixed:** scheduled runs now check `github.event_name == 'schedule'`
directly and always skip topic top-up, full stop — relying on the
dedicated once-daily Add Topics workflow the way it was always meant to.
Manual runs keep the existing checkbox, unaffected.

## Bug 2: a real Groq failure was reported as "not configured"

If a backup provider WAS configured but also failed (bad key, a retired
model name, Groq's own limits), the final error message still said "No
backup provider is configured" — the exact same text as when no key exists
at all. Two completely different problems, indistinguishable from the
dashboard.

**Fixed:** the message now says plainly which case actually happened —
"a backup provider IS configured and was tried, but it also failed:
{the real reason}" vs. the original "not configured" text, only when that's
actually true. Verified both branches directly.

## What to check on your end

If you're still seeing "No backup provider is configured" after this
update, that now means it, precisely: **`GROQ_API_KEY` isn't reaching the
workflow.** The most common cause is adding it as a Supabase secret instead
of a GitHub one — Supabase secrets only serve the two edge functions
(`trigger-render`, `trigger-workflow`); the actual generation workflow
reads secrets from GitHub's own store (repo → Settings → Secrets and
variables → Actions).

If instead you now see "IS configured and was tried, but it also failed:
...", the key IS reaching the workflow — the message will tell you exactly
what went wrong with it.

## Files changed

```
.github/workflows/generate.yml   schedule-vs-manual trigger detection
engine/script_generator.py       two distinct, accurate error messages
tools/selfcheck.py                20 checks total (2 new, guard both bugs)
```

## Verified

`python3 tools/selfcheck.py` → 20/20. Both new error-message branches
proven directly: Groq-configured-but-failing produces the correct
"was tried, but it also failed" text with the real Groq error attached;
no-key-at-all still produces the original "not configured" text.
