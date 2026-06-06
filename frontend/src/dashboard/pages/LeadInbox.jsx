import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Phone, MessageCircle, Mail, Eye, Search, Trash2, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";
import client, { formatApiErrorDetail } from "@/lib/api";
import { formatEuro, relativeDate } from "@/lib/format";
import { buildWhatsappUrl } from "@/lib/whatsapp";
import { STATI, priority, initials } from "@/dashboard/leadMeta";

const TABS = [
  { key: "tutti", label: "Tutti" },
  { key: "nuovo", label: "Nuovi" },
  { key: "da_contattare", label: "Da contattare" },
  { key: "in_trattativa", label: "In trattativa" },
  { key: "sopralluogo", label: "Sopralluogo" },
  { key: "preventivi", label: "Preventivi" },
  { key: "persi", label: "Persi" },
];

const SOURCES = [
  { key: "tutte", label: "Tutte fonti" },
  { key: "meta_ads", label: "Meta Ads" },
  { key: "landing", label: "Landing" },
  { key: "callback", label: "Callback" },
  { key: "ai_architect", label: "AI Architect" },
];

export default function LeadInbox() {
  const [params] = useSearchParams();
  const [tab, setTab] = useState("tutti");
  const [origine, setOrigine] = useState(params.get("origine") || "tutte");
  const [q, setQ] = useState(params.get("q") || "");
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { user } = useAuth();

  const { data: leads = [], isLoading } = useQuery({
    queryKey: ["leads", tab, q, origine],
    queryFn: async () => (await client.get("/leads", { params: { status: tab, q: q || undefined, origine } })).data,
    refetchInterval: 30000,
  });

  const cleanupTest = useMutation({
    mutationFn: () => client.post("/leads/cleanup-test", { keep_emails: [] }),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["leads"] });
      qc.invalidateQueries({ queryKey: ["lead-counts"] });
      toast.success(`Eliminati ${res.data.deleted} lead di test (mantenuti ${res.data.kept}).`);
    },
    onError: (e) => toast.error(formatApiErrorDetail(e.response?.data?.detail)),
  });

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="font-display font-bold uppercase text-3xl text-ink">Lead Inbox</h1>
        {user?.role === "admin" && (
          <button
            onClick={() => {
              if (window.confirm("Eliminare tutti i lead di test/esempio? Resteranno solo i lead reali (info@alantis.it).")) cleanupTest.mutate();
            }}
            disabled={cleanupTest.isPending}
            className="bg-danger/10 border border-danger/40 text-danger rounded-full px-4 py-2 font-display uppercase text-xs inline-flex items-center gap-2 hover:bg-danger/20 transition-colors disabled:opacity-60"
          >
            {cleanupTest.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
            Pulisci lead di test
          </button>
        )}
      </div>

      <div className="flex flex-wrap gap-2">
        {TABS.map((t) => (
          <button key={t.key} data-testid={`tab-${t.key}`} onClick={() => setTab(t.key)}
            className={`font-display uppercase text-xs tracking-wider px-4 py-2 rounded-full border transition-colors ${
              tab === t.key ? "bg-brand text-white border-brand" : "bg-surface text-fog border-stroke hover:text-ink"
            }`}>
            {t.label}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap gap-2">
        {SOURCES.map((s) => (
          <button key={s.key} onClick={() => setOrigine(s.key)}
            className={`font-display uppercase text-[10px] tracking-wider px-3 py-1.5 rounded-full border transition-colors ${
              origine === s.key ? "bg-ink text-bg border-ink" : "bg-surface text-fog border-stroke hover:text-ink"
            }`}>
            {s.label}
          </button>
        ))}
      </div>

      <div className="flex items-center gap-2 bg-surface border border-stroke rounded-full px-4 py-2 max-w-md">
        <Search className="w-4 h-4 text-fog" />
        <input data-testid="inbox-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Cerca per nome, città, email…"
          className="bg-transparent outline-none text-ink placeholder:text-fog w-full text-sm" />
      </div>

      <div className="bg-surface border border-stroke rounded-2xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-stroke text-left font-display uppercase text-[10px] tracking-wider text-fog">
                <th className="px-4 py-3">Pr.</th>
                <th className="px-4 py-3">Cliente</th>
                <th className="px-4 py-3">Immobile</th>
                <th className="px-4 py-3">Range €</th>
                <th className="px-4 py-3">Stato</th>
                <th className="px-4 py-3">Origine</th>
                <th className="px-4 py-3">Ultimo contatto</th>
                <th className="px-4 py-3">Owner</th>
                <th className="px-4 py-3 text-right">Azioni</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr><td colSpan={9} className="px-4 py-8 text-center text-fog font-display uppercase animate-pulse">Caricamento…</td></tr>
              ) : leads.length === 0 ? (
                <tr><td colSpan={9} className="px-4 py-8 text-center text-fog font-body">Nessun lead in questa vista.</td></tr>
              ) : leads.map((l) => (
                <tr key={l.id} data-testid={`lead-row-${l.id}`} className="border-b border-stroke/60 hover:bg-surface-2/50 transition-colors cursor-pointer"
                  onClick={() => navigate(`/dashboard/lead/${l.id}`)}>
                  <td className="px-4 py-3"><span className={`inline-block w-2.5 h-2.5 rounded-full ${priority(l.score).dot}`} /></td>
                  <td className="px-4 py-3"><div className="font-display uppercase text-xs text-ink">{l.nome}</div><div className="font-body text-[11px] text-fog">{l.citta}</div></td>
                  <td className="px-4 py-3 font-body text-xs text-fog capitalize">{l.tipo_immobile} · {l.mq}mq</td>
                  <td className="px-4 py-3"><div className="font-display text-xs text-brand">{formatEuro(l.range_basso)}</div><div className="font-body text-[10px] text-fog capitalize">{l.livello}</div></td>
                  <td className="px-4 py-3"><span className={`font-display uppercase text-[10px] px-2 py-1 rounded-full ${STATI[l.status]?.bg} ${STATI[l.status]?.color}`}>{STATI[l.status]?.label}</span></td>
                  <td className="px-4 py-3 font-body text-xs text-fog capitalize">{l.origine}</td>
                  <td className="px-4 py-3 font-body text-xs text-fog">{relativeDate(l.last_contact)}</td>
                  <td className="px-4 py-3">{l.owner ? <span className="w-7 h-7 rounded-full bg-brand/20 text-brand inline-flex items-center justify-center font-display text-[10px]">{initials(l.owner)}</span> : <span className="text-fog text-xs">—</span>}</td>
                  <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                    <div className="flex items-center justify-end gap-2 text-fog">
                      <a href={`tel:${l.telefono}`} className="hover:text-ink"><Phone className="w-4 h-4" /></a>
                      {buildWhatsappUrl(l.telefono, l.nome) ? (
                        <a href={buildWhatsappUrl(l.telefono, l.nome)} target="_blank" rel="noreferrer" className="hover:text-success"><MessageCircle className="w-4 h-4" /></a>
                      ) : (
                        <span className="opacity-30"><MessageCircle className="w-4 h-4" /></span>
                      )}
                      <a href={`mailto:${l.email}`} className="hover:text-ink"><Mail className="w-4 h-4" /></a>
                      <button onClick={() => navigate(`/dashboard/lead/${l.id}`)} className="hover:text-brand"><Eye className="w-4 h-4" /></button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
