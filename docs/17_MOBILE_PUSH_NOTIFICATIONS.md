# 17 — Real notifications on your phone (no Telegram, no Gmail)

## What this is

A video's ready for review, a run failed, quota's gone — the same events
already going to Telegram/email — now also show up as a real, OS-level
notification on any device where you tap **Enable Notifications**. Since
you've already installed this as an app on your phone, this is what makes
that app behave like every other app with notifications: banner, lock
screen, the works. No new account, no new app.

## Setup (about 10 minutes, free, one-time)

### Step 1 — Add three GitHub secrets

Repo → **Settings** → **Secrets and variables** → **Actions** → **New
repository secret**, three times. A working key pair is generated below —
use it directly, or generate your own (see the note at the bottom).

| Name | Value |
|---|---|
| `VAPID_PRIVATE_KEY` | `cvauGdPZ7uPGV4PiianPaqdyKQJ47w2hboHD7ytSZbM` |
| `VAPID_CLAIM_EMAIL` | your real email address (required by the push protocol — some push services use it to contact you if something's misbehaving; it's never shown to you or anyone else in the app) |

*(The third value, the public key, doesn't go here — it goes to Vercel
in Step 2, because the browser needs it, not GitHub Actions.)*

### Step 2 — Add one Vercel environment variable

Your dashboard is hosted on Vercel, so this one goes there instead of
GitHub:

1. **vercel.com** → your project → **Settings** → **Environment Variables**
2. Add: Name `VITE_VAPID_PUBLIC_KEY`, Value:
   ```
   BFQmU9Hu_O_p1hkDYN_qr_DMnlJSOxF_310XUgTl1AUa0b5ltvk7k7VrlqlfAPz7UzORXddtyo-bhO66vVD0txE
   ```
   **Type: `Config`, not `Secret`.** Vercel will reject `Secret` for anything
   starting with `VITE_` with the error *"Environment variables with a
   public framework prefix cannot use visibility: secret"* — Vercel enforces
   this because any `VITE_`-prefixed value gets baked directly into the
   downloaded website code so the browser can read it (that's the whole
   point — it needs this key to subscribe to push), so it was never really
   secret to begin with. This is expected, not a mistake — the public key
   genuinely is public.
3. **Redeploy** (Vercel → Deployments → ⋯ on the latest one → Redeploy) —
   environment variable changes need a fresh build to take effect.

### Step 3 — Run the database migration

`005_push_subscriptions.sql` — automatic if you set up docs/14, otherwise
paste it into the Supabase SQL Editor once.

### Step 4 — Turn it on for your phone

Open the app **from its home-screen icon** (not a browser tab — see the
iOS note below), go to **Settings**, and tap **Enable notifications on this
device**. Your phone will ask permission once. Approve it.

## Verify it worked

Dashboard → **Run something now** → any button → wait for it to finish.
You should get a real notification on your phone within a minute or two,
the same as the ones already going to Telegram.

## Platform notes

- **Android (Chrome/Edge)**: works great, no caveats.
- **iOS (Safari, 16.4+)**: works, but **only** when the app was opened from
  its home-screen icon. Opening it as a normal Safari tab, even on the same
  phone, will not receive push notifications — this is Apple's rule, not
  something this project can change. If notifications don't appear to work
  on iPhone, this is almost always why: check you're launching from the icon.
- **Desktop browsers**: also works, if you ever want a desktop notification
  too — same "Enable Notifications" button, no phone-specific setup needed.

## If you'd rather generate your own key pair

The one above is real and works, but if you'd prefer to generate your own
(same effect, just a different, unique credential):

```
pip install py-vapid
python3 -c "
from py_vapid import Vapid
import base64
v = Vapid(); v.generate_keys()
priv = v.private_key.private_numbers().private_value.to_bytes(32, 'big')
print('VAPID_PRIVATE_KEY=' + base64.urlsafe_b64encode(priv).rstrip(b'=').decode())
pub = v.public_key.public_numbers()
raw = b'\x04' + pub.x.to_bytes(32,'big') + pub.y.to_bytes(32,'big')
print('VAPID_PUBLIC_KEY=' + base64.urlsafe_b64encode(raw).rstrip(b'=').decode())
"
```

Use the two printed values in Steps 1 and 2 above instead.

## If it stops working later

Check **Video Queue** → any tab → the badges still work the same as
always. For notifications specifically: Settings page will show "Push
notifications aren't set up yet" if the public key isn't reaching the
browser (Step 2), or "blocked" if you denied the permission prompt (fix in
your phone's site settings, then reload).
