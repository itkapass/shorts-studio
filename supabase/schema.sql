-- ════════════════════════════════════════════════════════════════
-- Supabase Database Schema
-- YouTube Shorts AI Pipeline
--
-- HOW TO RUN:
--   1. Open Supabase Dashboard → SQL Editor
--   2. Paste this entire file and click "Run"
--   3. Then go to Authentication → Users → Add User and create YOURSELF
--      a login (email + password). The Admin Panel now requires signing
--      in — see docs/01_SUPABASE_DATABASE_SETUP.md.
--
-- SECURITY FIX (read this before you skip it):
-- The previous version of this file had policies literally named
-- "Allow all for service_role" that actually granted full read/write/delete
-- to EVERYONE, including the public anon role your Admin Panel ships in its
-- client-side JS bundle by design (that's normal for Supabase's anon key —
-- RLS policies are what's supposed to restrict it, and these didn't). In
-- practice that meant anyone who found your Supabase URL + anon key could
-- read everything, rewrite your settings, or insert a fake "approved" video
-- row pointing at content of their choosing — which your own
-- publish_approved.py would then upload to YOUR authenticated YouTube
-- channel. You don't need a policy for service_role at all: Supabase's
-- service_role key bypasses RLS entirely by design, which is exactly why
-- the Python engine (which uses that key) doesn't need any of this.
-- ════════════════════════════════════════════════════════════════

-- ── Topics Table ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS topics (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name            TEXT NOT NULL,
    description     TEXT NOT NULL,
    custom_context  TEXT DEFAULT '',
    category        TEXT DEFAULT 'tech',
    render_style    TEXT,                        -- 'stock_footage' | 'whiteboard_sketch' | 'quote_card' | NULL (= use the global default)
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Tones Table ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tones (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name            TEXT NOT NULL,
    description     TEXT NOT NULL,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Settings Table ────────────────────────────────────────────────
-- Key-value store for pipeline configuration. These are now actually read
-- by the engine (see engine/orchestrator.py and engine/publish_approved.py)
-- — previously max_videos_daily, publish_per_run, and auto_approve existed
-- here and in the Admin Panel UI but nothing in the Python code ever read
-- them, so changing them from the dashboard silently did nothing.
CREATE TABLE IF NOT EXISTS settings (
    key             TEXT PRIMARY KEY,
    value           TEXT,
    description     TEXT,
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Videos Table ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS videos (
    id              BIGSERIAL PRIMARY KEY,
    job_id          TEXT UNIQUE NOT NULL,
    title           TEXT,
    description     TEXT,
    hashtags        JSONB DEFAULT '[]',
    duration        FLOAT,
    status          TEXT DEFAULT 'pending',      -- pending | approved | rejected | published | failed
    render_style    TEXT DEFAULT 'stock_footage',-- which visual style this video was rendered with
    storyboard      JSONB,
    storage_url     TEXT,
    srt_url         TEXT,
    youtube_id      TEXT,
    youtube_url     TEXT,
    error_log       TEXT,
    flags           JSONB,                       -- e.g. {"possible_duplicate": true, "similarity": 0.91, "similar_to": "..."}
    topic_id        UUID REFERENCES topics(id),
    tone_id         UUID REFERENCES tones(id),
    tone_name       TEXT,                        -- set for custom-prompt videos that have no tone_id row
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    approved_at     TIMESTAMPTZ,
    published_at    TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Default Settings ──────────────────────────────────────────────
INSERT INTO settings (key, value, description) VALUES
    ('voice_profile',        'documentary_male',  'TTS voice style: documentary_male | documentary_female | conversational | energetic | british_calm'),
    ('channel_name',         '',                   'Your YouTube channel @handle (shown as watermark)'),
    ('publish_per_run',      '1',                  'How many approved videos to publish per cron run (quota-aware — see docs/04)'),
    ('auto_approve',         'false',              'If true, new videos start as "approved" instead of "pending" — skips manual review. Off by default on purpose: with no other content-review safety net in this pipeline, this is the one that most directly affects YPP inauthentic-content risk.'),
    ('max_videos_daily',     '5',                  'Max videos to generate per run'),
    ('default_render_style', 'stock_footage',      'Fallback visual style (stock_footage | whiteboard_sketch | quote_card) for topics that do not set their own')
ON CONFLICT (key) DO NOTHING;

-- ── Default Topics ─────────────────────────────────────────────────
INSERT INTO topics (name, description, custom_context, category, render_style) VALUES
    (
        'Semiconductor Manufacturing',
        'How computer chips are designed and fabricated at the nanometer scale inside ultra-clean factory facilities called fabs.',
        'Focus on ASML EUV lithography, the mind-blowing precision, and scale comparisons to everyday objects.',
        'tech', NULL
    ),
    (
        'How Data Centers Work',
        'The physical infrastructure behind the internet — massive warehouses of servers that power every website, app, and cloud service.',
        'Include facts about power consumption, cooling systems, and the global scale of the internet.',
        'tech', NULL
    ),
    (
        'How the Internet Actually Works',
        'The technical reality of data packets, fiber optic cables, submarine cables, and the protocols that make global communication possible.',
        'Use vivid analogies. Example: a message from India to the US traveling through a cable at the bottom of the ocean.',
        'tech', 'whiteboard_sketch'
    ),
    (
        'How AI Language Models Work',
        'The simplified but accurate explanation of how neural networks like GPT and Gemini are trained to understand and generate text.',
        'Focus on transformers, attention mechanisms, and training data scale in terms non-engineers can grasp.',
        'tech', 'whiteboard_sketch'
    ),
    (
        'Supercomputer Engineering',
        'How the world''s fastest supercomputers are built, cooled, and used for scientific breakthroughs.',
        'Include specific machine names (Frontier, Fugaku), their real performance numbers, and what problems they solve.',
        'tech', NULL
    )
ON CONFLICT DO NOTHING;

-- ── Default Tones ──────────────────────────────────────────────────
INSERT INTO tones (name, description) VALUES
    (
        'Mind-Blowing Facts',
        'Astonishing, hyper-specific facts that make people say "I had no idea". Confident and punchy delivery. Use real numbers and scale comparisons.'
    ),
    (
        'Sarcastic Commentary',
        'Clever, dry humor that highlights absurd or ironic aspects of a topic. Witty, not mean. Makes viewers laugh and share.'
    ),
    (
        'Genuine Advice',
        'Specific, actionable insights framed as direct advice. Avoids generic platitudes. Feels like advice from a brilliant friend.'
    ),
    (
        'Short Story',
        'A vivid, brief narrative with a surprising twist or insight at the end. Sensory, specific, emotional. Shows rather than tells.'
    ),
    (
        'Documentary Narrator',
        'Calm, authoritative, cinematic tone. Builds tension and wonder. Similar to a nature documentary, applied to technology.'
    )
ON CONFLICT DO NOTHING;

-- ── Indexes ────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_videos_status ON videos(status);
CREATE INDEX IF NOT EXISTS idx_videos_created_at ON videos(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_videos_topic_id ON videos(topic_id);

-- ── Row Level Security (RLS) ───────────────────────────────────────
ALTER TABLE topics   ENABLE ROW LEVEL SECURITY;
ALTER TABLE tones    ENABLE ROW LEVEL SECURITY;
ALTER TABLE settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE videos   ENABLE ROW LEVEL SECURITY;

-- Only real, logged-in Admin Panel users (Supabase Auth) can read or write.
-- The anon role gets NOTHING (no policy = no access, which is the point).
-- The Python engine's service_role key bypasses RLS entirely and needs no
-- policy here at all — see the note at the top of this file.
CREATE POLICY "Authenticated users only" ON topics   FOR ALL USING (auth.role() = 'authenticated');
CREATE POLICY "Authenticated users only" ON tones    FOR ALL USING (auth.role() = 'authenticated');
CREATE POLICY "Authenticated users only" ON settings FOR ALL USING (auth.role() = 'authenticated');
CREATE POLICY "Authenticated users only" ON videos   FOR ALL USING (auth.role() = 'authenticated');
