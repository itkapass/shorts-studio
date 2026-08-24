# IG AutoPoster — Project Overview

A from-scratch build of an automated Instagram content pipeline: generates original
text-quote posts with AI, renders them as branded images, queues them for approval,
and publishes to Instagram — all on infrastructure that costs $0/month at hobby scale.
Built as a learning project (AI/DevOps portfolio piece), then actually taken to a real,
live, publishing Instagram account through many rounds of real debugging.

This document is meant to be handed to someone who wants to build something similar
with their own AI assistant's help — it covers what this actually is, what it deliberately
is not, the real architecture, the actual prompts used, and the genuine lessons learned
from getting this from "looks done" to "actually works in production."

---

## 1. What this is

- A fully automated pipeline: pick a topic + tone → generate original text via an LLM →
  render it as a black-background quote-card image → upload → queue for review → publish
  to Instagram via the official Graph API.
- Supports both single-image posts and multi-slide carousel posts, generated from the
  same underlying pipeline.
- An admin web dashboard (not a spreadsheet, not hardcoded config) to control everything:
  which topics/tones exist, what times posts go out, approval mode, branding, all without
  touching code.
- A manual approval workflow: posts queue as "Pending," get reviewed via a web dashboard
  or an email with Approve/Reject links, and only publish once approved (or auto-publish,
  if you flip that setting).
- Built entirely on free tiers — no credit card required anywhere in the stack as shipped.

## 2. What this is NOT

- **Not a growth hack.** It uses Instagram's official Graph API — the same thing Buffer
  or Later use — not scraping, not fake engagement, not follow/unfollow botting. Those
  are genuinely different categories of tool and carry real ban risk; this doesn't touch
  any of that.
- **Not zero-maintenance.** Instagram access tokens expire (~60 days) and need refreshing.
  Gemini model names get deprecated on a ~4-6 month cycle. This needs occasional attention,
  not "set up once and forget forever."
- **Not guaranteed-unique content forever.** Duplicate-detection compares against roughly
  the last 30 days, not your entire all-time history — extremely unlikely to repeat, not
  mathematically impossible.
- **Not a content strategy by itself.** It removes the busywork of writing and posting;
  it doesn't replace having a point of view for the account. Garbage topic/tone config in,
  generic output out.
- **Not currently doing real analytics.** It logs what it posted; it doesn't yet pull
  likes/reach/saves back from Instagram. That's a natural next step, not built yet.

## 3. Architecture

```
Admin (you) → Admin Panel (React, Vercel) → Supabase (Postgres: topics, tones,
settings, posts, auth)
                                                      ↑↓
                                    GitHub Actions (cron, every 15 min)
                                                      ↓
                          Python engine: pick topic/tone → call Gemini →
                          check for duplicates (local embeddings) → render
                          image (Pillow) → upload to Supabase Storage →
                          write post row (status: pending/approved) →
                          email approval link (Resend)
                                                      ↓
                        Separate workflow (every 30 min): publish approved
                        posts → Instagram Graph API
```

Two independent GitHub Actions schedules drive everything — one generates and queues,
a separate one publishes whatever's been approved. They're deliberately decoupled: you
can approve at your own pace regardless of how fast things generate.

## 4. Tech stack

| Layer | Choice | Why |
|---|---|---|
| Admin panel | React + Vite, plain SPA | Lightweight, no server-side rendering needed for a single-user dashboard |
| Hosting (panel) | Vercel (Hobby) | Free, git-connected auto-deploy |
| Database + Auth | Supabase (Postgres) | Free tier, no card required, real SQL, built-in auth |
| Image storage | Supabase Storage | Needs to be genuinely public — Instagram fetches the image URL directly |
| AI text generation | Google Gemini API | Free tier covers this volume many times over |
| Image rendering | Pillow (Python), self-hosted font (Lora) | No AI needed for this part — plain code, instant, free |
| Duplicate detection | sentence-transformers (local) + pgvector | Runs inside the GitHub Action itself, no external API call, no extra cost |
| Scheduler | GitHub Actions (cron) | Free on public repos, no server to maintain |
| Email | Resend | Free tier, used only for approval links |
| Publishing | Instagram Graph API (official) | Sanctioned automation path, not scraping |

## 5. Accounts and API keys you'll need

No actual secret values are in this document — this is just what to go set up.

| Service | What you need | Roughly how |
|---|---|---|
| GitHub | A repo, Actions enabled | Free account |
| Supabase | Project URL + anon key + service_role key | Free project, Settings → API |
| Google AI Studio | Gemini API key | Free, no card |
| Meta for Developers | Instagram access token + account ID | Needs a Business/Creator IG account linked to a Facebook Page |
| Resend | API key + a from-address | Free tier |
| Vercel | Project + environment variables | Free, connects directly to the GitHub repo |

## 6. How content generation actually works — the real prompts

This is the actual system prompt template used for single-image posts (topic/tone/context
are injected dynamically from the database, so adding a new topic never requires touching
this code):

```
You are a writer creating short-form Instagram text posts for an audience aged 15 to 30.
The visual style is: black background, serif type, left-aligned - closer to a page from
someone's private notebook than a glossy motivational poster. The words need to carry
that entirely.

TOPIC: {topic name} — {topic description}
TONE: {tone name} — {tone description}
[optional: ADDITIONAL CONTEXT FROM ADMIN: {custom context}]

Your task:
1. Write ONE original passage related to the TOPIC - structured like a short piece of real
   writing, not a single tidy one-liner:
   - Optionally open with a short direct-address or hook line - only if it genuinely fits.
   - Then 2-3 short stanzas, each just 1-2 short sentences, building on each other.
   - Total length under ~55 words so it still reads in a few seconds on a phone.
   - Written as ONE string with real line breaks between lines/stanzas.
2. Write a matching Instagram caption (max 150 characters).
3. Generate exactly 10 relevant Instagram hashtags.
4. Suggest a background gradient (two hex codes), both near-black.

Rules: no copying real people, 100% original, stay within IG Community Guidelines,
no hate/violence/explicit content, should feel specific and earned, not generic.
Output ONLY valid JSON: {"quote": "...", "caption": "...", "hashtags": [...],
"bg_from": "#hex", "bg_to": "#hex"}
```

The carousel prompt follows the same pattern but asks for N short, independently-readable
slides that build a connected series (e.g. "5 signs...") instead of one multi-stanza
passage — carousels get more swipe-through engagement, so the format is structurally
different, not just "the same thing split up."

**Two things worth copying if you build your own version:**
- **Never trust the model's output blindly.** The background-color instruction above is
  backed up by actual code that force-darkens any color the AI returns, regardless of what
  it was asked for. Prompts get ignored sometimes; code-level guardrails don't.
- **JSON output mode** (`response_mime_type: "application/json"`) plus a strict schema
  check on the returned keys avoids a whole category of "the AI added a sentence before
  the JSON" parsing failures.

## 7. Python backend structure

| File | Responsibility |
|---|---|
| `config.py` | Loads all env vars; each script calls `require([...])` for just what *it* needs, rather than every script needing every credential |
| `generate_quote.py` | Builds the prompts above, calls Gemini, validates the JSON response |
| `duplicate_check.py` | Embeds new text, compares against recent posts via pgvector, fails open (allows the post) if the check itself errors |
| `render_image.py` | Pillow rendering: text wrapping, auto-shrinking font size, the logo/watermark header, gradient backgrounds |
| `main.py` | Orchestrator: figures out which posting-time slots are due right now, picks topic/tone, calls the above, writes to Supabase, sends the approval email |
| `publish_post.py` | Publishes exactly one oldest-approved post per run (deliberately throttled — see lessons below), handles both single and carousel Graph API flows |
| `cleanup_storage.py` | Deletes old images from storage after a retention window |
| `send_email.py` | Builds the approval email HTML with signed, single-use Approve/Reject links |

## 8. Admin panel structure

| Page | Purpose |
|---|---|
| Dashboard | At-a-glance recent activity |
| Topics / Tones | Add, edit, disable content categories and voices — no code changes ever needed |
| Schedule | Posting times, jitter, carousel settings, approval mode, branding/logo, CTA text |
| Post Queue | Review generated posts, approve/reject, swipe through carousel slides individually |
| Analytics | Post history (real Instagram insights pulled back in is a planned extension, not built yet) |

## 9. Cost, realistically

$0/month at hobby volume (a handful of posts/day) — every piece of this stack has a free
tier that comfortably covers that, and nothing in the setup requires a card on file
anywhere. Costs would only appear if: you outgrow Gemini's free-tier rate limits, want a
custom domain, want guaranteed to-the-minute scheduling instead of GitHub Actions' cron
(which can drift up to ~15 min under load), or scale to a volume where free storage/DB
quotas actually matter (a long way off at personal-account scale).

## 10. Real lessons learned (the actually useful part)

These are genuine bugs hit and fixed while building this, worth knowing in advance if
you're building something similar:

- **A value only counts as a "quoted string" in YAML if the quote is the very first
  character.** `run: echo "text: value"` is NOT a quoted string (it starts with `echo`),
  and a bare colon inside it will break parsing in a confusing way. Use `run: |` (block
  text) for any shell command containing a colon.
- **Don't make one config file eagerly require every credential for every script.**
  If script A needs 3 env vars and script B needs 5 different ones, importing a shared
  config that demands all 8 unconditionally means script A crashes on missing vars it
  never actually uses. Load everything as optional, then have each entry point declare
  what *it* needs.
- **Vite bakes environment variables in at build time, not runtime.** Adding/changing an
  env var in your hosting dashboard does nothing until the next build.
- **Supabase Storage enforces its own RLS-style policies on `storage.objects`, completely
  separate from your table policies.** Uploading from the browser as a logged-in user
  needs an explicit storage policy, even if your database RLS is otherwise perfect.
- **A scheduler that only processes the *first* matching time slot per run will silently
  drop slots once your schedule gets dense enough that two slots' tolerance windows
  overlap.** Process every currently-due item per run, not just one.
- **"Sensitive" environment variables in some hosting dashboards (Vercel, others) become
  permanently write-only once saved** — nobody can view the value again, including you.
  Don't try to verify it's correct; just overwrite it with a value you're certain of.
- **A field that's supposed to be user-configurable but defaults to a literal placeholder
  string (like `@yourhandle`) will eventually leak that placeholder into real output** if
  someone forgets to configure it. Default to empty/nothing instead, and make the empty
  state look intentional.

## 11. Ideas for extending this

Roughly in order of how much new infrastructure each needs:

- **Real analytics** — pull impressions/reach/saves back from the Graph API per post,
  show it in the Analytics page. Mostly additive; no architecture change needed.
- **First-comment hashtags** — post hashtags as the first comment instead of in the
  caption, via a follow-up Graph API call after publishing.
- **Slide re-numbering on removal** — currently, deleting one slide from a carousel
  leaves the "n/N" numbers baked into the *other* slide images stale. Fixing this means
  re-rendering the remaining slides, not just deleting a database row.
- **A public "upcoming posts" preview** — a lightweight page showing what's queued for
  the next several slots, without exposing the full admin panel.
- **Reels** — the biggest lift here. Needs video generation (Pillow frames + ffmpeg),
  a different Graph API publish flow (`media_type=REELS`, longer async processing), and
  is worth it mainly because Reels currently drive the most reach on Instagram of any
  format — genuinely worth the investment if you want to go further than static images.
- **Multi-account support** — turning this from "my account" into "anyone's account"
  is a real scope change: Meta's App Review process, per-user credential storage, and
  proper multi-tenancy in the database all become necessary at that point.

## 12. Policy notes (worth actually reading, not skipping)

- Publishing through the official Graph API is explicitly sanctioned automation — not a
  ToS gray area. What *does* create real risk: fake engagement, follow/unfollow botting,
  bought followers — none of which this touches.
- Current Meta AI-content-labeling requirements target photorealistic synthetic media
  (deepfake-style images/video), not plain text-on-background graphics like these — but
  that policy area is actively evolving, worth a periodic check rather than assuming
  permanently.
- If you ever monetize (affiliate links, sponsorships), disclosure rules apply — FTC-style
  in the US, ASCI guidelines in India, roughly-equivalent-elsewhere. Not this project's
  problem to solve, but a real thing to know about before adding a link-in-bio CTA.
