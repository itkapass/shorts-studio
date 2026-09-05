// src/lib/personas.js
//
// The one place this list is allowed to live.
//
// WHY THIS FILE EXISTS
// This used to be defined directly inside ChannelsPage.jsx. It is a
// hand-copied mirror of engine/personas.py's PERSONAS dict — nothing
// enforces the two staying in sync, because the frontend has no way to
// import Python at build time. That already caused a real bug: when
// `quotes_and_poetry` (the Tamil channel) was added on the backend, this
// copy was never updated, so it was completely unselectable in the
// dashboard with no error anywhere — just one option that could never
// appear.
//
// That bug can still happen again on the Python side (a 9th persona added
// to engine/personas.py without updating this file) — tools/selfcheck.py
// guards against that by comparing the two. What this file fixes is the
// OTHER way the same bug could happen: a second hand-copied list inside
// ManualControls.jsx quietly drifting from the one inside ChannelsPage.jsx.
// One shared file, imported by both, makes that specific failure mode
// structurally impossible instead of just checked-for.
//
// If you add a 9th persona to engine/personas.py, add it HERE too — that
// is still a manual step, but now it's exactly one manual step, not two.

export const PERSONAS = [
  ['', 'None — pick categories manually below'],
  ['tech_science_explainer', 'Tech, Science & How Things Work'],
  ['comedy_skits', 'Comedy, Dark Humour & Life Sketches'],
  ['top10_and_facts', 'Top 10s, Records & Strange True Things'],
  ['motivation_and_discipline', 'Motivation, Discipline & Wellbeing'],
  ['what_if_physics', 'What If — Real Science, Absurd Questions'],
  ['awareness_comedy', 'Awareness Through Comedy'],
  ['everyday_origins', 'Why Ordinary Things Are The Way They Are'],
  ['quotes_and_poetry', 'Tamil Words, Wisdom & Original Lines'],
]

// Personas only (no blank "None" entry) — for pickers where "not selecting
// a persona" and "explicitly wanting all/none" are meaningfully different
// choices, e.g. a "which channel" dropdown for a manual action.
export const PERSONAS_ONLY = PERSONAS.filter(([key]) => key)

export const PERSONAS_META = {
  tech_science_explainer: {
    categories: ['informative', 'myth_busting', 'life_hack'],
    description: 'Explains one real tech, science, or how-things-work concept per video.',
  },
  comedy_skits: {
    categories: ['dark_humour', 'sarcasm', 'absurd', 'observational', 'relatable'],
    description: 'Animated character skits about ordinary life — work, relationships, group chats.',
  },
  top10_and_facts: {
    categories: ['informative', 'myth_busting'],
    description: 'Rankings, records, and strange true facts people actually trade at 3am.',
  },
  motivation_and_discipline: {
    categories: ['informative', 'wholesome', 'life_hack'],
    description: 'Discipline, training and wellbeing, grounded in a real mechanism, never a flat quote card.',
  },
  what_if_physics: {
    categories: ['informative', 'absurd', 'myth_busting'],
    description: 'Absurd hypotheticals answered with real science — the question hooks, the true answer pays off.',
  },
  awareness_comedy: {
    categories: ['sarcasm', 'absurd', 'observational', 'myth_busting'],
    description: 'Climate, population and resources landed through comedy instead of lecturing.',
  },
  everyday_origins: {
    categories: ['informative', 'myth_busting', 'life_hack'],
    description: 'Why ordinary objects are the way they are. Effectively inexhaustible.',
  },
  quotes_and_poetry: {
    categories: ['informative', 'wholesome', 'myth_busting', 'life_hack'],
    description: 'Tamil proverbs, tongue twisters, folk sayings and slang alongside original '
      + 'aphorisms and short poems — real strands must be genuinely real, original ones genuinely new.',
  },
}
