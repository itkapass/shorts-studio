// src/App.jsx
import { BrowserRouter, Routes, Route, Navigate, NavLink, Link } from 'react-router-dom'
import { LayoutDashboard, Film, Palette, Settings, Sparkles, Flame, AlertCircle, LogOut } from 'lucide-react'
import Dashboard from './pages/Dashboard'
import VideoQueue from './pages/VideoQueue'
import CreateVideo from './pages/CreateVideo'
import TrendingRadar from './pages/TrendingRadar'
import TopicStudio from './pages/TopicStudio'
import SettingsPage from './pages/SettingsPage'
import Login from './pages/Login'
import { isSupabaseConfigured } from './lib/supabase'
import { AuthProvider, useAuth } from './lib/auth'
import './index.css'

const NAV_ITEMS = [
  { to: '/',         label: 'Dashboard',       icon: LayoutDashboard },
  { to: '/create',   label: 'Create Video',    icon: Sparkles, badge: 'AI' },
  { to: '/trending', label: 'Trending Radar',  icon: Flame, badge: 'HOT' },
  { to: '/queue',    label: 'Video Queue',     icon: Film },
  { to: '/studio',   label: 'Topic Studio',    icon: Palette },
  { to: '/settings', label: 'Settings',        icon: Settings },
]

function Sidebar() {
  const { user, signOut } = useAuth()
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <h2>🎬 Shorts Studio</h2>
        <span style={{ fontSize: '0.75rem', color: isSupabaseConfigured ? 'var(--accent-green)' : 'var(--accent-amber)', fontWeight: 600 }}>
          ● {isSupabaseConfigured ? 'Live Connected' : 'Studio Preview Mode'}
        </span>
      </div>
      <nav>
        {NAV_ITEMS.map(({ to, label, icon: Icon, badge }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
          >
            <Icon size={17} />
            <span style={{ flex: 1 }}>{label}</span>
            {badge && (
              <span className={`nav-badge nav-badge-${badge.toLowerCase()}`}>
                {badge}
              </span>
            )}
          </NavLink>
        ))}
      </nav>
      {user && (
        <button
          onClick={signOut}
          className="nav-item"
          style={{ marginTop: 'auto', width: '100%', border: 'none', background: 'none', cursor: 'pointer', textAlign: 'left' }}
        >
          <LogOut size={17} />
          <span style={{ flex: 1 }}>{user.email}</span>
        </button>
      )}
    </aside>
  )
}

// Gates every route below it on a real Supabase session. In Studio Preview
// Mode (no Supabase configured at all — nothing real to protect) this is a
// no-op, so the "try it without setup" experience is unaffected. Once real
// credentials are connected, this is what stops the Admin Panel itself from
// being a public, no-login control panel for your pipeline — see
// supabase/schema.sql for the matching server-side RLS enforcement, which
// is the part that actually matters; this is just the UI half.
function RequireAuth({ children }) {
  const { user, loading } = useAuth()
  if (!isSupabaseConfigured) return children
  if (loading) return <div style={{ padding: 40 }}>Loading…</div>
  if (!user) return <Navigate to="/login" replace />
  return children
}

function AppShell() {
  return (
    <div className="app-shell">
      <Sidebar />
      <main className="main-content">
        {!isSupabaseConfigured && (
          <div style={{ background: 'rgba(251, 133, 0, 0.12)', border: '1px solid rgba(251, 133, 0, 0.3)', borderRadius: 10, padding: '12px 18px', marginBottom: 20, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <AlertCircle size={18} color="var(--accent-amber)" />
              <span style={{ fontSize: '0.86rem', color: 'var(--text-primary)' }}>
                <strong>Studio Preview Mode:</strong> Connect your free Supabase database to save video drafts and topics permanently.
              </span>
            </div>
            <Link to="/settings" className="btn btn-secondary" style={{ fontSize: '0.78rem', padding: '5px 12px', whiteSpace: 'nowrap' }}>
              Setup Guide →
            </Link>
          </div>
        )}
        <Routes>
          <Route path="/"         element={<RequireAuth><Dashboard /></RequireAuth>} />
          <Route path="/create"   element={<RequireAuth><CreateVideo /></RequireAuth>} />
          <Route path="/trending" element={<RequireAuth><TrendingRadar /></RequireAuth>} />
          <Route path="/queue"    element={<RequireAuth><VideoQueue /></RequireAuth>} />
          <Route path="/studio"   element={<RequireAuth><TopicStudio /></RequireAuth>} />
          <Route path="/settings" element={<RequireAuth><SettingsPage /></RequireAuth>} />
        </Routes>
      </main>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/*" element={<AppShell />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
