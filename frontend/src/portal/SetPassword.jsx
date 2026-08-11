import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { CheckCircle2, KeyRound, Loader2 } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { browserSessionStorage, clearAuthCallback } from "@/lib/authCallback";

export default function SetPassword() {
  const { user, updatePassword } = useAuth();
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    if (password.length < 12) {
      setError("Usa almeno 12 caratteri.");
      return;
    }
    if (password !== confirm) {
      setError("Le password non coincidono.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      await updatePassword(password);
      clearAuthCallback(browserSessionStorage());
      navigate(user?.role === "client" ? "/portal" : "/dashboard", { replace: true });
    } catch (err) {
      setError(err.message || "Impossibile impostare la password.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative grid min-h-screen place-items-center overflow-hidden bg-bg px-5">
      <div className="blueprint-grid absolute inset-0 opacity-[0.03]" />
      <div className="relative w-full max-w-md rounded-2xl border border-stroke bg-surface p-7 sm:p-9">
        <div className="grid h-12 w-12 place-items-center rounded-xl bg-brand/10 text-brand">
          <KeyRound className="h-5 w-5" />
        </div>
        <div className="mt-5 font-display text-[10px] uppercase tracking-[0.22em] text-brand">
          Invito GB Construction
        </div>
        <h1 className="mt-2 font-display text-2xl font-bold uppercase text-ink">
          Imposta la tua password
        </h1>
        <p className="mt-3 font-body text-sm leading-6 text-fog">
          Completa l’attivazione dell’area riservata. La password rimane gestita in modo
          sicuro da Supabase Auth.
        </p>
        <form onSubmit={submit} className="mt-6 space-y-4">
          <label className="block space-y-1">
            <span className="font-display text-[10px] uppercase text-fog">Nuova password</span>
            <input
              type="password"
              minLength={12}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              autoComplete="new-password"
              className="w-full rounded-xl border border-stroke bg-bg px-4 py-3 text-ink focus:border-brand focus:outline-none"
            />
          </label>
          <label className="block space-y-1">
            <span className="font-display text-[10px] uppercase text-fog">Conferma password</span>
            <input
              type="password"
              minLength={12}
              value={confirm}
              onChange={(event) => setConfirm(event.target.value)}
              required
              autoComplete="new-password"
              className="w-full rounded-xl border border-stroke bg-bg px-4 py-3 text-ink focus:border-brand focus:outline-none"
            />
          </label>
          {error && <p className="font-body text-sm text-red-400">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-brand px-4 py-3 font-display text-xs font-semibold uppercase text-white disabled:opacity-60"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
            Attiva area riservata
          </button>
        </form>
      </div>
    </div>
  );
}
