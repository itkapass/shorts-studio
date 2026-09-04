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
    gemini_temperature: '0.9',
    auto_topic_personas: '',
    videos_per_run: '1',
    publish_min_gap_minutes: '0'
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
              Automatic Topic Rotation
            </label>
            <input
              type="text"
              className="form-input"
              value={settings.auto_topic_personas}
              onChange={e => setSettings({ ...settings, auto_topic_personas: e.target.value })}
              placeholder="tech_science_explainer, comedy_skits"
            />
            <div className="form-hint">
              <strong>This is what stops you adding topics by hand.</strong> Comma-separated
              persona keys. Before every generation run, the app checks how many unused topics
              each listed persona has left, and if it is running low it invents new specific ones
              inside that domain — each through a different <em>kind</em> of question so they
              never converge into forty "how does X work" videos.
              <br /><br />
              A topic counts as used the moment it produces a video, so every new video reaches
              for a genuinely new subject.
              <br /><br />
              Valid keys: <code>tech_science_explainer</code>, <code>comedy_skits</code>,{' '}
              <code>top10_and_facts</code>, <code>what_if_physics</code>,{' '}
              <code>awareness_comedy</code>, <code>everyday_origins</code>,{' '}
              <code>motivation_and_discipline</code>, <code>quotes_and_poetry</code>
              <br /><br />
              <strong>Leave this blank.</strong> Every enabled channel already gets topics
              invented for it automatically — this box only ADDS extra personas on top,
              for domains that do not have a channel yet.
              <br /><br />
              <em>This box used to be able to silently switch channels off.</em> It was
              seeded with a single value when your database was created, and the code
              treated it as an override that beat everything else — so Comedy and Tamil
              Quotes could never get topics no matter how they were configured on the
              Channels page. It is now additive only: it can add personas, never remove
              them.
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
                max="12"
                value={settings.max_videos_daily}
                onChange={e => setSettings({ ...settings, max_videos_daily: e.target.value })}
              />
              <div className="form-hint">
                The most videos that may be made in one day, across all runs.
                <br /><br />
                <strong>This used to be capped at 6</strong>, copying YouTube's ~6 uploads/day
                limit — the wrong limit to copy. Generation and publishing are separate steps
                with separate limits: publishing is capped by YouTube (see Publish Per Run
                below), but generation is capped by Gemini's free-tier quota, roughly 20
                requests/day at ~2 requests per video — about <strong>8 videos/day</strong>.
                <br /><br />
                Generation runs 6 times a day and makes one video each time, so 6 is the
                natural setting. The daily budget works out as: 6 videos x 2 requests, plus
                1 request per channel for topic invention = about 15 of your ~20 free
                requests.
                <br /><br />
                Setting this higher than the app can actually afford is safe: it stops itself
                cleanly at whatever the day's remaining Gemini quota allows, rather than failing
                partway through.
              </div>
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
              <div className="form-hint">
                How many approved videos to upload each time the publish job wakes up.
                <strong> Leave this at 1.</strong> The job wakes hourly but only actually
                uploads when the spacing gap below has passed, so raising this just
                re-creates the burst that spacing exists to prevent.
              </div>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <div className="form-group">
              <label className="form-label">Videos Per Run</label>
              <input
                type="number"
                className="form-input"
                min="1"
                max="3"
                value={settings.videos_per_run}
                onChange={e => setSettings({ ...settings, videos_per_run: e.target.value })}
              />
              <div className="form-hint">
                How many videos one scheduled generation run may render.
                <br /><br />
                <strong>1 is the right answer on a free plan.</strong> Rendering is the
                heaviest step in the whole pipeline — ffmpeg, text-to-speech and Whisper
                captioning, all on a free shared runner. Two videos in one run doubles how
                long that job holds the runner and doubles what you lose if it times out.
                Six small runs recover from a failure far better than three big ones: lose
                a run, lose one video.
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Minimum Gap Between Uploads (minutes)</label>
              <input
                type="number"
                className="form-input"
                min="0"
                max="1440"
                step="30"
                value={settings.publish_min_gap_minutes}
                onChange={e => setSettings({ ...settings, publish_min_gap_minutes: e.target.value })}
              />
              <div className="form-hint">
                <strong>0 = work it out automatically</strong> from each channel's daily cap.
                A cap of 4/day becomes one upload every 6 hours, 6/day becomes every 4 hours.
                That is almost always what you want, which is why 0 is the default.
                <br /><br />
                <strong>Why spacing matters:</strong> before this existed, the publish job
                uploaded every approved video the moment it found one. A channel capped at
                4/day did not post 4 videos across the day — it posted all 4 inside the
                first two hours and then went silent for twenty-two. Four Shorts released
                minutes apart compete with each other for the same slice of impressions
                instead of each getting its own window.
                <br /><br />
                Need something out immediately anyway? Use the <strong>Publish Now</strong>
                {' '}button on the video in the Video Queue — it skips the gap entirely.
              </div>
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
