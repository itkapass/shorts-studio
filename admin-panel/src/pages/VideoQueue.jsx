// src/pages/VideoQueue.jsx
// Review & Approval Queue for generated Shorts drafts

import { useState, useEffect } from 'react'
import { supabase } from '../lib/supabase'
import { 
  Film, Check, X, RefreshCw, Eye, Video, AlertCircle, 
  ChevronDown, ChevronUp, Play, Pause, Trash2, Sparkles, Filter
} from 'lucide-react'

// Triggers the manual-export workflow for a video: the file, captions,
// hashtags and a posting checklist get packaged into a downloadable zip, and
// the video leaves the auto-publish pipeline. Used when a video belongs on a
// different channel, on another platform, or should go out at a moment you
// choose.
async function requestManualExport(video, setBusy, setMsg) {
  setBusy(video.id)
  setMsg('')
  try {
    const { error } = await supabase
      .from('videos')
      .update({ status: 'needs_manual' })
      .eq('id', video.id)
    if (error) throw error
    setMsg(
      'Marked for manual posting. The next publish run packages it with captions, ' +
      'hashtags and a step-by-step checklist, then frees its storage.'
    )
  } catch (e) {
    setMsg('Could not mark for export: ' + e.message)
  } finally {
    setBusy(null)
  }
}

export default function VideoQueue() {
  const [videos, setVideos] = useState([])
  const [filter, setFilter] = useState('pending') // 'pending' | 'approved' | 'published' | 'all'
  const [loading, setLoading] = useState(true)
  const [expandedId, setExpandedId] = useState(null)
  const [actionLoading, setActionLoading] = useState({})

  useEffect(() => {
    loadVideos()
  }, [filter])

  async function loadVideos() {
    setLoading(true)
    let query = supabase
      .from('videos')
      .select('*, topics(name, category), tones(name)')
      .order('created_at', { ascending: false })

    if (filter !== 'all') {
      query = query.eq('status', filter)
    }

    const { data, error } = await query
    if (error) {
      console.error('Error fetching videos:', error)
    } else {
      setVideos(data || [])
    }
    setLoading(false)
  }

  async function updateStatus(id, newStatus) {
    setActionLoading(prev => ({ ...prev, [id]: true }))
    const updatePayload = { 
      status: newStatus, 
      updated_at: new Date().toISOString() 
    }
    if (newStatus === 'approved') {
      updatePayload.approved_at = new Date().toISOString()
    }

    const { error } = await supabase
      .from('videos')
      .update(updatePayload)
      .eq('id', id)

    if (error) {
      alert(`Error updating video: ${error.message}`)
    } else {
      setVideos(videos.map(v => v.id === id ? { ...v, ...updatePayload } : v))
    }
    setActionLoading(prev => ({ ...prev, [id]: false }))
  }

  async function deleteVideo(id) {
    if (!confirm('Are you sure you want to delete this video draft?')) return
    setActionLoading(prev => ({ ...prev, [id]: true }))
    
    const { error } = await supabase
      .from('videos')
      .delete()
      .eq('id', id)

    if (error) {
      alert(`Error deleting video: ${error.message}`)
    } else {
      setVideos(videos.filter(v => v.id !== id))
    }
    setActionLoading(prev => ({ ...prev, [id]: false }))
  }

  async function approveAllPending() {
    const pendingIds = videos.filter(v => v.status === 'pending').map(v => v.id)
    if (!pendingIds.length) return
    if (!confirm(
      `Approve all ${pendingIds.length} pending videos without watching them individually?\n\n` +
      `The whole point of manual review is catching issues (mispronunciations, mismatched b-roll, ` +
      `repetitive scripts) before they publish. Bulk-approving skips that. If you haven't watched ` +
      `each one, consider reviewing them individually instead.`
    )) return

    setLoading(true)
    const { error } = await supabase
      .from('videos')
      .update({ 
        status: 'approved', 
        approved_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      })
      .in('id', pendingIds)

    if (error) {
      alert(`Error bulk approving: ${error.message}`)
    } else {
      await loadVideos()
    }
    setLoading(false)
  }

  return (
    <div>
      {/* Header */}
      <div className="page-header">
        <div>
          <h1>Video Review Queue</h1>
          <p>Review and approve AI-generated video drafts before they publish to YouTube.</p>
        </div>
        <div className="flex gap-2">
          {filter === 'pending' && videos.length > 0 && (
            <button className="btn btn-success" onClick={approveAllPending}>
              <Check size={16} /> Approve All ({videos.length})
            </button>
          )}
          <button className="btn btn-ghost" onClick={loadVideos}>
            <RefreshCw size={15} /> Refresh
          </button>
        </div>
      </div>

      {/* Filter Tabs */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
        {[
          { id: 'queued_for_render', label: 'Awaiting Render' },
          { id: 'rendering', label: 'Rendering' },
          { id: 'pending', label: 'Pending Review' },
          { id: 'approved', label: 'Approved & Scheduled' },
          { id: 'published', label: 'Published' },
          { id: 'all', label: 'All History' }
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setFilter(tab.id)}
            className={`btn btn-sm ${filter === tab.id ? 'btn-primary' : 'btn-ghost'}`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Video List */}
      {loading ? (
        <div className="loading-screen">
          <div className="spinner" />
          <span>Loading queue...</span>
        </div>
      ) : videos.length === 0 ? (
        <div className="card empty-state">
          <Film size={48} opacity={0.3} />
          <h3>No videos in this queue</h3>
          <p>
            {filter === 'pending' 
              ? 'No pending drafts. GitHub Actions will generate new videos on schedule or trigger manual run.'
              : 'No videos found matching this filter.'}
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {videos.map(video => {
            const isExpanded = expandedId === video.id
            let parsedStoryboard = null
            try {
              parsedStoryboard = typeof video.storyboard === 'string' 
                ? JSON.parse(video.storyboard) 
                : video.storyboard
            } catch (e) {}

            return (
              <div key={video.id} className="card" style={{ padding: 20 }}>
                <div style={{ display: 'flex', gap: 24, alignItems: 'flex-start' }}>
                  
                  {/* Left: Video Player or Thumbnail */}
                  <div style={{ 
                    width: 180, 
                    height: 320, 
                    background: 'var(--bg-elevated)', 
                    borderRadius: 'var(--radius-sm)',
                    overflow: 'hidden',
                    flexShrink: 0,
                    border: '1px solid var(--border)',
                    position: 'relative',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                  }}>
                    {video.storage_url ? (
                      <video 
                        src={video.storage_url} 
                        controls 
                        playsInline
                        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                      />
                    ) : (
                      <div style={{ textAlign: 'center', padding: 12 }}>
                        <Film size={32} opacity={0.4} />
                        <span style={{ display: 'block', fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: 8 }}>
                          {video.status === 'failed' || video.status === 'publish_failed'
                            ? 'Render/Upload Failed'
                            : video.status === 'rendering'
                            ? 'Rendering in the cloud…'
                            : video.status === 'queued_for_render'
                            ? 'Not rendered yet'
                            : 'No Preview URL'}
                        </span>
                        {video.status === 'rendering' && (
                          <span style={{ display: 'block', fontSize: '0.62rem', marginTop: 6, color: 'var(--text-muted)' }}>
                            Usually a few minutes — refresh to check
                          </span>
                        )}
                        {video.status === 'queued_for_render' && (
                          <code style={{ display: 'block', fontSize: '0.62rem', marginTop: 6, color: 'var(--text-muted)', wordBreak: 'break-all' }}>
                            orchestrator --render-job {video.job_id}
                          </code>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Center & Right: Video Info & Actions */}
                  <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between', minHeight: 320 }}>
                    <div>
                      {/* Top Badges */}
                      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8, flexWrap: 'wrap' }}>
                        <span className={`badge badge-${video.status}`}>
                          {video.status.replace(/_/g, ' ')}
                        </span>
                        {video.render_style && (
                          <span className="badge" style={{ background: 'var(--bg-elevated)', color: 'var(--text-secondary)' }}>
                            🎨 {video.render_style.replace(/_/g, ' ')}
                          </span>
                        )}
                        {video.flags?.possible_duplicate && (
                          <span className="badge" title={`${Math.round((video.flags.similarity || 0) * 100)}% similar to "${video.flags.similar_to}"`}
                                style={{ background: 'rgba(251, 133, 0, 0.15)', color: 'var(--accent-amber)', border: '1px solid rgba(251, 133, 0, 0.3)' }}>
                            ⚠ {Math.round((video.flags.similarity || 0) * 100)}% similar to a recent video
                          </span>
                        )}
                        {video.topics?.name && (
                          <span className="badge" style={{ background: 'var(--bg-elevated)', color: 'var(--text-secondary)' }}>
                            📂 {video.topics.name}
                          </span>
                        )}
                        {(video.tones?.name || video.tone_name) && (
                          <span className="badge" style={{ background: 'var(--bg-elevated)', color: 'var(--text-secondary)' }}>
                            🎭 {video.tones?.name || video.tone_name}
                          </span>
                        )}
                        {video.duration && (
                          <span className="text-muted text-mono">
                            ⏱ {video.duration}s
                          </span>
                        )}
                        <span className="text-muted text-mono" style={{ marginLeft: 'auto' }}>
                          Job ID: {video.job_id}
                        </span>
                      </div>

                      {/* Title */}
                      <h2 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: 8 }}>
                        {video.title || 'Untitled Draft'}
                      </h2>

                      {/* Description */}
                      <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginBottom: 12, lineHeight: 1.5 }}>
                        {video.description || 'No description provided.'}
                      </p>

                      {/* Hashtags */}
                      {video.hashtags && (
                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 16 }}>
                          {(Array.isArray(video.hashtags) ? video.hashtags : JSON.parse(video.hashtags || '[]')).map((tag, i) => (
                            <span key={i} style={{ 
                              fontSize: '0.75rem', 
                              color: 'var(--accent-primary)',
                              background: 'var(--bg-elevated)',
                              padding: '2px 8px',
                              borderRadius: 4
                            }}>
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}

                      {/* Error Log (if failed) */}
                      {video.error_log && (
                        <div style={{ 
                          background: 'rgba(255, 77, 109, 0.1)', 
                          border: '1px solid rgba(255, 77, 109, 0.3)',
                          padding: 12,
                          borderRadius: 'var(--radius-sm)',
                          fontSize: '0.8rem',
                          color: 'var(--status-failed)',
                          marginBottom: 16
                        }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 700 }}>
                            <AlertCircle size={14} /> Generation Error:
                          </div>
                          <div className="text-mono" style={{ marginTop: 4, whiteSpace: 'pre-wrap' }}>
                            {video.error_log}
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Action Buttons Bar */}
                    <div style={{ 
                      display: 'flex', 
                      alignItems: 'center', 
                      justifyContent: 'space-between',
                      borderTop: '1px solid var(--border)',
                      paddingTop: 16,
                      marginTop: 16
                    }}>
                      <div className="flex gap-2">
                        {video.status === 'pending' && (
                          <>
                            <button 
                              className="btn btn-success btn-sm"
                              disabled={actionLoading[video.id]}
                              onClick={() => updateStatus(video.id, 'approved')}
                            >
                              <Check size={14} /> Approve for YouTube
                            </button>
                            <button 
                              className="btn btn-danger btn-sm"
                              disabled={actionLoading[video.id]}
                              onClick={() => updateStatus(video.id, 'rejected')}
                            >
                              <X size={14} /> Reject
                            </button>
                          </>
                        )}

                        {video.status === 'approved' && (
                          <button 
                            className="btn btn-ghost btn-sm"
                            disabled={actionLoading[video.id]}
                            onClick={() => updateStatus(video.id, 'pending')}
                          >
                            Move Back to Pending
                          </button>
                        )}

                        {video.status === 'published' && video.youtube_url && (
                          <a 
                            href={video.youtube_url} 
                            target="_blank" 
                            rel="noreferrer"
                            className="btn btn-primary btn-sm"
                          >
                            <Video size={14} /> Open on YouTube
                          </a>
                        )}

                        <button 
                          className="btn btn-ghost btn-sm"
                          onClick={() => setExpandedId(isExpanded ? null : video.id)}
                        >
                          {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                          {isExpanded ? 'Hide Storyboard' : 'View Storyboard'}
                        </button>
                      </div>

                      <button 
                        className="btn btn-ghost btn-icon btn-sm text-danger"
                        title="Delete video draft"
                        disabled={actionLoading[video.id]}
                        onClick={() => deleteVideo(video.id)}
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                </div>

                {/* Collapsible Scene Storyboard Breakdown */}
                {isExpanded && parsedStoryboard && parsedStoryboard.scenes && (
                  <div style={{ 
                    marginTop: 20, 
                    borderTop: '1px solid var(--border)', 
                    paddingTop: 16,
                    background: 'var(--bg-elevated)',
                    borderRadius: 'var(--radius-sm)',
                    padding: 16
                  }}>
                    <h4 style={{ fontSize: '0.85rem', fontWeight: 700, marginBottom: 12, color: 'var(--text-primary)' }}>
                      🎬 Scene-by-Scene Storyboard & B-Roll Keywords ({parsedStoryboard.scenes.length} scenes)
                    </h4>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 12 }}>
                      {parsedStoryboard.scenes.map((sc, i) => (
                        <div key={i} style={{ 
                          background: 'var(--bg-card)', 
                          padding: 12, 
                          borderRadius: 'var(--radius-sm)',
                          border: '1px solid var(--border)'
                        }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                            <span className="badge" style={{ background: 'var(--bg-deep)', fontSize: '0.65rem' }}>
                              Scene {sc.scene_number || i + 1}
                            </span>
                            <span className="text-muted text-mono" style={{ fontSize: '0.7rem' }}>
                              SFX: {sc.sfx || 'none'}
                            </span>
                          </div>
                          <p style={{ fontSize: '0.8rem', color: 'var(--text-primary)', marginBottom: 8 }}>
                            "{sc.voice_text}"
                          </p>
                          {sc.icons ? (
                            <div style={{ fontSize: '0.7rem', color: 'var(--accent-primary)' }}>
                              ✏️ Icons: <span style={{ color: 'var(--text-secondary)' }}>{sc.icons.join(', ')}</span>
                            </div>
                          ) : sc.visual_keyword ? (
                            <div style={{ fontSize: '0.7rem', color: 'var(--accent-primary)' }}>
                              🔍 B-Roll Keyword: <span style={{ color: 'var(--text-secondary)' }}>{sc.visual_keyword}</span>
                            </div>
                          ) : null}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
