import { useEffect, useRef, useState } from "react";
import { Outlet, NavLink, useNavigate, useLocation } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Home,
  Inbox,
  KanbanSquare,
  CalendarDays,
  FileText,
  HardHat,
  BarChart3,
  Settings as SettingsIcon,
  Menu,
  Bell,
  LogOut,
  Search,
  X,
  Brain,
  Calculator,
  ListTree,
  FileCheck2,
  Smartphone,
  Landmark,
  UsersRound,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { Avatar } from "@/dashboard/Avatar";
import EmailComposeModal from "@/dashboard/EmailComposeModal";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuLabel,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import client from "@/lib/api";
import { LEAD_AUTO_REFRESH_MS } from "@/lib/leadSync";
import { prefetchComputi } from "@/lib/computiPrefetch";

const NAV = [
  { to: "/dashboard", label: "Oggi", Icon: Home, end: true },
  { to: "/dashboard/inbox", label: "Lead Inbox", Icon: Inbox },
  { to: "/dashboard/pipeline", label: "Pipeline", Icon: KanbanSquare },
  { to: "/dashboard/sopralluoghi", label: "Sopralluoghi", Icon: CalendarDays },
  { to: "/dashboard/preventivi", label: "Preventivi", Icon: FileText },
  { to: "/dashboard/prezzario", label: "Prezzario", Icon: Calculator },
  { to: "/dashboard/computi", label: "Computi", Icon: ListTree },
  { to: "/dashboard/cantieri", label: "Cantieri attivi", Icon: HardHat },
  {
    to: "/dashboard/personale",
    label: "Personale",
    Icon: UsersRound,
    roles: ["owner", "admin", "staff", "operations"],
  },
  {
    to: "/dashboard/sal",
    label: "SAL",
    Icon: FileCheck2,
    roles: ["owner", "admin", "staff", "operations"],
  },
  {
    to: "/dashboard/economics",
    label: "Economics",
    Icon: Landmark,
    roles: ["owner", "admin"],
  },
  {
    to: "/campo",
    label: "Campo",
    Icon: Smartphone,
    roles: ["owner", "admin", "staff", "operations"],
  },
  { to: "/dashboard/ai-architect", label: "AI Architect", Icon: Brain },
  { to: "/dashboard/report", label: "Report", Icon: BarChart3, admin: true },
  {
    to: "/dashboard/impostazioni",
    label: "Impostazioni",
    Icon: SettingsIcon,
    admin: true,
  },
];

const MOBILE_QUICK_NAV = NAV.filter((item) =>
  ["/dashboard", "/dashboard/inbox", "/dashboard/cantieri"].includes(item.to),
);

function SidebarContent({ user, onNav, onComputiIntent }) {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex h-16 shrink-0 items-center gap-3 border-b border-stroke px-6 pr-16">
        <div className="w-9 h-9 rounded-full p-[2px] accent-metallic">
          <div className="w-full h-full rounded-full bg-bg flex items-center justify-center font-display font-bold text-sm text-ink">
            GB
          </div>
        </div>
        <span className="font-display font-bold uppercase text-ink">
          Construction
        </span>
      </div>
      <nav
        className="min-h-0 flex-1 space-y-1 overflow-y-auto overscroll-contain px-3 py-4"
        aria-label="Navigazione dashboard"
        style={{ WebkitOverflowScrolling: "touch" }}
      >
        {NAV.filter(
          (n) =>
            (!n.admin || user?.role === "admin") &&
            (!n.roles || n.roles.includes(user?.role)),
        ).map((n) => (
          <NavLink
            key={n.to}
            to={n.to}
            end={n.end}
            onClick={onNav}
            onPointerEnter={
              n.to === "/dashboard/computi" ? onComputiIntent : undefined
            }
            onPointerDown={
              n.to === "/dashboard/computi" ? onComputiIntent : undefined
            }
            onFocus={
              n.to === "/dashboard/computi" ? onComputiIntent : undefined
            }
            className={({ isActive }) =>
              `flex min-h-12 touch-manipulation items-center gap-3 rounded-xl px-3 py-2.5 font-display text-xs uppercase tracking-wider transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand ${
                isActive
                  ? "bg-brand/15 text-brand"
                  : "text-fog hover:bg-surface-2 hover:text-ink"
              }`
            }
          >
            <n.Icon className="w-4 h-4" aria-hidden="true" /> {n.label}
          </NavLink>
        ))}
      </nav>
      <div className="p-3 border-t border-stroke">
        <div className="flex items-center gap-3 px-2 py-2">
          <Avatar name={user?.name} photo={user?.photo} size={36} />
          <div className="min-w-0">
            <div className="font-display uppercase text-xs text-ink truncate">
              {user?.name}
            </div>
            <div className="font-body text-[10px] text-fog truncate">
              {user?.role}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function MobileBottomNav({ newLeadCount, onOpenMenu, menuOpen }) {
  return (
    <nav
      aria-label="Navigazione rapida mobile"
      className="fixed inset-x-0 bottom-0 z-[80] border-t border-stroke bg-bg/95 px-[env(safe-area-inset-left)] pb-safe backdrop-blur-xl lg:hidden"
    >
      <div className="grid min-h-16 grid-cols-4 px-1">
        {MOBILE_QUICK_NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              `relative flex min-h-14 touch-manipulation flex-col items-center justify-center gap-1 rounded-xl px-1 font-display text-[10px] uppercase tracking-wide focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand ${
                isActive ? "text-brand" : "text-fog active:bg-surface-2"
              }`
            }
          >
            <item.Icon className="h-5 w-5" aria-hidden="true" />
            <span>
              {item.label === "Cantieri attivi" ? "Cantieri" : item.label}
            </span>
            {item.to === "/dashboard/inbox" && newLeadCount > 0 && (
              <span className="absolute right-[22%] top-2 flex h-4 min-w-4 items-center justify-center rounded-full bg-brand px-1 text-[9px] text-white">
                {newLeadCount > 99 ? "99+" : newLeadCount}
              </span>
            )}
          </NavLink>
        ))}
        <button
          type="button"
          onClick={onOpenMenu}
          data-testid="sidebar-toggle-bottom"
          aria-label="Apri tutte le sezioni"
          aria-expanded={menuOpen}
          aria-controls="dashboard-mobile-nav"
          aria-haspopup="dialog"
          className="flex min-h-14 touch-manipulation flex-col items-center justify-center gap-1 rounded-xl px-1 font-display text-[10px] uppercase tracking-wide text-ink active:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
        >
          <Menu className="h-5 w-5" aria-hidden="true" />
          <span>Menu</span>
        </button>
      </div>
    </nav>
  );
}

export default function DashboardLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const drawerRef = useRef(null);
  const drawerCloseRef = useRef(null);
  const drawerReturnFocusRef = useRef(null);
  const { data: leadCounts } = useQuery({
    queryKey: ["lead-counts"],
    queryFn: async () => (await client.get("/leads/counts")).data,
    refetchInterval: LEAD_AUTO_REFRESH_MS,
    refetchOnWindowFocus: true,
    refetchOnReconnect: true,
  });
  const newLeadCount = leadCounts?.counts?.nuovo || 0;

  const warmComputi = () => {
    void prefetchComputi(queryClient);
  };

  useEffect(() => {
    if (location.pathname.startsWith("/dashboard/computi")) return undefined;

    const warm = () => {
      void prefetchComputi(queryClient);
    };
    if (typeof window.requestIdleCallback === "function") {
      const idleId = window.requestIdleCallback(warm, { timeout: 1500 });
      return () => window.cancelIdleCallback?.(idleId);
    }

    const timeoutId = window.setTimeout(warm, 800);
    return () => window.clearTimeout(timeoutId);
  }, [location.pathname, queryClient]);

  const crumb =
    NAV.find((n) => n.to === location.pathname)?.label ||
    (location.pathname.includes("/lead/") ? "Scheda lead" : "Dashboard");

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  const openMobileDrawer = (event) => {
    drawerReturnFocusRef.current = event.currentTarget;
    setOpen(true);
  };

  useEffect(() => {
    if (!open) return undefined;
    const toggleButton = drawerReturnFocusRef.current;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    drawerCloseRef.current?.focus();

    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setOpen(false);
        return;
      }
      if (event.key !== "Tab" || !drawerRef.current) return;
      const focusable = drawerRef.current.querySelectorAll(
        'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = previousOverflow;
      toggleButton?.focus();
    };
  }, [open]);

  return (
    <div className="min-h-screen bg-bg flex">
      {/* Sidebar desktop */}
      <aside className="hidden lg:flex w-64 shrink-0 border-r border-stroke bg-surface flex-col fixed inset-y-0">
        <SidebarContent user={user} onComputiIntent={warmComputi} />
      </aside>

      {/* Mobile drawer */}
      {open && (
        <div
          className="fixed inset-0 z-[100] flex lg:hidden"
          role="presentation"
        >
          <button
            type="button"
            tabIndex={-1}
            aria-label="Chiudi menu dashboard"
            className="absolute inset-0 touch-manipulation bg-black/70 backdrop-blur-[2px]"
            onClick={() => setOpen(false)}
          />
          <aside
            id="dashboard-mobile-nav"
            ref={drawerRef}
            className="relative h-[100dvh] w-[min(20rem,calc(100vw-2rem))] max-w-[88vw] overflow-hidden border-r border-stroke bg-surface pb-safe pt-safe shadow-2xl"
            role="dialog"
            aria-modal="true"
            aria-label="Menu dashboard"
          >
            <button
              ref={drawerCloseRef}
              type="button"
              onClick={() => setOpen(false)}
              aria-label="Chiudi menu dashboard"
              className="absolute right-2 top-[max(0.5rem,env(safe-area-inset-top))] z-10 inline-flex min-h-12 min-w-12 touch-manipulation items-center justify-center rounded-xl text-fog active:bg-surface-2 active:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
            >
              <X className="h-6 w-6" aria-hidden="true" />
            </button>
            <SidebarContent
              user={user}
              onNav={() => setOpen(false)}
              onComputiIntent={warmComputi}
            />
          </aside>
        </div>
      )}

      <div className="flex-1 lg:ml-64 min-w-0">
        {/* Topbar */}
        <header className="sticky top-0 z-[70] flex min-h-16 items-center justify-between border-b border-stroke bg-bg/95 py-2 pl-[max(0.5rem,env(safe-area-inset-left))] pr-[max(0.75rem,env(safe-area-inset-right))] pt-[max(0.5rem,env(safe-area-inset-top))] backdrop-blur-md md:px-8 md:py-0">
          <div className="flex min-w-0 items-center gap-1 sm:gap-3">
            <button
              type="button"
              className="relative z-10 inline-flex min-h-12 min-w-12 shrink-0 touch-manipulation items-center justify-center rounded-xl border border-stroke bg-surface text-ink shadow-sm active:scale-95 active:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand lg:hidden"
              onClick={openMobileDrawer}
              data-testid="sidebar-toggle"
              aria-label="Apri menu dashboard"
              aria-expanded={open}
              aria-controls="dashboard-mobile-nav"
              aria-haspopup="dialog"
            >
              <Menu className="w-6 h-6" aria-hidden="true" />
            </button>
            <div className="min-w-0 truncate font-display text-[11px] uppercase tracking-wider text-fog sm:text-sm">
              <span className="hidden sm:inline">
                Dashboard <span className="mx-1 text-stroke">/</span>{" "}
              </span>
              <span className="text-ink">{crumb}</span>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-1 sm:gap-3">
            <div className="hidden md:flex items-center gap-2 bg-surface border border-stroke rounded-full px-4 py-2 text-fog text-sm w-64">
              <Search className="w-4 h-4" aria-hidden="true" />
              <label htmlFor="dashboard-search" className="sr-only">
                Cerca lead o città
              </label>
              <input
                id="dashboard-search"
                type="search"
                placeholder="Cerca lead, città…"
                className="bg-transparent outline-none text-ink placeholder:text-fog w-full text-sm"
                onKeyDown={(e) =>
                  e.key === "Enter" &&
                  e.target.value &&
                  navigate(
                    `/dashboard/inbox?q=${encodeURIComponent(e.target.value)}`,
                  )
                }
              />
            </div>
            <button
              type="button"
              className="relative inline-flex min-h-11 min-w-11 touch-manipulation items-center justify-center rounded-xl text-fog hover:text-ink active:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
              onClick={() => navigate("/dashboard/inbox?status=nuovo")}
              aria-label={
                newLeadCount
                  ? `${newLeadCount} nuovi lead`
                  : "Nessun nuovo lead"
              }
            >
              <Bell className="w-5 h-5" aria-hidden="true" />
              {newLeadCount > 0 && (
                <span className="absolute -top-1 -right-1 min-w-4 h-4 px-1 rounded-full bg-brand text-white text-[9px] flex items-center justify-center">
                  {newLeadCount > 99 ? "99+" : newLeadCount}
                </span>
              )}
            </button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  type="button"
                  data-testid="account-menu"
                  aria-label="Apri menu account"
                  className="inline-flex min-h-11 min-w-11 touch-manipulation items-center justify-center overflow-hidden rounded-full border border-stroke focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
                >
                  <Avatar name={user?.name} photo={user?.photo} size={36} />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                align="end"
                className="bg-surface border-stroke"
              >
                <DropdownMenuLabel className="text-ink">
                  {user?.name}
                </DropdownMenuLabel>
                <DropdownMenuSeparator className="bg-stroke" />
                <DropdownMenuItem
                  data-testid="logout-btn"
                  onClick={handleLogout}
                  className="text-fog focus:text-ink cursor-pointer"
                >
                  <LogOut className="w-4 h-4 mr-2" /> Esci
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>

        <main className="mx-auto max-w-7xl p-3 pb-24 sm:p-4 sm:pb-24 md:p-8 lg:pb-8">
          <Outlet />
        </main>
      </div>

      <MobileBottomNav
        newLeadCount={newLeadCount}
        onOpenMenu={openMobileDrawer}
        menuOpen={open}
      />

      <EmailComposeModal />
    </div>
  );
}
