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

// FIXED: when an Edge Function returns a non-2xx status, supabase-js does
// NOT put the function's own JSON error body in `data` — it throws a
// FunctionsHttpError whose useful content is behind `error.context` (the
// raw Response), confirmed straight from @supabase/functions-js's own
// source. Every call site that just did `data?.error || error?.message`
// only ever showed the generic "Edge Function returned a non-2xx status
// code" — this is why the retryable-503 fix (see generate-storyboard)
// wasn't visibly reaching users; the specific reason was always being
// discarded. Use this everywhere an Edge Function call might fail.
export async function getFunctionErrorMessage(error, data, fallback) {
  if (data?.error) return data.error
  if (error && typeof error?.context?.json === 'function') {
    try {
      const body = await error.context.json()
      if (body?.error) return body.error
    } catch {
      // context wasn't JSON (e.g. a network-level FunctionsFetchError) — fall through
    }
  }
  return error?.message || fallback || 'Something went wrong calling the Edge Function.'
}

