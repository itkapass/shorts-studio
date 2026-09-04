# Start Here — what to do after downloading this zip

**Read time: 3 minutes. Doing time: about 20 minutes.**

Do these in order. Do not skip step 2 — the new code reads a database column
that does not exist yet, and publishing will error until you add it.

---

## Step 1 — Put the new files in your repo

1. Unzip the file you downloaded.
2. Open your `shorts-studio` folder on your computer.
3. Copy **everything** from the unzipped folder into it, replacing files when
   Windows asks. Your `.env` file is not in the zip, so it will not be touched.
4. Open a terminal in that folder and run:

```
git add .
git commit -m "Fix quota day boundary, two crash bugs, spread out publishing"
git push
```

**How you know it worked:** go to your repo on github.com. You should see a
new file called `START_HERE_AFTER_DOWNLOAD.md` in the file list.

---

## Step 2 — Run the database update (DO NOT SKIP)

1. Go to **supabase.com** → your project → **SQL Editor** (left sidebar).
2. Click **New query**.
3. Open the file `supabase/migrations/003_scheduling_and_manual_controls.sql`
   from the zip in Notepad. Copy **all** of it.
4. Paste into the SQL Editor and press **Run**.

**How you know it worked:** you see "Success. No rows returned" in green.

Safe to run twice. Every line is guarded, so nothing breaks if you run it again.

---

## Step 3 — Turn on the manual buttons (10 minutes, optional but recommended)

This is what makes the "Add Topics Now" / "Generate Video Now" / "Publish Now"
buttons work. Skip it and everything still runs on schedule — you just have to
use the GitHub Actions tab to run things by hand.

**3a. Make a GitHub token**

1. github.com → click your photo (top right) → **Settings**
2. Scroll to the very bottom → **Developer settings**
3. **Personal access tokens** → **Fine-grained tokens** → **Generate new token**
4. Fill in:
   - Token name: `shorts-studio-buttons`
   - Expiration: 1 year
   - Repository access: **Only select repositories** → pick `shorts-studio`
   - Permissions → Repository permissions → find **Actions** → set to
     **Read and write**
5. **Generate token**, then copy it. You cannot see it again after leaving
   this page.

**3b. Give it to Supabase**

In a terminal in your project folder:

```
npx supabase login
npx supabase link --project-ref YOUR_PROJECT_REF
npx supabase secrets set GITHUB_PAT=paste_your_token_here
npx supabase secrets set GITHUB_REPO=itkapass/shorts-studio
npx supabase secrets set GITHUB_REF=main
npx supabase functions deploy trigger-workflow
```

(Your `YOUR_PROJECT_REF` is in your Supabase URL: `https://<THIS_BIT>.supabase.co`)

**How you know it worked:** open your dashboard, press **Add Topics Now**.
You should get a green message with a "Watch it run" link.

---

## Step 4 — Check your settings

Open your dashboard → **Settings**. Set these:

| Setting | Set it to | Why |
|---|---|---|
| Daily Video Generation Batch | `6` | Matches the 6 scheduled runs per day |
| Videos Per Run | `1` | One render per run — see docs/11 |
| Publish Per Run | `1` | Leave at 1, always |
| Minimum Gap Between Uploads | `0` | 0 means "work it out from the daily cap" |
| Automatic Topic Rotation | **blank** | Your channels drive this now |

Press **Save Settings**.

That last one matters: leaving it blank is what lets all three channels get
topics. It used to contain `tech_science_explainer`, and that single value was
silently stopping channels 2 and 3 from ever getting any.

---

## Step 5 — Prove it works

1. Dashboard → **Add Topics Now**. Wait about a minute.
2. Go to **Topic Studio**. You should see new topics with a ✨ **AI-invented**
   badge, for **all** of your enabled channels — not just Science.
3. Dashboard → **Generate Video Now**. Wait about 8 minutes.
4. Go to **Video Queue** → **Pending Review**. Your video should be there.

If step 2 only shows topics for one channel, your other channels are not
enabled — check the **Channels** page.

---

## Step 6 — Fix the thing that was silently costing you quota

Your `docs/10` said Gemini's free limit is "20 requests per day per API key."
It is actually **per Google Cloud project**. Three API keys made inside one
Google account share **one** 20/day pool, so making them would have given you
nothing and told you nothing.

To genuinely get three separate pools you need **three separate Google
accounts**, one key from each. `docs/10` Step 5 already tells you to do it that
way — only its explanation was wrong.

You do not have to do this today. One shared key now supports 6 videos/day
comfortably (15 of 20 requests used). Do it when you want more than that.

---

## That's it

From here it runs itself:

- **07:30 UTC (1:00 PM IST)** — invents new topics for every channel
- **6 times a day** — writes and renders one video each time
- **Hourly** — checks if a video is due to publish, and publishes if so

You review videos in the queue whenever you like. Nothing publishes without
your approval.

**If something looks wrong**, read `docs/12_GITHUB_ACTIONS_EXPLAINED.md` — it
explains every workflow in plain English and what each failure means.
