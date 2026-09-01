# Start here

You already have Supabase, Vercel and GitHub set up. Don't redo any of that.

## Do these three things, in order

### 1. Run the database migration (2 min) — required

Nothing new works without this.

1. Supabase → your project → **SQL Editor** → **New query**
2. Open `supabase/migrations/002_channels_and_concepts.sql`, copy all of it, paste
3. **Run** → expect `Success. No rows returned.`
4. Vercel → your project → **Deployments** → **⋯** → **Redeploy**

You'll now see **Channels** and **Concept Ledger** in your dashboard sidebar.

> **"Dashboard" means your admin panel** — the website you deployed to Vercel,
> e.g. `https://your-project.vercel.app`. Not the Vercel control panel.

### 2. Set up Telegram alerts (5 min) — strongly recommended

[docs/08](08_ALERTS_AND_MONITORING.md)

Every failure in this app is silent. Without alerts you find out weeks later.

### 3. Add a channel (2 min)

Dashboard → **Channels** → **Add channel** → leave **Publishing: Manual** →
tick some categories → tick **Catch-all** → Save.

Manual means the app packages each approved video into a zip you upload
yourself. **Start here.** Get videos you like before automating uploads.

---

## Then, when you want to

| Want | Read | Time |
|---|---|---|
| Automatic YouTube uploads | [docs/07](07_YOUTUBE_AND_CHANNELS.md) | 20 min |
| More storage (10 GB instead of 1 GB) | [docs/06](06_CLOUDFLARE_R2_STORAGE.md) | 15 min |
| Understand what the app is actually doing | [docs/09](09_CONTENT_SYSTEM.md) | read |

Cloudflare R2 is optional — the app falls back to Supabase Storage on its own.

---

## Running commands

Always from the project folder (the one **containing** `engine`), and always
with `-m`:

```
python -m engine.publisher --setup
python -m engine.orchestrator
python -m engine.health_check
```

`python engine/publisher.py` also works now, but `-m` is the correct form.

---

## Checking everything works

Repo → **Actions** → **Health Check** → **Run workflow**. It tells you exactly
what's configured and what isn't.

---

## What changed since your last version

[`CHANGES_V2.md`](../CHANGES_V2.md)
