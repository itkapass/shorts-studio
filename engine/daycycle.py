"""
daycycle.py — one definition of "today", matching the API that actually counts.
==============================================================================

WHAT WENT WRONG (the bug this module exists to kill)

Every daily counter in this project was keyed on the **UTC** date:

    api_calls_default_2026_09_04      <- api_budget.py
    videos_made_2026_09_04            <- orchestrator.py

But Google's Gemini free tier does not reset at midnight UTC. Its
requests-per-day allowance resets at **midnight Pacific**, which is 07:00 UTC
during daylight time and 08:00 UTC in winter. Those two "days" are offset by
seven or eight hours, and the generate workflow ran every 2 hours, so the
offset was guaranteed to be hit every single day:

    00:00 UTC  our counter rolls over to a fresh 20.
               Google still thinks it is YESTERDAY and yesterday is spent.
    00:00 UTC  run starts a video -> real 429 from Google
      to       -> hard_stop() pins our counter to 20/20
    07:00 UTC  ...and that pin now lasts the whole UTC day.

    07:00 UTC  Google's quota genuinely resets to full.
    07:00 UTC  ...but our counter still reads 20/20, so every run refuses to
      to       start, reporting "quota exhausted" against a quota that is
    24:00 UTC  actually completely untouched.

Net effect: the first four runs of the day burned yesterday's empty quota,
and the remaining eight runs refused to use today's full one. Zero videos,
every day, with a log that said "20/20 used" and a videos-made counter that
said 0 — the two numbers that cannot both be true under normal spending, and
the clue that led here.

THE FIX

All daily keys now come from this module, and this module answers in the
same timezone Google resets in. Nothing else in the codebase is allowed to
call datetime.now() to build a daily key — if it does, the bug comes back.

WHY A WHOLE MODULE FOR ONE LINE

Because the bug was that two files each had their own idea of "today" and
neither was the right one. A shared helper makes the correct answer the
easy one to reach for, and makes it a one-line change if Google ever moves
the reset (they have moved free-tier details several times).
"""
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
    _QUOTA_TZ = ZoneInfo("America/Los_Angeles")
except Exception:  # pragma: no cover - only if tzdata is missing entirely
    # Fall back to a fixed -08:00. Not perfect across daylight saving, but
    # far closer than UTC, and it fails soft instead of crashing the run.
    _QUOTA_TZ = timezone(timedelta(hours=-8))

# The publishing side has a different natural "day" — yours, not Google's.
# A 4-videos-per-day cap should mean four videos in YOUR day, so the spacing
# lines up with when your audience is actually awake.
DEFAULT_LOCAL_TZ = "Asia/Kolkata"


def quota_now() -> datetime:
    """Right now, in the timezone Gemini's daily quota resets in."""
    return datetime.now(_QUOTA_TZ)


def quota_day() -> str:
    """Today's date string for Gemini-quota counters, e.g. '2026_09_04'.

    This is THE date that daily API counters must be keyed on.
    """
    return quota_now().strftime("%Y_%m_%d")


def seconds_until_quota_reset() -> int:
    """How long until Gemini's daily allowance refills.

    Used to tell you 'try again in 4h 12m' instead of the useless
    'resets at midnight Pacific', which requires you to do timezone
    arithmetic in your head while something is broken.
    """
    now = quota_now()
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(0, int((tomorrow - now).total_seconds()))


def humanize_until_reset() -> str:
    secs = seconds_until_quota_reset()
    hours, rem = divmod(secs, 3600)
    mins = rem // 60
    if hours:
        return f"{hours}h {mins}m"
    return f"{mins}m"


def local_tz(name: str = None):
    """The timezone used for PUBLISHING spacing and daily publish caps.

    Separate from the quota timezone on purpose. Google's reset time is a
    fact about Google; your posting schedule is a fact about your audience.
    Tying them together would mean changing your upload times whenever
    Google changed a quota policy.
    """
    try:
        return ZoneInfo(name or DEFAULT_LOCAL_TZ)
    except Exception:
        return timezone.utc


def local_day(tz_name: str = None) -> str:
    return datetime.now(local_tz(tz_name)).strftime("%Y_%m_%d")


def utc_now() -> datetime:
    """Plain UTC, for timestamps stored in the database.

    Timestamps are a different problem from daily buckets: a stored
    created_at should always be UTC and unambiguous. Only the BUCKETING
    needed to move to Pacific.
    """
    return datetime.now(timezone.utc)
