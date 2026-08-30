"""
health_check.py — find the silent failures before they cost you a day.
======================================================================

Every way this pipeline breaks is quiet. The OAuth token expires and publishing
just stops. Storage fills and renders fail at the last step. Someone disables
the last active topic and generation produces nothing. The Gemini model name
retires and every call 404s. In none of those cases does anything crash loudly
— the pipeline simply does less and less until you happen to notice.

This runs every morning and checks each one on purpose. Anything broken sends
an alert; anything fine stays quiet.

EXIT CODE
Always 0, even when checks fail. A red X in the Actions tab every morning
teaches you to ignore the Actions tab, which is worse than no check at all.
The alert is the signal; the workflow run is just the vehicle.
"""
import sys
from datetime import datetime, timezone, timedelta

from engine.config import get


def _line(ok, name, detail=""):
    print(f"  {'✓' if ok else '✗'} {name}{': ' + detail if detail else ''}")
    return {"name": name, "ok": ok, "detail": detail}


def check_database():
    try:
        from supabase import create_client
        db = create_client(get("SUPABASE_URL"), get("SUPABASE_SERVICE_KEY"))
        db.table("settings").select("key").limit(1).execute()
        return _line(True, "Database reachable"), db
    except Exception as e:
        return _line(False, "Database reachable", str(e)[:160]), None


def check_topics(db):
    """An empty topic or tone list makes generation produce nothing at all,
    with no error. It is the least obvious failure in the whole system."""
    try:
        topics = db.table("topics").select("id").eq("is_active", True).execute().data or []
        tones = db.table("tones").select("id").eq("is_active", True).execute().data or []
        ok = bool(topics) and bool(tones)
        return _line(ok, "Active topics and tones",
                     f"{len(topics)} topics, {len(tones)} tones"
                     + ("" if ok else " — generation will silently produce NOTHING"))
    except Exception as e:
        return _line(False, "Active topics and tones", str(e)[:160])


def check_gemini():
    try:
        from engine import model_registry
        model = model_registry.choose_text_model(force_refresh=True)
        return _line(bool(model), "Gemini model available", model)
    except Exception as e:
        return _line(False, "Gemini model available", str(e)[:160])


def check_storage():
    try:
        from engine import storage_r2
        p = storage_r2.check_storage_pressure()
        ok = not p["should_pause_renders"]
        return _line(ok, "Storage headroom",
                     f"{p['used_mb']:.0f}/{p['limit_mb']} MB ({p['percent']}%) on {p['backend']}")
    except Exception as e:
        return _line(False, "Storage headroom", str(e)[:160])


def check_youtube_auth():
    """The single most valuable check here.

    Google expires refresh tokens after 7 days while the OAuth consent screen
    is in 'Testing'. This attempts a real token refresh, so it catches the
    expiry the morning it happens rather than whenever you next notice that
    nothing has been published for a week.
    """
    from engine import channels as channels_mod
    results = []
    chans = channels_mod.load_channels()

    if not chans:
        return [_line(True, "YouTube auth", "no channels configured yet — nothing to check")]

    for ch in chans:
        name = ch.get("name", "?")
        if ch.get("publish_mode") != "auto":
            results.append(_line(True, f"YouTube auth [{name}]", "manual mode, no token needed"))
            continue
        creds = channels_mod.credentials_for(ch)
        if not creds:
            results.append(_line(False, f"YouTube auth [{name}]", "secrets missing"))
            continue
        try:
            from engine.publisher import _credentials_from_env
            _credentials_from_env(creds)
            results.append(_line(True, f"YouTube auth [{name}]", "token refreshed OK"))
        except Exception as e:
            results.append(_line(False, f"YouTube auth [{name}]", str(e)[:200]))
    return results


def check_queue(db):
    """A queue that only grows means nobody is reviewing, and videos sitting
    in storage are what eventually fills the bucket."""
    try:
        pending = db.table("videos").select("id").eq("status", "pending").execute().data or []
        n = len(pending)
        return _line(n < 40, "Review queue", f"{n} video(s) waiting for approval")
    except Exception as e:
        return _line(False, "Review queue", str(e)[:160])


def check_recent_activity(db):
    try:
        since = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
        rows = db.table("videos").select("id").gte("created_at", since).execute().data or []
        return _line(bool(rows), "Recent generation",
                     f"{len(rows)} video(s) in the last 3 days"
                     + ("" if rows else " — the daily workflow may have stopped"))
    except Exception as e:
        return _line(False, "Recent generation", str(e)[:160])


def check_alerting():
    tg = bool(get("TELEGRAM_BOT_TOKEN") and get("TELEGRAM_CHAT_ID"))
    em = bool(get("SMTP_HOST") and get("ALERT_EMAIL_TO"))
    return _line(tg or em, "Alerting configured",
                 f"telegram={'yes' if tg else 'no'}, email={'yes' if em else 'no'}"
                 + ("" if (tg or em) else " — you will not be told when something breaks"))


def main():
    print("\n" + "=" * 62)
    print(f"HEALTH CHECK — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 62)

    results = []
    db_result, db = check_database()
    results.append(db_result)

    if db:
        results.append(check_topics(db))
        results.append(check_queue(db))
        results.append(check_recent_activity(db))
        results.extend(check_youtube_auth())

    results.append(check_gemini())
    results.append(check_storage())
    results.append(check_alerting())

    failures = [r for r in results if not r["ok"]]
    print("=" * 62)
    print(f"{len(results) - len(failures)}/{len(results)} checks passed.")
    print("=" * 62 + "\n")

    if failures:
        from engine import alerts
        body = "\n".join(f"- {f['name']}: {f['detail']}" for f in failures)
        alerts.alert(
            f"Health check found {len(failures)} problem(s)",
            body + "\n\nEach of these stops part of the pipeline silently. "
                   "Fix guidance is in docs/08_TROUBLESHOOTING.md.",
            severity="critical" if any("auth" in f["name"].lower() or "Database" in f["name"]
                                       for f in failures) else "warn",
        )

    # Always exit 0 — see the module docstring.
    return 0


if __name__ == "__main__":
    sys.exit(main())
