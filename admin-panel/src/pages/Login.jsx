// src/pages/Login.jsx
import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import { Lock, AlertCircle } from 'lucide-react'
import { useAuth } from '../lib/auth'

export default function Login() {
  const { user, signIn } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  if (user) return <Navigate to="/" replace />

  async function handleSubmit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    const { error: signInError } = await signIn(email, password)
    setBusy(false)
    if (signInError) setError(signInError.message)
  }

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'var(--bg-primary, #0b0d12)',
    }}>
      <form onSubmit={handleSubmit} className="card" style={{ width: 360, padding: 32 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
          <Lock size={20} />
          <h2 style={{ margin: 0 }}>Admin Panel Login</h2>
        </div>
        <p style={{ color: 'var(--text-secondary, #9aa)', fontSize: '0.85rem', marginTop: 0 }}>
          This dashboard controls a real, connected pipeline — create your account in
          Supabase (Authentication → Users → Add user) first, then sign in here.
        </p>

        {error && (
          <div style={{
            display: 'flex', gap: 8, alignItems: 'center', background: 'rgba(220,50,50,0.12)',
            border: '1px solid rgba(220,50,50,0.3)', borderRadius: 8, padding: '8px 12px',
            fontSize: '0.82rem', marginBottom: 14,
          }}>
            <AlertCircle size={16} />
            {error}
          </div>
        )}

        <label style={{ display: 'block', fontSize: '0.8rem', marginBottom: 4 }}>Email</label>
        <input
          type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
          className="input" style={{ width: '100%', marginBottom: 14 }} autoFocus
        />

        <label style={{ display: 'block', fontSize: '0.8rem', marginBottom: 4 }}>Password</label>
        <input
          type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
          className="input" style={{ width: '100%', marginBottom: 18 }}
        />

        <button type="submit" disabled={busy} className="btn btn-primary" style={{ width: '100%' }}>
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </div>
  )
}
