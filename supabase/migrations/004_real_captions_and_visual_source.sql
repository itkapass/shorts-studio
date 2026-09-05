-- ============================================================================
-- 004_real_captions_and_visual_source.sql
--
-- Safe to run more than once. Applies automatically if you followed docs/14
-- (Deploy Database Migrations) — otherwise paste into Supabase SQL Editor.
-- ============================================================================

-- The exact .srt this video's burned-in captions were generated from. Stored
-- as text directly on the row (small — a 45s Short's captions are a few KB)
-- rather than as a separate storage file, so publish time can read it
-- straight off the row it already has without a second download.
--
-- WHY THIS EXISTS: subtitle_engine.py has always generated a perfect SRT
-- file every render, and its own docstring says it's "useful ... as a
-- YouTube subtitle upload" — but nothing ever uploaded it. The file was
-- written to the render job's temporary disk and discarded when that job's
-- runner shut down, since generation and publishing run as separate GitHub
-- Actions jobs with no shared filesystem. This column is what lets the
-- content survive from one job to the other.
ALTER TABLE videos ADD COLUMN IF NOT EXISTS captions_srt TEXT;

-- Nothing else in this migration. Kept single-purpose and reversible:
--   ALTER TABLE videos DROP COLUMN IF EXISTS captions_srt;
