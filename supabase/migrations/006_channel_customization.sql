-- ============================================================================
-- 006_channel_customization.sql
-- (multiple personas per channel, plus per-channel voice/render-style overrides)
--
-- Safe to run more than once. Applies automatically if you followed docs/14,
-- otherwise paste into the Supabase SQL Editor once.
-- ============================================================================

-- A channel used to accept exactly one persona (persona_key). That was a
-- real limitation for a channel meant to be broad by design — "explain
-- something new" naturally spans tech_science_explainer, top10_and_facts,
-- and everyday_origins at once, not just one of them.
--
-- persona_key is UNTOUCHED — still the "primary" persona, still what a
-- brand-new channel gets from the ordinary dropdown. This column is purely
-- additive: extra personas on top, empty by default, so a channel that
-- never sets it behaves exactly as it did before this migration.
ALTER TABLE channels ADD COLUMN IF NOT EXISTS additional_persona_keys TEXT[] DEFAULT '{}';

-- Per-channel voice and render-style overrides — "these related voices for
-- this channel, these kind of videos for this channel." Both optional; a
-- channel that leaves them blank behaves exactly as before, falling
-- through to its persona's own preference, then the global Settings
-- default (see the resolution order in engine/orchestrator.py).
ALTER TABLE channels ADD COLUMN IF NOT EXISTS voice_override TEXT;
ALTER TABLE channels ADD COLUMN IF NOT EXISTS render_style_override TEXT;

-- Nothing else in this migration. Reversible:
--   ALTER TABLE channels DROP COLUMN IF EXISTS additional_persona_keys;
--   ALTER TABLE channels DROP COLUMN IF EXISTS voice_override;
--   ALTER TABLE channels DROP COLUMN IF EXISTS render_style_override;
