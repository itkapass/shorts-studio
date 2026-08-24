"""
duplicate_check.py
-------------------
MODULE 2b — Duplicate / Near-Duplicate Script Detection

This module didn't exist before. The sibling Instagram project this codebase
was modeled on has an embeddings-based duplicate_check.py comparing new posts
against the last ~30 days; this YouTube project had nothing equivalent, so
nothing stopped the same topic+tone combination from producing substantially
similar scripts days or weeks apart — which is exactly the pattern YouTube's
"inauthentic / mass-produced content" policy (updated July 2025) scrutinizes.

Uses TF-IDF + cosine similarity (scikit-learn) rather than sentence-transformers
to avoid pulling in torch as a dependency — good enough to catch near-duplicate
scripts at this project's volume (a handful of videos/day), much lighter to
install in CI than a transformer model.

Fails OPEN, not closed: if the check itself errors (DB unreachable, sklearn
issue, empty history), a video is allowed through rather than the whole
pipeline breaking over a broken dedup check. A false negative here just means
one un-flagged similar video; a hard crash here would silently stop the whole
day's generation, which is worse.
"""
from datetime import datetime, timedelta, timezone
import json

from engine.config import get

SIMILARITY_THRESHOLD = 0.75   # cosine similarity above this -> treat as a duplicate
LOOKBACK_DAYS = 30

# HONEST LIMITATION: TF-IDF is a lexical (word-overlap) similarity measure,
# not a semantic one. It reliably catches near-verbatim repeats — the same
# topic+tone combination producing substantially the same script again,
# which is the actual failure mode this project has no other defense
# against. It will NOT reliably catch a script that covers the same ground
# in fully different words (a true paraphrase). If that matters more than
# the extra dependency weight, swap this module's vectorizer for
# sentence-transformers embeddings + cosine similarity — same call shape,
# heavier install (pulls in torch).


def _get_db():
    from supabase import create_client
    url = get("SUPABASE_URL")
    key = get("SUPABASE_SERVICE_KEY") or get("SUPABASE_ANON_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_KEY not configured")
    return create_client(url, key)


def _full_script_text(storyboard: dict) -> str:
    """Flattens a storyboard's scene voice_text into one string for comparison."""
    scenes = storyboard.get("scenes", [])
    return " ".join(s.get("voice_text", "") for s in scenes)


def check_duplicate(new_storyboard: dict, lookback_days: int = LOOKBACK_DAYS) -> dict:
    """
    Compares a freshly generated storyboard's script text against recently
    generated videos (any status) in the last `lookback_days`.

    Returns:
        {"is_duplicate": bool, "similarity": float, "matched_title": str | None}
        On any internal error: {"is_duplicate": False, "similarity": 0.0, "error": "..."}
        (fails open — see module docstring)
    """
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        new_text = _full_script_text(new_storyboard)
        if not new_text.strip():
            return {"is_duplicate": False, "similarity": 0.0, "matched_title": None}

        db = _get_db()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()
        result = (
            db.table("videos")
            .select("title, storyboard")
            .gte("created_at", cutoff)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return {"is_duplicate": False, "similarity": 0.0, "matched_title": None}

        history_texts, history_titles = [], []
        for row in rows:
            try:
                sb = row["storyboard"] if isinstance(row.get("storyboard"), dict) else json.loads(row.get("storyboard") or "{}")
            except (json.JSONDecodeError, TypeError):
                continue
            text = _full_script_text(sb)
            if text.strip():
                history_texts.append(text)
                history_titles.append(row.get("title", "(untitled)"))

        if not history_texts:
            return {"is_duplicate": False, "similarity": 0.0, "matched_title": None}

        corpus = history_texts + [new_text]
        vectorizer = TfidfVectorizer(stop_words="english")
        matrix = vectorizer.fit_transform(corpus)
        sims = cosine_similarity(matrix[-1], matrix[:-1])[0]

        best_idx = int(sims.argmax())
        best_sim = float(sims[best_idx])

        return {
            "is_duplicate": best_sim >= SIMILARITY_THRESHOLD,
            "similarity": round(best_sim, 3),
            "matched_title": history_titles[best_idx] if best_sim >= SIMILARITY_THRESHOLD else None,
        }

    except Exception as e:
        print(f"[duplicate_check] \u26a0 Check failed, allowing video through (fail-open): {e}")
        return {"is_duplicate": False, "similarity": 0.0, "matched_title": None, "error": str(e)}
