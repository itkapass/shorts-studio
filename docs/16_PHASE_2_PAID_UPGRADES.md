# 16 — Phase 2: paid upgrades (postponed until the channel earns)

**Nothing in this document is built.** This is a saved decision, not a
task list — so it travels with the code instead of living only in a chat
that will eventually scroll away.

Agreed early in this project: build entirely on free tiers first, and once
a channel is actually generating ad revenue, reinvest a slice of it into
paid upgrades — in this order, highest leverage first.

## The order, and why

1. **Paid Gemini tier — first, above everything else.** Every quota problem
   this project has ever had traces back to one number: ~20 free
   requests/day. Enabling billing on the Google Cloud project removes that
   ceiling entirely (thousands/day) and unlocks a stronger model than
   Flash. Highest value per rupee spent, by a wide margin — do this alone
   before touching anything else on this list.

2. **Paid text-to-speech** (ElevenLabs, or Google/Azure's paid tier).
   `edge-tts` is free but unofficial and can break without warning — a
   fallback chain already absorbs that, but a paid voice is also simply
   more expressive. A real retention lever, not just a reliability fix.

3. **Real AI video generation** (Veo, Runway, Kling) for the visual side.
   The direct, paid answer to the same gap `backup_visuals.py` (docs/15)
   fills for free with still images — full generated motion instead of a
   zoomed still or stock footage.

4. **A paid stock footage library** (Storyblocks, Artgrid, Envato
   Elements). Fixes the last of the "close but not quite right" b-roll —
   Pexels' free catalog is generic; paid libraries have far more specific
   footage per keyword.

5. **Paid storage/compute** — only once 1–4 are already earning their
   keep. Removes the Supabase 1GB ceiling and GitHub Actions' free-minute
   dependency for faster, more parallel rendering.

## The instruction for whoever picks this up

**Don't build all five at once.** Turn on #1, run it a couple of weeks,
only add the next once the last one is clearly paying for itself in output
quality or reach. This mirrors how the free version was built —
incrementally, verified at each step, not as one large unproven leap.

## What "verified" means before moving to the next one

- **#1 (Gemini):** api_budget.py's daily-cap logic becomes mostly
  unnecessary. If quota-related warnings in the Actions log drop to
  ~zero and video quality visibly improves, it's earning its keep.
- **#2 (TTS):** compare retention (average % viewed) on videos before and
  after switching, same channel, same archetype mix.
- **#3 (AI video):** compare against the free `backup_visuals.py` path on
  the same kind of scene it currently fills in for.
- **#4 (stock library):** check whether b-roll-mismatch complaints (like
  the original "alters the terrain" find) actually stop.
- **#5 (storage/compute):** only relevant once 1-4 justify rendering more
  than the free tier can keep up with.
