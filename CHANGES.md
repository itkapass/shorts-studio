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

- **`numpy<2.0.0` broke installs on newer Python (confirmed on 3.14).** That upper
  bound was added out of caution around moviepy 1.0.3 possibly not supporting numpy
  2.x — tested directly, it renders fine under numpy 2.x. The cap was actively
  harmful: newer Python versions have no prebuilt wheel for numpy 1.26.4 (the last
  1.x release, which predates them), so pip fell back to compiling from source and
  failed without a C compiler installed. Removed the upper bound.
- **A missing local ffmpeg install surfaced as a bare `[WinError 2]`.** Whisper and
  MoviePy both need the real ffmpeg program on PATH, not just the `ffmpeg-python`
  Python package — this was never actually documented for local (non-Docker,
  non-Actions) use. `engine/voice_engine.py` now checks for it up front and raises a
  clear, actionable error instead of a cryptic traceback 20 seconds into a run; see
  `docs/03`'s new prerequisites section for install steps per OS (Windows needs a
  fresh terminal after installing — PATH changes don't reach already-open ones).

- **A single "high demand" response from Gemini killed that video outright, with zero retries.** Confirmed live: `503 UNAVAILABLE... This model is currently experiencing high demand` failed 5/5 videos in one run, and the identical error hit the `generate-storyboard` Edge Function too. Google's own message calls it temporary, but nothing ever retried — one bad moment lost the whole video. Both `engine/script_generator.py` and the Edge Function now retry transient errors (503/500/429) with exponential backoff (3s → 6s → 12s → 24s) before giving up; permanent errors (404 bad model, bad request) still fail immediately rather than wasting time retrying something a retry can't fix.
- **Edge Function errors were always showing the same generic message, hiding the real reason.** `supabase.functions.invoke()` doesn't put a failed function's own JSON error body where you'd expect (`data`) — it's behind `error.context` (a Response you have to `.json()` yourself), confirmed straight from `@supabase/functions-js`'s source. Every call site was showing "Edge Function returned a non-2xx status code" no matter what actually went wrong underneath, including the retryable-503 case above. Added `getFunctionErrorMessage()` in `src/lib/supabase.js`, used everywhere an Edge Function gets called, so the actual reason reaches the screen.

- **A silent ~2 second cut to solid black, mid-sentence, at scene boundaries.**
  Found by inspecting real generated output frame-by-frame, not by reading code:
  a scene's background would end, the next one's would start slightly later, and
  for that gap `CompositeVideoClip` shows its default canvas — solid black —
  while the caption (timed independently, straight off word timestamps) kept
  playing right through it, since nothing about it was actually broken. This
  happened even with the difflib alignment fix from earlier, because each
  scene's boundary was still computed independently — nothing forced scene N's
  end to exactly equal scene N+1's start. Fixed two ways: `get_scene_timestamps()`
  now forces exact contiguity as a final pass (no gap can exist by
  construction), and `compose_video()` adds a cheap flat-color base layer under
  everything as a second line of defense, so any future timing edge case shows
  a plain color for a moment instead of a black hole. Verified both
  independently — fed deliberately-gapped data straight into the compositor to
  confirm the base layer catches it, and fed deliberately-misaligned transcript
  data into the timestamp function to confirm it no longer produces a gap.

## Fixed after reviewing actual generated output (not just code)

Three real videos were generated and watched frame-by-frame. The feedback was blunt
and, on inspection, correct. What was actually wrong, and what's now fixed:

- **A ~2 second cut to solid black, mid-sentence.** Found in 3 of 5 real generated
  videos. Root cause and fix: see "A silent ~2 second cut to solid black" above.
- **The same irrelevant stock clip repeating in one video** — a person in swimming
  goggles stood in for "keep these beasts cool" AND "high-stakes water" in the same
  data-center video. Two different search phrases both loosely matched the same
  unrelated Pexels video; the old dedup only caught *identical* keyword text.
  `engine/visual_fetcher.py` now tracks the actual Pexels video ID used across a
  whole video and refuses to reuse it even from a differently-worded search.
- **Hard cuts between scenes.** Part of "not in a flow, uneven" — scenes used to
  cut instantly. `stock_footage` and `quote_card` scenes now crossfade into each
  other (0.4s dissolve) instead of popping.
- **B-roll keywords describing abstract concepts instead of filmable things.**
  Stock sites have zero footage of "a mechanism" or "the internet" — only of real
  objects and places. The generation prompt (both `script_generator.py` and the
  `generate-storyboard` Edge Function) now explicitly requires a concrete physical
  stand-in for abstract ideas, and explicitly forbids "person wearing/modeling
  equipment" as a subject, which is what produced the goggles clip in the first
  place. Topic Studio also now shows guidance on which topics suit which style.
- **Whiteboard-sketch icons didn't connect to each other or to the narration.**
  This was a real design gap, not a bug — see "Whiteboard mode redesigned" below.

## Whiteboard mode redesigned: one connected diagram, not random icon flashes

The original `whiteboard_sketch` gave every scene a fresh canvas with 1-3
independently-positioned icons. Watching real output made the problem obvious:
icons didn't relate to each other or build toward anything — it read as random
shapes flashing rather than a diagram being drawn, and a generic ~40-icon
vocabulary often couldn't specifically represent a given sentence anyway.

Redesigned as a genuinely different architecture (`engine/styles/whiteboard_sketch.py`
now builds one continuous clip for the *entire* video, not one clip per scene — see
the new `mode: "whole_video"` flag in `engine/styles/__init__.py` and the branch in
`compose_video()`): one node per scene, laid out in a top-to-bottom zigzag, each new
node connected to the previous one with a hand-drawn arrow as its scene begins.
Nothing is erased — earlier nodes stay on screen for the rest of the video, the same
way a real whiteboard does. Verified by rendering a full test video and inspecting
frames across its whole length: the diagram visibly grows and connects,
lightbulb → network → globe → chip → rocket, each linked by an arrow.

This does not close the gap with hand-illustrated content (Branch Education-style) —
it's still simple line art from a fixed icon set. It does fix the specific,
legitimate complaint that nothing connected to anything else.

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

## Added: deploy the dashboard, render without your own computer

Not something fixed so much as a genuine gap in what was ever documented: nothing
before explained how to get the Admin Panel online, or that the scheduled pipeline
already runs entirely in GitHub's cloud with no computer needed. See
`docs/05_DEPLOY_THE_DASHBOARD.md` for the full picture. Also new:

- **`.github/workflows/render-on-demand.yml`** — a `workflow_dispatch`-triggered
  workflow that renders one specific `queued_for_render` job.
- **`supabase/functions/trigger-render`** — a new Edge Function the deployed
  dashboard calls to kick that workflow off remotely (holding a scoped GitHub PAT
  server-side, never in the browser — same pattern as every other credential in this
  project). The Create Video page's "Render in Cloud" button uses this; "render
  locally instead" is still there if you'd rather.

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
