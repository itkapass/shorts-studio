"""
trending.py — turns real search results into new topics, automatically.

WHY THIS EXISTS
Trending Radar in the dashboard already does real work — it searches YouTube
for what's actually rising and lets you click "add" on results you like. What
it couldn't do is act without you, and you specifically asked for that:
tracking what's trending across every category, every day, is more than a
person can keep up with, and that is precisely the kind of repetitive
judgment-light work automation should carry.

This is the same idea, unattended. It is a SEPARATE, OPT-IN script rather than
something silently folded into the daily generate run, for one reason: adding
a topic is not reversible in the same way rejecting a bad video is. A bad
video costs one review. A bad topic keeps generating bad videos every day
until someone notices and turns it off. That is worth a deliberate decision
maintaining a real barrier, not a config flag flipped once and forgotten —
which is exactly why the docs recommend running this manually a few times
before wiring it into a schedule.

SAFETY, REUSED FROM PULSE
Trending search results are exactly the same category of risk as the news feed
in pulse.py — real-world content arrives unfiltered, and "trending" skews
toward exactly the volatile, sometimes-tragic events that make the worst
automated topics. This reuses pulse.py's safety screen rather than
re-implementing a second, possibly-looser one.

WHAT IT WON'T DO
It will not add a topic whose keywords overlap heavily with an existing topic
or a recent concept — reusing concept_memory's own similarity check for that,
so "trending" can't quietly duplicate a topic that already exists under a
different name.
"""
import urllib.parse
import urllib.request
import json as jsonlib

from engine.config import get
from engine import pulse
from engine import archetypes as arch


YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"

# Seed queries per archetype — broad enough to surface real trends, specific
# enough that results are actually about the format rather than generic news.
SEED_QUERIES = {
    "informative":   ["mind blowing fact", "did you know"],
    "myth_busting":  ["common myth debunked", "everyone believes this wrong"],
    "life_hack":     ["life hack that actually works", "daily routine tip"],
    "dark_humour":   ["dark humor relatable"],
    "sarcasm":       ["sarcastic take"],
    "absurd":        ["absurd but true"],
    "observational": ["things everyone does but never says"],
}


def _db():
    from supabase import create_client
    return create_client(get("SUPABASE_URL"), get("SUPABASE_SERVICE_KEY"))


def _search_youtube(query: str, api_key: str, max_results: int = 6) -> list:
    """One real search against YouTube Data API v3. Same free-tier key the
    dashboard's Trending Radar already uses — no new credential to set up."""
    params = urllib.parse.urlencode({
        "part": "snippet", "q": query, "type": "video", "order": "viewCount",
        "publishedAfter": _seven_days_ago(), "maxResults": max_results, "key": api_key,
    })
    with urllib.request.urlopen(f"{YOUTUBE_SEARCH_URL}?{params}", timeout=15) as resp:
        data = jsonlib.loads(resp.read())
    return [
        {"title": item["snippet"]["title"], "channel": item["snippet"]["channelTitle"]}
        for item in data.get("items", [])
    ]


def _seven_days_ago() -> str:
    from datetime import datetime, timedelta, timezone
    return (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")


def discover(limit_per_archetype: int = 1, archetypes: list = None) -> list:
    """Finds candidate topics. Returns them WITHOUT writing anything —
    dry-run is the default so this is safe to run just to look."""
    api_key = get("YOUTUBE_API_KEY")
    if not api_key:
        print("[trending] YOUTUBE_API_KEY is not set. This is a separate, simple API key — "
              "not the OAuth one used for publishing. See docs/07.")
        return []

    archetypes = archetypes or list(SEED_QUERIES.keys())
    candidates = []

    for a in archetypes:
        for query in SEED_QUERIES.get(a, []):
            try:
                results = _search_youtube(query, api_key)
            except Exception as e:
                print(f"[trending] \u26a0 Search failed for {query!r}: {e}")
                continue

            comedic = a in arch.COMEDIC_ARCHETYPES
            safe = [r for r in results if pulse._is_safe(r["title"], comedic)]

            for r in safe[:limit_per_archetype]:
                candidates.append({
                    "archetype": a,
                    "title": r["title"],
                    "source_channel": r["channel"],
                })

    print(f"[trending] Found {len(candidates)} safety-screened candidate(s).")
    return candidates


def topic_inspiration(persona_key: str, limit: int = 5) -> list:
    """Real, currently-rising video titles in a persona's own archetype space
    — returned as INSPIRATION TEXT for topic_synthesizer's prompt, never as
    a topic to insert directly.

    THIS IS THE DELIBERATE ALTERNATIVE TO auto_add(). auto_add() takes a
    trending title and inserts it AS a topic — someone else's video title
    becomes your topic name. That is the exact "another list to read from"
    pattern this project's own philosophy warns against (see
    PROJECT_HANDOFF.md's "actual reason for this architecture" section):
    it skips lenses, skips the five-angle brief, skips every reasoning step
    that makes a topic THIS app's own idea rather than a copy of someone
    else's title.

    This function does something narrower and safer: it hands
    topic_synthesizer a short list of real titles doing well right now, the
    same way pulse.py hands brief.py real headlines. The model still has to
    invent its own specific topic, through the same lens-forced, avoid-list
    reasoning as any other run. Trending informs; it never decides.

    Returns [] (never raises) if YOUTUBE_API_KEY is not set or any search
    fails — trending inspiration is a nice-to-have layered on top of a
    system that already works without it, not a new dependency it needs.
    """
    api_key = get("YOUTUBE_API_KEY")
    if not api_key:
        return []

    from engine import personas as personas_mod
    persona = personas_mod.get_persona(persona_key)
    if not persona:
        return []

    archetypes = persona.get("preferred_archetypes") or []
    comedic = any(a in arch.COMEDIC_ARCHETYPES for a in archetypes)

    titles = []
    for a in archetypes:
        for query in SEED_QUERIES.get(a, [])[:1]:  # one query per archetype is enough for inspiration
            try:
                results = _search_youtube(query, api_key, max_results=4)
            except Exception as e:
                print(f"[trending] \u26a0 Inspiration search failed for {query!r}: {e}")
                continue
            safe = [r["title"] for r in results if pulse._is_safe(r["title"], comedic)]
            titles.extend(safe)
        if len(titles) >= limit:
            break

    return titles[:limit]


def auto_add(limit: int = 2, dry_run: bool = False) -> list:
    """Adds the best candidates as new active topics.

    Checks each candidate against BOTH existing topic names and the concept
    ledger before adding, using the same similarity logic that stops duplicate
    videos — reused rather than reimplemented, so "trending" cannot quietly
    add a topic that already exists under different wording.
    """
    from engine import concept_memory as cm

    db = _db()
    existing = db.table("topics").select("name").execute().data or []
    existing_names = {t["name"].strip().lower() for t in existing}
    ledger = cm.load_ledger(db=db)

    candidates = discover(limit_per_archetype=2)
    added = []

    for c in candidates:
        if len(added) >= limit:
            break

        title = c["title"]
        if title.strip().lower() in existing_names:
            continue

        # Reuse the exact duplicate-scoring logic videos are checked against,
        # so a trending topic can't sneak in as a near-copy of one that
        # already exists.
        fake_storyboard = {"video_title": title, "concept": title, "scenes": []}
        dup = cm.check_concept(fake_storyboard, ledger=ledger)
        if dup["is_repeat"]:
            print(f"[trending] Skipping {title!r} — too close to {dup['matched_title']!r}")
            continue

        if dry_run:
            print(f"[trending] Would add: {title!r} ({c['archetype']})")
            added.append(c)
            continue

        try:
            db.table("topics").insert({
                "name": title,
                "description": f"Trending in the {c['archetype']} format as of this week.",
                "archetype": c["archetype"],
                "is_active": True,
                "added_by": "trending-auto",
                "source_url": None,
            }).execute()
            print(f"[trending] \u2713 Added: {title!r}")
            added.append(c)
            existing_names.add(title.strip().lower())
        except Exception as e:
            print(f"[trending] \u26a0 Could not add {title!r}: {e}")

    if not added:
        print("[trending] Nothing new to add — everything found already exists or is too similar.")

    return added


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Find or auto-add trending topics")
    p.add_argument("--auto-add", action="store_true", help="Actually add topics (default: preview only)")
    p.add_argument("--limit", type=int, default=2, help="Max topics to add per run")
    args = p.parse_args()

    if args.auto_add:
        auto_add(limit=args.limit, dry_run=False)
    else:
        for c in discover():
            print(f"  [{c['archetype']}] {c['title']}")
        print("\nThis was a preview. Add --auto-add to actually create topics.")
