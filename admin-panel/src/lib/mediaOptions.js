// src/lib/mediaOptions.js
//
// Voice and render-style options for the Channels page's "these related
// voices/videos for this channel" controls (voice_override,
// render_style_override). Mirrors engine/voice_engine.py's VOICE_PROFILES
// and engine/styles/STYLES — kept here as ONE shared list for the same
// reason lib/personas.js exists: a second hand-copied list is exactly how
// the Tamil-persona dropdown bug happened before. If either list changes
// on the backend, update here too — there's only one place to remember now.

export const VOICES = [
  ['', 'Use the channel\u2019s persona default'],
  ['documentary_male', 'Documentary — male (Guy)'],
  ['documentary_female', 'Documentary — female (Jenny)'],
  ['conversational', 'Conversational — male (Andrew)'],
  ['energetic', 'Energetic — male (Christopher)'],
  ['british_calm', 'Calm — British male (Ryan)'],
  ['warm_female', 'Warm — female (Aria)'],
  ['young_casual', 'Casual — female (Ana)'],
]

export const RENDER_STYLES = [
  ['', 'Use the persona/archetype default'],
  ['stock_footage', 'Stock Footage — real b-roll with a Ken Burns zoom'],
  ['whiteboard_sketch', 'Whiteboard Sketch — hand-drawn diagram, builds scene by scene'],
  ['character_skit', 'Character Skit — animated 2D characters'],
  ['quote_card', 'Quote Card — minimal text-forward card'],
]
