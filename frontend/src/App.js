import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider, useAuth } from "@/context/AuthContext";

import Landing from "@/landing/Landing";
import Login from "@/dashboard/Login";
import DashboardLayout from "@/dashboard/DashboardLayout";
import Today from "@/dashboard/pages/Today";
import LeadInbox from "@/dashboard/pages/LeadInbox";
import LeadDetail from "@/dashboard/pages/LeadDetail";
import Pipeline from "@/dashboard/pages/Pipeline";
import Sopralluoghi from "@/dashboard/pages/Sopralluoghi";
import Preventivi from "@/dashboard/pages/Preventivi";
import Cantieri from "@/dashboard/pages/Cantieri";
import Report from "@/dashboard/pages/Report";
import Settings from "@/dashboard/pages/Settings";

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

function App() {
  return (
    <div className="App dark">
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/login" element={<Login />} />
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
              <Route path="report" element={<Report />} />
              <Route path="impostazioni" element={<Settings />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
        <Toaster position="top-right" theme="dark" richColors />
      </AuthProvider>
    </div>
  );
}

export default App;
