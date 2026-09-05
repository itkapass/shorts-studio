# v8 — The real reason Groq wasn't helping, plus visibility fixes

No new migration.

## The main bug: Groq was configured correctly and still never ran

This is the fix that matters most this round. Reported symptom: Groq key
added, saved to secrets, but runs still exit in under a minute with zero
videos and no sign Groq was ever tried.

**Root cause:** the pipeline checks a LOCAL counter before ever attempting
a real Gemini call — "do we have enough recorded budget for this?" If that
counter said zero (whether genuinely exhausted from heavy testing, or just
stale), the run exited immediately. The Groq fallback only ever runs from
*inside* a caught, real 429 during an actual attempted call — so if the
local counter stopped the attempt before it began, Groq never got reached
at all. A correctly-configured backup could sit there unused indefinitely.

**Fixed in two places** (`api_budget.py`'s `require()`, and
`orchestrator.py`'s pre-flight gate): a locally-exhausted reading no longer
hard-stops the run when a backup provider is configured. It proceeds to the
real call instead — which either succeeds (the local count was stale) or
genuinely 429s and correctly falls to Groq (the local count was right).
Either way, something happens instead of nothing.

Verified with the exact reported scenario: local budget at 20/20, Groq
configured — confirmed it now proceeds instead of exiting.

**One thing to double-check on your end:** `GROQ_API_KEY` needs to be a
**GitHub repository secret** (Settings → Secrets and variables → Actions),
not a Supabase secret. Supabase secrets are only for the two edge functions
(`trigger-render`, `trigger-workflow`) — the generation workflow itself
reads `GEMINI_API_KEY`/`GROQ_API_KEY` from GitHub's secrets, a completely
separate store.

## Second bug: Tamil Quotes was never selectable

`ChannelsPage.jsx`'s persona dropdown is a hand-copied list, not read live
from `engine/personas.py` — and `quotes_and_poetry` was missing from it
entirely. Not a rare edge case: it was the persona for your third planned
channel, unselectable with no error anywhere. Added, plus a selfcheck that
now fails the build if the two lists ever drift apart again.

## Third fix: Test Alerts' false red X

Running it with neither Telegram nor email configured exited with code 1 —
a scary red X for what is actually a normal, optional, unconfigured state.
Now exits 0 in that case; still exits 1 if something IS configured and
genuinely fails to send.

## Visibility: counts and schedule, where you asked for them

**Video Queue tabs now show live counts** (Awaiting Render, Rendering,
Pending Review, Approved, Published, and a new **Failed** tab combining
generation + publish failures). Lightweight count-only queries — doesn't
pull full rows just to display a number.

**"Next auto-run in Xh Ym"** now shows on each manual action button
(Dashboard and Topic Studio) — mirrors the actual cron schedule, updates
live.

**Worth knowing, not new:** Topic Studio already sorts newest-first with an
age label per card, and the Add Topics workflow's Actions Summary tab
already lists exactly what was invented, for which persona, by which
model — that's the answer to "what was in the last batch" without needing
a dashboard round-trip.

## Files changed

```
engine/api_budget.py       require() no longer hard-blocks when a backup exists
engine/orchestrator.py     pre-flight gate: same fix
engine/alerts.py           exit 0, not 1, when alerts are simply unconfigured
admin-panel/src/pages/ChannelsPage.jsx    quotes_and_poetry added
admin-panel/src/pages/VideoQueue.jsx      per-tab counts, new Failed tab
admin-panel/src/components/ManualControls.jsx   next-auto-run countdown
tools/selfcheck.py         18 checks total (2 new, one guards this exact bug)
```

## Verified

`python3 tools/selfcheck.py` → 18/18. Frontend builds clean. The budget fix
specifically re-tested against your exact reported numbers (20/20 spent,
Groq configured) — confirmed it now proceeds instead of exiting.
