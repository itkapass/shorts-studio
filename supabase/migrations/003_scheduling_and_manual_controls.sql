-- ============================================================================
-- 003_scheduling_and_manual_controls.sql
--
-- Safe to run more than once. Every statement is additive or guarded.
-- Paste the whole file into Supabase -> SQL Editor -> Run.
--
-- WHAT THIS MIGRATION DOES
--   1. Adds a "Publish Now" flag so you can force one video out immediately
--      without waiting for its scheduled slot.
--   2. Adds the scheduling settings the new spread-out publishing uses.
--   3. Clears the seeded 'auto_topic_personas' value that was silently
--      stopping channels 2 and 3 from ever getting topics.
-- ============================================================================


-- ── 1. Publish Now ──────────────────────────────────────────────────────────
-- Publishing is now spaced out (one video every N hours instead of every
-- video the moment it is approved). That spacing is right for the robot and
-- wrong for you: when YOU decide a video should go out now, it should go out
-- now. This column is how the dashboard's "Publish Now" button says so.

ALTER TABLE videos ADD COLUMN IF NOT EXISTS publish_now BOOLEAN DEFAULT FALSE;

-- Partial index: the publish job asks "is anything forced?" every 30 minutes,
-- and this makes that a near-free lookup instead of a scan of every video
-- you have ever made.
CREATE INDEX IF NOT EXISTS idx_videos_publish_now
    ON videos (publish_now)
    WHERE publish_now = TRUE;


-- ── 2. Scheduling settings ──────────────────────────────────────────────────

INSERT INTO settings (key, value)
SELECT 'publish_min_gap_minutes', '0'
WHERE NOT EXISTS (SELECT 1 FROM settings WHERE key = 'publish_min_gap_minutes');
-- 0 means "work it out from the channel's daily cap" — 4/day becomes one
-- every 6 hours automatically. Set a number here only to override that.

INSERT INTO settings (key, value)
SELECT 'videos_per_run', '1'
WHERE NOT EXISTS (SELECT 1 FROM settings WHERE key = 'videos_per_run');
-- How many videos a single scheduled run may render. ONE is deliberate.
-- Rendering is the slowest, heaviest step in the pipeline (ffmpeg, TTS and
-- Whisper on a free GitHub runner); two in one run doubles the time the job
-- holds a runner and doubles what is lost if it times out. Small, frequent
-- runs recover from failure far better than large, rare ones.

INSERT INTO settings (key, value)
SELECT 'max_videos_daily', '6'
WHERE NOT EXISTS (SELECT 1 FROM settings WHERE key = 'max_videos_daily');


-- ── 3. THE BUG FIX ──────────────────────────────────────────────────────────
-- Migration 002 seeded this setting with a single persona:
--
--     INSERT INTO settings (key, value)
--     SELECT 'auto_topic_personas', 'tech_science_explainer'
--
-- ...and engine/topic_synthesizer.py treated that setting as the HIGHEST
-- priority source, on the reasoning that "a person set it deliberately".
-- No person had. The migration had. So the next source down — personas
-- attached to your enabled channels — became unreachable, and the Comedy
-- and Tamil Quotes channels could never get topics invented for them no
-- matter what you configured on the Channels page. No error was ever shown.
--
-- The code side is fixed (sources are now unioned, so an enabled channel
-- can never be silently cancelled by a setting). This clears the stale
-- seeded value too, so the setting means what it says: empty = "just use
-- my channels".
--
-- Guarded on the exact seeded string, so if you have since typed your own
-- list in Settings, yours is left completely alone.

UPDATE settings
SET value = ''
WHERE key = 'auto_topic_personas'
  AND value = 'tech_science_explainer';


-- ── 4. Helpful view for the dashboard ───────────────────────────────────────
-- Lets the Video Queue show "next slot in 2h 10m" without every browser
-- recomputing it from raw rows.

CREATE OR REPLACE VIEW publishing_status AS
SELECT
    c.id            AS channel_id,
    c.name          AS channel_name,
    c.daily_cap,
    c.publish_mode,
    (SELECT COUNT(*) FROM videos v
      WHERE v.channel_id = c.id
        AND v.status = 'published'
        AND v.published_at > NOW() - INTERVAL '24 hours')          AS published_24h,
    (SELECT MAX(v.published_at) FROM videos v
      WHERE v.channel_id = c.id AND v.status = 'published')        AS last_published_at,
    (SELECT COUNT(*) FROM videos v
      WHERE v.channel_id = c.id AND v.status = 'approved')         AS waiting_approved
FROM channels c;
