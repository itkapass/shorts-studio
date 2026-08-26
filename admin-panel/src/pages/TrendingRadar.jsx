// src/pages/TrendingRadar.jsx
// Trending Radar
//
// FIXED A REAL GAP: this page used to be a fixed array of 6 hardcoded
// example topics (Titan, NVIDIA, Rolex, Apple, Costco, De Beers) with
// invented "viral_score" and "$26 CPM" numbers with no basis in anything
// real, and "Refresh Hot Trends" called setTimeout() for 800ms and nothing
// else. "+Queue" inserted a fake video row into the real queue with NO
// storyboard at all — nothing to ever render.
//
// This now calls the discover-trends Edge Function, which does a real
// YouTube Data API search for what's actually getting views this week —
// see supabase/functions/discover-trends. No invented scores: just real
// titles, real channels, real view counts, honestly labeled as recent
// search results, not a prediction.

import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { supabase, getFunctionErrorMessage } from '../lib/supabase'
import { Flame, ArrowRight, Wand2, Eye, RefreshCw, AlertTriangle, ExternalLink } from 'lucide-react'

function formatViews(n) {
  if (!n) return '—'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M views`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K views`
  return `${n} views`
}

function timeAgo(iso) {
  if (!iso) return ''
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / (1000 * 60 * 60 * 24))
  if (days <= 0) return 'today'
  if (days === 1) return '1 day ago'
  return `${days} days ago`
}

export default function TrendingRadar() {
  const navigate = useNavigate()
  const [results, setResults] = useState([])
  const [isScanning, setIsScanning] = useState(false)
  const [error, setError] = useState(null)
  const [note, setNote] = useState(null)

  async function handleScanTrends() {
    setIsScanning(true)
    setError(null)
    const { data, error: fnError } = await supabase.functions.invoke('discover-trends', { body: {} })
    setIsScanning(false)

    if (fnError || data?.error) {
      setError(await getFunctionErrorMessage(fnError, data, 'Could not reach the discover-trends function.'))
      setResults([])
      return
    }
    setResults(data.results || [])
    setNote(data.note)
  }

  useEffect(() => { handleScanTrends() }, [])

  function handleUseAsPrompt(item) {
    sessionStorage.setItem('custom_prompt_preload', `A short explainer inspired by this real, currently-popular video: "${item.title}"`)
    navigate('/create')
  }

  return (
    <div className="trending-radar-page">
      <div className="page-header">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <span className="badge badge-accent" style={{ background: 'rgba(251, 133, 0, 0.15)', color: 'var(--accent-amber)', border: '1px solid rgba(251, 133, 0, 0.3)' }}>
              <Flame size={13} style={{ marginRight: 4 }} /> Real YouTube Search
            </span>
          </div>
          <h1>Trending Radar</h1>
          <p>What's actually getting views on Shorts this week — real search results, not a prediction.</p>
        </div>

        <button className="btn btn-secondary" onClick={handleScanTrends} disabled={isScanning} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <RefreshCw size={15} className={isScanning ? 'spin' : ''} />
          {isScanning ? 'Searching YouTube…' : 'Refresh'}
        </button>
      </div>

      {note && !error && (
        <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: 16 }}>{note}</p>
      )}

      {error && (
        <div className="card" style={{ display: 'flex', gap: 10, alignItems: 'flex-start', borderLeft: '3px solid #d33', marginBottom: 20 }}>
          <AlertTriangle size={18} style={{ flexShrink: 0, marginTop: 2 }} color="#d33" />
          <div>
            <strong>Couldn't load trends</strong>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: 4 }}>{error}</p>
          </div>
        </div>
      )}

      {!error && !isScanning && results.length === 0 && (
        <div className="card empty-storyboard-state">
          <Flame size={40} opacity={0.3} />
          <h3>No results yet</h3>
          <p>Click Refresh to search YouTube for what's currently popular.</p>
        </div>
      )}

      <div className="trending-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 20 }}>
        {results.map((item) => (
          <div key={item.video_id} className="trending-card card" style={{ display: 'flex', flexDirection: 'column' }}>
            {item.thumbnail && (
              <img src={item.thumbnail} alt="" style={{ width: '100%', borderRadius: 8, marginBottom: 12, aspectRatio: '16/9', objectFit: 'cover' }} />
            )}
            <span className="badge" style={{ alignSelf: 'flex-start', marginBottom: 8, fontSize: '0.72rem', textTransform: 'uppercase' }}>{item.category}</span>
            <h3 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: 8, lineHeight: 1.4 }}>{item.title}</h3>
            <div style={{ display: 'flex', gap: 12, fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: 14 }}>
              <span>{item.channel}</span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><Eye size={12} /> {formatViews(item.view_count)}</span>
              <span>{timeAgo(item.published_at)}</span>
            </div>
            <div style={{ display: 'flex', gap: 10, marginTop: 'auto' }}>
              <button className="btn btn-primary" onClick={() => handleUseAsPrompt(item)} style={{ flex: 1, padding: '10px 14px', fontSize: '0.85rem' }}>
                <Wand2 size={14} /> Use as Prompt <ArrowRight size={14} />
              </button>
              <a href={item.url} target="_blank" rel="noreferrer" className="btn btn-secondary" style={{ padding: '10px 14px' }} title="Open on YouTube">
                <ExternalLink size={14} />
              </a>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
