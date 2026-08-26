// src/pages/CreateVideo.jsx
// Custom Prompt Video Studio
//
// FIXED A REAL GAP: this page used to do simple string-matching on the
// prompt text and fill in one fixed template — every "AI storyboard" had
// the same scene 2-4 text and b-roll keywords no matter what you typed,
// and "estimated_cpm" was a hardcoded string. Nothing called an LLM.
// Generation now calls the generate-storyboard Edge Function (real Gemini
// call, server-side — see supabase/functions/generate-storyboard). Also
// added: a render-style picker (stock_footage / whiteboard_sketch /
// quote_card), and "Save to Queue" now saves status='queued_for_render'
// with no storage_url yet (nothing has actually been rendered — that needs
// real compute, not a browser tab) instead of previously inserting a fully
// fake "pending" row with a made-up duration as if it were ready to review.

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { supabase, getFunctionErrorMessage } from '../lib/supabase'
import {
  Sparkles, Wand2, Film, Mic, CheckCircle2, Copy, ArrowRight,
  Volume2, AlertTriangle, PenLine,
} from 'lucide-react'

const PROMPT_PRESETS = [
  { title: 'How EUV Lithography Works', prompt: 'How EUV lithography machines carve transistors smaller than a virus, and why only one company on Earth can build them.' },
  { title: 'Why Submarine Cables Matter', prompt: 'How a single undersea fiber cable carries most of the internet traffic between continents, and what happens when one breaks.' },
  { title: 'The Real Cost of a Data Center', prompt: 'What actually happens inside a hyperscale data center: the power, the cooling, and the physical scale most people never see.' },
  { title: 'How LLMs Actually Predict Text', prompt: 'A specific, accurate explanation of how a transformer model turns your prompt into the next word, over and over.' },
]

const TONES = [
  { id: 'documentary', name: 'Documentary Narrator', desc: 'Calm, authoritative, cinematic — builds tension and wonder' },
  { id: 'facts', name: 'Mind-Blowing Facts', desc: 'Punchy, confident, specific numbers and scale comparisons' },
  { id: 'story', name: 'Short Story', desc: 'A vivid, brief narrative with a surprising twist at the end' },
  { id: 'sarcasm', name: 'Sarcastic Commentary', desc: 'Clever, dry humor — witty, not mean' },
  { id: 'advice', name: 'Genuine Advice', desc: 'Specific, actionable — feels like advice from a brilliant friend' },
]

const HOOKS = [
  { id: 'fact', name: 'Surprising Fact / Question' },
  { id: 'twist', name: 'Counter-Intuitive Twist' },
  { id: 'story', name: 'The Underdog / Origin Story' },
]

const VOICES = [
  { id: 'documentary_male', name: 'Deep Documentary Male' },
  { id: 'documentary_female', name: 'Cinematic Female' },
  { id: 'energetic', name: 'Fast & High-Energy' },
  { id: 'british_calm', name: 'Calm British' },
]

const STYLES = [
  { id: 'stock_footage', name: 'Stock Footage', desc: 'Real b-roll with a Ken Burns zoom' },
  { id: 'whiteboard_sketch', name: 'Whiteboard Sketch', desc: 'Hand-drawn icons that draw themselves on paper' },
  { id: 'quote_card', name: 'Quote Card', desc: 'Minimal drifting gradient, captions carry the video' },
]

export default function CreateVideo() {
  const navigate = useNavigate()

  const [prompt, setPrompt] = useState(PROMPT_PRESETS[0].prompt)
  const [selectedTone, setSelectedTone] = useState(TONES[0])
  const [selectedHook, setSelectedHook] = useState(HOOKS[0].name)
  const [selectedVoice, setSelectedVoice] = useState(VOICES[0].id)
  const [selectedStyle, setSelectedStyle] = useState(STYLES[0].id)

  useState(() => {
    const preloaded = sessionStorage.getItem('custom_prompt_preload')
    if (preloaded) {
      setPrompt(preloaded)
      sessionStorage.removeItem('custom_prompt_preload')
    }
  })

  const [isGenerating, setIsGenerating] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [savedSuccess, setSavedSuccess] = useState(false)
  const [storyboard, setStoryboard] = useState(null)
  const [genError, setGenError] = useState(null)
  const [copiedCmd, setCopiedCmd] = useState(false)
  const [lastJobId, setLastJobId] = useState(null)
  const [isTriggering, setIsTriggering] = useState(false)
  const [triggerResult, setTriggerResult] = useState(null) // { ok, message, actions_url } | { error }

  async function handleGenerateStoryboard() {
    if (!prompt.trim()) return
    setIsGenerating(true)
    setSavedSuccess(false)
    setGenError(null)
    setStoryboard(null)

    const { data, error } = await supabase.functions.invoke('generate-storyboard', {
      body: {
        prompt,
        tone_name: selectedTone.name,
        tone_desc: selectedTone.desc,
        hook_style: selectedHook,
        render_style: selectedStyle,
        num_scenes: 5,
      },
    })

    setIsGenerating(false)

    if (error || data?.error) {
      setGenError(await getFunctionErrorMessage(error, data,
        'Generation failed — check that the generate-storyboard function is deployed and GEMINI_API_KEY is set as its secret.'))
      return
    }
    setStoryboard(data.storyboard)
  }

  function updateScene(index, field, value) {
    if (!storyboard) return
    const updatedScenes = [...storyboard.scenes]
    updatedScenes[index] = { ...updatedScenes[index], [field]: value }
    setStoryboard({ ...storyboard, scenes: updatedScenes })
  }

  // Saves the REVIEWED (possibly edited) storyboard as a job awaiting
  // render. This does NOT fake a duration or a storage_url — nothing has
  // been rendered yet. "Copy Render Command" below renders exactly this
  // saved storyboard, not a freshly regenerated one.
  async function handleSaveToQueue() {
    if (!storyboard) return
    setIsSaving(true)
    try {
      const jobId = Math.random().toString(36).substring(2, 10)
      const { error } = await supabase.from('videos').insert({
        job_id: jobId,
        title: storyboard.video_title,
        description: storyboard.description,
        hashtags: storyboard.hashtags,
        tone_name: selectedTone.name,
        render_style: selectedStyle,
        status: 'queued_for_render',
        storyboard: JSON.stringify(storyboard),
        created_at: new Date().toISOString(),
      })
      if (error) throw error
      setLastJobId(jobId)
      setSavedSuccess(true)
    } catch (err) {
      console.error('Save error:', err)
      alert(`Could not save to queue: ${err.message}`)
    } finally {
      setIsSaving(false)
    }
  }

  function copyRenderCommand() {
    const cmd = lastJobId
      ? `python -m engine.orchestrator --render-job ${lastJobId}`
      : `python -m engine.orchestrator --prompt "${prompt.replace(/"/g, '\\"')}" --style ${selectedStyle}`
    navigator.clipboard.writeText(cmd)
    setCopiedCmd(true)
    setTimeout(() => setCopiedCmd(false), 3000)
  }

  // NEW: renders in GitHub Actions instead of requiring your own machine —
  // see supabase/functions/trigger-render. Needs GITHUB_PAT + GITHUB_REPO
  // set as that function's secrets (docs/05_DEPLOY_THE_DASHBOARD.md).
  async function handleRenderInCloud() {
    if (!lastJobId) return
    setIsTriggering(true)
    setTriggerResult(null)
    const { data, error } = await supabase.functions.invoke('trigger-render', {
      body: { job_id: lastJobId },
    })
    setIsTriggering(false)
    if (error || data?.error) {
      setTriggerResult({ error: await getFunctionErrorMessage(error, data, 'Could not reach the trigger-render function.') })
      return
    }
    setTriggerResult(data)
  }

  return (
    <div className="create-video-page">
      <div className="page-header">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <span className="badge badge-accent" style={{ background: 'rgba(132, 94, 247, 0.15)', color: 'var(--accent-purple)', border: '1px solid rgba(132, 94, 247, 0.3)' }}>
              <Sparkles size={13} style={{ marginRight: 4 }} /> Real Gemini generation
            </span>
          </div>
          <h1>Custom Prompt Video Studio</h1>
          <p>Turn any topic into a storyboard, in whichever visual style you want, then render it for real.</p>
        </div>
      </div>

      <div className="presets-banner card" style={{ marginBottom: 24, padding: '16px 20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
          <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Prompt Ideas
          </span>
        </div>
        <div className="preset-chips-grid">
          {PROMPT_PRESETS.map((p, idx) => (
            <button key={idx} className="preset-chip" onClick={() => setPrompt(p.prompt)} title={p.prompt}>
              <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{p.title}</span>
              <span className="preset-preview-text">{p.prompt}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="create-grid">
        <div className="controls-col">
          <div className="card">
            <div className="card-header"><span className="card-title">1. Your Video Prompt</span></div>

            <div className="form-group">
              <label>Topic / Prompt Description</label>
              <textarea
                rows={4} value={prompt} onChange={(e) => setPrompt(e.target.value)}
                placeholder="e.g. How EUV lithography carves transistors smaller than a virus..."
                className="custom-prompt-input"
              />
            </div>

            <div className="form-group">
              <label>Visual Style</label>
              <select value={selectedStyle} onChange={(e) => setSelectedStyle(e.target.value)} className="select-input">
                {STYLES.map((s) => <option key={s.id} value={s.id}>{s.name} — {s.desc}</option>)}
              </select>
            </div>

            <div className="form-group">
              <label>Writing Style & Tone</label>
              <select
                value={selectedTone.id}
                onChange={(e) => setSelectedTone(TONES.find((t) => t.id === e.target.value) || TONES[0])}
                className="select-input"
              >
                {TONES.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
            </div>

            <div className="form-group">
              <label>3-Second Hook Strategy</label>
              <select value={selectedHook} onChange={(e) => setSelectedHook(e.target.value)} className="select-input">
                {HOOKS.map((h) => <option key={h.id} value={h.name}>{h.name}</option>)}
              </select>
            </div>

            <div className="form-group">
              <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <Mic size={14} color="var(--accent-primary)" /> Voice Narrator (used when rendering)
              </label>
              <select value={selectedVoice} onChange={(e) => setSelectedVoice(e.target.value)} className="select-input">
                {VOICES.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
              </select>
            </div>

            <button
              className="btn btn-primary generate-btn"
              onClick={handleGenerateStoryboard}
              disabled={isGenerating || !prompt.trim()}
              style={{ width: '100%', marginTop: 8, padding: '14px 20px', fontSize: '1rem' }}
            >
              {isGenerating ? (<><div className="spinner-sm" /> Calling Gemini…</>) : (<><Wand2 size={18} /> Generate Storyboard</>)}
            </button>

            {genError && (
              <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start', background: 'rgba(220,50,50,0.1)', border: '1px solid rgba(220,50,50,0.3)', borderRadius: 8, padding: '10px 12px', marginTop: 10, fontSize: '0.8rem' }}>
                <AlertTriangle size={15} style={{ flexShrink: 0, marginTop: 2 }} />
                <span>{genError}</span>
              </div>
            )}
          </div>
        </div>

        <div className="storyboard-col">
          {!storyboard ? (
            <div className="card empty-storyboard-state">
              <Film size={48} opacity={0.3} color="var(--accent-primary)" />
              <h3>Storyboard will appear here</h3>
              <p>Type a prompt and click <strong>Generate Storyboard</strong> — this calls Gemini for real, so results vary by prompt.</p>
            </div>
          ) : (
            <div className="storyboard-container">
              <div className="card" style={{ marginBottom: 16 }}>
                <h2 style={{ fontSize: '1.25rem', color: 'var(--text-primary)', marginBottom: 4 }}>{storyboard.video_title}</h2>
                <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)' }}>{storyboard.description}</p>
                <div className="hashtags-list" style={{ marginTop: 12, display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {storyboard.hashtags.map((h, i) => <span key={i} className="hashtag-chip">{h}</span>)}
                </div>
              </div>

              <div className="scenes-list">
                {storyboard.scenes.map((scene, idx) => (
                  <div key={idx} className="scene-card card">
                    <div className="scene-header">
                      <div className="scene-num-badge">Scene {scene.scene_number ?? idx + 1}</div>
                      <div className="scene-meta-badges">
                        <span className="scene-badge mood-badge">{scene.visual_mood}</span>
                        <span className="scene-badge sfx-badge"><Volume2 size={11} /> {scene.sfx}</span>
                        <span className="scene-badge transition-badge">{scene.transition}</span>
                      </div>
                    </div>
                    <div className="scene-body">
                      <div className="scene-field">
                        <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}><PenLine size={12} /> Voiceover Text:</label>
                        <textarea rows={2} value={scene.voice_text} onChange={(e) => updateScene(idx, 'voice_text', e.target.value)} className="scene-text-input" />
                      </div>
                      {selectedStyle === 'whiteboard_sketch' ? (
                        <div className="scene-field">
                          <label>Icons (comma-separated, from the fixed vocabulary):</label>
                          <input
                            type="text" value={(scene.icons || []).join(', ')}
                            onChange={(e) => updateScene(idx, 'icons', e.target.value.split(',').map((s) => s.trim()).filter(Boolean))}
                            className="scene-keyword-input"
                          />
                        </div>
                      ) : selectedStyle === 'stock_footage' ? (
                        <div className="scene-field">
                          <label>B-Roll Search Keywords:</label>
                          <input type="text" value={scene.visual_keyword || ''} onChange={(e) => updateScene(idx, 'visual_keyword', e.target.value)} className="scene-keyword-input" />
                        </div>
                      ) : null}
                    </div>
                  </div>
                ))}
              </div>

              <div className="card action-bar-card" style={{ marginTop: 16 }}>
                {!savedSuccess ? (
                  <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                    <button className="btn btn-primary" onClick={handleSaveToQueue} disabled={isSaving}>
                      {isSaving ? 'Saving…' : (<><CheckCircle2 size={16} /> Save Storyboard <ArrowRight size={16} /></>)}
                    </button>
                  </div>
                ) : (
                  <div>
                    <p style={{ fontSize: '0.85rem', marginBottom: 10 }}>
                      Saved. This storyboard is <strong>not rendered yet</strong>.
                    </p>

                    {!triggerResult?.ok && (
                      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', marginBottom: 12 }}>
                        <button className="btn btn-primary" onClick={handleRenderInCloud} disabled={isTriggering}>
                          {isTriggering ? 'Starting…' : (<><Sparkles size={16} /> Render in Cloud</>)}
                        </button>
                        <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                          Runs on GitHub Actions — no need to keep your own computer on.
                        </span>
                      </div>
                    )}

                    {triggerResult?.ok && (
                      <div style={{ display: 'flex', gap: 8, alignItems: 'center', background: 'rgba(46,160,67,0.1)', border: '1px solid rgba(46,160,67,0.3)', borderRadius: 8, padding: '10px 12px', marginBottom: 12, fontSize: '0.82rem' }}>
                        <CheckCircle2 size={16} color="var(--accent-green)" />
                        Render started in the cloud — usually a few minutes. It'll show up in the Video Queue as "Rendering", then "Pending Review" once done.
                        {triggerResult.actions_url && (
                          <a href={triggerResult.actions_url} target="_blank" rel="noreferrer" style={{ marginLeft: 4 }}>Watch progress →</a>
                        )}
                      </div>
                    )}
                    {triggerResult?.error && (
                      <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start', background: 'rgba(220,50,50,0.1)', border: '1px solid rgba(220,50,50,0.3)', borderRadius: 8, padding: '10px 12px', marginBottom: 12, fontSize: '0.8rem' }}>
                        <AlertTriangle size={15} style={{ flexShrink: 0, marginTop: 2 }} />
                        <span>{triggerResult.error}</span>
                      </div>
                    )}

                    <details>
                      <summary style={{ fontSize: '0.78rem', color: 'var(--text-muted)', cursor: 'pointer' }}>
                        Or render locally instead
                      </summary>
                      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', marginTop: 10 }}>
                        <code style={{ background: 'var(--bg-secondary, #161b27)', padding: '8px 12px', borderRadius: 6, fontSize: '0.8rem' }}>
                          python -m engine.orchestrator --render-job {lastJobId}
                        </code>
                        <button className="btn btn-secondary" onClick={copyRenderCommand}>
                          {copiedCmd ? <CheckCircle2 size={16} color="var(--accent-green)" /> : <Copy size={16} />}
                          {copiedCmd ? 'Copied!' : 'Copy'}
                        </button>
                      </div>
                    </details>

                    <div style={{ marginTop: 14 }}>
                      <button className="btn btn-secondary" onClick={() => navigate('/queue')}>Go to Video Queue</button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
