import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
} from "react";
import client, { setApiAccessToken } from "@/lib/api";
import { supabase, supabaseConfigured } from "@/lib/supabase";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // null = checking, false = anon, obj = user
  const [loading, setLoading] = useState(true);

  const check = useCallback(async () => {
    try {
      const { data } = await client.get("/auth/me");
      setUser(data);
    } catch {
      setUser(false);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    let subscription;

    const initialize = async () => {
      if (supabaseConfigured) {
        try {
          // La sottoscrizione deve esistere prima di leggere la sessione: i
          // callback invite/recovery vengono risolti in modo asincrono dal
          // client Supabase durante l'inizializzazione.
          const listener = supabase.auth.onAuthStateChange(
            (event, session) => {
              setApiAccessToken(session?.access_token);
              if (event === "SIGNED_OUT") {
                setUser(false);
                setLoading(false);
              } else if (session?.access_token) {
                // Fuori dal callback Auth per evitare lock interni di GoTrue.
                window.setTimeout(() => check(), 0);
              }
            },
          );
          subscription = listener.data.subscription;

          const { data } = await supabase.auth.getSession();
          if (!active) return;
          setApiAccessToken(data.session?.access_token);
        } catch {
          setApiAccessToken(null);
        }
      }
      if (active) await check();
    };

    initialize();
    return () => {
      active = false;
      subscription?.unsubscribe();
    };
  }, [check]);

  const clearSupabaseSession = async () => {
    setApiAccessToken(null);
    if (!supabaseConfigured) return;
    try {
      await supabase.auth.signOut({ scope: "local" });
    } catch {
      /* la sessione locale viene comunque ignorata dal client API */
    }
  };

  const login = async (email, password) => {
    let supabaseVerificationError = null;

    if (supabaseConfigured) {
      try {
        const result = await supabase.auth.signInWithPassword({
          email,
          password,
        });
        if (!result.error && result.data.session?.access_token) {
          setApiAccessToken(result.data.session.access_token);
          try {
            const { data } = await client.get("/auth/me");
            setUser(data);
            return data;
          } catch (error) {
            supabaseVerificationError = error;
          }
        }
      } catch {
        // Se Supabase non e raggiungibile, il login legacy resta operativo.
      }
      await clearSupabaseSession();
    }

    try {
      const { data } = await client.post("/auth/login", { email, password });
      setUser(data);
      return data;
    } catch (error) {
      throw supabaseVerificationError || error;
    }
  };

  const logout = async () => {
    setApiAccessToken(null);
    try {
      await client.post("/auth/logout");
    } catch {
      /* ignore */
    }
    await clearSupabaseSession();
    setUser(false);
  };

  const updatePassword = async (password) => {
    if (!supabaseConfigured || !supabase) {
      throw new Error("Aggiornamento password non disponibile.");
    }
    const { error } = await supabase.auth.updateUser({ password });
    if (error) throw error;
    await check();
  };

  return (
    <AuthContext.Provider
      value={{ user, loading, login, logout, updatePassword, refresh: check }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
