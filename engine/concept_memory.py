"""
concept_memory.py — the "don't make this video again" ledger.
=============================================================

WHAT PROBLEM THIS SOLVES
duplicate_check.py already compares finished SCRIPTS for near-verbatim overlap.
That is not enough. Two scripts can share almost no wording and still be the
same video: "why the ocean is salty" written twice, once as a fact-drop and
once as a two-character skit, has near-zero lexical overlap and is still a
repeat. YouTube's inauthentic-content policy cares about the second kind.

So this works one level up, on the CONCEPT rather than the script:
  - Every approved / published / manually-exported video writes its concept
    into a ledger.
  - Before generation, the ledger is handed to the model as an explicit
    "do not write about any of these" list.
  - After generation, the new concept is scored against the ledger and
    anything above the similarity ceiling is rejected before it is ever
    rendered (rejecting at render time would waste the expensive step).

TWO SIMILARITY SIGNALS, DELIBERATELY
  1. Lexical (TF-IDF cosine) — catches rewordings of the same sentence.
  2. Topical (keyword-set Jaccard) — catches the same subject approached from
     a different angle, which is exactly what signal 1 misses.
A concept is a duplicate if EITHER fires. Using only the first is the mistake
the old duplicate_check made; using only the second would reject legitimately
different videos that happen to share nouns.

THE LEDGER IS A REAL FILE, ON PURPOSE
`concepts.jsonl` is committed to the repo by the workflow, so you can open it,
read it, and hand-edit it. That was a specific request and it is also good
engineering: an opaque table in a database you have to query is much harder to
sanity-check than a file you can scroll. The database copy is the source of
truth for the pipeline; the file is the copy for humans.
"""
import json
import os
import re
from datetime import datetime, timedelta, timezone

from engine.config import get

# Above either of these, a new concept is treated as a repeat.
LEXICAL_CEILING = 0.50    # TF-IDF cosine on title + premise
TOPICAL_CEILING = 0.32    # keyword overlap (see _topical_similarity)
LOOKBACK_DAYS = 120       # concepts older than this stop blocking new ones
LEDGER_PATH = "concepts.jsonl"

_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for", "with",
    "is", "are", "was", "were", "be", "been", "it", "its", "this", "that", "these",
    "those", "as", "at", "by", "from", "you", "your", "we", "our", "they", "their",
    "how", "why", "what", "when", "where", "who", "which", "can", "will", "would",
    "about", "into", "than", "then", "so", "if", "not", "no", "do", "does", "did",
    "shorts", "video", "actually", "really", "just", "one", "more", "most", "some",
}


def _keywords(text: str) -> set:
    words = re.findall(r"[a-z][a-z0-9\-]{2,}", (text or "").lower())
    return {w for w in words if w not in _STOPWORDS}


def _topical_similarity(a: set, b: set) -> float:
    """How much two keyword sets are about the same thing.

    Originally plain Jaccard (intersection / union), which was too forgiving.
    Union grows with every word either side uses, so two videos about the
    identical subject written at different lengths scored around 0.25 and
    slipped under a 0.50 ceiling. That is how the same idea came out three
    times.

    Overlap coefficient (intersection / size of the smaller set) does not get
    diluted by length. Measured across known same/different pairs, same-idea
    pairs land at 0.25-0.62 and genuinely different pairs at 0.00, so a 0.32
    ceiling separates them cleanly with room on both sides.

    The max of both is used so neither measure can hide a repeat on its own.
    """
    if not a or not b:
        return 0.0
    inter = len(a & b)
    jaccard = inter / len(a | b)
    overlap = inter / min(len(a), len(b))
    return max(jaccard, overlap)


def concept_signature(storyboard: dict) -> dict:
    """Reduces a storyboard to the small record the ledger stores.

    Deliberately does NOT store the full script. The ledger is about "which
    ideas are used up", and keeping it small keeps it readable and keeps the
    prompt that consumes it from eating the context window.
    """
    title = storyboard.get("video_title", "") or ""
    premise = storyboard.get("concept") or storyboard.get("hook_concept") or ""
    body = " ".join(s.get("voice_text", "") for s in storyboard.get("scenes", []))
    return {
        "title": title.replace("#Shorts", "").strip(),
        "premise": premise.strip(),
        "keywords": sorted(_keywords(f"{title} {premise} {body}"))[:24],
        "archetype": storyboard.get("archetype", ""),
        "render_style": storyboard.get("render_style", ""),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _db():
    from supabase import create_client
    url, key = get("SUPABASE_URL"), get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_KEY not configured")
    return create_client(url, key)


def load_ledger(lookback_days: int = LOOKBACK_DAYS, db=None) -> list:
    """Reads used concepts, newest first.

    Reads from TWO places, and the second one matters more than it looks:

      1. The `concepts` table — ideas from videos that were actually published.
      2. The `videos` table — every video that has been GENERATED and not
         rejected, including ones still sitting in the review queue.

    Source 2 was missing originally and it was a real bug. The reasoning for
    recording concepts only on approval was that a rejected video shouldn't
    burn its idea — which is correct on its own, but it left a blind spot
    exactly the size of the review backlog. With 20 videos pending and none
    approved, the ledger was empty, so every run happily rewrote ideas that
    had already been rendered. That is how the same script came out three
    times with different footage.

    An idea that has already been turned into a video is used up for
    generation purposes, whether or not a human has got round to approving it.

    Fails open and returns [] on error: an unreachable ledger should slow
    nothing down. The cost is one possibly-repeated video; the cost of the
    opposite choice is the whole day's generation stopping.
    """
    rows = []
    cutoff = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()

    try:
        db = db or _db()
    except Exception as e:
        print(f"[concept_memory] ⚠ Could not connect, continuing without a ledger: {e}")
        return []

    # 1. Published concepts
    try:
        rows += (
            db.table("concepts")
            .select("title, premise, keywords, archetype, created_at")
            .gte("created_at", cutoff)
            .order("created_at", desc=True)
            .limit(500)
            .execute()
            .data
        ) or []
    except Exception as e:
        print(f"[concept_memory] ⚠ Could not read the concepts table: {e}")

    # 2. Concepts from videos already generated but not yet published
    try:
        videos = (
            db.table("videos")
            .select("title, storyboard, archetype, created_at, status")
            .gte("created_at", cutoff)
            .neq("status", "rejected")
            .order("created_at", desc=True)
            .limit(300)
            .execute()
            .data
        ) or []
        for v in videos:
            storyboard = v.get("storyboard")
            if isinstance(storyboard, str):
                try:
                    storyboard = json.loads(storyboard)
                except Exception:
                    storyboard = None
            if not storyboard:
                continue
            sig = concept_signature(storyboard)
            if not sig.get("title"):
                sig["title"] = v.get("title") or ""
            sig["created_at"] = v.get("created_at") or sig["created_at"]
            rows.append(sig)
    except Exception as e:
        print(f"[concept_memory] ⚠ Could not read pending videos: {e}")

    # Same idea can appear in both sources; keep one copy.
    seen, unique = set(), []
    for r in rows:
        key = (r.get("title") or "").strip().lower()
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        unique.append(r)

    return unique


def check_concept(storyboard: dict, ledger: list = None, db=None) -> dict:
    """Scores a new storyboard against the ledger.

    Returns {"is_repeat", "score", "reason", "matched_title", "signature"}.
    """
    sig = concept_signature(storyboard)
    ledger = ledger if ledger is not None else load_ledger(db=db)

    if not ledger:
        return {"is_repeat": False, "score": 0.0, "reason": "", "matched_title": None, "signature": sig}

    new_kw = set(sig["keywords"])
    best_topical, best_topical_title = 0.0, None
    for row in ledger:
        score = _topical_similarity(new_kw, set(row.get("keywords") or []))
        if score > best_topical:
            best_topical, best_topical_title = score, row.get("title")

    best_lexical, best_lexical_title = 0.0, None
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        new_text = f"{sig['title']} {sig['premise']}".strip()
        corpus = [f"{r.get('title','')} {r.get('premise','')}".strip() for r in ledger]
        corpus = [c for c in corpus if c]
        if new_text and corpus:
            m = TfidfVectorizer(stop_words="english").fit_transform(corpus + [new_text])
            sims = cosine_similarity(m[-1], m[:-1])[0]
            idx = int(sims.argmax())
            best_lexical = float(sims[idx])
            best_lexical_title = ledger[idx].get("title")
    except Exception as e:
        print(f"[concept_memory] ⚠ Lexical check unavailable ({e}); using topical only.")

    if best_topical >= TOPICAL_CEILING:
        return {
            "is_repeat": True, "score": round(best_topical, 3), "reason": "same subject matter",
            "matched_title": best_topical_title, "signature": sig,
        }
    if best_lexical >= LEXICAL_CEILING:
        return {
            "is_repeat": True, "score": round(best_lexical, 3), "reason": "near-identical premise",
            "matched_title": best_lexical_title, "signature": sig,
        }

    return {
        "is_repeat": False,
        "score": round(max(best_topical, best_lexical), 3),
        "reason": "", "matched_title": None, "signature": sig,
    }


def record_concept(storyboard: dict, job_id: str, db=None, ledger_path: str = LEDGER_PATH):
    """Commits a concept to the ledger. Call this at APPROVAL, not generation.

    That ordering matters. Recording at generation time burns the concept even
    when the video is rejected for quality, which would slowly starve the topic
    pool of its best ideas. A concept is only "used up" once a video built on
    it is actually going out.
    """
    sig = concept_signature(storyboard)
    sig["job_id"] = job_id

    try:
        db = db or _db()
        db.table("concepts").insert(sig).execute()
    except Exception as e:
        print(f"[concept_memory] ⚠ Could not write concept to database: {e}")

    try:
        with open(ledger_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(sig, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[concept_memory] ⚠ Could not append to {ledger_path}: {e}")

    return sig


def avoid_list_for_prompt(ledger: list, limit: int = 60) -> str:
    """Formats the ledger as a 'do not repeat these' block for the model.

    Titles only, newest first, hard-capped. Sending the full ledger would grow
    the prompt without bound as the channel ages, and the model does not need
    the detail — it needs the shape of what is already taken.
    """
    if not ledger:
        return "(nothing yet — this is a fresh channel)"
    seen, lines = set(), []
    for row in ledger[:limit]:
        t = (row.get("title") or "").strip()
        if t and t.lower() not in seen:
            seen.add(t.lower())
            lines.append(f"- {t}")
    return "\n".join(lines) if lines else "(nothing yet)"
