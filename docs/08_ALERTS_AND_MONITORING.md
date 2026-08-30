# 08 — Alerts: getting told when something breaks

**Time: 5 minutes for Telegram. Do this one — it's the highest-value 5 minutes
in the whole setup.**

## Why this matters more than it sounds

Every way this pipeline breaks is **quiet**:

- Your YouTube token expires → publishing stops, nothing errors
- Storage fills up → renders start failing at the last step
- You hit the daily upload cap → videos queue up forever
- Someone disables the last active topic → generation produces nothing
- GitHub disables the cron after 60 days → everything stops

In none of those cases does anything crash loudly. The pipeline just quietly
does less and less until you happen to notice weeks later.

**An unattended pipeline with no alerting isn't automated. It's just unattended.**

---

## Option A — Telegram (recommended)

Free forever, no sending limits, arrives on your phone in about a second, and
setup is genuinely five minutes with no domain, no DNS, and no spam-folder
problems.

### Step 1 — Create a bot

1. Open Telegram (phone or **https://web.telegram.org**)
2. Search for **@BotFather** — the one with the blue verified check
3. Send: `/newbot`
4. It asks for a display name → type anything, e.g. `Shorts Studio Alerts`
5. It asks for a username → must end in `bot`, e.g. `my_shorts_studio_bot`
6. BotFather replies with a token like:

   ```
   8123456789:AAHk3_xYzExampleTokenStringHere
   ```

7. **Copy that token.** It's your `TELEGRAM_BOT_TOKEN`.

### Step 2 — Get your chat ID

The bot can't message you until you message it first — Telegram requires that,
to stop bots spamming people.

1. In Telegram, search for the bot username you just made
2. Open the chat and press **Start** (or send `hello`)
3. Now open this URL in a browser, replacing `<TOKEN>` with your token:

   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```

   Note there's no space and no `<>` — it reads `.../bot8123456789:AAHk.../getUpdates`

4. You'll see JSON. Find this bit:

   ```json
   "chat":{"id":987654321,"first_name":"..."
   ```

5. That number is your `TELEGRAM_CHAT_ID`.

> **Seeing `{"ok":true,"result":[]}`?** The empty result means you haven't
> messaged the bot yet. Go back to step 2, send it a message, then reload the URL.

### Step 3 — Add the secrets

GitHub repo → **Settings** → **Secrets and variables** → **Actions** →
**New repository secret**:

| Name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | the token from Step 1 |
| `TELEGRAM_CHAT_ID` | the number from Step 2 |

### Step 4 — Test it

Repo → **Actions** → **Health Check** → **Run workflow**.

If everything's healthy you get no message (that's correct — no news is good
news). To force a test message, temporarily disable all your topics in the
dashboard and run it again; you should get an alert within seconds. Re-enable
them afterwards.

---

## Option B — Email

Better if you want a written record. Works alongside Telegram; you can have both.

### With Gmail

Gmail blocks normal password logins from scripts, so you need an **App Password**:

1. Go to **https://myaccount.google.com/security**
2. Turn on **2-Step Verification** if it isn't already (App Passwords require it)
3. Go to **https://myaccount.google.com/apppasswords**
4. App name: `Shorts Studio` → **Create**
5. Copy the 16-character password it shows

Then add these secrets:

| Name | Value |
|---|---|
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | your full Gmail address |
| `SMTP_PASSWORD` | the 16-character app password (not your real password) |
| `ALERT_EMAIL_TO` | where to send alerts (can be the same address) |

> **Port 587 vs 465:** 587 uses STARTTLS, 465 uses implicit TLS. Using the wrong
> one for the port is the single most common reason SMTP "silently" fails. The
> code handles both correctly, but the port and the setting have to agree —
> just use 587 with Gmail.

---

## What you'll actually receive

Alerts have three levels. **Only warnings and critical ones interrupt you.**
Routine info is batched into the daily digest so you're not pinged all day.

### Critical — something is broken right now

| Alert | What it means |
|---|---|
| **YouTube publishing is BROKEN** | Token expired. Publishing has stopped. Fix in docs/07 §3 |
| **Generation paused — storage almost full** | Above 90%. Approve or reject the queue to free space |
| **Video generation failing** | Half or more of today's batch errored |
| **Health check found problems** | The morning check found something broken |

### Warning — something will break soon

| Alert | What it means |
|---|---|
| **Daily upload cap reached** | Normal, expected. Resets at midnight Pacific |
| **Storage filling up** | Past 75%. Still working, worth clearing the queue |
| **GitHub will disable your workflows** | Repo inactive too long. Keepalive should prevent this |

### Info — the daily digest

Once a day after generation: how many videos were made, published, waiting for
review, rejected by quality gates, skipped as repeats, and how much storage
you're using.

---

## How often things check

| Workflow | When | Looking for |
|---|---|---|
| Health Check | Every day, 06:43 UTC | Token expiry, storage, empty topics, stalled generation |
| Generate | Daily | Sends the digest when it finishes |
| Publish | Every 30 min | Quota caps, auth failures |
| Keepalive | Every 10 days | Keeps GitHub cron alive |

---

## If you set up nothing

The app still works. Alerts print to the GitHub Actions log and nothing breaks.
You'll just have to go and look at the Actions tab to find out something went
wrong — which, realistically, you won't, until several weeks of output have been
lost. That's exactly the failure this document exists to prevent.
