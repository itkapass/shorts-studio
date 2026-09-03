// src/pages/ChannelsPage.jsx
//
// Manage YouTube channels and which content categories route to each one.
//
// DESIGN NOTE — NO CREDENTIALS ARE ENTERED HERE, ON PURPOSE.
// A channel row stores the SUFFIX of the environment variables that hold its
// OAuth secrets, never the secrets themselves. Those live only in GitHub
// Secrets. This page is served over the public internet from Vercel, so any
// credential typed into it would be one XSS or one misconfigured RLS policy
// away from being someone else's. Storing a variable NAME has no such risk.
//
// QUOTA NOTE shown in the UI: YouTube's 10,000-unit daily budget is per Google
// Cloud PROJECT, not per channel, and each upload costs 1,600 units. Five
// channels sharing one project share 6 uploads/day between them. Each channel
// needs its own project to get its own budget — that is what env_suffix is for.

import { useEffect, useState } from 'react'
import { Plus, Trash2, Save, AlertTriangle, Radio, Hand } from 'lucide-react'
import { supabase, isSupabaseConfigured } from '../lib/supabase'

const CATEGORIES = [
  { key: 'informative',   label: 'Unknown Facts' },
  { key: 'myth_busting',  label: 'Myth vs Fact' },
  { key: 'life_hack',     label: 'Daily Hacks' },
  { key: 'relatable',     label: 'Relatable' },
  { key: 'wholesome',     label: 'Wholesome' },
  { key: 'empathy',       label: 'Social & Human' },
  { key: 'dark_humour',   label: 'Dark Humour' },
  { key: 'sarcasm',       label: 'Sarcasm' },
  { key: 'absurd',        label: 'Absurd' },
  { key: 'observational', label: 'Observational' },
]

const PERSONAS = [
  ['', 'None — pick categories manually below'],
  ['tech_science_explainer', 'Tech, Science & How Things Work'],
  ['comedy_skits', 'Comedy, Dark Humour & Life Sketches'],
  ['top10_and_facts', 'Top 10s, Records & Strange True Things'],
  ['motivation_and_discipline', 'Motivation, Discipline & Wellbeing'],
  ['what_if_physics', 'What If — Real Science, Absurd Questions'],
  ['awareness_comedy', 'Awareness Through Comedy'],
  ['everyday_origins', 'Why Ordinary Things Are The Way They Are'],
]

const PERSONAS_META = {
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
}

const BLANK = {
  name: '', handle: '', persona_key: '', categories: [], publish_mode: 'manual',
  env_suffix: '', daily_cap: 5, priority: 100, is_catchall: false,
  is_enabled: true, notes: '',
}

export default function ChannelsPage() {
  const [channels, setChannels] = useState([])
  const [loading, setLoading] = useState(true)
  const [draft, setDraft] = useState(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => { load() }, [])

  async function load() {
    if (!isSupabaseConfigured) { setLoading(false); return }
    setLoading(true)
    const { data, error } = await supabase.from('channels').select('*').order('priority')
    if (error) setError(error.message)
    setChannels(data || [])
    setLoading(false)
  }

  async function save(channel) {
    setSaving(true); setError('')
    const payload = { ...channel }
    delete payload.created_at
    const { error } = channel.id
      ? await supabase.from('channels').update(payload).eq('id', channel.id)
      : await supabase.from('channels').insert(payload)
    if (error) setError(error.message)
    setSaving(false); setDraft(null); load()
  }

  async function remove(id) {
    if (!confirm('Delete this channel? Videos already published to it are unaffected.')) return
    await supabase.from('channels').delete().eq('id', id)
    load()
  }

  function toggleCategory(channel, key, setter) {
    const has = (channel.categories || []).includes(key)
    setter({
      ...channel,
      categories: has
        ? channel.categories.filter(c => c !== key)
        : [...(channel.categories || []), key],
    })
  }

  const autoChannels = channels.filter(c => c.publish_mode === 'auto' && c.is_enabled)
  const suffixes = new Set(autoChannels.map(c => (c.env_suffix || '').trim()))
  const sharedProject = autoChannels.length > 1 && suffixes.size < autoChannels.length

  if (!isSupabaseConfigured) {
    return <div className="page"><h1>Channels</h1>
      <p className="muted">Connect Supabase to manage channels.</p></div>
  }

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>Channels</h1>
          <p className="muted">
            Where each kind of video gets posted. Add as many channels as you want.
          </p>
        </div>
        <button className="btn primary" onClick={() => setDraft({ ...BLANK })}>
          <Plus size={16} /> Add channel
        </button>
      </header>

      {error && <div className="alert error">{error}</div>}

      {sharedProject && (
        <div className="alert warn">
          <AlertTriangle size={16} />
          <div>
            <strong>Two auto-publish channels share the same credentials.</strong>
            <p>
              YouTube's daily upload budget is per Google Cloud project, not per channel.
              Channels sharing one project share about 6 uploads a day between them.
              Give each channel its own project and its own environment-variable suffix
              to get a full budget each. See docs/07 section 5.
            </p>
          </div>
        </div>
      )}

      {loading ? <p className="muted">Loading…</p> : (
        <div className="card-grid">
          {channels.map(ch => (
            <ChannelCard
              key={ch.id}
              channel={ch}
              onEdit={() => setDraft({ ...ch })}
              onDelete={() => remove(ch.id)}
            />
          ))}
          {channels.length === 0 && (
            <p className="muted">No channels yet. Add one to start routing videos.</p>
          )}
        </div>
      )}

      {draft && (
        <div className="modal-backdrop" onClick={() => setDraft(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h2>{draft.id ? 'Edit channel' : 'New channel'}</h2>

            <label>Content persona <span className="muted">(optional — picks your channel's whole domain)</span>
              <select value={draft.persona_key || ''}
                      onChange={e => {
                        const key = e.target.value
                        const preset = PERSONAS_META[key]
                        setDraft({
                          ...draft,
                          persona_key: key,
                          // Auto-fill categories from the persona's preferred
                          // formats so the routing "just works" — still
                          // editable afterwards if you want something narrower.
                          categories: preset ? preset.categories : draft.categories,
                        })
                      }}>
                {PERSONAS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </label>
            {draft.persona_key && PERSONAS_META[draft.persona_key] && (
              <p className="hint">
                {PERSONAS_META[draft.persona_key].description} The app will keep inventing new,
                specific topics inside this domain on its own as its topic pool runs low — you
                do not need to type them in one at a time.
              </p>
            )}

            <label>Channel name
              <input value={draft.name}
                     onChange={e => setDraft({ ...draft, name: e.target.value })}
                     placeholder="Science Shorts" />
            </label>

            <label>Handle <span className="muted">(optional)</span>
              <input value={draft.handle || ''}
                     onChange={e => setDraft({ ...draft, handle: e.target.value })}
                     placeholder="@scienceshorts" />
            </label>

            <label>Publishing
              <select value={draft.publish_mode}
                      onChange={e => setDraft({ ...draft, publish_mode: e.target.value })}>
                <option value="manual">Manual — package it and I'll post it myself</option>
                <option value="auto">Automatic — publish straight to YouTube</option>
              </select>
            </label>

            {draft.publish_mode === 'auto' && (
              <>
                <label>Secret name suffix
                  <input value={draft.env_suffix || ''}
                         onChange={e => setDraft({
                           ...draft,
                           env_suffix: e.target.value.toUpperCase().replace(/[^A-Z0-9_]/g, ''),
                         })}
                         placeholder="SCIENCE" />
                </label>
                <p className="hint">
                  This channel will read its credentials from{' '}
                  <code>YOUTUBE_CLIENT_ID{draft.env_suffix ? '_' + draft.env_suffix : ''}</code>,{' '}
                  <code>YOUTUBE_CLIENT_SECRET{draft.env_suffix ? '_' + draft.env_suffix : ''}</code>{' '}
                  and{' '}
                  <code>YOUTUBE_REFRESH_TOKEN{draft.env_suffix ? '_' + draft.env_suffix : ''}</code>{' '}
                  in GitHub Secrets. Leave the suffix empty to use the unsuffixed names.
                  Credentials are never stored in this database.
                </p>

                <label>Uploads per day
                  <input type="number" min="1" max="6" value={draft.daily_cap}
                         onChange={e => setDraft({ ...draft, daily_cap: Number(e.target.value) })} />
                </label>
                <p className="hint">
                  Keep this at 5 or below. YouTube allows 10,000 API units per project per
                  day and each upload costs 1,600, so 6 is the hard ceiling — 5 leaves room
                  for a retry.
                </p>
              </>
            )}

            <fieldset>
              <legend>Content categories this channel accepts</legend>
              <div className="chip-grid">
                {CATEGORIES.map(c => (
                  <button key={c.key} type="button"
                          className={`chip${(draft.categories || []).includes(c.key) ? ' on' : ''}`}
                          onClick={() => toggleCategory(draft, c.key, setDraft)}>
                    {c.label}
                  </button>
                ))}
              </div>
            </fieldset>

            <label className="row">
              <input type="checkbox" checked={!!draft.is_catchall}
                     onChange={e => setDraft({ ...draft, is_catchall: e.target.checked })} />
              Catch-all — also receive videos no other channel claimed
            </label>

            <label className="row">
              <input type="checkbox" checked={!!draft.is_enabled}
                     onChange={e => setDraft({ ...draft, is_enabled: e.target.checked })} />
              Enabled
            </label>

            <div className="modal-actions">
              <button className="btn" onClick={() => setDraft(null)}>Cancel</button>
              <button className="btn primary" disabled={saving || !draft.name}
                      onClick={() => save(draft)}>
                <Save size={16} /> {saving ? 'Saving…' : 'Save channel'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function ChannelCard({ channel, onEdit, onDelete }) {
  const auto = channel.publish_mode === 'auto'
  return (
    <div className={`card${channel.is_enabled ? '' : ' dim'}`}>
      <div className="card-head">
        <h3>{channel.name}</h3>
        <span className={`pill ${auto ? 'pill-green' : 'pill-amber'}`}>
          {auto ? <Radio size={12} /> : <Hand size={12} />} {auto ? 'Auto' : 'Manual'}
        </span>
      </div>
      {channel.handle && <p className="muted">{channel.handle}</p>}
      <div className="chip-row">
        {(channel.categories || []).map(c => (
          <span key={c} className="chip sm on">
            {CATEGORIES.find(x => x.key === c)?.label || c}
          </span>
        ))}
        {channel.is_catchall && <span className="chip sm">catch-all</span>}
      </div>
      <p className="muted small">
        {auto ? `Up to ${channel.daily_cap}/day` : 'Packaged for manual posting'}
        {channel.env_suffix ? ` · secrets: *_${channel.env_suffix}` : ''}
      </p>
      <div className="card-actions">
        <button className="btn sm" onClick={onEdit}>Edit</button>
        <button className="btn sm danger" onClick={onDelete}><Trash2 size={14} /></button>
      </div>
    </div>
  )
}
