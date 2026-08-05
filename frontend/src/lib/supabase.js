import { createClient } from "@supabase/supabase-js";

export const SUPABASE_URL = process.env.REACT_APP_SUPABASE_URL || "";
const anon = process.env.REACT_APP_SUPABASE_ANON_KEY || "";

export const supabaseConfigured = Boolean(SUPABASE_URL && anon);

export const supabase = supabaseConfigured
  ? createClient(SUPABASE_URL, anon, {
      auth: { persistSession: true, autoRefreshToken: true },
    })
  : null;
