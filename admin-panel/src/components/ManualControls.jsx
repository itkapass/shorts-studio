// src/components/ManualControls.jsx
//
// The "do it now" buttons.
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
// Before this, "run it now" meant leaving the dashboard, opening the
// GitHub Actions tab, finding the right workflow in a list of seven, and
// pressing "Run workflow" inside a dropdown. That is a lot of steps to
// remember for something you do several times a week.
//
// Each button dispatches a real GitHub Actions run through the
// trigger-workflow edge function. Nothing runs in your browser — the
// browser only asks GitHub to start the same job the schedule would.

import { useState } from 'react'
import { supabase, getFunctionErrorMessage } from '../lib/supabase'
import { Lightbulb, Clapperboard, Send, Loader2, ExternalLink, AlertTriangle, CheckCircle2 } from 'lucide-react'

const ACTIONS = [
  {
    id: 'topics',
    label: 'Add Topics Now',
    icon: Lightbulb,
    color: '#fbbf24',
    cost: '1 Gemini request per channel',
    time: '~1 min',
    blurb: 'Invents fresh topics for every enabled channel and saves them to Topic Studio. No video is made.',
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

  async function run(action) {
    setBusy(action.id)
    setResult(null)
    const { data, error } = await supabase.functions.invoke('trigger-workflow', {
      body: { workflow: action.id, inputs: action.inputs || {} },
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
          you do not want to wait — testing a change, or retrying after a failure.
        </p>
      )}

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: 12,
      }}>
        {ACTIONS.map(action => {
          const Icon = action.icon
          const isBusy = busy === action.id
          return (
            <button
              key={action.id}
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
            </button>
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

function AlertTriangleOrCheck({ ok }) {
  return ok
    ? <CheckCircle2 size={15} style={{ flexShrink: 0, marginTop: 2 }} />
    : <AlertTriangle size={15} style={{ flexShrink: 0, marginTop: 2 }} />
}
