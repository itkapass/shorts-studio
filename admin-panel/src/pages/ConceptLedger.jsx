// src/pages/ConceptLedger.jsx
//
// Two jobs on one page, because they are two halves of the same idea:
//
//   1. WHAT'S BEEN USED — every concept already published, so nothing gets
//      made twice. This is the readable view of the same ledger the generator
//      reads before writing anything.
//
//   2. ADD A TOPIC — drop in a subject, or paste a link to a video/article
//      whose angle you want covered. This is the "a new kind of content just
//      appeared, get on it today" path, without waiting for a code change.
//
// ON PASTED LINKS: the URL is stored as context for the writer, not scraped
// and not reproduced. The generator is told to write something ORIGINAL in
// that territory. Re-voicing someone else's video is a copyright problem and
// exactly the reused-content pattern that gets channels demonetised, so the
// prompt is explicit about the difference.

import { useEffect, useState } from 'react'
import { Plus, Search, Link2, Trash2, BookOpen } from 'lucide-react'
import { supabase, isSupabaseConfigured } from '../lib/supabase'

const ARCHETYPES = [
  ['', 'Rotate automatically (recommended)'],
  ['informative', 'Unknown Facts'],
  ['myth_busting', 'Myth vs Fact'],
  ['life_hack', 'Daily Hacks'],
  ['relatable', 'Relatable'],
  ['wholesome', 'Wholesome'],
  ['empathy', 'Social & Human'],
  ['dark_humour', 'Dark Humour'],
  ['sarcasm', 'Sarcasm'],
  ['absurd', 'Absurd'],
  ['observational', 'Observational'],
]

export default function ConceptLedger() {
  const [concepts, setConcepts] = useState([])
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [form, setForm] = useState({ name: '', description: '', source_url: '', archetype: '' })
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState('')

  useEffect(() => { load() }, [])

  async function load() {
    if (!isSupabaseConfigured) { setLoading(false); return }
    setLoading(true)
    const { data } = await supabase
      .from('concepts').select('*').order('created_at', { ascending: false }).limit(300)
    setConcepts(data || [])
    setLoading(false)
  }

  async function addTopic() {
    if (!form.name.trim()) return
    setSaving(true); setMsg('')
    const { error } = await supabase.from('topics').insert({
      name: form.name.trim(),
      description: form.description.trim(),
      custom_context: form.source_url
        ? `Reference for the SUBJECT AREA only: ${form.source_url}\n` +
          `Write something entirely original about this territory. Do not summarise, ` +
          `re-voice, or closely follow the referenced video's script or structure.`
        : '',
      source_url: form.source_url.trim() || null,
      archetype: form.archetype || null,
      is_active: true,
      added_by: 'manual',
    })
    setSaving(false)
    if (error) { setMsg(error.message); return }
    setMsg('Topic added. It enters the rotation on the next generation run.')
    setForm({ name: '', description: '', source_url: '', archetype: '' })
    setShowAdd(false)
  }

  async function forget(id) {
    if (!confirm('Remove this concept from the ledger? The same idea could then be generated again.')) return
    await supabase.from('concepts').delete().eq('id', id)
    load()
  }

  const filtered = concepts.filter(c =>
    !query ||
    (c.title || '').toLowerCase().includes(query.toLowerCase()) ||
    (c.keywords || []).join(' ').toLowerCase().includes(query.toLowerCase())
  )

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>Concept Ledger</h1>
          <p className="muted">
            Every idea already used. The writer reads this before every video so nothing
            repeats.
          </p>
        </div>
        <button className="btn primary" onClick={() => setShowAdd(true)}>
          <Plus size={16} /> Add a topic
        </button>
      </header>

      {msg && <div className="alert info">{msg}</div>}

      {showAdd && (
        <div className="modal-backdrop" onClick={() => setShowAdd(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h2>Add a topic</h2>
            <p className="hint">
              For when something new shows up and you want videos on it today.
            </p>

            <label>Topic
              <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })}
                     placeholder="Deep sea creatures" />
            </label>

            <label>What angle interests you <span className="muted">(optional)</span>
              <textarea rows={3} value={form.description}
                        onChange={e => setForm({ ...form, description: e.target.value })}
                        placeholder="Focus on how they survive the pressure, not on how they look." />
            </label>

            <label><Link2 size={14} /> Reference link <span className="muted">(optional)</span>
              <input value={form.source_url}
                     onChange={e => setForm({ ...form, source_url: e.target.value })}
                     placeholder="https://www.youtube.com/shorts/…" />
            </label>
            <p className="hint">
              Used only to point the writer at the subject area. It writes something
              original in that territory — it does not summarise or re-voice the linked
              video. Copying another creator's script is a copyright problem and is the
              fastest way to get a channel flagged for reused content.
            </p>

            <label>Force a format
              <select value={form.archetype}
                      onChange={e => setForm({ ...form, archetype: e.target.value })}>
                {ARCHETYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </label>
            <p className="hint">
              Leave on rotate unless this topic only works one way. A channel that posts a
              single format every day gets stale quickly.
            </p>

            <div className="modal-actions">
              <button className="btn" onClick={() => setShowAdd(false)}>Cancel</button>
              <button className="btn primary" disabled={saving || !form.name.trim()}
                      onClick={addTopic}>
                {saving ? 'Adding…' : 'Add topic'}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="toolbar">
        <div className="search">
          <Search size={15} />
          <input value={query} onChange={e => setQuery(e.target.value)}
                 placeholder="Search used concepts…" />
        </div>
        <span className="muted small">{filtered.length} of {concepts.length}</span>
      </div>

      {loading ? <p className="muted">Loading…</p> : filtered.length === 0 ? (
        <div className="empty">
          <BookOpen size={28} />
          <p>Nothing here yet. Concepts are recorded when a video is published.</p>
        </div>
      ) : (
        <ul className="ledger">
          {filtered.map(c => (
            <li key={c.id}>
              <div>
                <strong>{c.title}</strong>
                {c.archetype && <span className="chip sm">{c.archetype}</span>}
                <p className="muted small">{c.premise}</p>
                <div className="chip-row">
                  {(c.keywords || []).slice(0, 8).map(k => (
                    <span key={k} className="chip xs">{k}</span>
                  ))}
                </div>
              </div>
              <button className="btn sm danger" title="Allow this idea to be used again"
                      onClick={() => forget(c.id)}>
                <Trash2 size={14} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
