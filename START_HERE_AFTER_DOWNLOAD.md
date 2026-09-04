# Start Here — what to do after downloading this zip

**Read time: 5 minutes. Doing time: about 35 minutes (most of it optional).**

Steps 1–2 are required. Steps 3–5 are optional but each removes a real
recurring annoyance — do them once and never think about them again.

---

## Step 1 — Put the new files in your repo (required)

1. Unzip the file you downloaded.
2. Open your `shorts-studio` folder on your computer.
3. Copy **everything** from the unzipped folder into it, replacing files when
   Windows asks. Your `.env` file is not in the zip, so it will not be touched.
4. Open a terminal in that folder and run:

```
git add .
git commit -m "Add Groq backup, auto migrations, visibility, scheduling fixes"
git push
```

**How you know it worked:** go to your repo on github.com. You should see a
new file called `docs/13_BACKUP_AI_PROVIDER.md` in the file list.

---

## Step 2 — Database check (required, but likely already done)

**Nothing new to run this time.** This update is entirely code — no new
columns, no new tables. The only requirement is that migration `003` from
the last update has already been applied.

If you already ran `003_scheduling_and_manual_controls.sql` and the
dashboard's Video Queue is working (it is, based on your last test) — **skip
this step, you're done.**

If you're not sure or this is a fresh setup, check:

1. Supabase → your project → **SQL Editor** → **New query**
2. Run: `SELECT column_name FROM information_schema.columns WHERE table_name = 'videos' AND column_name = 'publish_now';`
3. If it returns a row, migration 003 is applied. If it returns nothing, open
   `supabase/migrations/003_scheduling_and_manual_controls.sql` from the zip,
   copy all of it, paste into a new query, and run it.

*(After Step 4 below, any future migration applies itself — you won't do
this check manually again.)*

---

## Step 3 — Add a free backup AI (5 minutes, strongly recommended)

This is the fix for "we can't test anything because one Gemini key ran dry."
When Gemini's daily quota is genuinely gone, the pipeline now automatically
tries **Groq** (free, no card, ~14,400 requests/day) instead of just failing.

1. **console.groq.com/keys** → sign in with any Google/GitHub account →
   **Create API Key** → copy it
2. Your repo → **Settings** → **Secrets and variables** → **Actions** →
   **New repository secret**
3. Name: `GROQ_API_KEY`, value: the key you copied

That's it — nothing else to configure. Full details, and exactly what it
does and doesn't protect, in `docs/13_BACKUP_AI_PROVIDER.md`.

---

## Step 4 — Never paste SQL by hand again (10 minutes, one-time)

From here on, a database update applies itself automatically when you push
to GitHub. No more Step 2, ever again, for future updates.

1. **supabase.com/dashboard/account/tokens** → generate a token → copy it
2. Get your DB password: your project → **Settings** → **Database** →
   **Reset database password** (copy it immediately — shown once)
3. Add three GitHub secrets: `SUPABASE_ACCESS_TOKEN`, `SUPABASE_DB_PASSWORD`,
   `SUPABASE_PROJECT_REF` (the part of your Supabase URL before `.supabase.co`)
4. One-time bootstrap in a terminal, so the CLI knows which migrations you
   already ran by hand:

```
npx supabase login
npx supabase link --project-ref YOUR_PROJECT_REF
npx supabase migration repair --status applied 002
npx supabase migration repair --status applied 003
```

Full details, and what to do if it fails, in `docs/14_AUTOMATIC_MIGRATIONS.md`.

---

## Step 5 — Turn on the manual buttons (10 minutes, optional)

Makes the "Add Topics Now" / "Generate Video Now" / "Publish Now" buttons
work on the dashboard. Skip it and everything still runs on schedule — you'd
just use the GitHub Actions tab to run things by hand instead.

**5a. Make a GitHub token**

1. github.com → your photo (top right) → **Settings**
2. Scroll to the bottom → **Developer settings**
3. **Personal access tokens** → **Fine-grained tokens** → **Generate new token**
4. Fill in:
   - Token name: `shorts-studio-buttons`
   - Repository access: **Only select repositories** → pick `shorts-studio`
   - Permissions → Repository permissions → **Actions** → **Read and write**
5. **Generate token**, copy it (you can't see it again after leaving the page)

**5b. Give it to Supabase**

```
npx supabase secrets set GITHUB_PAT=paste_your_token_here
npx supabase secrets set GITHUB_REPO=itkapass/shorts-studio
npx supabase secrets set GITHUB_REF=main
npx supabase functions deploy trigger-workflow
```

**How you know it worked:** dashboard → **Add Topics Now** → green message
with a "Watch it run" link.

*(If `GITHUB_REPO` was already set from a previous setup, double-check it
doesn't end in `.git` — that one character difference causes a 404.)*

---

## Step 6 — Check your settings

Dashboard → **Settings**:

| Setting | Set it to | Why |
|---|---|---|
| Daily Video Generation Batch | `6` | Matches the 6 scheduled runs per day |
| Videos Per Run | `1` | One render per run — see docs/11 |
| Publish Per Run | `1` | Leave at 1, always |
| Minimum Gap Between Uploads | `0` | 0 means "work it out from the daily cap" |
| Automatic Topic Rotation | **blank** | Your channels drive this now |

Press **Save Settings**. The last one matters most: leaving it blank is what
lets all three channels get topics, instead of only Science.

---

## Step 7 — Prove it works

1. Dashboard → **Add Topics Now**. Wait about a minute.
2. **Actions** tab → click that run → **Summary** tab. You'll see exactly
   which topics were added and for which channel — no dashboard digging
   needed. Cross-check in **Topic Studio**: badges should appear across
   all three channels, not just Science.
3. Dashboard → **Generate Video Now**. Wait about 8 minutes (longer on the
   very first run after any code change — no warm cache yet, that's normal).
4. Check that run's **Summary** tab too: title, channel, and which AI wrote
   it. Then **Video Queue** → **Pending Review** to see the actual video.

If step 2 only shows topics for one channel, that channel isn't enabled —
check the **Channels** page.

---

## That's it

From here it runs itself:

- **07:30 UTC (1:00 PM IST)** — invents new topics for every channel
- **6 times a day** — writes and renders one video each time
- **Hourly** — checks if a video is due to publish, and publishes if so
- **On every push** — applies any new database changes automatically

You review videos whenever you like; nothing publishes without your
approval. If Gemini's quota runs dry mid-day, the free Groq backup keeps
things moving, clearly labeled wherever it did.

**If something looks wrong**, read `docs/12_GITHUB_ACTIONS_EXPLAINED.md` — it
explains every workflow in plain English and what each failure means.
