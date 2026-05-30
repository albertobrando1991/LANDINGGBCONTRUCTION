import { useState } from "react";
import { Outlet, NavLink, useNavigate, useLocation } from "react-router-dom";
import {
  Home, Inbox, KanbanSquare, CalendarDays, FileText, HardHat,
  BarChart3, Settings as SettingsIcon, Menu, Bell, LogOut, Search, X,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { Avatar } from "@/dashboard/Avatar";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
  DropdownMenuLabel, DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";

const NAV = [
  { to: "/dashboard", label: "Oggi", Icon: Home, end: true },
  { to: "/dashboard/inbox", label: "Lead Inbox", Icon: Inbox },
  { to: "/dashboard/pipeline", label: "Pipeline", Icon: KanbanSquare },
  { to: "/dashboard/sopralluoghi", label: "Sopralluoghi", Icon: CalendarDays },
  { to: "/dashboard/preventivi", label: "Preventivi", Icon: FileText },
  { to: "/dashboard/cantieri", label: "Cantieri attivi", Icon: HardHat },
  { to: "/dashboard/report", label: "Report", Icon: BarChart3, admin: true },
  { to: "/dashboard/impostazioni", label: "Impostazioni", Icon: SettingsIcon, admin: true },
];

function SidebarContent({ user, onNav }) {
  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-3 px-6 h-16 border-b border-stroke">
        <div className="w-9 h-9 rounded-full p-[2px] accent-metallic">
          <div className="w-full h-full rounded-full bg-bg flex items-center justify-center font-display font-bold text-sm text-ink">GB</div>
        </div>
        <span className="font-display font-bold uppercase text-ink">Construction</span>
      </div>
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {NAV.filter((n) => !n.admin || user?.role === "admin").map((n) => (
          <NavLink key={n.to} to={n.to} end={n.end} onClick={onNav}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-xl font-display uppercase text-xs tracking-wider transition-colors ${
                isActive ? "bg-brand/15 text-brand" : "text-fog hover:bg-surface-2 hover:text-ink"
              }`}>
            <n.Icon className="w-4 h-4" /> {n.label}
          </NavLink>
        ))}
      </nav>
      <div className="p-3 border-t border-stroke">
        <div className="flex items-center gap-3 px-2 py-2">
          <Avatar name={user?.name} photo={user?.photo} size={36} />
          <div className="min-w-0">
            <div className="font-display uppercase text-xs text-ink truncate">{user?.name}</div>
            <div className="font-body text-[10px] text-fog truncate">{user?.role}</div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function DashboardLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [open, setOpen] = useState(false);

  const crumb = NAV.find((n) => n.to === location.pathname)?.label ||
    (location.pathname.includes("/lead/") ? "Scheda lead" : "Dashboard");

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <div className="min-h-screen bg-bg flex">
      {/* Sidebar desktop */}
      <aside className="hidden lg:flex w-64 shrink-0 border-r border-stroke bg-surface flex-col fixed inset-y-0">
        <SidebarContent user={user} />
      </aside>

      {/* Mobile drawer */}
      {open && (
        <div className="lg:hidden fixed inset-0 z-50 flex">
          <div className="absolute inset-0 bg-black/60" onClick={() => setOpen(false)} />
          <aside className="relative w-64 bg-surface border-r border-stroke">
            <button onClick={() => setOpen(false)} className="absolute top-4 right-4 text-fog"><X className="w-5 h-5" /></button>
            <SidebarContent user={user} onNav={() => setOpen(false)} />
          </aside>
        </div>
      )}

      <div className="flex-1 lg:ml-64 min-w-0">
        {/* Topbar */}
        <header className="h-16 sticky top-0 z-40 bg-bg/90 backdrop-blur-md border-b border-stroke flex items-center justify-between px-4 md:px-8">
          <div className="flex items-center gap-3">
            <button className="lg:hidden text-ink" onClick={() => setOpen(true)} data-testid="sidebar-toggle"><Menu className="w-6 h-6" /></button>
            <div className="font-display uppercase tracking-wider text-sm text-fog">
              Dashboard <span className="text-stroke mx-1">/</span> <span className="text-ink">{crumb}</span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden md:flex items-center gap-2 bg-surface border border-stroke rounded-full px-4 py-2 text-fog text-sm w-64">
              <Search className="w-4 h-4" />
              <input placeholder="Cerca lead, città…" className="bg-transparent outline-none text-ink placeholder:text-fog w-full text-sm"
                onKeyDown={(e) => e.key === "Enter" && e.target.value && navigate(`/dashboard/inbox?q=${encodeURIComponent(e.target.value)}`)} />
            </div>
            <button className="relative text-fog hover:text-ink"><Bell className="w-5 h-5" /><span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-brand text-white text-[9px] flex items-center justify-center">3</span></button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button data-testid="account-menu" className="rounded-full overflow-hidden border border-stroke">
                  <Avatar name={user?.name} photo={user?.photo} size={36} />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="bg-surface border-stroke">
                <DropdownMenuLabel className="text-ink">{user?.name}</DropdownMenuLabel>
                <DropdownMenuSeparator className="bg-stroke" />
                <DropdownMenuItem data-testid="logout-btn" onClick={handleLogout} className="text-fog focus:text-ink cursor-pointer">
                  <LogOut className="w-4 h-4 mr-2" /> Esci
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>

        <main className="p-4 md:p-8 max-w-7xl mx-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
