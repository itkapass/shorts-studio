"""
push_notifications.py — real, OS-level phone notifications for a PWA.

WHY THIS EXISTS

Every alert-worthy event in this project (a video ready for review, a
generation failure, a quota warning) already goes through engine/alerts.py
to Telegram and email. Telegram works well, but it means leaving this app
to go check a different one. Web Push closes that gap: once a device has
subscribed (Settings -> Enable Notifications, or the equivalent prompt in
the dashboard), the SAME events show up as a real notification on that
phone's lock screen, through the browser's own OS-level notification
system, the same way any other installed app's notifications behave. No
new app, no new account — the PWA already installed on the home screen
gains the one capability it was missing.

HOW THIS ACTUALLY WORKS (so it's not just SDK-shaped magic)

A browser's Push API doesn't let a server hold a raw connection open to a
phone. Instead, each subscribed device registers a unique "endpoint" URL
with its OS's own push service (Google's FCM for Chrome/Android, Apple's
web push service for Safari/iOS 16.4+) — that registration is a
PushSubscription, saved in the new `push_subscriptions` table. Sending a
notification means POSTing an *encrypted* payload to that endpoint, signed
with this project's own VAPID key pair so the push service can verify it
really came from this app and not anyone else. `pywebpush` (this file's
only new dependency) handles the encryption and signing; this file's job is
just deciding WHEN to call it and cleaning up subscriptions that stop
working.

THIS IS ADDITIVE, NOT A REPLACEMENT
Telegram and email keep working exactly as before. A device that never
subscribes to push simply never receives one — nothing about the existing
alert flow changes for anyone who doesn't set this up.
"""
from engine.config import get


def available() -> bool:
    """True if push notifications are configured at all. Checked before
    ever trying to send — a missing VAPID key should mean 'silently do
    nothing,' the same contract every other optional feature in this
    project follows (Groq, Hugging Face visuals, etc.)."""
    return bool(get("VAPID_PRIVATE_KEY") and get("VAPID_CLAIM_EMAIL"))


def send_to_all(title: str, body: str, url: str = "/queue", tag: str = None) -> dict:
    """Sends one push notification to every currently-subscribed device.

    Returns {"sent": N, "removed": N} — removed counts subscriptions that
    were cleaned up because the push service reported them as permanently
    gone (a browser uninstalled, a subscription expired). This is expected
    background housekeeping, not a failure to report loudly.

    Never raises. A push failure must never be the thing that breaks the
    actual pipeline run calling this — see how this is wired into
    engine/alerts.py for why that matters.
    """
    if not available():
        return {"sent": 0, "removed": 0, "skipped": "not configured"}

    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        print("[push_notifications] \u26a0 pywebpush is not installed "
              "(pip install pywebpush) — skipping push, nothing else affected.")
        return {"sent": 0, "removed": 0, "skipped": "pywebpush not installed"}

    try:
        from supabase import create_client
        db = create_client(get("SUPABASE_URL"), get("SUPABASE_SERVICE_KEY"))
        subs = db.table("push_subscriptions").select("*").execute().data or []
    except Exception as e:
        print(f"[push_notifications] \u26a0 Could not load subscriptions: {e}")
        return {"sent": 0, "removed": 0, "skipped": f"db error: {e}"}

    if not subs:
        return {"sent": 0, "removed": 0, "skipped": "no subscribed devices"}

    import json
    payload = json.dumps({"title": title, "body": body, "url": url, "tag": tag})
    vapid_claims = {"sub": f"mailto:{get('VAPID_CLAIM_EMAIL')}"}

    sent, removed = 0, 0
    for sub in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub["endpoint"],
                    "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]},
                },
                data=payload,
                vapid_private_key=get("VAPID_PRIVATE_KEY"),
                vapid_claims=dict(vapid_claims),
            )
            sent += 1
        except WebPushException as e:
            status = getattr(e.response, "status_code", None)
            if status in (404, 410):
                # 404/410 means the push service itself says this
                # subscription is permanently gone — the browser was
                # uninstalled, storage was cleared, whatever. Keeping a
                # dead subscription around forever would just mean this
                # loop gets slower every month for no benefit; removing it
                # is correct cleanup, not data loss (the device can always
                # resubscribe with one tap).
                try:
                    db.table("push_subscriptions").delete().eq("id", sub["id"]).execute()
                    removed += 1
                except Exception:
                    pass
            else:
                print(f"[push_notifications] \u26a0 Push failed for one device "
                      f"({status}): {e}")
        except Exception as e:
            print(f"[push_notifications] \u26a0 Unexpected push error for one device: {e}")

    return {"sent": sent, "removed": removed}
