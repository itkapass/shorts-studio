"""
pulse.py — what the world is talking about right now.
=====================================================

WHY
A topic like "office life" is static. What makes a video about office life feel
alive is that it lands on something happening THIS WEEK. A human cannot track
that across ten topics every day, and shouldn't have to — that is the whole
point of automating this.

So before writing anything, the pipeline pulls a short list of what is
currently being discussed around the topic, and hands it to the writer as
context. The writer does not summarise the news; it uses it as the thing the
video is quietly reacting to. That is the difference between "here is a joke
about meetings" and "here is a joke about meetings that lands because of what
everyone read this morning".

SOURCES — ALL FREE, NO API KEY
  1. Google News RSS  — free, unlimited, no key, no signup. Any search query.
  2. YouTube Data API — already configured; shows what is getting views now.
                        Optional; skipped if no key is set.

Google News RSS is the workhorse. It is a documented public feed, it costs
nothing, and it has no quota, which matters for something that runs daily
forever.

════════════════════════════════════════════════════════════════════════════
SAFETY: THIS IS THE RISKIEST MODULE IN THE PROJECT
════════════════════════════════════════════════════════════════════════════
Feeding live news into a comedy generator is exactly how an automated channel
ends up joking about a fresh tragedy. The news does not arrive pre-labelled,
and by the time a bad headline reaches the writer it is already too late — the
model will dutifully find the funny angle on a plane crash if you hand it one.

So filtering happens HERE, at the source, before anything reaches a prompt:

  - Every headline is screened against a block list of harm markers.
  - Anything matching is dropped entirely, for every format — not just comedy.
    A "serious" video about a named victim is its own problem.
  - For comedic formats the screen is stricter still, and headlines about
    identifiable individuals are dropped as well.
  - If filtering leaves nothing, the pipeline writes from the topic alone.
    Producing a slightly less timely video is always the correct trade.

The filter is deliberately blunt and over-blocks. A missed joke costs nothing.
A joke about a bombing costs the channel.
"""
import html
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

from engine.config import get

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
REQUEST_TIMEOUT = 15
MAX_ITEMS = 8
MAX_AGE_DAYS = 14

# Headlines containing any of these are dropped for EVERY format. Blunt on
# purpose — see the module docstring.
HARD_BLOCK = (
    "killed", "kills", "death", "dead", "dies", "died", "fatal", "murder",
    "shooting", "shooter", "stabbing", "massacre", "genocide", "terror",
    "bombing", "explosion", "crash", "collision", "derail",
    "rape", "assault", "abuse", "molest", "trafficking", "kidnap",
    "suicide", "self-harm", "overdose",
    "war", "airstrike", "missile", "invasion", "troops", "militant",
    "famine", "starvation", "outbreak", "epidemic", "pandemic",
    "earthquake", "tsunami", "hurricane", "wildfire", "flood", "disaster",
    "cancer", "tumour", "tumor", "hospitalised", "hospitalized", "critical condition",
    "arrested", "charged", "convicted", "lawsuit", "sued", "fraud", "scandal",
    "layoffs", "fired", "bankrupt", "collapse", "crisis", "recession",
    "protest", "riot", "unrest", "crackdown", "sanctions", "election",
    "verdict", "trial", "court", "jail", "prison",
)

# Additionally dropped for comedic formats: anything centred on a named person.
# A joke about a company is fine; a joke about a specific human is a different
# thing and this module cannot tell whether it would be punching down.
PERSON_MARKERS = (
    "ceo", "founder", "president", "minister", "senator", "governor", "mayor",
    "actor", "actress", "singer", "rapper", "star", "influencer", "streamer",
    "billionaire", "heir", "widow", "family of", "mother of", "father of",
)

_TAG_RE = re.compile(r"<[^>]+>")


def _clean(text: str) -> str:
    return html.unescape(_TAG_RE.sub("", text or "")).strip()


def _is_safe(headline: str, comedic: bool) -> bool:
    low = (headline or "").lower()
    if any(m in low for m in HARD_BLOCK):
        return False
    if comedic and any(m in low for m in PERSON_MARKERS):
        return False
    return True


def _fetch_google_news(query: str, comedic: bool) -> list:
    url = GOOGLE_NEWS_RSS.format(query=urllib.parse.quote(query))
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; ShortsStudio/1.0)"})
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        raw = resp.read()

    root = ET.fromstring(raw)
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
    items = []

    for item in root.iter("item"):
        title = _clean((item.findtext("title") or ""))
        if not title:
            continue

        # Google News appends " - Publisher" to every headline.
        title = re.sub(r"\s+-\s+[^-]{2,40}$", "", title).strip()

        pub = item.findtext("pubDate") or ""
        try:
            from email.utils import parsedate_to_datetime
            when = parsedate_to_datetime(pub)
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            if when < cutoff:
                continue
        except Exception:
            when = None

        if not _is_safe(title, comedic):
            continue

        items.append({
            "headline": title,
            "source": _clean(item.findtext("source") or ""),
            "when": when.isoformat() if when else "",
        })

        if len(items) >= MAX_ITEMS:
            break

    return items


def fetch_pulse(topic_name: str, topic_description: str = "", archetype: str = "") -> list:
    """Returns a short list of current, safety-screened items about a topic.

    Returns [] on any failure, and [] is a perfectly good outcome — the writer
    falls back to the topic alone. Timeliness is a bonus, never a requirement,
    so nothing here is allowed to block or slow a generation run.
    """
    from engine import archetypes as arch

    comedic = archetype in arch.COMEDIC_ARCHETYPES

    # Two queries: the topic itself, and the topic paired with a
    # change-oriented word, which surfaces "what is different now" rather than
    # evergreen background articles.
    queries = [topic_name]
    if topic_description:
        first_noun = " ".join(topic_description.split()[:4])
        queries.append(f"{topic_name} {first_noun}")

    seen, out = set(), []
    for q in queries:
        try:
            for item in _fetch_google_news(q, comedic):
                key = item["headline"].lower()[:60]
                if key not in seen:
                    seen.add(key)
                    out.append(item)
        except Exception as e:
            print(f"[pulse] ⚠ Could not fetch news for {q!r}: {e}")
        if len(out) >= MAX_ITEMS:
            break

    if out:
        print(f"[pulse] ✓ {len(out)} current item(s) found for '{topic_name}'"
              f"{' (comedy-safe filtered)' if comedic else ''}")
    else:
        print(f"[pulse] No usable current items for '{topic_name}' — writing from the topic alone.")
    return out[:MAX_ITEMS]


def prompt_block(items: list, archetype: str = "") -> str:
    """Formats the pulse as prompt context.

    The instructions matter as much as the headlines. Without them the model
    writes a news summary, which is both boring and a copyright problem. What
    is wanted is a video that is ABOUT the topic and quietly informed by what
    is happening — the difference between reporting a trend and having a point
    of view about it.
    """
    if not items:
        return ""

    lines = "\n".join(f"- {i['headline']}" for i in items)
    return f"""

WHAT IS HAPPENING RIGHT NOW (context only — do NOT report on it):
{lines}

HOW TO USE THIS:
Do not summarise these, quote them, or make the video "about the news". Use
them the way a good comedian uses the week's headlines: the video is about the
TOPIC, and it lands harder because it is quietly aware of what people already
have in their heads.

Aim for the second thought, not the first. If the headline is "AI will replace
most office jobs", the obvious video restates that. The good video asks who
maintains the machines, or what the last human in the building actually does
all day. Go one step past the headline to the thing it implies but does not say.

Never state a headline as a fact in the video. Never name a real person.
If none of these give you a genuinely better angle, ignore them completely and
write the strongest possible video from the topic alone.
"""


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Preview the current-affairs pulse for a topic")
    p.add_argument("topic")
    p.add_argument("--archetype", default="observational")
    a = p.parse_args()

    items = fetch_pulse(a.topic, archetype=a.archetype)
    for i in items:
        print(f"  - {i['headline']}")
    if items:
        print(prompt_block(items, a.archetype))
