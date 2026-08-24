# What changed in this build

This is a fixed-and-extended version of the project you had. Everything below was
either broken, misleading, or missing before. Where something is a genuine trade-off
rather than a clean fix, that's called out too — this file doesn't oversell what
changed the same way the old build summary oversold what was "done."

## Do this first

**Rotate your Supabase keys.** A previous zip of this project included a populated
`.env` with a real `SUPABASE_SERVICE_KEY` (full admin access, bypasses every
permission check) and `SUPABASE_ANON_KEY`. Once a secret like that leaves a proper
secrets manager — including into a zip file, a screenshot, or a chat — treat it as
compromised: Supabase Dashboard → Project Settings → API → regenerate both keys,
then update every place that used the old ones (GitHub Secrets, Vercel env vars,
your local `.env`). This build doesn't ship any real `.env` file — only `.env.example`
with placeholders — on purpose; see "New rule" at the bottom of this file.

## Fixed: things that were silently broken

- **The video pipeline couldn't render a single real clip.** `moviepy==1.0.3`'s crop
  step called a Pillow function (`Image.ANTIALIAS`) that Pillow 10+ removed. Confirmed
  by reproducing it in a clean environment — every scene with real footage crashed.
  Fixed at the code level (`engine/styles/stock_footage.py` no longer calls the
  vulnerable moviepy function at all), which is more robust than just pinning an old
  Pillow version — that pin would have forced a slow/failing source build on Python
  3.12+, since no prebuilt wheels exist below Pillow 10 for it.
- **The Gemini model was almost certainly dead.** `gemini-1.5-flash` was hardcoded.
  Google's Flash line has moved through 2.0 → 2.5 → 3.x since, retiring predecessors
  as it goes. Also, while fixing this, testing surfaced that the `google-generativeai`
  package itself is now fully end-of-life ("All support... has ended") — this project
  was built on a deprecated SDK, not just a stale model name. Migrated to the current
  `google-genai` package, with the model name now overridable via `GEMINI_MODEL`
  without touching code (this will need updating again someday — that's the nature of
  this API, not a bug).
- **Generated videos could never actually reach "published."** Two independent gaps,
  each alone enough to block it:
  - Nothing uploaded the rendered file to Supabase Storage except an unguarded script
    bolted onto the GitHub Actions YAML — meaning local runs, Docker runs, and the
    `--prompt` CLI flag never uploaded anything at all, and a mid-batch failure in
    that YAML step silently orphaned whatever came after it. Fixed: real upload logic
    now lives in `engine/storage.py`, called directly by the orchestrator everywhere,
    with retries and a `videos` row status of `failed` (not silent) if it truly can't.
  - `publisher.py` only knew how to authenticate via a local pickle file + an
    interactive browser flow — which cannot run on a headless CI runner. The workflow
    worked around this by base64-encoding the pickle into a GitHub secret and decoding
    it back before each run. It worked, but was needlessly roundabout. Fixed: auth now
    reads `YOUTUBE_CLIENT_ID` / `YOUTUBE_CLIENT_SECRET` / `YOUTUBE_REFRESH_TOKEN` as
    plain env vars first (same code path everywhere), falling back to the pickle file
    only for local dev convenience.
- **The Admin Panel had no real access control.** RLS policies were named
  `"Allow all for service_role"` but used `USING (true)`, granting full read/write to
  the public `anon` role too — the same role your deployed site's JS bundle exposes by
  design. Combined with zero login screen in the React app, anyone who found your
  Supabase URL + anon key could read everything or insert a fake "approved" video that
  your own `publish_approved.py` would upload to your authenticated YouTube channel.
  Fixed: `supabase/schema.sql` now scopes every policy to `auth.role() = 'authenticated'`,
  and the Admin Panel has a real login gate (`src/lib/auth.jsx`, `src/pages/Login.jsx`)
  backed by Supabase Auth. Create yourself a user in Supabase (Authentication → Users)
  before you can log in — see `docs/01_SUPABASE_DATABASE_SETUP.md`.
- **The channel watermark almost certainly never rendered.** It used MoviePy's
  `TextClip`, which shells out to ImageMagick — not installed in the Dockerfile or the
  GitHub Actions workflow, so it failed silently every time (caught by its own
  try/except). Rewritten to render with PIL directly, the same approach the captions
  already used, removing the dependency entirely.
- **Scene cuts could drift out of sync with narration.** Scene-to-visual timing
  assumed a scene's position in the ORIGINAL script (by character count) maps
  proportionally onto Whisper's returned word list — which drifts whenever Whisper's
  word count doesn't exactly match a naive split of the source text (numbers,
  contractions, mispronounced technical terms). `engine/voice_engine.py` now aligns
  the expected script against Whisper's actual transcript with `difflib`, falling
  back to proportional guessing only for the small stretches with no confident match.
  Tested against synthetic drift (dropped words, "50" vs "fifty", stray filler words)
  — stays in order and contiguous where the old approach could compound error
  scene-to-scene.
- **Audio ducking wasn't actually smoothed.** The docstring promised a "smooth 0.2s
  ramp"; `FADE_DURATION` was defined but never referenced anywhere, so music volume
  jumped instantly at every word boundary. Rewritten with a real precomputed envelope
  (Hann-window smoothing) applied per-sample, not per-chunk. Verified numerically —
  flat at the correct levels away from transitions, genuinely ramped right at them.
- **Three Admin Panel settings did nothing.** `auto_approve`, `max_videos_daily`, and
  `publish_per_run` existed in the database and the Settings page, but nothing in the
  Python ever read them — `MAX_VIDEOS_PER_RUN` and `PUBLISH_PER_RUN` were hardcoded
  constants/env-vars instead. All three are now the actual source of truth.

## Fixed: real risk, not just a bug

- **No defense against repetitive content.** The sibling Instagram project this was
  modeled on has embeddings-based duplicate detection against the last 30 days; this
  project had nothing equivalent — a real gap given YouTube's July 2025 "inauthentic /
  mass-produced content" policy update specifically targets exactly this pattern.
  Added `engine/duplicate_check.py` (TF-IDF cosine similarity — catches near-verbatim
  repeats reliably; a true paraphrase in fully different words won't be caught by this
  approach, that's a real trade-off against pulling in a heavier embeddings dependency).
  Flags likely duplicates in the queue rather than silently dropping them — you still
  decide.
- **Two "AI" admin pages were entirely hardcoded mocks.** "Trending Radar" was a fixed
  array of 6 example topics with invented "viral_score" and "$26 CPM" numbers, and its
  refresh button called nothing. "Create Video" did keyword matching on your prompt
  and filled in one fixed template regardless of what you typed — scenes 2-4 never
  changed. Both now call real Supabase Edge Functions: `generate-storyboard` (a real,
  server-side Gemini call) and `discover-trends` (a real YouTube Data API search for
  what's actually getting views this week — no invented scores). You'll need to deploy
  these and set their secrets — see `docs/04`.
- **Engagement-bait defaults.** The default CTA was "Comment 'X' and I'll DM you...",
  and scripts were explicitly prompted toward wealth/CPM-chasing framing. Both walked
  back — the prompt now explicitly asks for genuine reasons to keep watching instead
  of empty engagement-bait, which YouTube's spam policies discourage anyway.

## Added: multiple render styles (the actual feature request)

The pipeline no longer only produces the stock-footage-and-captions format. Visual
style is now a pluggable choice per render (`engine/styles/`):

- **`stock_footage`** — the original plan: real Pexels b-roll with a Ken Burns zoom.
- **`whiteboard_sketch`** — new. Hand-drawn-style line icons (an original ~40-icon
  vocabulary, `engine/styles/icon_library.py` — plain coordinate data, nothing to
  license) that draw themselves on a paper-textured background, deterministically
  jittered for a hand-drawn feel. This is what the sample video you shared looks
  like structurally — worth being direct: that sample is a more custom,
  illustration-driven style than this build's icon-based approximation. This gets you
  a real, working, honestly-scoped version of that genre, not a mockup.
- **`quote_card`** — new, bonus. Minimal drifting gradient, no footage or icons —
  captions carry the whole video. Cheap to render, works well for punchy scripts.

Pick per-topic (Topic Studio) or globally (Settings). All three were rendered
end-to-end in testing, under the same Pillow version that used to crash the old code.

Adding a fourth style later means writing one new file with a
`build_background_clip(scene, duration, w, h)` function and registering it in
`engine/styles/__init__.py` — nothing else in the pipeline needs to change.

## New rule worth actually keeping

**Never let a real `.env` leave your machine** — not zipped, not screenshotted, not
pasted into a chat, including this one. Only `.env.example` (placeholders) should ever
be shared. If a real secret ever does get out, the fix is rotating it, not just
deleting the file it was in.

## Still true, not this build's job to fix

- Google's 7-day refresh-token expiry for OAuth apps in "Testing" status is a Google
  policy, not a bug here — documented clearly in `docs/04`, with a clear error message
  now surfaced when it happens, but the actual fix (verifying your OAuth consent
  screen) is a Google Cloud Console step only you can do.
- `edge-tts` is still an unofficial, reverse-engineered wrapper around Microsoft
  Edge's read-aloud feature. It can break without notice. Fine for a $0 hobby project;
  just don't be surprised if it happens.
- Real royalty-free music/SFX files still aren't bundled (`assets/music/`,
  `assets/sfx/` are empty, same as before) — sourcing properly licensed audio isn't
  something to fake with placeholder files.
