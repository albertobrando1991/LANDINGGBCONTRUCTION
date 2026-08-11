import "@/App.css";
import { lazy, Suspense } from "react";
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  Outlet,
} from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { TenantProvider } from "@/context/TenantContext";
import { loadComputiPage, loadComputoEditorPage } from "@/lib/computiPrefetch";

const Landing = lazy(() => import("@/landing/Landing"));
const Login = lazy(() => import("@/dashboard/Login"));
const SetPassword = lazy(() => import("@/portal/SetPassword"));
const AuthConfirm = lazy(() => import("@/portal/AuthConfirm"));
const LegalPage = lazy(() => import("@/legal/LegalPage"));
const DashboardLayout = lazy(() => import("@/dashboard/DashboardLayout"));
const Today = lazy(() => import("@/dashboard/pages/Today"));
const LeadInbox = lazy(() => import("@/dashboard/pages/LeadInbox"));
const LeadDetail = lazy(() => import("@/dashboard/pages/LeadDetail"));
const Pipeline = lazy(() => import("@/dashboard/pages/Pipeline"));
const Sopralluoghi = lazy(() => import("@/dashboard/pages/Sopralluoghi"));
const Preventivi = lazy(() => import("@/dashboard/pages/Preventivi"));
const ContractEditor = lazy(() => import("@/dashboard/pages/ContractEditor"));
const Cantieri = lazy(() => import("@/dashboard/pages/Cantieri"));
const Personale = lazy(() => import("@/dashboard/pages/Personale"));
const Report = lazy(() => import("@/dashboard/pages/Report"));
const Settings = lazy(() => import("@/dashboard/pages/Settings"));
const AIArchitectReview = lazy(
  () => import("@/dashboard/pages/AIArchitectReview"),
);
const Prezzario = lazy(() => import("@/dashboard/pages/Prezzario"));
const PrezzarioWizard = lazy(() => import("@/dashboard/pages/PrezzarioWizard"));
const Computi = lazy(loadComputiPage);
const ComputoEditor = lazy(loadComputoEditorPage);
const Sal = lazy(() => import("@/dashboard/pages/Sal"));
const Economics = lazy(() => import("@/dashboard/pages/Economics"));
const Campo = lazy(() => import("@/campo/Campo"));
const ClientPortal = lazy(() => import("@/portal/ClientPortal"));

function RouteFallback() {
  return (
    <div
      className="min-h-screen bg-bg flex items-center justify-center"
      role="status"
      aria-live="polite"
    >
      <div className="font-display uppercase tracking-[0.3em] text-fog text-sm animate-pulse">
        Caricamento…
      </div>
    </div>
  );
}

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading || user === null) {
    return (
      <div className="min-h-screen bg-bg flex items-center justify-center">
        <div className="font-display uppercase tracking-[0.3em] text-fog text-sm animate-pulse">
          Caricamento…
        </div>
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function StaffRoute({ children }) {
  const { user } = useAuth();
  if (user?.role === "client") return <Navigate to="/portal" replace />;
  return children;
}

function ClientRoute({ children }) {
  const { user } = useAuth();
  if (user?.role !== "client") return <Navigate to="/dashboard" replace />;
  return children;
}

function AuthBoundary() {
  return (
    <AuthProvider>
      <Outlet />
    </AuthProvider>
  );
}

function App() {
  return (
    <div className="App dark">
      <TenantProvider>
        <BrowserRouter>
          <Suspense fallback={<RouteFallback />}>
            <Routes>
              <Route path="/" element={<Landing />} />
              <Route
                path="/privacy-policy"
                element={<LegalPage kind="privacy" />}
              />
              <Route
                path="/cookie-policy"
                element={<LegalPage kind="cookie" />}
              />
              <Route element={<AuthBoundary />}>
                <Route path="/login" element={<Login />} />
                <Route path="/auth/confirm" element={<AuthConfirm />} />
                <Route
                  path="/set-password"
                  element={
                    <ProtectedRoute>
                      <SetPassword />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/campo"
                  element={
                    <ProtectedRoute>
                      <StaffRoute>
                        <Campo />
                      </StaffRoute>
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/dashboard"
                  element={
                    <ProtectedRoute>
                      <StaffRoute>
                        <DashboardLayout />
                      </StaffRoute>
                    </ProtectedRoute>
                  }
                >
                  <Route index element={<Today />} />
                  <Route path="inbox" element={<LeadInbox />} />
                  <Route path="lead/:id" element={<LeadDetail />} />
                  <Route path="pipeline" element={<Pipeline />} />
                  <Route path="sopralluoghi" element={<Sopralluoghi />} />
                  <Route path="preventivi" element={<Preventivi />} />
                  <Route
                    path="preventivi/:id/contratto"
                    element={<ContractEditor />}
                  />
                  <Route path="cantieri" element={<Cantieri />} />
                  <Route path="personale" element={<Personale />} />
                  <Route path="prezzario" element={<Prezzario />} />
                  <Route
                    path="prezzario/wizard"
                    element={<PrezzarioWizard />}
                  />
                  <Route path="computi" element={<Computi />} />
                  <Route path="computi/:id" element={<ComputoEditor />} />
                  <Route path="sal" element={<Sal />} />
                  <Route path="economics" element={<Economics />} />
                  <Route path="ai-architect" element={<AIArchitectReview />} />
                  <Route path="report" element={<Report />} />
                  <Route path="impostazioni" element={<Settings />} />
                </Route>
                <Route
                  path="/portal"
                  element={
                    <ProtectedRoute>
                      <ClientRoute>
                        <ClientPortal />
                      </ClientRoute>
                    </ProtectedRoute>
                  }
                />
              </Route>
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </BrowserRouter>
        <Toaster position="top-right" theme="dark" richColors />
      </TenantProvider>
    </div>
  );
}

export default App;
