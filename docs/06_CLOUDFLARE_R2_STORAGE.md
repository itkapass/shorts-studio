# 06 — Cloudflare R2 Storage (replaces Supabase Storage)

**Time: about 15 minutes. Cost: free.**

## Why you're doing this

Supabase's free tier gives you **1 GB** of file storage. Each finished video is
5–25 MB, so you can hold roughly 40–200 videos before everything stops. And
"stops" here is the annoying kind: renders succeed, then fail at the upload
step, so you've already paid the compute for nothing.

Cloudflare R2's free tier gives you **10 GB**, plus something no other storage
service offers for free: **zero egress fees**. Every other provider charges you
when files are downloaded, and this pipeline downloads every video again at
publish time. On R2 that's free.

With automatic deletion after publishing (already built in), 10 GB is
effectively unlimited here. You'd need 400+ unreviewed videos sitting in the
queue to fill it.

**You can skip this whole document.** If you don't set up R2, the app
automatically uses Supabase Storage instead and everything works. You'll just
have 1 GB instead of 10 GB. Nothing else changes.

---

## Step 1 — Make a Cloudflare account

1. Go to **https://dash.cloudflare.com/sign-up**
2. Enter your email and a password. Click **Sign up**.
3. Check your email and click the verification link.

No credit card. You do not need to add a domain — skip any prompt asking for one.

---

## Step 2 — Turn on R2

1. In the left sidebar of the Cloudflare dashboard, click **R2 Object Storage**.
2. Click the **Purchase R2 Plan** button.

> Do not let the word "Purchase" alarm you. Cloudflare asks for a card to
> prevent abuse, but the free tier is genuinely free — 10 GB storage, 1 million
> writes and 10 million reads a month. This project uses a tiny fraction of
> that. You will not be charged unless you exceed those limits, and there is a
> spend alert in Step 7 to make sure you never do.

3. Choose the plan that says **$0/month** for the first 10 GB.
4. Enter your card details and confirm.

---

## Step 3 — Create the bucket

1. Still in **R2 Object Storage**, click **Create bucket**.
2. Bucket name: **`shorts-videos`**

   Use exactly this name. It's the default the code expects. If you use a
   different one, you'll need to set a `STORAGE_BUCKET` secret to match.
3. Location: leave it on **Automatic**.
4. Click **Create bucket**.

---

## Step 4 — Make the bucket publicly readable

YouTube has to be able to fetch the video file at publish time, so it needs a
public URL.

1. Click your new **shorts-videos** bucket.
2. Go to the **Settings** tab.
3. Find **Public access** → **R2.dev subdomain**.
4. Click **Allow Access**.
5. It asks you to type `allow` to confirm. Type it and confirm.
6. Cloudflare now shows a **Public R2.dev Bucket URL** that looks like:

   ```
   https://pub-a1b2c3d4e5f6.r2.dev
   ```

7. **Copy that whole URL and keep it somewhere.** You need it in Step 6.

> Only the video files live here, and only until they're published or exported.
> No credentials, no database, nothing personal. Public read on this bucket is
> exactly what you want.

---

## Step 5 — Create API credentials

1. Go back to the main **R2 Object Storage** page (click R2 in the sidebar).
2. On the right, click **Manage R2 API Tokens** (sometimes shown as **API** →
   **Manage API tokens**).
3. Click **Create API token**.
4. Token name: `shorts-studio`
5. Permissions: choose **Object Read & Write**.
6. Under "Specify bucket", select **Apply to specific buckets only** and pick
   **shorts-videos**.

   Scoping the token to one bucket means that even if it leaked, it couldn't
   touch anything else in your account.
7. TTL / expiry: leave as **Forever**.
8. Click **Create API Token**.

You'll now see three things **shown only once**:

| Label on screen | What you'll call it |
|---|---|
| **Access Key ID** | `R2_ACCESS_KEY_ID` |
| **Secret Access Key** | `R2_SECRET_ACCESS_KEY` |
| The `https://<long-id>.r2.cloudflarestorage.com` endpoint | you need the `<long-id>` part as `R2_ACCOUNT_ID` |

**Copy all three into a text file right now.** Cloudflare will not show the
secret again. If you lose it, delete the token and make a new one — no harm
done, it just wastes five minutes.

> **Finding your Account ID separately:** it's also shown on the R2 overview
> page on the right side, and it's the long string in your dashboard URL:
> `dash.cloudflare.com/`**`THIS-PART`**`/r2`

---

## Step 6 — Add the secrets to GitHub

1. Open your repository on GitHub.
2. **Settings** (top tab of the repo, not your account settings)
3. Left sidebar → **Secrets and variables** → **Actions**
4. Click **New repository secret** and add these four, one at a time:

| Name | Value |
|---|---|
| `R2_ACCOUNT_ID` | the long id from the endpoint URL |
| `R2_ACCESS_KEY_ID` | Access Key ID from Step 5 |
| `R2_SECRET_ACCESS_KEY` | Secret Access Key from Step 5 |
| `R2_PUBLIC_BASE` | the `https://pub-....r2.dev` URL from Step 4 |

Name them **exactly** as written — they're case-sensitive and the code looks
them up by these names.

> For `R2_PUBLIC_BASE`, do not put a `/` on the end. `https://pub-abc.r2.dev`
> is right; `https://pub-abc.r2.dev/` will produce double-slash URLs.

That's it. The app checks for these four secrets at startup. If all four are
present it uses R2; if any are missing it silently falls back to Supabase
Storage. There is nothing to switch on.

---

## Step 7 — Set a spend alert (2 minutes, do not skip)

You will not exceed the free tier with this project. Set the alert anyway —
it's the difference between "definitely free" and "probably free".

1. Cloudflare dashboard → **Notifications** (left sidebar)
2. Click **Add** → find **R2** in the product list
3. Choose the storage-usage notification and set the threshold to around **8 GB**
4. Enter your email → **Create**

---

## Step 8 — Confirm it works

Push any commit, then in your repo go to **Actions** → **Health Check** →
**Run workflow**. In the log you should see:

```
✓ Storage headroom: 0/10240 MB (0.0%) on r2
```

If it says `on supabase`, one of the four secrets is missing or misspelled. Go
back to Step 6 and check each name character by character — that is nearly
always what it is.

---

## What happens to your files now

| Moment | What happens |
|---|---|
| Video finishes rendering | Uploaded to R2, a row appears in your review queue |
| You approve it | It gets published, then **the file is deleted from R2 immediately** |
| You reject it | **Deleted immediately** |
| You export it for manual posting | Packaged into a zip, then **deleted from R2** |
| Nothing happens to it | Stays until you decide; the weekly cleanup removes very old ones |

Storage only ever holds videos that are waiting for your decision. That's why
10 GB is more than you'll ever need.

---

## If something goes wrong

**"R2_PUBLIC_BASE is not set"** — Step 4 wasn't completed, or the secret name
is misspelled. The public r2.dev subdomain has to be explicitly enabled; the
bucket is private by default.

**Uploads fail with `SignatureDoesNotMatch`** — the Secret Access Key is wrong.
Most often a copy-paste that grabbed a trailing space. Delete the token, create
a new one, re-enter it.

**Uploads fail with `NoSuchBucket`** — the bucket name doesn't match. It must be
`shorts-videos`, or you must set a `STORAGE_BUCKET` secret to whatever you did
name it.

**Videos upload but YouTube can't fetch them** — public access is off. Redo
Step 4. You can test it yourself: paste `R2_PUBLIC_BASE/somefile.mp4` into a
browser. If you get a Cloudflare error page instead of a download, the bucket is
still private.
