import { useState } from "react";
import { useNavigate, Navigate } from "react-router-dom";
import { ArrowRight, Loader2 } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { formatApiErrorDetail } from "@/lib/api";

export default function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  if (user) return <Navigate to="/dashboard" replace />;

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
      navigate("/dashboard");
    } catch (err) {
      setError(formatApiErrorDetail(err.response?.data?.detail) || err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center px-6 relative overflow-hidden">
      <div className="absolute inset-0 blueprint-grid opacity-[0.03]" />
      <div className="relative w-full max-w-md">
        <div className="text-center mb-8">
          <div className="w-14 h-14 rounded-full p-[2px] accent-metallic animate-gradient-shift mx-auto mb-4">
            <div className="w-full h-full rounded-full bg-bg flex items-center justify-center font-display font-bold text-ink">GB</div>
          </div>
          <h1 className="font-display font-bold uppercase text-2xl text-ink">Dashboard Staff</h1>
          <p className="font-display uppercase tracking-[0.2em] text-xs text-brand mt-1">GB Construction · Lead Engine</p>
        </div>

        <form onSubmit={submit} className="bg-surface border border-stroke rounded-2xl p-8 space-y-4">
          <div>
            <label className="font-display uppercase text-xs text-fog">Email</label>
            <input data-testid="login-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required
              className="w-full mt-1 bg-bg border border-stroke rounded-xl px-4 py-3 text-ink focus:outline-none focus:border-brand" />
          </div>
          <div>
            <label className="font-display uppercase text-xs text-fog">Password</label>
            <input data-testid="login-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required
              className="w-full mt-1 bg-bg border border-stroke rounded-xl px-4 py-3 text-ink focus:outline-none focus:border-brand" />
          </div>
          {error && <p data-testid="login-error" className="text-brand text-sm">{error}</p>}
          <button data-testid="login-submit" type="submit" disabled={loading}
            className="w-full bg-brand text-white rounded-full py-3 font-display font-semibold uppercase tracking-wider inline-flex items-center justify-center gap-2 hover:scale-[1.02] transition-transform disabled:opacity-60">
            {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <>Accedi <ArrowRight className="w-4 h-4" /></>}
          </button>
          <p className="font-body text-xs text-fog text-center pt-2">
            Demo admin: admin@gbconstruction.it · GBadmin2026!
          </p>
        </form>
      </div>
    </div>
  );
}
