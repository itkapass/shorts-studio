# v9 — Targeted manual control: pick the channel, the count, even the exact topic

No new migration.

## What this adds

Manual runs used to mean "do the next scheduled thing, right now" — no way
to say which channel, how many, or which topic. This round adds that.

**Add Topics Now → Customize:** pick one channel and exactly how many
topics to invent (up to 20), regardless of how deep that channel's pool
already is. Separate from the automatic top-up, which only acts when a
pool runs thin — `topic_synthesizer.force_add_topics()` is the deliberate
version: you asked for N, you get N.

**Generate Video Now → Customize:** pick a channel to restrict to, a count,
or go all the way down to one **exact topic** pulled live from Topic
Studio — bypasses pool shuffling and the "already used" exclusion
entirely, since hand-picking a topic usually means you want it made (or
remade) on purpose.

**Live quota hint.** Once you pick a channel, a line appears: *"≈14 Gemini
requests left today on 'SCIENCE' — roughly 7 videos."* Reads the same
counter the backend actually uses (Pacific-dated, matching
`engine/daycycle.py`), so the number means what it says. It's a sizing
guide, not a promise — a per-deployment budget override in Settings isn't
visible from the dashboard.

**Everything above also works from the raw GitHub Actions UI** — both
workflows now have real dropdown inputs, not just the dashboard.

## One structural cleanup along the way

The persona list used to live only inside `ChannelsPage.jsx` — exactly the
kind of hand-copied list that caused last round's "Tamil channel missing
from the dropdown" bug. Pulled it into one shared file
(`admin-panel/src/lib/personas.js`), imported by both `ChannelsPage.jsx`
and the new `ManualControls.jsx`. That specific bug — one list updated, a
second one quietly left behind — can't happen a second time; there's only
one list now.

## Files changed

```
NEW
  admin-panel/src/lib/personas.js         single shared persona source

CHANGED
  engine/topic_synthesizer.py    force_add_topics(); shared synthesis logic
                                 extracted into _synthesize_and_insert()
  engine/orchestrator.py         --persona, --topic-id, --topics-for,
                                 --topics-count; targeted error messages
                                 when a filter finds nothing
  .github/workflows/
    add-topics.yml, generate.yml   real dropdown inputs for channel/count/topic
  admin-panel/src/pages/ChannelsPage.jsx    imports the shared persona list
  admin-panel/src/components/ManualControls.jsx   full rewrite: Customize
                                 panels, topic picker, live quota hint
  tools/selfcheck.py             18 checks total; dropdown check now
                                 verifies the shared file, not a page copy
```

## Verified

`python3 tools/selfcheck.py` → 18/18. Frontend builds clean. The new CLI
flags tested directly against argparse (channel + topic-id together,
targeted topic-add with a count) — both parse exactly as intended.

## Setup

None. Same secrets as before — this is entirely new capability on existing
infrastructure.
