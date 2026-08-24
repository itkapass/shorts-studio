// src/lib/auth.jsx
//
// FIXED A REAL GAP: this file didn't exist before. App.jsx rendered every
// page with no login check of any kind, and schema.sql's RLS policies
// granted full read/write to the public anon role too — so the deployed
// Admin Panel had no access control at either layer. This provides the
// session state the new login gate in App.jsx and Login.jsx need; the
// actual enforcement is schema.sql's `auth.role() = 'authenticated'`
// policies (this context alone doesn't secure anything by itself — a
// client-side check is a UX nicety, not a security boundary).
import { createContext, useContext, useEffect, useState } from 'react'
import { supabase, isSupabaseConfigured } from './supabase'

const AuthContext = createContext({ user: null, loading: true, session: null })

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null)
  const [loading, setLoading] = useState(isSupabaseConfigured)

  useEffect(() => {
    if (!isSupabaseConfigured) {
      setLoading(false)
      return
    }
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session)
      setLoading(false)
    })
    const { data: listener } = supabase.auth.onAuthStateChange((_event, newSession) => {
      setSession(newSession)
    })
    return () => listener.subscription.unsubscribe()
  }, [])

  const value = {
    user: session?.user ?? null,
    session,
    loading,
    accessToken: session?.access_token ?? null,
    signIn: (email, password) => supabase.auth.signInWithPassword({ email, password }),
    signOut: () => supabase.auth.signOut(),
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  return useContext(AuthContext)
}
