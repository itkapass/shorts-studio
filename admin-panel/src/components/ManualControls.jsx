// src/components/ManualControls.jsx
//
// The "do it now" buttons — now with real targeting.
//
// WHY THIS EXISTS
// Every stage of this pipeline runs on a schedule, which is right for
// day-to-day operation and wrong for two very common situations:
//
//   1. You changed something and want to see the result NOW, not in
//      four hours.
//   2. Something failed and you want to retry it without waiting for
//      the next cron.
//
// The plain "Add Topics Now" / "Generate Video Now" buttons cover the quick
// case: one click, the same thing the schedule would have done anyway.
// "Customize" on each covers the deliberate case — a specific channel, a
// specific count, or (for generation) one exact topic picked from Topic
// Studio instead of whatever the pool would have shuffled up. This is the
// difference between "do the next scheduled thing now" and "do THIS thing,
// for THIS channel, right now instead of the next batch."
//
// Each button dispatches a real GitHub Actions run through the
// trigger-workflow edge function. Nothing runs in your browser — the
// browser only asks GitHub to start the same job the schedule would, with
// extra inputs when you've customized it.

import { useState, useEffect } from 'react'
import { supabase, getFunctionErrorMessage } from '../lib/supabase'
import { PERSONAS_ONLY } from '../lib/personas'
import {
  Lightbulb, Clapperboard, Send, Loader2, ExternalLink, AlertTriangle,
  CheckCircle2, Clock, Settings2, ChevronDown, ChevronUp, Zap,
} from 'lucide-react'

// Matches the actual cron schedules in .github/workflows/*.yml. Not fetched
// live — GitHub doesn't expose "when will this cron next fire" through any
// API, so the schedule is mirrored here. If you ever change a cron line in
// the workflow files, update the matching entry below too, or this countdown
// will confidently show the wrong time.
const SCHEDULES_UTC = {
  topics:   { hours: [7], minutes: 30 },                          // add-topics.yml
  generate: { hours: [8, 11, 14, 17, 20, 23], minutes: 0 },        // generate.yml
  publish:  { hours: Array.from({ length: 24 }, (_, h) => h), minutes: 7 }, // publish.yml, hourly
}

// Mirrors engine/api_budget.py's DEFAULT_DAILY_BUDGET. Settings can override
// this per-deployment (Settings -> Gemini Daily Budget), which this
// client-side estimate has no way to see — it's a helpful guide for sizing
// a request, not a promise, and is presented that way below.
const ASSUMED_DAILY_BUDGET = 20
const CALLS_PER_VIDEO = 2   // creative brief + storyboard
const CALLS_PER_TOPIC_BATCH = 1  // up to 20 topics per call, regardless of how many you ask for

function nextRunFor(schedule, now) {
  let best = null
  for (const h of schedule.hours) {
    const candidate = new Date(Date.UTC(
      now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(), h, schedule.minutes, 0
    ))
    if (candidate <= now) candidate.setUTCDate(candidate.getUTCDate() + 1)
    if (!best || candidate < best) best = candidate
  }
  return best
}

function formatCountdown(target, now) {
  const ms = target - now
  if (ms <= 0) return 'due now'
  const mins = Math.floor(ms / 60000)
  const h = Math.floor(mins / 60)
  const m = mins % 60
  return h > 0 ? `${h}h ${m}m` : `${m}m`
}

// The Gemini quota day is Pacific, not UTC — see engine/daycycle.py for why
// (Google's free tier resets at midnight Pacific; using UTC here would show
// a budget number that quietly disagrees with the one the backend actually
// uses, exactly the kind of two-copies-drifting bug this whole file exists
// to avoid elsewhere).
function pacificDateKey() {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/Los_Angeles', year: 'numeric', month: '2-digit', day: '2-digit',
  }).format(new Date()).replaceAll('-', '_')
}

const ACTIONS = [
  {
    id: 'topics',
    label: 'Add Topics Now',
    icon: Lightbulb,
    color: '#fbbf24',
    cost: '1 Gemini request per channel',
    time: '~1 min',
    blurb: 'Invents fresh topics for every enabled channel and saves them to Topic Studio. No video is made.',
    customizable: true,
  },
  {
    id: 'generate',
    label: 'Generate Video Now',
    icon: Clapperboard,
    color: '#845ef7',
    cost: '2 Gemini requests',
    time: '~8 min',
    blurb: 'Writes and renders one video, then puts it in your review queue. It will not publish on its own.',
    inputs: { manual_count: '1' },
    customizable: true,
  },
  {
    id: 'publish',
    label: 'Publish Next Approved',
    icon: Send,
    color: '#2dce89',
    cost: 'no Gemini cost',
    time: '~1 min',
    blurb: 'Uploads the next approved video that is due. Still respects each channel\u2019s spacing and daily cap.',
  },
]

export default function ManualControls({ compact = false }) {
  const [busy, setBusy] = useState(null)
  const [result, setResult] = useState(null)
  const [now, setNow] = useState(() => new Date())
  const [expanded, setExpanded] = useState(null)       // which action id is customizing, if any
  const [channelsMap, setChannelsMap] = useState([])    // [{persona_key, env_suffix, name}]

  // Per-action custom form state, keyed by action id so switching between
  // "Add Topics" and "Generate Video" doesn't bleed one's picks into the
  // other's form.
  const [form, setForm] = useState({
    topics:   { persona: '', count: '' },
    generate: { persona: '', count: '1', topicId: '' },
  })
  const [topicOptions, setTopicOptions] = useState([])
  const [loadingTopics, setLoadingTopics] = useState(false)
  const [budget, setBudget] = useState(null)            // { remaining, keyId } for the selected persona

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 30000)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    supabase.from('channels').select('persona_key, env_suffix, name')
      .then(({ data }) => setChannelsMap(data || []))
  }, [])

  // Refetch the topic list (for Generate's picker) whenever its persona
  // selection changes. Deliberately NOT filtered to "unused only" — if you
  // are picking a topic by hand, you may well want to deliberately remake
  // or retry a specific one, not just see what the automatic pool would
  // have offered.
  useEffect(() => {
    const persona = form.generate.persona
    if (!persona) { setTopicOptions([]); return }
    setLoadingTopics(true)
    supabase.from('topics').select('id, name')
      .eq('persona_key', persona).eq('is_active', true)
      .order('created_at', { ascending: false }).limit(50)
      .then(({ data }) => { setTopicOptions(data || []); setLoadingTopics(false) })
  }, [form.generate.persona])

  // Live quota readout for whichever persona is currently selected in
  // WHICHEVER form is expanded — this is the direct answer to "can the app
  // just tell me how many topics/videos I can afford to ask for right now."
  useEffect(() => {
    const persona = expanded ? form[expanded]?.persona : null
    if (!persona) { setBudget(null); return }
    const channel = channelsMap.find(c => c.persona_key === persona)
    const keyId = channel?.env_suffix || 'default'
    const settingKey = `api_calls_${keyId}_${pacificDateKey()}`
    supabase.from('settings').select('value').eq('key', settingKey).maybeSingle()
      .then(({ data }) => {
        const spent = data ? (parseInt(data.value, 10) || 0) : 0
        setBudget({ remaining: Math.max(0, ASSUMED_DAILY_BUDGET - spent), keyId })
      })
      .catch(() => setBudget(null))
  }, [expanded, form.topics.persona, form.generate.persona, channelsMap])

  function updateForm(actionId, patch) {
    setForm(prev => ({ ...prev, [actionId]: { ...prev[actionId], ...patch } }))
  }

  async function run(action, customInputs) {
    setBusy(action.id)
    setResult(null)
    const { data, error } = await supabase.functions.invoke('trigger-workflow', {
      body: { workflow: action.id, inputs: customInputs || action.inputs || {} },
    })
    setBusy(null)
    if (error || data?.error) {
      setResult({
        ok: false,
        message: await getFunctionErrorMessage(
          error, data,
          'Could not reach the trigger-workflow function. It may not be deployed yet — see docs/11.',
        ),
      })
      return
    }
    setResult({ ok: true, message: data.message, url: data.actions_url })
  }

  function runCustomTopics() {
    const { persona, count } = form.topics
    const inputs = {}
    if (persona) inputs.persona = persona
    if (count) inputs.count = String(count)
    run(ACTIONS[0], inputs)
  }

  function runCustomGenerate() {
    const { persona, count, topicId } = form.generate
    const inputs = {}
    if (topicId) {
      inputs.topic_id = topicId  // a specific topic implies exactly one video
    } else if (count) {
      inputs.manual_count = String(count)
    }
    if (persona && !topicId) inputs.persona = persona
    run(ACTIONS[1], inputs)
  }

  return (
    <div className="card" style={{ marginBottom: 20 }}>
      <div className="card-header">
        <span className="card-title">Run something now</span>
        <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
          Starts a real GitHub Actions run
        </span>
      </div>

      {!compact && (
        <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: '0 0 16px' }}>
          Everything here also happens automatically on a schedule. These buttons are for when
          you do not want to wait — testing a change, retrying after a failure, or asking for a
          specific channel or topic instead of whatever the next batch would pick.
        </p>
      )}

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
        gap: 12,
        alignItems: 'start',
      }}>
        {ACTIONS.map(action => {
          const Icon = action.icon
          const isBusy = busy === action.id
          const isExpanded = expanded === action.id
          return (
            <div key={action.id}>
              <button
                onClick={() => run(action)}
                disabled={busy !== null}
                className="manual-action-btn"
                style={{ opacity: busy && !isBusy ? 0.5 : 1 }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                  {isBusy
                    ? <Loader2 size={16} color={action.color} className="spin" />
                    : <Icon size={16} color={action.color} />}
                  <span style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--text-primary)' }}>
                    {isBusy ? 'Starting\u2026' : action.label}
                  </span>
                </div>
                <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', lineHeight: 1.45 }}>
                  {action.blurb}
                </div>
                <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginTop: 8, opacity: 0.8 }}>
                  {action.time} · {action.cost}
                </div>
                {SCHEDULES_UTC[action.id] && (
                  <div style={{
                    fontSize: '0.68rem', color: 'var(--text-muted)', marginTop: 4,
                    display: 'flex', alignItems: 'center', gap: 4, opacity: 0.7,
                  }}>
                    <Clock size={11} />
                    next auto-run in {formatCountdown(nextRunFor(SCHEDULES_UTC[action.id], now), now)}
                  </div>
                )}
              </button>

              {action.customizable && (
                <button
                  onClick={() => setExpanded(isExpanded ? null : action.id)}
                  style={{
                    all: 'unset', display: 'flex', alignItems: 'center', gap: 4,
                    fontSize: '0.7rem', color: 'var(--text-muted)', cursor: 'pointer',
                    marginTop: 6, padding: '2px 4px',
                  }}
                >
                  <Settings2 size={11} />
                  Customize (channel, count{action.id === 'generate' ? ', specific topic' : ''})
                  {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                </button>
              )}

              {isExpanded && action.id === 'topics' && (
                <CustomPanel>
                  <FieldLabel>Channel</FieldLabel>
                  <select
                    className="form-input" style={selectStyle}
                    value={form.topics.persona}
                    onChange={e => updateForm('topics', { persona: e.target.value })}
                  >
                    <option value="">All enabled channels (normal top-up)</option>
                    {PERSONAS_ONLY.map(([key, label]) => (
                      <option key={key} value={key}>{label}</option>
                    ))}
                  </select>

                  {form.topics.persona && (
                    <>
                      <FieldLabel>How many (max 20)</FieldLabel>
                      <input
                        type="number" min="1" max="20" className="form-input" style={selectStyle}
                        placeholder="15 (default)"
                        value={form.topics.count}
                        onChange={e => updateForm('topics', { count: e.target.value })}
                      />
                    </>
                  )}

                  <BudgetHint budget={budget} kind="topics" persona={form.topics.persona} />

                  <RunButton onClick={runCustomTopics} disabled={busy !== null} busy={busy === 'topics'} />
                </CustomPanel>
              )}

              {isExpanded && action.id === 'generate' && (
                <CustomPanel>
                  <FieldLabel>Channel</FieldLabel>
                  <select
                    className="form-input" style={selectStyle}
                    value={form.generate.persona}
                    onChange={e => updateForm('generate', { persona: e.target.value, topicId: '' })}
                  >
                    <option value="">Any channel (normal pool selection)</option>
                    {PERSONAS_ONLY.map(([key, label]) => (
                      <option key={key} value={key}>{label}</option>
                    ))}
                  </select>

                  {!form.generate.topicId && (
                    <>
                      <FieldLabel>How many videos</FieldLabel>
                      <input
                        type="number" min="1" max="10" className="form-input" style={selectStyle}
                        value={form.generate.count}
                        onChange={e => updateForm('generate', { count: e.target.value })}
                      />
                    </>
                  )}

                  {form.generate.persona && (
                    <>
                      <FieldLabel>
                        Specific topic (optional — overrides the count above to exactly 1)
                      </FieldLabel>
                      <select
                        className="form-input" style={selectStyle}
                        value={form.generate.topicId}
                        onChange={e => updateForm('generate', { topicId: e.target.value })}
                      >
                        <option value="">Let the pool pick one</option>
                        {loadingTopics && <option disabled>Loading topics…</option>}
                        {topicOptions.map(t => (
                          <option key={t.id} value={t.id}>{t.name}</option>
                        ))}
                      </select>
                      {!loadingTopics && form.generate.persona && topicOptions.length === 0 && (
                        <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginTop: 2 }}>
                          No topics for this channel yet — try "Add Topics Now" first.
                        </div>
                      )}
                    </>
                  )}

                  <BudgetHint budget={budget} kind="generate" persona={form.generate.persona} />

                  <RunButton onClick={runCustomGenerate} disabled={busy !== null} busy={busy === 'generate'} />
                </CustomPanel>
              )}
            </div>
          )
        })}
      </div>

      {result && (
        <div style={{
          marginTop: 14,
          padding: '10px 12px',
          borderRadius: 6,
          fontSize: '0.78rem',
          display: 'flex',
          gap: 8,
          alignItems: 'flex-start',
          background: result.ok ? 'rgba(45, 206, 137, 0.12)' : 'rgba(239, 68, 68, 0.12)',
          color: result.ok ? 'var(--accent-green)' : '#f87171',
        }}>
          {result.ok ? <AlertTriangleOrCheck ok /> : <AlertTriangle size={15} style={{ flexShrink: 0, marginTop: 2 }} />}
          <div>
            {result.message}
            {result.url && (
              <>
                {' '}
                <a href={result.url} target="_blank" rel="noreferrer"
                   style={{ color: 'inherit', textDecoration: 'underline' }}>
                  Watch it run <ExternalLink size={11} style={{ display: 'inline' }} />
                </a>
                <div style={{ opacity: 0.75, marginTop: 4 }}>
                  It takes a few seconds to appear in the Actions list.
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

const selectStyle = { fontSize: '0.78rem', padding: '6px 8px', marginBottom: 8, width: '100%' }

function FieldLabel({ children }) {
  return (
    <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginBottom: 3, marginTop: 6 }}>
      {children}
    </div>
  )
}

function CustomPanel({ children }) {
  return (
    <div style={{
      marginTop: 8, padding: 10, borderRadius: 8,
      background: 'var(--bg-elevated)', border: '1px dashed var(--border)',
    }}>
      {children}
    </div>
  )
}

function RunButton({ onClick, disabled, busy }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="btn btn-primary btn-sm"
      style={{ width: '100%', marginTop: 6, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}
    >
      {busy ? <Loader2 size={13} className="spin" /> : <Zap size={13} />}
      {busy ? 'Starting…' : 'Run with these options'}
    </button>
  )
}

// Translates a raw "requests remaining" number into a plain-language sizing
// hint. Deliberately hedged ("roughly," "up to") — this reads a snapshot of
// a counter that can change the moment another workflow run fires, and a
// per-deployment daily budget override in Settings isn't visible from here.
// A helpful estimate, not a promise.
function BudgetHint({ budget, kind, persona }) {
  if (!persona) return null
  if (!budget) {
    return (
      <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginTop: 4, opacity: 0.7 }}>
        Checking today's Gemini quota for this channel…
      </div>
    )
  }
  const { remaining, keyId } = budget
  const affordable = kind === 'generate'
    ? Math.floor(remaining / CALLS_PER_VIDEO)
    : Math.floor(remaining / CALLS_PER_TOPIC_BATCH)
  const unit = kind === 'generate' ? (affordable === 1 ? 'video' : 'videos') : 'more batch(es) of up to 20 topics'
  return (
    <div style={{
      fontSize: '0.68rem', marginTop: 4, marginBottom: 2,
      color: remaining === 0 ? '#f87171' : 'var(--text-muted)',
    }}>
      {remaining === 0
        ? `This channel's key ('${keyId}') shows 0 Gemini requests left today — a Groq backup will be used if one is configured.`
        : `\u2248 ${remaining} Gemini request(s) left today on '${keyId}' \u2014 roughly ${affordable} ${unit}.`}
    </div>
  )
}

function AlertTriangleOrCheck({ ok }) {
  return ok
    ? <CheckCircle2 size={15} style={{ flexShrink: 0, marginTop: 2 }} />
    : <AlertTriangle size={15} style={{ flexShrink: 0, marginTop: 2 }} />
}
