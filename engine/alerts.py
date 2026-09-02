"""
alerts.py — tells you when something needs your attention.
==========================================================

WHY THIS MATTERS MORE THAN IT LOOKS
Every failure mode this project has is silent. The OAuth token expires and
publishing just stops. The upload quota is hit and videos queue up forever.
Storage fills and renders start failing. GitHub disables the cron after 60 days
of no commits. In every one of those cases the pipeline does not crash, it just
quietly does nothing, and you find out weeks later.

An unattended pipeline without alerting is not automated, it is only unattended.

CHANNELS
  Telegram — recommended. Free forever, no sending limits, arrives on your
             phone in a second, and setup is two API calls with no domain,
             no DNS, and no deliverability problems.
  Email    — via SMTP (Gmail app password works). Better for things you want
             a written record of.
Both are optional and independent. With neither configured, alerts print to the
workflow log and nothing breaks.

SEVERITY
  info     — routine, batched into the daily digest, no interrupt
  warn     — something will break soon (quota near, storage near, token aging)
  critical — something IS broken right now and output has stopped
Only warn and critical send immediately.
"""
import json
import os
import smtplib
import ssl
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from email.message import EmailMessage

from engine.config import get

SEVERITY_ICON = {"info": "ℹ️", "warn": "⚠️", "critical": "🚨"}


def _telegram_configured():
    return bool(get("TELEGRAM_BOT_TOKEN") and get("TELEGRAM_CHAT_ID"))


def _email_configured():
    return bool(get("SMTP_HOST") and get("SMTP_USER") and get("SMTP_PASSWORD") and get("ALERT_EMAIL_TO"))


def send_telegram(subject: str, body: str, severity: str = "info") -> bool:
    if not _telegram_configured():
        return False
    token = get("TELEGRAM_BOT_TOKEN")
    chat_id = get("TELEGRAM_CHAT_ID")
    icon = SEVERITY_ICON.get(severity, "")
    text = f"{icon} *{subject}*\n\n{body}"
    try:
        payload = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": text[:4000],          # Telegram hard-caps messages at 4096
            "parse_mode": "Markdown",
            "disable_web_page_preview": "true",
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status == 200
    except Exception as e:
        print(f"[alerts] ⚠ Telegram send failed: {e}")
        return False


def send_email(subject: str, body: str, severity: str = "info") -> bool:
    if not _email_configured():
        return False
    try:
        msg = EmailMessage()
        msg["Subject"] = f"[Shorts Studio] {SEVERITY_ICON.get(severity,'')} {subject}"
        msg["From"] = get("SMTP_USER")
        msg["To"] = get("ALERT_EMAIL_TO")
        msg.set_content(body)

        host = get("SMTP_HOST")
        port = int(get("SMTP_PORT", "587"))
        # Port 465 is implicit TLS; 587 is STARTTLS. Using the wrong one for
        # the port is the most common reason SMTP "silently" fails.
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=20) as s:
                s.login(get("SMTP_USER"), get("SMTP_PASSWORD"))
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=20) as s:
                s.starttls(context=ssl.create_default_context())
                s.login(get("SMTP_USER"), get("SMTP_PASSWORD"))
                s.send_message(msg)
        return True
    except Exception as e:
        print(f"[alerts] ⚠ Email send failed: {e}")
        return False


def alert(subject: str, body: str, severity: str = "info", force: bool = False) -> dict:
    """Sends an alert on every configured channel.

    Never raises. An alerting system that can crash the thing it is monitoring
    is worse than no alerting system.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    full = f"{body}\n\n---\n{stamp}"

    print(f"[alerts] [{severity.upper()}] {subject}\n{body}")

    if severity == "info" and not force:
        return {"telegram": False, "email": False, "logged": True}

    return {
        "telegram": send_telegram(subject, full, severity),
        "email": send_email(subject, full, severity),
        "logged": True,
    }


# ── Prebuilt alerts for the specific failure modes this project has ──────────


def daily_quota_reached(published_today: int, cap: int):
    return alert(
        "Daily upload cap reached",
        f"Published {published_today} of {cap} videos allowed today.\n\n"
        f"This is the safety cap, not a YouTube error. YouTube's default API budget "
        f"is 10,000 units/day and each upload costs 1,600, so ~6 uploads/day is the "
        f"real ceiling per Google Cloud project. Publishing resumes automatically at "
        f"midnight Pacific, when Google resets the quota.\n\n"
        f"To publish more per day, give each channel its own Google Cloud project — "
        f"quota is per project, not per channel. See docs/07.",
        severity="warn",
    )


def youtube_auth_broken(channel: str, detail: str):
    return alert(
        f"YouTube publishing is BROKEN for '{channel}'",
        f"Publishing has stopped and will not resume on its own.\n\n{detail}\n\n"
        f"Most likely cause: the OAuth refresh token expired. If your Google Cloud "
        f"consent screen is still in 'Testing' status, Google kills refresh tokens "
        f"after 7 days.\n\n"
        f"Permanent fix (do this once): set the consent screen to 'In production'. "
        f"Step-by-step in docs/07_YOUTUBE_AND_CHANNELS.md, section 3.",
        severity="critical",
    )


def storage_pressure(used_mb: float, limit_mb: float):
    pct = (used_mb / limit_mb * 100) if limit_mb else 0
    return alert(
        "Storage is filling up",
        f"Using {used_mb:.0f} MB of {limit_mb:.0f} MB ({pct:.0f}%).\n\n"
        f"Rendering pauses automatically at 90% so you never lose a video to a "
        f"failed upload. Published and rejected videos should be deleted "
        f"automatically — if usage keeps climbing, the cleanup workflow may have "
        f"stopped. Check the Actions tab for 'Cleanup Old Storage'.",
        severity="warn",
    )


def keepalive_due(days_since_commit: int):
    return alert(
        "GitHub will disable your scheduled workflows soon",
        f"No commit to this repository for {days_since_commit} days.\n\n"
        f"GitHub disables scheduled (cron) workflows after 60 days of repository "
        f"inactivity, which would silently stop all video generation.\n\n"
        f"The keepalive workflow should be handling this automatically. If you are "
        f"seeing this message, it means the keepalive itself did not run — go to "
        f"the Actions tab and run 'Keepalive' manually, or push any commit.",
        severity="warn",
    )


def generation_failed(failed: int, attempted: int, errors: list):
    sample = "\n".join(f"- {e}" for e in errors[:5])
    return alert(
        f"Video generation failing ({failed}/{attempted} failed)",
        f"Today's batch had {failed} failures out of {attempted} attempts.\n\n{sample}",
        severity="critical" if failed == attempted else "warn",
    )


def daily_digest(summary: dict):
    lines = [
        f"Generated:  {summary.get('generated', 0)}",
        f"Published:  {summary.get('published', 0)}",
        f"Pending review: {summary.get('pending', 0)}",
        f"Rejected by quality gates: {summary.get('gate_rejected', 0)}",
        f"Rejected as repeat concepts: {summary.get('concept_rejected', 0)}",
        f"Storage used: {summary.get('storage_mb', 0):.0f} MB",
    ]
    return alert("Daily digest", "\n".join(lines), severity="info", force=True)


# ─── Test harness ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Test your alert setup")
    p.add_argument("--test", action="store_true", help="Send a test alert")
    args = p.parse_args()

    if not args.test:
        p.print_help()
        raise SystemExit(0)

    print("\nChecking what is configured...")
    tg = _telegram_configured()
    em = _email_configured()
    print(f"  Telegram: {'configured' if tg else 'NOT configured'}")
    print(f"  Email:    {'configured' if em else 'NOT configured'}")

    if not (tg or em):
        print("\n  Neither is set up, so nothing can be sent.")
        print("  Telegram takes 5 minutes and is free: see docs/08.")
        print("  You need TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.\n")
        raise SystemExit(1)

    print("\nSending a test alert...")
    result = alert(
        "Test alert",
        "If you are reading this, your alerts are working.\n\n"
        "You will get messages like this when something needs attention: "
        "the YouTube login expiring, storage filling up, a generation run "
        "failing, or every topic being switched off.",
        severity="warn",
    )

    sent = [k for k, v in result.items() if v and k != "logged"]
    if sent:
        print(f"\n  Sent via: {', '.join(sent)}")
        print("  Check your phone.\n")
        raise SystemExit(0)

    print("\n  Sending FAILED. Common causes:")
    print("    - The bot token is wrong, or has a space at the end")
    print("    - You never sent your bot a message (Telegram blocks bots")
    print("      from messaging you first — open the chat and press Start)")
    print("    - The chat ID is wrong. Get it from:")
    print("      https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates\n")
    raise SystemExit(1)
