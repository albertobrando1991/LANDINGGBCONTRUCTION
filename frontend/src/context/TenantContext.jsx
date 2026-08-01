import { createContext, useContext, useEffect, useMemo, useState } from "react";

const TenantContext = createContext({
  slug: "gbconstruction",
  theme: {},
  setTenantMeta: () => {},
});

function slugFromLocation() {
  if (typeof window === "undefined") return "gbconstruction";
  const params = new URLSearchParams(window.location.search);
  const q = (params.get("tenant") || "").toLowerCase();
  if (q) return q;

  const host = window.location.hostname.toLowerCase();
  const base = (process.env.REACT_APP_BASE_DOMAIN || "alantis.it").toLowerCase();
  if (host.endsWith("." + base)) {
    const slug = host.slice(0, -(base.length + 1));
    if (slug && !slug.includes(".")) return slug;
  }
  return "gbconstruction";
}

const DEFAULT_THEME = {
  primary: "#C41E3A",
  secondary: "#D4AF37",
  background: "#0B0B0B",
  font_display: "Oswald",
  font_body: "Montserrat",
};

export function TenantProvider({ children }) {
  const [slug] = useState(() => slugFromLocation());
  const [theme, setTheme] = useState(DEFAULT_THEME);
  const [meta, setMeta] = useState({});

  const setTenantMeta = (next) => {
    if (!next) return;
    setMeta(next);
    if (next.theme) setTheme({ ...DEFAULT_THEME, ...next.theme });
  };

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
    [slug, theme, meta]
  );

  return <TenantContext.Provider value={value}>{children}</TenantContext.Provider>;
}

export function useTenant() {
  return useContext(TenantContext);
}
