import { createContext, useContext, useEffect, useState, useCallback } from "react";
import client from "@/lib/api";

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
    check();
  }, [check]);

  const login = async (email, password) => {
    const { data } = await client.post("/auth/login", { email, password });
    setUser(data);
    return data;
  };

  const logout = async () => {
    try {
      await client.post("/auth/logout");
    } catch {
      /* ignore */
    }
    setUser(false);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, refresh: check }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
