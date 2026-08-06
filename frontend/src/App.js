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

const Landing = lazy(() => import("@/landing/Landing"));
const Login = lazy(() => import("@/dashboard/Login"));
const LegalPage = lazy(() => import("@/legal/LegalPage"));
const DashboardLayout = lazy(() => import("@/dashboard/DashboardLayout"));
const Today = lazy(() => import("@/dashboard/pages/Today"));
const LeadInbox = lazy(() => import("@/dashboard/pages/LeadInbox"));
const LeadDetail = lazy(() => import("@/dashboard/pages/LeadDetail"));
const Pipeline = lazy(() => import("@/dashboard/pages/Pipeline"));
const Sopralluoghi = lazy(() => import("@/dashboard/pages/Sopralluoghi"));
const Preventivi = lazy(() => import("@/dashboard/pages/Preventivi"));
const Cantieri = lazy(() => import("@/dashboard/pages/Cantieri"));
const Report = lazy(() => import("@/dashboard/pages/Report"));
const Settings = lazy(() => import("@/dashboard/pages/Settings"));
const AIArchitectReview = lazy(
  () => import("@/dashboard/pages/AIArchitectReview"),
);
const Prezzario = lazy(() => import("@/dashboard/pages/Prezzario"));
const PrezzarioWizard = lazy(() => import("@/dashboard/pages/PrezzarioWizard"));
const Computi = lazy(() => import("@/dashboard/pages/Computi"));
const ComputoEditor = lazy(() => import("@/dashboard/pages/ComputoEditor"));
const Sal = lazy(() => import("@/dashboard/pages/Sal"));
const Economics = lazy(() => import("@/dashboard/pages/Economics"));
const Campo = lazy(() => import("@/campo/Campo"));

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
                <Route
                  path="/campo"
                  element={
                    <ProtectedRoute>
                      <Campo />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/dashboard"
                  element={
                    <ProtectedRoute>
                      <DashboardLayout />
                    </ProtectedRoute>
                  }
                >
                  <Route index element={<Today />} />
                  <Route path="inbox" element={<LeadInbox />} />
                  <Route path="lead/:id" element={<LeadDetail />} />
                  <Route path="pipeline" element={<Pipeline />} />
                  <Route path="sopralluoghi" element={<Sopralluoghi />} />
                  <Route path="preventivi" element={<Preventivi />} />
                  <Route path="cantieri" element={<Cantieri />} />
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
