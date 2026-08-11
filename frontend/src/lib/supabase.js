import { createClient } from "@supabase/supabase-js";
import { browserSessionStorage, captureAuthCallback } from "./authCallback";

// Supabase puo ricadere sul Site URL quando il redirect dell'invito non e
// ancora allowlistato. Conserviamo subito il tipo di callback prima che il
// client Auth ripulisca hash/query, cosi anche /login puo completare l'invito.
if (typeof window !== "undefined") {
  captureAuthCallback(window.location, browserSessionStorage());
}

export const SUPABASE_URL = process.env.REACT_APP_SUPABASE_URL || "";
// La publishable key e l'equivalente moderno della legacy anon key per il
// browser. Manteniamo il fallback durante la migrazione dei deployment.
const publishable =
  process.env.REACT_APP_SUPABASE_PUBLISHABLE_KEY ||
  process.env.REACT_APP_SUPABASE_ANON_KEY ||
  "";

export const supabaseConfigured = Boolean(SUPABASE_URL && publishable);

export const supabase = supabaseConfigured
  ? createClient(SUPABASE_URL, publishable, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
      },
    })
  : null;
