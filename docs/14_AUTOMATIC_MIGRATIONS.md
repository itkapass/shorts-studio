# 14 — Automatic database updates (no more pasting SQL by hand)

## What this is

From now on, a new `supabase/migrations/*.sql` file that gets committed and
pushed to `main` is applied to your real database **automatically**, within
about a minute — via `.github/workflows/deploy-migrations.yml`. You never
open the Supabase SQL Editor again for a project update.

## One-time setup (about 5 minutes)

### Step 1 — Get a Supabase access token

1. Go to **supabase.com/dashboard/account/tokens**
2. **Generate new token** → name it `github-actions` → copy it

### Step 2 — Get your database password

This is the password you set when the project was first created. If you
don't remember it:

1. Supabase dashboard → your project → **Settings** → **Database**
2. **Reset database password** → copy the new one immediately (shown once)

### Step 3 — Add three GitHub secrets

Repo → **Settings** → **Secrets and variables** → **Actions** → **New
repository secret**, three times:

| Name | Value |
|---|---|
| `SUPABASE_ACCESS_TOKEN` | from Step 1 |
| `SUPABASE_DB_PASSWORD` | from Step 2 |
| `SUPABASE_PROJECT_REF` | your project ref — the part of your Supabase URL before `.supabase.co`, e.g. `ginwhrnncquejdylmvqd` |

### Step 4 — Tell Supabase which migrations you already applied by hand

This is the only fiddly part, and it's one-time.

Migrations 002 and 003 were applied earlier by pasting SQL directly into the
SQL Editor — outside the CLI's own tracking. Before switching on
automation, tell the CLI those two are already done, so its first real run
doesn't try to redo them:

```
npx supabase login
npx supabase link --project-ref YOUR_PROJECT_REF
npx supabase migration repair --status applied 002
npx supabase migration repair --status applied 003
```

(Use your actual project ref from Step 3, not the placeholder text.)

**If you skip this step:** nothing breaks. Every migration file in this
project is written to be safely re-runnable (`IF NOT EXISTS`, `WHERE NOT
EXISTS` guards everywhere) specifically so a repeat run is harmless — you'd
just see an extra, no-op entry in the migration history. The repair step
just keeps that history accurate, which matters if you ever need to
reason about it later.

## From here on

That's it. Every future zip that includes a new `supabase/migrations/NNN_*.sql`
file needs exactly this:

```
git add .
git commit -m "..."
git push
```

Watch it apply: Actions tab → **Deploy Database Migrations** → should turn
green within a minute of the push.

## If it fails

Open the failed run's log — the two most likely causes:

| Error mentions | Likely cause |
|---|---|
| `password authentication failed` | `SUPABASE_DB_PASSWORD` is wrong — reset it (Step 2) and update the secret |
| `Project not specified` / link error | `SUPABASE_PROJECT_REF` is wrong or missing |
| A specific SQL error on a real column/table | The migration file itself has a real bug — this is the one case where you do need to look at the actual SQL |

The workflow also sends a Telegram alert on failure if you have alerts
configured (docs/08), so a broken migration doesn't sit silently unnoticed
the way the old manual step could.
