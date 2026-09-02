"""
channels.py — route each video to the right YouTube channel.
============================================================

WHY THIS IS A MODULE AND NOT A SETTING
You said the channel count cannot be fixed now. So nothing here hardcodes a
number. Channels are rows in the database; adding your fifth or fiftieth is a
form submission, not a code change or a redeploy.

THE QUOTA FACT THAT DRIVES THE DESIGN
YouTube's API budget of 10,000 units/day is per GOOGLE CLOUD PROJECT, not per
channel. Each upload costs 1,600 units, so one project caps out at 6 uploads a
day no matter how many channels you point it at. Ten channels sharing one
project still get 6 uploads a day between them.

Give each channel its own Google Cloud project and each gets its own 10,000.
That is why every channel row carries its OWN client id, client secret and
refresh token rather than sharing one set. It costs nothing (Cloud projects are
free) and it is the difference between 6 uploads/day total and 6 per channel.

CREDENTIALS NEVER TOUCH THE DATABASE
A channel row stores the NAME of the environment variables holding its
credentials, not the credentials. So the database holds
`YOUTUBE_REFRESH_TOKEN_SCIENCE` as a string, and the actual token lives only in
GitHub Secrets. If the database ever leaked, no channel would be compromised.

CATEGORY ROUTING
Each channel declares which content categories it accepts. A video is routed to
the first enabled channel accepting its category. Nothing matches, and it falls
through to manual export rather than being force-posted somewhere wrong.
"""
import os
import re

from engine.config import get

# The content categories the pipeline can produce. A channel subscribes to any
# subset. Keep these in sync with script_generator.ARCHETYPES.
CATEGORIES = [
    "informative", "myth_busting", "life_hack", "relatable", "wholesome",
    "empathy", "dark_humour", "sarcasm", "absurd", "observational",
]

ENV_SUFFIX_RE = re.compile(r"^[A-Z0-9_]{1,40}$")


def _db():
    from supabase import create_client
    url, key = get("SUPABASE_URL"), get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_KEY not configured")
    return create_client(url, key)


def load_channels(db=None, only_enabled: bool = True) -> list:
    try:
        db = db or _db()
        q = db.table("channels").select("*")
        if only_enabled:
            q = q.eq("is_enabled", True)
        return q.order("priority", desc=False).execute().data or []
    except Exception as e:
        print(f"[channels] ⚠ Could not load channels: {e}")
        return []


def credentials_for(channel: dict) -> dict | None:
    """Resolves a channel's OAuth credentials from the environment.

    A channel with env_suffix 'SCIENCE' reads YOUTUBE_CLIENT_ID_SCIENCE etc.
    A channel with an empty suffix reads the unsuffixed names, so a single
    existing channel keeps working with no migration.
    """
    suffix = (channel.get("env_suffix") or "").strip().upper()
    if suffix and not ENV_SUFFIX_RE.match(suffix):
        print(f"[channels] ⚠ Ignoring unsafe env_suffix on '{channel.get('name')}': {suffix!r}")
        return None

    def var(base):
        return f"{base}_{suffix}" if suffix else base

    cid = os.environ.get(var("YOUTUBE_CLIENT_ID")) or get(var("YOUTUBE_CLIENT_ID"))
    secret = os.environ.get(var("YOUTUBE_CLIENT_SECRET")) or get(var("YOUTUBE_CLIENT_SECRET"))
    token = os.environ.get(var("YOUTUBE_REFRESH_TOKEN")) or get(var("YOUTUBE_REFRESH_TOKEN"))

    if not (cid and secret and token):
        missing = [
            var(n) for n, v in (
                ("YOUTUBE_CLIENT_ID", cid),
                ("YOUTUBE_CLIENT_SECRET", secret),
                ("YOUTUBE_REFRESH_TOKEN", token),
            ) if not v
        ]
        print(f"[channels] ⚠ Channel '{channel.get('name')}' is missing secrets: {', '.join(missing)}")
        return None

    return {"client_id": cid, "client_secret": secret, "refresh_token": token}


def route(category: str, channels: list = None, db=None, persona_key: str = None) -> dict | None:
    """Picks the channel a video should publish to.

    Tries persona first when the video has one: a tech-explainer channel and a
    top-10-facts channel can both legitimately accept the "informative"
    archetype, and archetype alone cannot tell them apart — only the persona
    can. Falls back to archetype-only matching for videos with no persona,
    which is every video from before this existed, so nothing already set up
    breaks.

    Returns None when nothing accepts it — the caller should then fall back to
    manual export. Silently posting an unmatched video to whichever channel
    happens to be first would be worse than not posting it.
    """
    channels = channels if channels is not None else load_channels(db=db)
    if not channels:
        return None

    if persona_key:
        persona_match = [c for c in channels if c.get("persona_key") == persona_key]
        if persona_match:
            return persona_match[0]

    for ch in channels:
        accepted = ch.get("categories") or []
        if isinstance(accepted, str):
            accepted = [c.strip() for c in accepted.split(",") if c.strip()]
        if category in accepted:
            return ch

    catchall = [c for c in channels if c.get("is_catchall")]
    return catchall[0] if catchall else None


def publishable_channels(db=None) -> list:
    """Channels that are enabled, set to auto-publish, AND have working
    credentials. A channel missing its secrets is reported once here rather
    than failing later inside the upload call."""
    out = []
    for ch in load_channels(db=db):
        if ch.get("publish_mode") != "auto":
            continue
        if credentials_for(ch):
            out.append(ch)
    return out


def daily_cap_for(channel: dict) -> int:
    """Per-channel daily upload cap.

    Defaults to 5, one below the real API ceiling of 6. That headroom is
    deliberate: a retried upload consumes quota twice, and hitting the hard
    ceiling mid-batch produces confusing 403s rather than a clean stop.
    """
    try:
        return max(1, min(int(channel.get("daily_cap") or 5), 6))
    except (TypeError, ValueError):
        return 5


def published_today(channel_id, db=None) -> int:
    from datetime import datetime, timezone, timedelta
    try:
        db = db or _db()
        # YouTube's quota resets at midnight Pacific. Approximating with a
        # rolling 24h window is intentionally conservative — it can only ever
        # under-publish, never over-publish into a 403.
        since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        rows = (
            db.table("videos").select("id")
            .eq("channel_id", channel_id).eq("status", "published")
            .gte("published_at", since).execute().data
        ) or []
        return len(rows)
    except Exception as e:
        print(f"[channels] ⚠ Could not count today's uploads: {e}")
        return 0


def describe(channel: dict) -> str:
    cats = channel.get("categories") or []
    if isinstance(cats, str):
        cats = [c.strip() for c in cats.split(",")]
    return (
        f"{channel.get('name')} "
        f"[{channel.get('publish_mode')}] "
        f"cap={daily_cap_for(channel)}/day "
        f"categories={', '.join(cats) or 'none'}"
    )
