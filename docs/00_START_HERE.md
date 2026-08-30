# Start here

You have already set up Supabase, Vercel, GitHub secrets and the basic
workflows. **You do not need to redo any of that.**

## What to do, in order

| # | Do this | Time | Skip it? |
|---|---|---|---|
| 1 | Run `supabase/migrations/002_channels_and_concepts.sql` in the Supabase SQL Editor | 2 min | **No.** Nothing new works without it |
| 2 | [docs/08 — Alerts](08_ALERTS_AND_MONITORING.md) — Telegram bot | 5 min | Highest-value 5 min in the whole setup |
| 3 | [docs/07 §3 — Switch OAuth to "In production"](07_YOUTUBE_AND_CHANNELS.md) | 2 min | **No.** This is the 7-day expiry fix |
| 4 | [docs/06 — Cloudflare R2](06_CLOUDFLARE_R2_STORAGE.md) | 15 min | Yes — falls back to Supabase automatically |
| 5 | [docs/09 — Content system](09_CONTENT_SYSTEM.md) | read | Explains the three dials. Read before tuning |
| 6 | Dashboard → **Channels** → set up your channels | 5 min | Do at least one |

Steps 1–3 are the ones that matter. Everything else is optional or reading.

## Running the migration (step 1)

1. Supabase dashboard → your project → **SQL Editor** → **New query**
2. Open `supabase/migrations/002_channels_and_concepts.sql`, copy all of it, paste
3. Click **Run**
4. Expect: `Success. No rows returned.`

Safe to run twice — every statement uses `IF NOT EXISTS`.

## Then check it worked

Repo → **Actions** → **Health Check** → **Run workflow**. It tells you exactly
what's configured and what isn't.

## What changed since your last version

See [`CHANGES_V2.md`](../CHANGES_V2.md) in the project root.
