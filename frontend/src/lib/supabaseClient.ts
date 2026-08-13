import { createClient } from '@supabase/supabase-js'

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY

// Login is optional - most of the app works fully offline against the local
// backend. When these aren't configured (no .env, or a dev checkout before
// the Supabase project values are filled in), auth features quietly turn
// themselves off instead of crashing the whole app at import time.
export const isAuthConfigured = Boolean(SUPABASE_URL && SUPABASE_ANON_KEY)

export const supabase =
  SUPABASE_URL && SUPABASE_ANON_KEY ? createClient(SUPABASE_URL, SUPABASE_ANON_KEY) : null
