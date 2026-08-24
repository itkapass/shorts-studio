// src/lib/supabase.js
// Supabase client singleton with safe demo/fallback mode

import { createClient } from '@supabase/supabase-js'

const supabaseUrl  = import.meta.env.VITE_SUPABASE_URL || 'https://placeholder.supabase.co'
const supabaseKey  = import.meta.env.VITE_SUPABASE_ANON_KEY || 'placeholder-anon-key'

export const isSupabaseConfigured = Boolean(
  import.meta.env.VITE_SUPABASE_URL && 
  import.meta.env.VITE_SUPABASE_ANON_KEY &&
  !import.meta.env.VITE_SUPABASE_URL.includes('your-project-id')
)

export const supabase = isSupabaseConfigured
  ? createClient(supabaseUrl, supabaseKey)
  : {
      from: (table) => {
        const chain = {
          select: () => chain,
          insert: async (data) => ({ data, error: null }),
          update: () => chain,
          upsert: () => chain,
          delete: () => chain,
          eq: () => chain,
          order: () => chain,
          limit: () => chain,
          single: async () => ({ data: null, error: null }),
          then: (resolve) => resolve({ data: [], error: null }),
        }
        return chain
      },
      storage: {
        from: () => ({
          getPublicUrl: (path) => ({ data: { publicUrl: `https://placeholder/${path}` } }),
          upload: async () => ({ data: {}, error: null })
        })
      }
    }

