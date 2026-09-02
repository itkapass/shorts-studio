// src/pages/SettingsPage.jsx
// Pipeline settings, voice profiles, channel branding, and API status

import { useState, useEffect } from 'react'
import { supabase } from '../lib/supabase'
import { Settings, Save, CheckCircle, AlertTriangle, Shield, Mic, Sliders, Info } from 'lucide-react'

export default function SettingsPage() {
  const [settings, setSettings] = useState({
    voice_profile: 'documentary_male',
    channel_name: '',
    publish_per_run: '1',
    max_videos_daily: '5',
    auto_approve: 'false',
    default_render_style: 'stock_footage',
    gemini_temperature: '0.9'
  })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [savedSuccess, setSavedSuccess] = useState(false)

  useEffect(() => {
    loadSettings()
  }, [])

  async function loadSettings() {
    setLoading(true)
    const { data } = await supabase.from('settings').select('key, value')
    if (data) {
      const map = {}
      data.forEach(row => { map[row.key] = row.value })
      setSettings(prev => ({ ...prev, ...map }))
    }
    setLoading(false)
  }

  async function handleSave(e) {
    e.preventDefault()
    setSaving(true)
    setSavedSuccess(false)

    const updates = Object.entries(settings).map(([key, value]) => ({
      key,
      value: String(value),
      updated_at: new Date().toISOString()
    }))

    const { error } = await supabase.from('settings').upsert(updates, { onConflict: 'key' })
    if (error) {
      alert(`Error saving settings: ${error.message}`)
    } else {
      setSavedSuccess(true)
      setTimeout(() => setSavedSuccess(false), 3000)
    }
    setSaving(false)
  }

  if (loading) return (
    <div className="loading-screen">
      <div className="spinner" />
      <span>Loading settings...</span>
    </div>
  )

  return (
    <div style={{ maxWidth: 800 }}>
      {/* Header */}
      <div className="page-header">
        <div>
          <h1>Pipeline Settings</h1>
          <p>Configure narration voice, channel watermark, publishing frequency, and batch quotas.</p>
        </div>
        {savedSuccess && (
          <div className="flex gap-2" style={{ color: 'var(--accent-green)', fontWeight: 600, alignItems: 'center' }}>
            <CheckCircle size={18} /> Settings Saved!
          </div>
        )}
      </div>

      <form onSubmit={handleSave}>
        {/* Voice Profile */}
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-header">
            <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Mic size={18} color="var(--accent-primary)" /> Voice & Narration Profile
            </span>
          </div>

          <div className="form-group">
            <label className="form-label">Active Neural Voice (Edge-TTS)</label>
            <select
              className="form-select"
              value={settings.voice_profile}
              onChange={e => setSettings({ ...settings, voice_profile: e.target.value })}
            >
              <option value="documentary_male">Guy (en-US) — Deep, cinematic, authoritative documentary narrator</option>
              <option value="documentary_female">Jenny (en-US) — Clear, polished, professional tech presenter</option>
              <option value="conversational">Andrew (en-US) — Natural, friendly, casual explainer</option>
              <option value="energetic">Christopher (en-US) — Upbeat, fast-paced, high energy</option>
              <option value="british_calm">Ryan (en-GB) — British accent, calm, intellectual & precise</option>
            </select>
            <div className="form-hint">
              100% free neural voices from Microsoft Edge Speech API with zero character limits.
            </div>
          </div>
        </div>

        {/* Branding & Visuals */}
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-header">
            <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Sliders size={18} color="var(--accent-primary)" /> Branding & Safe Zones
            </span>
          </div>

          <div className="form-group">
            <label className="form-label">Channel Handle / Watermark</label>
            <input 
              type="text" 
              className="form-input" 
              placeholder="e.g. TechUnfolded (leave blank for no watermark)"
              value={settings.channel_name}
              onChange={e => setSettings({ ...settings, channel_name: e.target.value.replace('@', '') })}
            />
            <div className="form-hint">
              Rendered subtly in the top-left safe zone below YouTube's top bar.
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Default Visual Style</label>
            <select
              className="form-select"
              value={settings.default_render_style}
              onChange={e => setSettings({ ...settings, default_render_style: e.target.value })}
            >
              <option value="character_skit">Character Skit — animated characters talking (comedy, dialogue)</option>
              <option value="stock_footage">Stock Footage — real b-roll with a Ken Burns zoom</option>
              <option value="whiteboard_sketch">Whiteboard Sketch — hand-drawn icons on paper</option>
              <option value="quote_card">Quote Card — minimal drifting gradient, captions only</option>
            </select>
            <div className="form-hint">
              Used for any topic that doesn't set its own style in Topic Studio.
            </div>

            <label className="form-label" style={{ marginTop: 16 }}>
              AI Creativity (temperature) — {settings.gemini_temperature}
            </label>
            <input
              type="range" min="0.2" max="1.4" step="0.1"
              value={settings.gemini_temperature}
              onChange={e => setSettings({ ...settings, gemini_temperature: e.target.value })}
              style={{ width: '100%' }}
            />
            <div className="form-hint">
              <strong>This is a real AI-engineering concept, not just a slider.</strong> It
              controls how often Gemini picks a less-obvious next word instead of the safest one.
              <br /><br />
              <strong>Low (0.2–0.5):</strong> predictable, same-ish phrasing every time. Good for
              factual accuracy, bad for jokes — the safest word is rarely the funny one.
              <br />
              <strong>Default (0.9):</strong> the sweet spot for short-form writing — varied
              without breaking down.
              <br />
              <strong>High (1.2+):</strong> more surprising, but risks sentences that technically
              parse yet read oddly. Try generating the same topic at 0.5 and then at 1.2 and
              compare — that's the fastest way to actually understand what this number does.
            </div>
          </div>
        </div>

        {/* Publishing & Batch Quota */}
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-header">
            <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Shield size={18} color="var(--accent-primary)" /> Publishing & YouTube Quota Guardrails
            </span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <div className="form-group">
              <label className="form-label">Daily Video Generation Batch</label>
              <input 
                type="number" 
                className="form-input" 
                min="1" 
                max="6"
                value={settings.max_videos_daily}
                onChange={e => setSettings({ ...settings, max_videos_daily: e.target.value })}
              />
              <div className="form-hint">Number of video drafts generated by GitHub Actions each night (max 5-6).</div>
            </div>

            <div className="form-group">
              <label className="form-label">Publish Per Run</label>
              <input 
                type="number" 
                className="form-input" 
                min="1" 
                max="3"
                value={settings.publish_per_run}
                onChange={e => setSettings({ ...settings, publish_per_run: e.target.value })}
              />
              <div className="form-hint">How many approved videos to upload per 30-min cron trigger (default 1).</div>
            </div>
          </div>

          {/* Auto Approve Warning */}
          <div style={{ 
            background: 'var(--bg-elevated)', 
            padding: 16, 
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--border)',
            marginTop: 8
          }}>
            <label style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer' }}>
              <div>
                <div style={{ fontWeight: 600, fontSize: '0.875rem' }}>Auto-Approve Videos (Bypass Review)</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 2 }}>
                  Automatically marks all generated videos as approved without human review.
                </div>
              </div>
              <input 
                type="checkbox" 
                checked={settings.auto_approve === 'true'}
                onChange={e => setSettings({ ...settings, auto_approve: e.target.checked ? 'true' : 'false' })}
              />
            </label>

            {settings.auto_approve === 'true' && (
              <div style={{ 
                display: 'flex', 
                gap: 8, 
                alignItems: 'center', 
                color: 'var(--accent-amber)', 
                fontSize: '0.78rem',
                marginTop: 12,
                padding: '8px 12px',
                background: 'rgba(251, 133, 0, 0.1)',
                borderRadius: 4
              }}>
                <AlertTriangle size={16} flexShrink={0} />
                <span>
                  <strong>YPP Warning:</strong> Disabling human review increases the risk of YouTube flagging the channel as "Reused / Low-Effort Content".
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Save Button */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 24 }}>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            <Save size={16} /> {saving ? 'Saving...' : 'Save Settings'}
          </button>
        </div>
      </form>
    </div>
  )
}
