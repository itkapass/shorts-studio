# 15 — Three upgrades: real captions, smarter dedup, AI-generated visuals

All three are additive. Nothing about today's behavior changes unless you
add a key, and even then, each has a safe fallback if it fails.

---

## 1. Real YouTube captions (no new key needed — uses what you have)

**What it is.** Every render already produces a perfect `.srt` file
(`subtitle_engine.py`) — it was just never uploaded anywhere. It now rides
along on the video's database row and gets uploaded as a real, native
YouTube caption track right after the video goes live.

**This is NOT a replacement for the burned-in animated captions, and they
don't compete.** They do two different jobs:

| | Burned-in (word-highlight) captions | Real uploaded captions |
|---|---|---|
| Purpose | Engagement — what makes someone stop scrolling | Accessibility + search indexing |
| Visible by default? | Yes, always (part of the video image) | No — off unless a viewer taps CC |
| Screen readers | Can't read it (it's pixels) | Can |
| Helps YouTube's search/recommendations | No | Yes — it's real text YouTube can index |

Since the real track is off by default, a viewer never sees two caption
styles at once. The only edge case: if someone manually turns captions ON,
they'd see YouTube's plain caption text *underneath* your animated one —
a minor, rare overlap, not a real problem.

**Setup:** none. Uses your existing YouTube OAuth credentials.

**If it fails:** logged as a warning, the video still publishes normally.
Burned-in captions are never affected either way.

---

## 2. Smarter duplicate detection (optional, installed by default)

**The gap this closes.** Duplicate detection already checks two things:
shared wording, and shared keywords. Both miss a real paraphrase — two
ideas that are the same thing said in completely different words. Example:
*"Why phone batteries wear out"* vs. *"The chemistry behind losing charge
capacity over time"* — almost no shared words, same idea.

**What was added:** a third check using sentence embeddings (meaning-based
similarity, not word-matching) via the free `sentence-transformers` library,
running locally — no API key, no per-request cost.

**Honest cost:** adds ~300-800MB to the install (it needs `torch`) and a
couple of minutes to the first `pip install` in a fresh environment. A
GitHub Actions cache step was added so this only happens once, not on every
run.

**If you'd rather not pay that install cost:** delete the
`sentence-transformers` line from `requirements.txt`. Everything degrades
cleanly to the original two checks — nothing breaks, you just lose this
third layer.

**How to verify it's active:** check a Generate Video Drafts log for a line
starting `[concept_memory]`. If you see "Semantic similarity unavailable,"
it fell back safely; no line at all before a duplicate-check result means
it ran normally.

---

## 3. AI-generated visuals when stock footage has nothing (optional)

**The gap this closes.** Pexels is real footage of real things, so for an
abstract concept ("AI is changing the landscape") it sometimes has nothing
good — and the closest keyword match is often visibly unrelated. This is
exactly the "alters the terrain" mismatch found early on: a stock clip that
matched a keyword but nothing about the actual scene.

**What was added:** when Pexels comes up empty for a scene (not before —
Pexels is always tried first), a free Hugging Face image model generates a
picture that actually matches the scene, which then gets the same subtle
zoom effect any stock clip would.

**Setup (2 minutes, free, no card):**
1. huggingface.co/settings/tokens → New token → role "Read"
2. Add as GitHub secret: `HUGGINGFACE_API_KEY`

**Honest limits:**
- Hugging Face's free tier has no fixed published rate limit — it flexes
  with overall load. A "cold" model can take 30-60 seconds on its first
  request of the day. This is why it's a fallback, not the default: it's
  fine for the rare case, not fast enough to be the primary source.
- It generates a still image, not real video. That fits this style fine —
  `stock_footage.py` already applies its own zoom to any clip it's given.
- If Hugging Face fails or isn't configured, it drops to the exact same
  flat-gradient fallback that existed before this feature — never blocks
  a render.

**How to know when it fired:** the video's stored storyboard now tags each
scene with `_visual_source` (`pexels`, `cache`, `ai_generated`, or
`fallback`), and the render log prints a line starting `[backup_visuals]`
whenever it's used.

---

## One-time setup checklist

```
git add .
git commit -m "Real captions, smarter dedup, AI-generated visual backup"
git push
```

Then run the migration (`004_real_captions_and_visual_source.sql`) — automatic
if you set up docs/14, otherwise paste it into the Supabase SQL Editor once.

Both new API keys (`HUGGINGFACE_API_KEY`, and `YOUTUBE_API_KEY` if you
haven't already — see the note below) are optional. Add them whenever you
want; nothing needs them to keep working as-is.

**Related fix bundled in this release:** `YOUTUBE_API_KEY` (a plain search
key, different from your YouTube OAuth credentials) was never actually
reachable by the code even when set — a real bug, now fixed. If you want
Trending Radar or topic inspiration active, this is the key that turns it
on. See `.env.example` for where it goes.
