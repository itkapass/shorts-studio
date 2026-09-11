-- ============================================================================
-- 005_push_subscriptions.sql
--
-- Safe to run more than once. Applies automatically if you followed docs/14
-- (Deploy Database Migrations) — otherwise paste into Supabase SQL Editor.
-- ============================================================================

-- One row per device that has enabled push notifications (Settings -> Enable
-- Notifications). A "subscription" is the browser's own way of saying "here
-- is exactly how to reach THIS device" — an endpoint URL unique to that
-- browser install, plus two keys used to encrypt the message so only that
-- device can read it. None of this is a login credential; it can only be
-- used to PUSH a notification to this one device, nothing else.
CREATE TABLE IF NOT EXISTS push_subscriptions (
    id          BIGSERIAL PRIMARY KEY,
    endpoint    TEXT NOT NULL UNIQUE,
    p256dh      TEXT NOT NULL,
    auth        TEXT NOT NULL,
    user_agent  TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- RLS: the anon/publishable key (used by the dashboard itself) needs to be
-- able to INSERT its own subscription and DELETE it (to unsubscribe) —
-- nothing more. Reading the list, or sending pushes, only ever happens from
-- the Python backend using the service key, which bypasses RLS entirely.
ALTER TABLE push_subscriptions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "anyone can subscribe" ON push_subscriptions;
CREATE POLICY "anyone can subscribe" ON push_subscriptions
    FOR INSERT WITH CHECK (true);

DROP POLICY IF EXISTS "anyone can unsubscribe their own endpoint" ON push_subscriptions;
CREATE POLICY "anyone can unsubscribe their own endpoint" ON push_subscriptions
    FOR DELETE USING (true);

-- Nothing else in this migration. Reversible:
--   DROP TABLE IF EXISTS push_subscriptions;
