"""
api_budget.py — stop running out of Gemini quota mid-batch.
===========================================================

WHAT WENT WRONG
The Gemini free tier allows a limited number of generate_content requests per
day (20 on gemini-3.0-flash at time of writing — the exact number is returned
in the 429 error body as `quotaValue`). The pipeline was quietly spending far
more than that:

    creative brief      1 call
    storyboard          1 call
    visual ranking      1 call PER SCENE  <-- 5 calls for a 5-scene video
    -----------------------------------
                        7 calls per video

Four videos = 28 calls, plus topic synthesis = 30. Against a 20/day limit,
that meant the first two videos worked and everything after failed with
429 RESOURCE_EXHAUSTED — which is exactly what the queue showed.

Worse, it failed one video at a time. Each of the remaining videos still ran
its whole pipeline, hit the wall, and logged a separate failure. The run
burned quota it did not have and produced a queue full of red.

WHAT THIS DOES
Tracks spend against a daily budget and refuses to start work it cannot
finish. Three rules:

  1. RESERVE BEFORE STARTING. A video needs a known number of calls. If that
     many are not left, do not start it — leaving a half-generated video is
     worse than not starting.
  2. ONE 429 STOPS THE WHOLE RUN. A quota error is not a per-video problem,
     it is a per-day problem. Retrying the next video guarantees another 429.
  3. PERSIST ACROSS RUNS. The daily quota does not reset because a workflow
     restarted. Counts are stored in the database, keyed by UTC date.

The budget deliberately reserves headroom: the free-tier number is not always
exactly what the docs say, and being one call short is far more annoying than
generating one fewer video.
"""
from engine import daycycle

# Gemini free tier daily request cap. Overridable via the GEMINI_DAILY_BUDGET
# setting because Google changes this and paid tiers are far higher.
DEFAULT_DAILY_BUDGET = 20

# Never spend the last few calls — leaves room for a retry and for the health
# check, which also calls the model.
RESERVE_HEADROOM = 2


class QuotaExhausted(Exception):
    """Raised when the daily budget is gone. Callers should stop the entire
    run, not move to the next item."""


class BudgetTracker:
    def __init__(self, db=None, daily_budget: int = None, key_id: str = "default"):
        self.db = db
        self.daily_budget = int(daily_budget or DEFAULT_DAILY_BUDGET)
        # key_id distinguishes one Gemini API key's quota from another's. A
        # single global "today" counter would still show the SAME number for
        # every channel even after each got its own Gemini key — the whole
        # point of a separate key is a separate 20/day pool, so the counter
        # tracking it has to be separate too.
        self.key_id = key_id or "default"
        self.spent = 0
        self._loaded = False
        self._hard_stopped = False

    # ── persistence ─────────────────────────────────────────────────────────

    def _today_key(self) -> str:
        # PACIFIC, not UTC. Gemini's requests-per-day allowance resets at
        # midnight Pacific; keying this counter on the UTC date meant our
        # "day" started 7-8 hours before Google's did, so early-morning runs
        # spent yesterday's exhausted quota, got a real 429, and pinned this
        # counter to full for the rest of the UTC day — including all the
        # hours when the real quota WAS available. See engine/daycycle.py.
        return f"api_calls_{self.key_id}_{daycycle.quota_day()}"

    def load(self):
        """Reads today's spend so a re-run doesn't reset the counter."""
        if self._loaded or not self.db:
            self._loaded = True
            return
        try:
            rows = (
                self.db.table("settings").select("key, value")
                .eq("key", self._today_key()).execute().data
            ) or []
            self.spent = int(rows[0]["value"]) if rows else 0
        except Exception as e:
            print(f"[api_budget] ⚠ Could not read today's usage ({e}); assuming 0.")
            self.spent = 0
        self._loaded = True
        print(f"[api_budget] {self.spent}/{self.daily_budget} Gemini calls used today.")

    def _persist(self):
        if not self.db:
            return
        try:
            key = self._today_key()
            existing = self.db.table("settings").select("key").eq("key", key).execute().data
            if existing:
                self.db.table("settings").update({"value": str(self.spent)}).eq("key", key).execute()
            else:
                self.db.table("settings").insert({"key": key, "value": str(self.spent)}).execute()
        except Exception as e:
            print(f"[api_budget] ⚠ Could not save usage count: {e}")

    # ── budget checks ───────────────────────────────────────────────────────

    @property
    def remaining(self) -> int:
        return max(0, self.daily_budget - RESERVE_HEADROOM - self.spent)

    def can_afford(self, calls: int) -> bool:
        self.load()
        return not self._hard_stopped and self.remaining >= calls

    def require(self, calls: int, what: str = "this step"):
        """Raises QuotaExhausted if `calls` cannot be afforded.

        Call this BEFORE starting an expensive multi-step operation, so the
        pipeline never begins a video it cannot finish.
        """
        self.load()
        if self._hard_stopped:
            raise QuotaExhausted(
                "The Gemini daily quota was already hit earlier in this run. "
                "Stopping so the rest of today's budget is not wasted on calls "
                "that will also fail."
            )
        if self.remaining < calls:
            raise QuotaExhausted(
                f"Not enough Gemini quota left for {what}: needs {calls}, "
                f"{self.remaining} remaining of {self.daily_budget} today.\n\n"
                f"The free tier allows about {self.daily_budget} requests per day, "
                f"and it refills in about {daycycle.humanize_until_reset()}.\n\n"
                f"Reduce 'Daily video generation batch' in Settings, or give this "
                f"channel its own Gemini key from a separate Google account "
                f"(see docs/10)."
            )

    def spend(self, calls: int = 1):
        self.load()
        self.spent += calls
        self._persist()

    def hard_stop(self, reason: str = ""):
        """Called when a real 429 comes back. Ends the run immediately.

        A quota error is a per-DAY condition, not a per-video one. Continuing
        to the next video guarantees another 429 and produces a queue full of
        identical red errors, which is what happened before this existed.
        """
        self._hard_stopped = True
        # Assume the budget is gone; the exact remaining count is unknowable
        # from a 429 alone. This is now SAFE to do, because the counter is
        # keyed on the Pacific day (engine/daycycle.py) — so this pin expires
        # exactly when Google's real quota does. Under the old UTC keying it
        # expired 7-8 hours too late and blocked a perfectly good quota.
        self.spent = self.daily_budget
        self._persist()
        print(f"[api_budget] 🛑 HARD STOP — Gemini daily quota exhausted. {reason}")
        print(f"[api_budget]    Refills in about {daycycle.humanize_until_reset()} "
              f"(midnight Pacific). This is expected on a free key, not a crash.")

    @property
    def stopped(self) -> bool:
        return self._hard_stopped


def is_rate_limit_error(exc) -> bool:
    """True for any 429 — daily OR per-minute. Says nothing about which."""
    text = str(exc)
    return "RESOURCE_EXHAUSTED" in text or "429" in text or "quota" in text.lower()


def is_per_minute_limit(exc) -> bool:
    """True if a 429 is the PER-MINUTE limit, not the daily one.

    Google returns HTTP 429 for both, and the two need opposite responses:

      per-MINUTE  -> wait ~30 seconds and the exact same request succeeds
      per-DAY     -> nothing will succeed until midnight Pacific

    Treating every 429 as fatal-for-the-day meant one momentary burst — three
    calls landing inside the same minute, which happens naturally when topic
    synthesis and a storyboard run back to back — would call hard_stop() and
    throw away a completely intact daily allowance.

    The error body distinguishes them: the free tier's daily quota is named
    'GenerateRequestsPerDayPerProjectPerModel-FreeTier', while the per-minute
    one is 'GenerateRequestsPerMinutePerProjectPerModel-FreeTier'. So we look
    at the quota ID rather than guessing from the status code alone.
    """
    text = str(exc)
    if "PerDay" in text:
        return False
    return "PerMinute" in text or "RequestsPerMinute" in text


def is_quota_error(exc) -> bool:
    """True if an exception means the DAILY allowance is gone.

    503 UNAVAILABLE means the model is busy and a retry very likely will
    help. A per-minute 429 means slow down for a moment. Only a per-day 429
    means stop for the day — and only that one should ever reach hard_stop().
    """
    if not is_rate_limit_error(exc):
        return False
    return not is_per_minute_limit(exc)


def retry_delay_seconds(exc, default: int = 35) -> int:
    """Pulls Google's own suggested wait out of a 429 body when it is there.

    The error payload carries a RetryInfo block with a 'retryDelay' like
    '21s'. Obeying the number the server gave us beats guessing.
    """
    import re
    m = re.search(r"retryDelay['\"]?\s*:\s*['\"]?(\d+)s", str(exc))
    if m:
        return min(int(m.group(1)) + 5, 120)
    return default


def estimate_calls_per_video(use_brief: bool = True, use_ranking: bool = True) -> int:
    """How many Gemini calls one video costs with the current feature set."""
    return 1 + (1 if use_brief else 0) + (1 if use_ranking else 0)
