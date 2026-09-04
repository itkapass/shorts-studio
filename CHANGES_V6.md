# v6 — Dark theme fix, trending as reasoning input, one real bug found

No new migration.

## UI fix

`Add Topics Now` / `Generate Video Now` buttons used the `.card` class
(built for `<div>`s) directly on `<button>` elements. Browsers default
unstyled buttons to black text — that's why the labels were nearly
invisible on the dark background. New `.manual-action-btn` class resets
native button styling properly and sets the right colors. Verified with an
actual before/after render, not just by reading the CSS.

## Trending — wired in the way that keeps the app deciding, not copying

Per your last note: trending signal now feeds `topic_synthesizer`'s prompt
as inspiration (same role `pulse.py` already plays for the creative brief).
The model still invents its own specific topic through every lens — it
never gets to rename a trending title and call that a topic.

`trending.auto_add()` (inserts a trending title directly as a topic) is
untouched and still fully opt-in — this is a new, separate, safer path
alongside it, not a replacement.

**Real bug found while testing this:** `YOUTUBE_API_KEY` was never in
`config.py`'s env dict. The workflow passed the secret in correctly; nothing
ever read it back out. `trending.py` — the *existing* Discover Trending
Topics workflow included — has been silently dead this whole time even when
configured correctly. Fixed.

## Files changed

```
admin-panel/src/components/ManualControls.jsx   uses the new button class
admin-panel/src/index.css                       .manual-action-btn (dark-theme correct)
engine/trending.py            topic_inspiration() — new, read-only, no DB writes
engine/topic_synthesizer.py   folds trending inspiration into the existing prompt
engine/config.py              YOUTUBE_API_KEY (and GROQ_API_KEY/GROQ_MODEL) registered
tools/selfcheck.py            13th & 14th checks: the config fix, and that
                              trending can never bypass reasoning
```

Verified: `python3 tools/selfcheck.py` → 13/13. Frontend builds clean.
Trending wiring proven end-to-end with a mocked YouTube response.

## Setup note

None required unless you want trending inspiration active — it already is,
automatically, once `YOUTUBE_API_KEY` is set as a GitHub secret (same key
Trending Radar already uses). No key set = silently skipped, nothing
changes.
