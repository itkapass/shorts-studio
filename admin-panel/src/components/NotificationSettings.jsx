// src/components/NotificationSettings.jsx
//
// "Enable Notifications" — the frontend half of real push notifications.
//
// WHY THIS EXISTS
// engine/push_notifications.py can send a real, OS-level notification to
// any subscribed device the moment a video's ready, fails, or the daily
// quota runs out — the same events already going to Telegram/email. This
// component is how a device actually GETS subscribed: request permission,
// register with the browser's push service, save the resulting
// subscription to Supabase so the backend knows this device exists.
//
// This only does anything useful once the app is actually installed to a
// home screen (or at least running over HTTPS) — browsers require both a
// secure context and, on iOS specifically, that the site was launched from
// its home-screen icon, not just opened as a normal tab.

import { useState, useEffect } from 'react'
import { supabase } from '../lib/supabase'
import { Bell, BellRing, Loader2, AlertTriangle } from 'lucide-react'

// Public key only — safe to ship in the bundle. Its matching PRIVATE key
// (which is what actually lets the backend send notifications) never
// leaves the server; it's a GitHub secret read only by engine/push_notifications.py.
// Set once as a Vercel environment variable (VITE_VAPID_PUBLIC_KEY) so
// rotating keys later never needs a code change — see docs/17.
const VAPID_PUBLIC_KEY = import.meta.env.VITE_VAPID_PUBLIC_KEY || ''

// Browsers want the VAPID key as a raw Uint8Array, not the base64url string
// everything else in this project passes it around as.
function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
  const rawData = atob(base64)
  return Uint8Array.from([...rawData].map((c) => c.charCodeAt(0)))
}

export default function NotificationSettings() {
  const [status, setStatus] = useState('checking') // checking | unsupported | no-key | denied | off | on
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    checkStatus()
  }, [])

  async function checkStatus() {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
      setStatus('unsupported')
      return
    }
    if (!VAPID_PUBLIC_KEY) {
      setStatus('no-key')
      return
    }
    if (Notification.permission === 'denied') {
      setStatus('denied')
      return
    }
    try {
      const reg = await navigator.serviceWorker.ready
      const existing = await reg.pushManager.getSubscription()
      setStatus(existing ? 'on' : 'off')
    } catch {
      setStatus('off')
    }
  }

  async function enable() {
    setBusy(true)
    setMessage('')
    try {
      const permission = await Notification.requestPermission()
      if (permission !== 'granted') {
        setStatus('denied')
        setMessage('Notifications were not allowed. You can re-enable them in your browser/phone settings.')
        setBusy(false)
        return
      }
      const reg = await navigator.serviceWorker.ready
      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY),
      })
      const raw = sub.toJSON()
      const { error } = await supabase.from('push_subscriptions').insert({
        endpoint: raw.endpoint,
        p256dh: raw.keys.p256dh,
        auth: raw.keys.auth,
        user_agent: navigator.userAgent,
      })
      // A duplicate endpoint (re-enabling on the same device) isn't a real
      // error — the subscription already exists and works fine either way.
      if (error && !String(error.message || '').toLowerCase().includes('duplicate')) {
        throw error
      }
      setStatus('on')
      setMessage('Notifications enabled on this device.')
    } catch (e) {
      setMessage(`Could not enable notifications: ${e.message || e}`)
    }
    setBusy(false)
  }

  async function disable() {
    setBusy(true)
    setMessage('')
    try {
      const reg = await navigator.serviceWorker.ready
      const sub = await reg.pushManager.getSubscription()
      if (sub) {
        await supabase.from('push_subscriptions').delete().eq('endpoint', sub.endpoint)
        await sub.unsubscribe()
      }
      setStatus('off')
      setMessage('Notifications turned off on this device.')
    } catch (e) {
      setMessage(`Could not disable notifications: ${e.message || e}`)
    }
    setBusy(false)
  }

  if (status === 'checking') return null

  return (
    <div className="card" style={{ marginBottom: 20 }}>
      <div className="card-header">
        <span className="card-title">Notifications on this device</span>
      </div>

      {status === 'unsupported' && (
        <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
          This browser doesn't support push notifications. They work in Chrome/Edge on Android
          and desktop, and in Safari on iOS 16.4+ — but only when opened from the home-screen
          icon, not a normal browser tab.
        </p>
      )}

      {status === 'no-key' && (
        <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
          Push notifications aren't set up yet for this deployment. See docs/17_MOBILE_PUSH_NOTIFICATIONS.md
          — about 10 minutes, free.
        </p>
      )}

      {status === 'denied' && (
        <p style={{ fontSize: '0.8rem', color: '#f87171', display: 'flex', gap: 8, alignItems: 'flex-start' }}>
          <AlertTriangle size={15} style={{ flexShrink: 0, marginTop: 2 }} />
          Notifications are blocked for this site. Re-enable them in your browser or phone's
          site settings, then reload this page.
        </p>
      )}

      {(status === 'on' || status === 'off') && (
        <>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: 12 }}>
            Get a real notification on this device — the same as Telegram, but here — when a
            video's ready for review, a run fails, or the daily quota runs out.
          </p>
          <button
            onClick={status === 'on' ? disable : enable}
            disabled={busy}
            className="btn btn-sm"
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              background: status === 'on' ? 'rgba(45, 206, 137, 0.12)' : 'var(--bg-elevated)',
              color: status === 'on' ? 'var(--accent-green)' : 'var(--text-primary)',
              border: `1px solid ${status === 'on' ? 'rgba(45, 206, 137, 0.3)' : 'var(--border)'}`,
            }}
          >
            {busy ? <Loader2 size={14} className="spin" />
              : status === 'on' ? <BellRing size={14} /> : <Bell size={14} />}
            {busy ? 'Working\u2026' : status === 'on' ? 'Notifications on \u2014 tap to turn off' : 'Enable notifications on this device'}
          </button>
        </>
      )}

      {message && (
        <div style={{ marginTop: 10, fontSize: '0.75rem', color: 'var(--text-muted)' }}>
          {message}
        </div>
      )}
    </div>
  )
}
