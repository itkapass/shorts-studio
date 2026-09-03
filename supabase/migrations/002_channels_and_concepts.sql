-- ============================================================================
-- MIGRATION 002 — channels, concept ledger, and new video metadata
-- ============================================================================
--
-- SAFE TO RE-RUN. Every statement uses IF NOT EXISTS or CREATE OR REPLACE, so
-- running this twice does nothing the second time. That matters because the
-- most common way a beginner breaks a database is running a migration twice
-- and getting a wall of red errors they cannot interpret.
--
-- HOW TO RUN
--   Supabase dashboard -> SQL Editor -> New query -> paste all of this -> Run.
--   You should see "Success. No rows returned."
--
-- WHAT IT ADDS
--   channels   — one row per YouTube channel, with category routing
--   concepts   — the "already made this idea" ledger
--   videos.*   — archetype/category, channel, quality verdict, export tracking
-- ============================================================================


-- ── New columns on videos ───────────────────────────────────────────────────
-- Split out one per statement so a single pre-existing column cannot abort
-- the whole migration.

ALTER TABLE videos ADD COLUMN IF NOT EXISTS archetype        TEXT;
ALTER TABLE videos ADD COLUMN IF NOT EXISTS category         TEXT;
ALTER TABLE videos ADD COLUMN IF NOT EXISTS channel_id       BIGINT;
ALTER TABLE videos ADD COLUMN IF NOT EXISTS quality_verdict  TEXT;
ALTER TABLE videos ADD COLUMN IF NOT EXISTS storage_backend  TEXT;
ALTER TABLE videos ADD COLUMN IF NOT EXISTS storage_freed_at TIMESTAMPTZ;
ALTER TABLE videos ADD COLUMN IF NOT EXISTS exported_at      TIMESTAMPTZ;

-- The status column gains three new values: 'exported' (packaged for manual
-- posting), 'needs_manual' (no auto-publish channel accepted it), and
-- 'gate_failed'. Status is TEXT with no CHECK constraint, so no change is
-- needed here — this comment exists so the values are documented somewhere.


-- ── channels ────────────────────────────────────────────────────────────────
-- One row per YouTube channel. Deliberately holds NO credentials: it stores
-- the SUFFIX of the environment variables that hold them. A channel with
-- env_suffix 'SCIENCE' reads YOUTUBE_CLIENT_ID_SCIENCE, and so on, from GitHub
-- Secrets. If this table ever leaked, no channel would be compromised.

CREATE TABLE IF NOT EXISTS channels (
    id            BIGSERIAL PRIMARY KEY,
    name          TEXT NOT NULL,
    handle        TEXT,
    -- Which content categories this channel accepts. Must match the keys in
    -- engine/archetypes.py.
    categories    TEXT[] DEFAULT '{}',
    -- 'auto'   = the pipeline publishes to this channel by itself
    -- 'manual' = approved videos are packaged for you to post by hand
    publish_mode  TEXT NOT NULL DEFAULT 'manual',
    -- Env var suffix for this channel's OAuth secrets. Empty = the
    -- unsuffixed YOUTUBE_* variables, so an existing single-channel setup
    -- keeps working with no migration.
    env_suffix    TEXT DEFAULT '',
    -- Uploads per day. Keep at or below 5: YouTube gives 10,000 API units per
    -- Google Cloud project per day and each upload costs 1,600, so 6 is the
    -- hard ceiling and 5 leaves headroom for a retry.
    daily_cap     INTEGER NOT NULL DEFAULT 5,
    -- Lower runs first when several channels accept the same category.
    priority      INTEGER NOT NULL DEFAULT 100,
    -- Receives anything no other channel claimed.
    is_catchall   BOOLEAN NOT NULL DEFAULT FALSE,
    is_enabled    BOOLEAN NOT NULL DEFAULT TRUE,
    notes         TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_channels_enabled ON channels (is_enabled, priority);


-- ── concepts ────────────────────────────────────────────────────────────────
-- The "do not make this video again" ledger. A row is written when a video is
-- APPROVED or PUBLISHED, never at generation time — see the note in
-- engine/concept_memory.py for why that ordering matters.

CREATE TABLE IF NOT EXISTS concepts (
    id            BIGSERIAL PRIMARY KEY,
    job_id        TEXT,
    title         TEXT NOT NULL,
    premise       TEXT,
    -- Extracted keyword set, used for topical (Jaccard) similarity. This is
    -- what catches "same subject, different wording" — the case a pure text
    -- comparison misses entirely.
    keywords      TEXT[] DEFAULT '{}',
    archetype     TEXT,
    render_style  TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_concepts_created ON concepts (created_at DESC);


-- ── topics: archetype pinning ───────────────────────────────────────────────
-- Lets a topic force a specific format. NULL means "rotate through formats",
-- which is the better default — a channel that only ever posts one format
-- gets stale fast.

ALTER TABLE topics ADD COLUMN IF NOT EXISTS archetype TEXT;
ALTER TABLE topics ADD COLUMN IF NOT EXISTS source_url TEXT;
ALTER TABLE topics ADD COLUMN IF NOT EXISTS added_by  TEXT DEFAULT 'system';


-- ── Row Level Security ──────────────────────────────────────────────────────
-- Same posture as the rest of the schema: authenticated users only. The
-- earlier version of this project shipped policies NAMED for service_role that
-- actually granted the public anon key full read/write, which meant anyone
-- with the project URL could insert a row. These are scoped properly.

ALTER TABLE channels ENABLE ROW LEVEL SECURITY;
ALTER TABLE concepts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "authenticated_all_channels" ON channels;
CREATE POLICY "authenticated_all_channels" ON channels
    FOR ALL TO authenticated USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "authenticated_all_concepts" ON concepts;
CREATE POLICY "authenticated_all_concepts" ON concepts
    FOR ALL TO authenticated USING (true) WITH CHECK (true);


-- ── Seed: one manual-posting catchall channel ───────────────────────────────
-- Starts in 'manual' mode on purpose. Nothing should ever publish to a real
-- YouTube channel until you have explicitly set it up and switched it over.

INSERT INTO channels (name, categories, publish_mode, env_suffix, is_catchall, notes)
SELECT
    'Main Channel',
    ARRAY['informative','myth_busting','life_hack','relatable','wholesome',
          'empathy','dark_humour','sarcasm','absurd','observational'],
    'manual',
    '',
    TRUE,
    'Default channel. Set publish_mode to auto once your YouTube OAuth is working.'
WHERE NOT EXISTS (SELECT 1 FROM channels);


-- ── New settings keys ───────────────────────────────────────────────────────

INSERT INTO settings (key, value)
SELECT * FROM (VALUES
    ('storage_backend',        'auto'),
    ('alerts_enabled',         'true'),
    ('concept_dedupe_enabled', 'true'),
    ('quality_gates_enabled',  'true'),
    ('videos_per_topic_daily', '2')
) AS v(key, value)
WHERE NOT EXISTS (SELECT 1 FROM settings s WHERE s.key = v.key);


-- ── Narrative structure (added with the props/structure upgrade) ────────────
-- The third axis alongside topic and archetype: the SHAPE of the video.
-- NULL means "rotate automatically", which is the better default.

ALTER TABLE videos ADD COLUMN IF NOT EXISTS structure TEXT;
ALTER TABLE topics ADD COLUMN IF NOT EXISTS structure TEXT;
ALTER TABLE concepts ADD COLUMN IF NOT EXISTS structure TEXT;


-- ── Creative brief + current-affairs context ────────────────────────────────
-- The brief is stored so you can see WHY a video was made the way it was:
-- which angles were considered, which won, and what was deliberately avoided.
-- When output is weak, that is the difference between guessing and knowing.

ALTER TABLE videos ADD COLUMN IF NOT EXISTS creative_brief JSONB;
ALTER TABLE videos ADD COLUMN IF NOT EXISTS pulse_context  TEXT[];


-- ── Topic label (free-text grouping, separate from the AI content format) ───
-- "category" on topics/videos already means the AI FORMAT (dark_humour,
-- informative, etc) and channels.py routes on it — repurposing it would break
-- multi-channel routing. topic_label is the user's own subject tag ("office",
-- "school", "science") for filtering the review queue, independent of format.

ALTER TABLE videos ADD COLUMN IF NOT EXISTS topic_label TEXT;


-- ── Personas: a channel becomes a DOMAIN, not just an upload address ────────
-- persona_key references a template in engine/personas.py (code, not a table,
-- consistent with how archetypes/narrative structures already work — easy to
-- add new ones without a migration). NULL everywhere means "today's behaviour,
-- unchanged" — nothing here is required.

ALTER TABLE channels ADD COLUMN IF NOT EXISTS persona_key TEXT;
ALTER TABLE topics   ADD COLUMN IF NOT EXISTS persona_key TEXT;
ALTER TABLE videos   ADD COLUMN IF NOT EXISTS persona_key TEXT;

CREATE INDEX IF NOT EXISTS idx_topics_persona ON topics (persona_key) WHERE persona_key IS NOT NULL;


-- ── Allow deleting a topic that already has videos ──────────────────────────
-- videos.topic_id referenced topics(id) with no ON DELETE rule, so Postgres
-- defaults to NO ACTION and refuses the delete:
--   'update or delete on table "topics" violates foreign key constraint
--    "videos_topic_id_fkey" on table "videos"'
--
-- ON DELETE SET NULL is the right rule here rather than CASCADE. CASCADE
-- would delete every video ever made from that topic — including published
-- ones, taking their YouTube IDs and history with them. Setting the reference
-- to NULL keeps the videos and their history intact; they simply stop
-- pointing at a topic that no longer exists.

ALTER TABLE videos DROP CONSTRAINT IF EXISTS videos_topic_id_fkey;
ALTER TABLE videos ADD  CONSTRAINT videos_topic_id_fkey
    FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE SET NULL;

ALTER TABLE videos DROP CONSTRAINT IF EXISTS videos_tone_id_fkey;
ALTER TABLE videos ADD  CONSTRAINT videos_tone_id_fkey
    FOREIGN KEY (tone_id) REFERENCES tones(id) ON DELETE SET NULL;
