// src/pages/Dashboard.jsx
// Overview page — shows live stats, quick actions, and revenue-focused pipeline status

import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { supabase } from '../lib/supabase'
import { 
  Film, 
  CheckCircle, 
  Clock, 
  Video, 
  TrendingUp, 
  Sparkles, 
  Flame, 
  ArrowRight, 
  DollarSign, 
  Zap,
  Play
} from 'lucide-react'

const STAT_CONFIG = [
  { key: 'pending',   label: 'Pending Review', icon: Clock,        color: '#fb8500' },
  { key: 'approved',  label: 'Approved',       icon: CheckCircle,  color: '#2dce89' },
  { key: 'published', label: 'Published',      icon: Video,        color: '#4f8ef7' },
  { key: 'total',     label: 'Total Generated',icon: Film,         color: '#845ef7' },
]

function StatCard({ label, value, icon: Icon, color }) {
  return (
    <div className="stat-card" style={{ '--accent-color': color }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span className="stat-label">{label}</span>
        <Icon size={18} color={color} opacity={0.7} />
      </div>
      <div className="stat-value">{value ?? '—'}</div>
    </div>
  )
}

export default function Dashboard() {
  const [stats, setStats]     = useState({})
  const [recent, setRecent]   = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => { loadData() }, [])

  async function loadData() {
    setLoading(true)
    const { data } = await supabase
      .from('videos')
      .select('status, title, created_at, youtube_url, job_id')
      .order('created_at', { ascending: false })
      .limit(50)

    if (data) {
      const counts = { pending: 0, approved: 0, published: 0, total: data.length }
      data.forEach(v => { if (counts[v.status] !== undefined) counts[v.status]++ })
      setStats(counts)
      setRecent(data.slice(0, 8))
    }
    setLoading(false)
  }

  if (loading) return (
    <div className="loading-screen">
      <div className="spinner" />
      <span>Loading dashboard...</span>
    </div>
  )

  return (
    <div className="dashboard-page">
      <div className="page-header">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <span className="badge badge-published">Shorts & Reels Pipeline</span>
            <span className="badge badge-accent" style={{ background: 'rgba(45, 206, 137, 0.15)', color: 'var(--accent-green)', border: '1px solid rgba(45, 206, 137, 0.3)' }}>
              <DollarSign size={12} style={{ marginRight: 2 }} /> High-CPM Monetization Engine
            </span>
          </div>
          <h1>Creator Dashboard</h1>
          <p>Generate, review, and auto-publish high-retention AI videos engineered for monetization.</p>
        </div>
        <button className="btn btn-secondary" onClick={loadData}>
          <TrendingUp size={15} /> Refresh
        </button>
      </div>

      {/* Quick Actions Action Banner */}
      <div className="quick-actions-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16, marginBottom: 24 }}>
        <Link to="/create" className="card action-banner-card prompt-card" style={{ padding: '20px', textDecoration: 'none', border: '1px solid rgba(132, 94, 247, 0.3)', background: 'linear-gradient(135deg, rgba(22, 27, 39, 0.9), rgba(132, 94, 247, 0.12))' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <div className="action-icon-circle" style={{ width: 38, height: 38, borderRadius: 10, background: 'rgba(132, 94, 247, 0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Sparkles size={20} color="var(--accent-purple)" />
            </div>
            <span className="badge badge-accent" style={{ background: 'rgba(132, 94, 247, 0.2)', color: 'var(--accent-purple)' }}>
              Interactive
            </span>
          </div>
          <h3 style={{ fontSize: '1.1rem', color: 'var(--text-primary)', marginBottom: 4 }}>
            Prompt-to-Video Studio
          </h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: 14 }}>
            Give any topic (e.g. Titan Company, Nvidia Moat) and build custom 5-scene videos with voiceover & b-roll.
          </p>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--accent-purple)', fontWeight: 600, fontSize: '0.88rem' }}>
            <span>Launch Studio</span> <ArrowRight size={15} />
          </div>
        </Link>

        <Link to="/trending" className="card action-banner-card trending-card" style={{ padding: '20px', textDecoration: 'none', border: '1px solid rgba(251, 133, 0, 0.3)', background: 'linear-gradient(135deg, rgba(22, 27, 39, 0.9), rgba(251, 133, 0, 0.12))' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <div className="action-icon-circle" style={{ width: 38, height: 38, borderRadius: 10, background: 'rgba(251, 133, 0, 0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Flame size={20} color="var(--accent-amber)" />
            </div>
            <span className="badge badge-pending">
              High CPM
            </span>
          </div>
          <h3 style={{ fontSize: '1.1rem', color: 'var(--text-primary)', marginBottom: 4 }}>
            Viral & Trending Radar
          </h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: 14 }}>
            Explore high-view viral niches ($25+ CPM) like business empires, luxury psychology, and AI monopolies.
          </p>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--accent-amber)', fontWeight: 600, fontSize: '0.88rem' }}>
            <span>Explore Trends</span> <ArrowRight size={15} />
          </div>
        </Link>

        <Link to="/queue" className="card action-banner-card queue-card" style={{ padding: '20px', textDecoration: 'none', border: '1px solid rgba(45, 206, 137, 0.3)', background: 'linear-gradient(135deg, rgba(22, 27, 39, 0.9), rgba(45, 206, 137, 0.12))' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <div className="action-icon-circle" style={{ width: 38, height: 38, borderRadius: 10, background: 'rgba(45, 206, 137, 0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Film size={20} color="var(--accent-green)" />
            </div>
            <span className="badge badge-approved">
              {stats.pending || 0} Pending
            </span>
          </div>
          <h3 style={{ fontSize: '1.1rem', color: 'var(--text-primary)', marginBottom: 4 }}>
            Review Video Queue
          </h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: 14 }}>
            Preview generated videos, inspect subtitle timings, approve drafts, or trigger one-click publishing.
          </p>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--accent-green)', fontWeight: 600, fontSize: '0.88rem' }}>
            <span>Open Queue</span> <ArrowRight size={15} />
          </div>
        </Link>
      </div>

      {/* Stats */}
      <div className="stats-grid" style={{ marginBottom: 24 }}>
        {STAT_CONFIG.map(s => (
          <StatCard key={s.key} {...s} value={stats[s.key]} />
        ))}
      </div>

      {/* Recent Videos */}
      <div className="card">
        <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span className="card-title">Recent Video Pipeline</span>
          <Link to="/queue" className="btn btn-secondary" style={{ fontSize: '0.82rem', padding: '6px 12px' }}>
            View Full Queue →
          </Link>
        </div>
        {recent.length === 0 ? (
          <div className="empty-state">
            <Film size={36} opacity={0.3} />
            <h3>No videos yet</h3>
            <p>Use the <strong>Prompt-to-Video Studio</strong> or <strong>Trending Radar</strong> above to generate your first draft.</p>
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {recent.map(v => (
                  <tr key={v.job_id}>
                    <td style={{ color: 'var(--text-primary)', maxWidth: 340 }}>
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', display: 'block' }}>
                        {v.title || `Video ${v.job_id}`}
                      </span>
                    </td>
                    <td>
                      <span className={`badge badge-${v.status}`}>
                        {v.status}
                      </span>
                    </td>
                    <td className="text-muted">
                      {new Date(v.created_at).toLocaleDateString()}
                    </td>
                    <td>
                      {v.youtube_url ? (
                        <a href={v.youtube_url} target="_blank" rel="noreferrer" className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: '0.8rem' }}>
                          <Video size={13} /> Watch
                        </a>
                      ) : (
                        <Link to="/queue" className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: '0.8rem' }}>
                          Review
                        </Link>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

