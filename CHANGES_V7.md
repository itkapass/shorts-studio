# v7 — Real captions, smarter dedup, AI-generated visuals, Phase 2 recorded

One new migration: `004_real_captions_and_visual_source.sql`.

## Built this round

**Real YouTube captions.** The `.srt` file every render already produced
was never uploaded — now it rides on the video row and gets pushed as a
real caption track after publish. Doesn't compete with the burned-in
animated captions; different job (accessibility + search), off by default.
Best-effort — a failure here never blocks the actual publish.

**Semantic duplicate detection.** Existing checks (wording, keywords) miss
a genuine paraphrase — same idea, different words. Added a third signal
using free local sentence embeddings. Installed by default
(`sentence-transformers` in requirements.txt); degrades cleanly to the
original two checks if it's ever unavailable. Honest cost: +300-800MB
install, cached after the first run.

**AI-generated scene visuals.** When Pexels has nothing good for a scene —
not before, only after it's already tried — a free Hugging Face model
generates an on-topic image instead of a flat gradient. Opt-in
(`HUGGINGFACE_API_KEY`), silent no-op if unset, falls back to the old
gradient if it fails.

**Trending-as-inspiration, from last round, confirmed working**, plus one
real bug fixed while building it: `YOUTUBE_API_KEY` was never actually
reachable from `config.py` even when set correctly. Fixed — this is also
what the trending feature and Trending Radar both depend on.

## Recorded, not built

`docs/16_PHASE_2_PAID_UPGRADES.md` — the paid-upgrade roadmap (Gemini paid
tier → paid TTS → real AI video → paid stock footage → paid infra), in
priority order, for once the channel earns. Nothing in it is built. This is
so the decision travels with the repo, not just a chat thread.

## Files changed

```
NEW
  engine/backup_visuals.py                  AI-visual fallback (Hugging Face)
  supabase/migrations/004_real_captions_and_visual_source.sql
  docs/15_AI_GENERATED_VISUALS.md
  docs/16_PHASE_2_PAID_UPGRADES.md

CHANGED
  engine/orchestrator.py       captures SRT content; persists each scene's
                               real visual source into the stored storyboard
  engine/publisher.py          upload_captions() — real caption track upload
  engine/publish_approved.py   passes stored captions_srt through
  engine/concept_memory.py     third signal: semantic (embedding) similarity
  engine/visual_fetcher.py     _get_fallback tries backup_visuals before
                               dropping to the flat gradient
  engine/config.py             HUGGINGFACE_API_KEY / _IMAGE_MODEL registered
  .github/workflows/generate.yml, render-on-demand.yml
                               HUGGINGFACE_API_KEY passed through; new cache
                               step for the embedding model
  requirements.txt             sentence-transformers (honest cost noted inline)
  .env.example                 YOUTUBE_API_KEY, HUGGINGFACE_API_KEY documented
  tools/selfcheck.py           16 checks total (4 new this round)
```

## Verified

`python3 tools/selfcheck.py` → 16/16. Frontend builds clean. Every new
fallback path proven with a real mocked test: no-key / success / failure
for both Groq-style backups (Hugging Face visuals, semantic dedup's
graceful degradation). Could not execute the actual embedding model inside
this sandbox specifically — `huggingface.co` isn't in this sandbox's
network allowlist — but the fallback path was proven twice (missing
package, and blocked network), and GitHub Actions has full internet access,
so the real model will load there.

## Setup

1. `git push` the usual way.
2. Run migration `004` (automatic if docs/14 is set up).
3. Optional: `HUGGINGFACE_API_KEY` for AI-generated visuals (docs/15).
4. Nothing else required — real captions and smarter dedup work with zero
   new setup.
