import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import client from "@/lib/api";
import { resolveTenantSlug } from "@/lib/tenant";

const TenantContext = createContext({
  slug: "gbconstruction",
  theme: {},
  setTenantMeta: () => {},
});

const DEFAULT_THEME = {
  primary: "#C41E3A",
  secondary: "#D4AF37",
  background: "#0B0B0B",
  font_display: "Oswald",
  font_body: "Montserrat",
};

export function TenantProvider({ children }) {
  const [slug] = useState(() => resolveTenantSlug());
  const [theme, setTheme] = useState(DEFAULT_THEME);
  const [meta, setMeta] = useState({});

  const setTenantMeta = useCallback((next) => {
    if (!next) return;
    setMeta(next);
    if (next.theme) setTheme({ ...DEFAULT_THEME, ...next.theme });
  }, []);

  useEffect(() => {
    let active = true;
    client
      .get("/tenant/config", { params: { tenant: slug } })
      .then(({ data }) => {
        if (active) setTenantMeta(data);
      })
      .catch(() => {
        // Il tema locale resta un fallback sicuro se il backend non è raggiungibile.
      });
    return () => {
      active = false;
    };
  }, [slug, setTenantMeta]);

  useEffect(() => {
    const root = document.documentElement;
    root.style.setProperty("--brand-primary", theme.primary || DEFAULT_THEME.primary);
    root.style.setProperty("--brand-secondary", theme.secondary || DEFAULT_THEME.secondary);
    root.style.setProperty("--brand-bg", theme.background || DEFAULT_THEME.background);
    if (theme.font_display) {
      root.style.setProperty("--font-display", theme.font_display);
    }
    if (theme.font_body) {
      root.style.setProperty("--font-body", theme.font_body);
    }
  }, [theme]);

  const value = useMemo(
    () => ({ slug, theme, meta, setTenantMeta }),
    [slug, theme, meta, setTenantMeta]
  );

  return <TenantContext.Provider value={value}>{children}</TenantContext.Provider>;
}

export function useTenant() {
  return useContext(TenantContext);
}
