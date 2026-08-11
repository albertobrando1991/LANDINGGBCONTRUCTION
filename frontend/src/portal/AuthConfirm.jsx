import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Loader2, ShieldCheck } from "lucide-react";
import { supabase, supabaseConfigured } from "@/lib/supabase";

const ALLOWED_TYPES = new Set(["invite", "magiclink", "recovery"]);

export default function AuthConfirm() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    const confirm = async () => {
      const token_hash = params.get("token_hash") || "";
      const type = params.get("type") || "";
      if (!supabaseConfigured || !token_hash || !ALLOWED_TYPES.has(type)) {
        setError("Il link non e valido. Richiedine uno nuovo dall'area clienti.");
        return;
      }
      const { error: verificationError } = await supabase.auth.verifyOtp({
        token_hash,
        type,
      });
      if (!active) return;
      if (verificationError) {
        setError(
          "Il link e scaduto o e gia stato utilizzato. Richiedine uno nuovo.",
        );
        return;
      }
      navigate("/set-password", { replace: true });
    };
    confirm();
    return () => {
      active = false;
    };
  }, [navigate, params]);

  return (
    <div className="relative grid min-h-screen place-items-center overflow-hidden bg-bg px-5">
      <div className="blueprint-grid absolute inset-0 opacity-[0.03]" />
      <div className="relative w-full max-w-md rounded-2xl border border-stroke bg-surface p-7 text-center sm:p-9">
        <div className="mx-auto grid h-12 w-12 place-items-center rounded-xl bg-brand/10 text-brand">
          {error ? (
            <ShieldCheck className="h-5 w-5" />
          ) : (
            <Loader2 className="h-5 w-5 animate-spin" />
          )}
        </div>
        <h1 className="mt-5 font-display text-2xl font-bold uppercase text-ink">
          {error ? "Link non disponibile" : "Verifica accesso"}
        </h1>
        <p className="mt-3 font-body text-sm leading-6 text-fog">
          {error || "Stiamo verificando in sicurezza il tuo link GB Construction..."}
        </p>
        {error && (
          <Link
            to="/login"
            className="mt-6 inline-flex rounded-xl bg-brand px-5 py-3 font-display text-xs font-semibold uppercase text-white"
          >
            Vai all'area clienti
          </Link>
        )}
      </div>
    </div>
  );
}
