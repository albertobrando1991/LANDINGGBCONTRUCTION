import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Phone, MessageCircle, Mail, ArrowLeft, Sparkles, Loader2, Send,
  AlertTriangle, FileText, MapPin, Home, Brain, Download, ExternalLink, Unlock,
} from "lucide-react";
import { toast } from "sonner";
import client, { BACKEND_URL, formatApiErrorDetail } from "@/lib/api";
import { formatEuro, formatDateTime } from "@/lib/format";
import { buildWhatsappUrl } from "@/lib/whatsapp";
import { STATI, PIPELINE_ORDER, priority, initials } from "@/dashboard/leadMeta";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";

export default function LeadDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [note, setNote] = useState("");
  const [noteType, setNoteType] = useState("nota");

  const { data: lead, isLoading } = useQuery({
    queryKey: ["lead", id],
    queryFn: async () => (await client.get(`/leads/${id}`)).data,
  });

  const patch = useMutation({
    mutationFn: (body) => client.patch(`/leads/${id}`, body),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["lead", id] }); toast.success("Lead aggiornato"); },
    onError: (e) => toast.error(formatApiErrorDetail(e.response?.data?.detail)),
  });

  const addEvent = useMutation({
    mutationFn: (body) => client.post(`/leads/${id}/timeline`, body),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["lead", id] }); setNote(""); toast.success("Aggiunto alla timeline"); },
  });

  const suggest = useMutation({
    mutationFn: () => client.post(`/leads/${id}/suggest`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["lead", id] }); toast.success("Suggerimento AI generato"); },
    onError: (e) => toast.error(formatApiErrorDetail(e.response?.data?.detail)),
  });

  const unlockEmail = useMutation({
    mutationFn: (email) => client.post(`/leads/unlock-email`, { email }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["lead", id] });
      toast.success("Email sbloccata: il cliente può generare un nuovo preventivo.");
    },
    onError: (e) => toast.error(formatApiErrorDetail(e.response?.data?.detail)),
  });

  const aiJobId = lead?.ai_architect_job_id;
  const { data: aiJob } = useQuery({
    queryKey: ["lead-ai-job", aiJobId],
    enabled: Boolean(aiJobId),
    queryFn: async () => (await client.get(`/ai-architect/jobs/${aiJobId}`)).data,
  });

  if (isLoading || !lead) return <div className="text-fog font-display uppercase animate-pulse">Caricamento…</div>;

  const est = lead.estimate?.pacchetti || {};
  const pkg = est[lead.livello] || {};
  const alerts = lead.estimate?.alerts || [];
  const whatsappUrl = buildWhatsappUrl(lead.telefono, lead.nome);

  const aiOutputs = aiJob?.outputs || [];
  const aiLatest = (type) => {
    const items = aiOutputs.filter((o) => o.output_type === type);
    return items[items.length - 1];
  };
  const aiAssetUrl = (url) => (!url ? "" : url.startsWith("http") ? url : `${BACKEND_URL}${url}`);
  const aiConcept = aiLatest("redistributed_2d_plan") || aiLatest("clean_2d_plan");
  const aiTopdown = aiLatest("topdown_3d_plan");
  const aiRenders = aiOutputs.filter((o) => o.output_type === "room_render");
  const aiReport = aiLatest("pdf_report");

  return (
    <div className="space-y-5">
      <button onClick={() => navigate(-1)} className="font-display uppercase text-xs text-fog hover:text-ink inline-flex items-center gap-1">
        <ArrowLeft className="w-4 h-4" /> Indietro
      </button>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* LEFT: cliente */}
        <div className="space-y-5">
          <div className="bg-surface border border-stroke rounded-2xl p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 rounded-full bg-brand/20 text-brand flex items-center justify-center font-display font-bold">{initials(lead.nome)}</div>
              <div>
                <div className="font-display font-bold uppercase text-ink">{lead.nome}</div>
                <div className="font-body text-xs text-fog flex items-center gap-1"><MapPin className="w-3 h-3" /> {lead.citta || "—"}</div>
              </div>
            </div>
            <div className="grid grid-cols-3 gap-2 mb-4">
              <a href={`tel:${lead.telefono}`} className="flex flex-col items-center gap-1 bg-bg border border-stroke rounded-xl py-2 text-fog hover:text-ink hover:border-brand transition-colors"><Phone className="w-4 h-4" /><span className="text-[10px] font-display uppercase">Chiama</span></a>
              {whatsappUrl ? (
                <a href={whatsappUrl} target="_blank" rel="noreferrer" className="flex flex-col items-center gap-1 bg-bg border border-stroke rounded-xl py-2 text-fog hover:text-success hover:border-success transition-colors"><MessageCircle className="w-4 h-4" /><span className="text-[10px] font-display uppercase">WhatsApp</span></a>
              ) : (
                <span className="flex flex-col items-center gap-1 bg-bg border border-stroke rounded-xl py-2 text-fog/40"><MessageCircle className="w-4 h-4" /><span className="text-[10px] font-display uppercase">WhatsApp</span></span>
              )}
              <a href={`mailto:${lead.email}`} className="flex flex-col items-center gap-1 bg-bg border border-stroke rounded-xl py-2 text-fog hover:text-ink hover:border-brand transition-colors"><Mail className="w-4 h-4" /><span className="text-[10px] font-display uppercase">Email</span></a>
            </div>
            <div className="space-y-1 font-body text-xs text-fog">
              <div>📞 {lead.telefono || "—"}</div>
              <div>✉ {lead.email || "—"}</div>
              {lead.indirizzo && (
                <div className="flex items-start gap-1">
                  <MapPin className="w-3 h-3 mt-0.5 shrink-0" /> {lead.indirizzo}
                </div>
              )}
              <div className="capitalize">Origine: {lead.origine} · {formatDateTime(lead.created_at)}</div>
            </div>
            {lead.email && (
              <div className="mt-3 flex items-center justify-between gap-2 bg-bg border border-stroke rounded-xl px-3 py-2">
                <span className="font-body text-[11px] text-fog">
                  {lead.dedup_released
                    ? "Email sbloccata: nuova generazione consentita."
                    : "Limite: un preventivo per email."}
                </span>
                {!lead.dedup_released && (
                  <button
                    onClick={() => unlockEmail.mutate(lead.email)}
                    disabled={unlockEmail.isPending}
                    className="shrink-0 font-display uppercase text-[10px] text-brand hover:text-ink inline-flex items-center gap-1 disabled:opacity-60"
                  >
                    {unlockEmail.isPending ? (
                      <Loader2 className="w-3 h-3 animate-spin" />
                    ) : (
                      <Unlock className="w-3 h-3" />
                    )}
                    Sblocca email
                  </button>
                )}
              </div>
            )}
            <div className="mt-4 flex items-center justify-between bg-bg border border-stroke rounded-xl px-3 py-2">
              <span className="font-display uppercase text-xs text-fog">Lead score</span>
              <span className={`font-display font-bold text-lg ${priority(lead.score).text}`}>{lead.score}/100</span>
            </div>
            <div className="mt-4">
              <Select value={lead.status} onValueChange={(v) => patch.mutate({ status: v })}>
                <SelectTrigger data-testid="lead-status-select" className="bg-bg border-stroke text-ink"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {PIPELINE_ORDER.map((s) => <SelectItem key={s} value={s}>{STATI[s].label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="bg-surface border border-stroke rounded-2xl p-6">
            <h4 className="font-display font-semibold uppercase text-sm text-ink mb-3">Tag</h4>
            <div className="flex flex-wrap gap-2">
              {(lead.tags || []).map((t) => (
                <span key={t} className="font-display uppercase text-[10px] bg-brand/15 text-brand px-3 py-1 rounded-full">{t}</span>
              ))}
              {(!lead.tags || lead.tags.length === 0) && <span className="font-body text-xs text-fog">Nessun tag</span>}
            </div>
          </div>
        </div>

        {/* CENTER: configurazione + stima */}
        <div className="space-y-5">
          <div className="bg-surface border border-stroke rounded-2xl p-6">
            <h4 className="font-display font-semibold uppercase text-sm text-ink mb-4 flex items-center gap-2"><Home className="w-4 h-4 text-brand" /> Dati immobile</h4>
            <div className="grid grid-cols-2 gap-3 font-body text-sm">
              <Info label="Tipo" value={lead.tipo_immobile} />
              <Info label="Superficie" value={`${lead.mq} mq`} />
              <Info label="Intervento" value={lead.livello} />
              <Info label="Bagni" value={lead.bagni} />
              <Info label="Camere" value={lead.camere} />
              <Info label="Stile" value={lead.stile} />
              <Info label="Tempistiche" value={lead.tempistiche} />
              <Info label="File" value={lead.has_files ? "Sì" : "No"} />
            </div>
            <div className="mt-3"><Info label="Ambienti" value={(lead.ambienti || []).join(", ")} /></div>
          </div>

          <div className="bg-surface border border-stroke rounded-2xl p-6">
            <h4 className="font-display font-semibold uppercase text-sm text-ink mb-4 flex items-center gap-2"><FileText className="w-4 h-4 text-brand" /> Stima predittiva</h4>
            <div className="grid grid-cols-3 gap-2 mb-4">
              {["essenziale", "premium", "luxury"].map((k) => (
                <div key={k} className={`rounded-xl p-3 border ${lead.livello === k ? "border-brand bg-brand/10" : "border-stroke bg-bg"}`}>
                  <div className="font-display uppercase text-[10px] text-fog capitalize">{k}</div>
                  <div className="font-display font-bold text-sm text-brand">{formatEuro(est[k]?.range_basso)}</div>
                  <div className="font-body text-[10px] text-fog">{formatEuro(est[k]?.range_alto)}</div>
                </div>
              ))}
            </div>

            {pkg.categorie && (
              <Accordion type="single" collapsible>
                <AccordionItem value="computo" className="border-stroke">
                  <AccordionTrigger data-testid="computo-toggle" className="font-display uppercase text-xs text-ink hover:no-underline">
                    Vedi dettaglio computo ({pkg.n_voci} voci)
                  </AccordionTrigger>
                  <AccordionContent>
                    <div className="space-y-1">
                      {pkg.categorie.map((c) => (
                        <div key={c.categoria} className="flex justify-between font-body text-xs py-1.5 border-b border-stroke/50">
                          <span className="text-fog">{c.categoria} <span className="text-stroke">({c.voci})</span></span>
                          <span className="text-ink">{formatEuro(c.totale)}</span>
                        </div>
                      ))}
                    </div>
                  </AccordionContent>
                </AccordionItem>
              </Accordion>
            )}

            {alerts.length > 0 && (
              <div className="mt-4 space-y-2">
                {alerts.map((a, i) => (
                  <div key={i} className="flex items-start gap-2 bg-bg border border-stroke rounded-xl px-3 py-2">
                    <AlertTriangle className={`w-4 h-4 mt-0.5 shrink-0 ${a.tipo === "warning" ? "text-warning" : "text-fog"}`} />
                    <span className="font-body text-xs text-fog">{a.testo}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {aiJobId && (
            <div className="bg-surface border border-stroke rounded-2xl p-6">
              <div className="flex items-center justify-between mb-4">
                <h4 className="font-display font-semibold uppercase text-sm text-ink flex items-center gap-2">
                  <Brain className="w-4 h-4 text-brand" /> AI Architect
                </h4>
                <button
                  onClick={() => navigate(`/dashboard/ai-architect?job=${aiJobId}`)}
                  className="font-display uppercase text-[10px] text-brand inline-flex items-center gap-1 hover:text-ink"
                >
                  Apri revisione <ExternalLink className="w-3 h-3" />
                </button>
              </div>
              {lead.ai_architect_summary && (
                <p className="font-body text-xs text-fog mb-3">{lead.ai_architect_summary}</p>
              )}
              {aiJob ? (
                <>
                  <div className="grid grid-cols-2 gap-2">
                    {aiConcept?.image_url && (
                      <div>
                        <div className="font-display uppercase text-[9px] text-fog mb-1">Concept 2D</div>
                        <img src={aiAssetUrl(aiConcept.image_url)} alt="Concept 2D" className="w-full rounded-lg border border-stroke bg-bg object-contain max-h-40" />
                      </div>
                    )}
                    {aiTopdown?.image_url && (
                      <div>
                        <div className="font-display uppercase text-[9px] text-fog mb-1">Top-down 3D</div>
                        <img src={aiAssetUrl(aiTopdown.image_url)} alt="Top-down" className="w-full rounded-lg border border-stroke bg-bg object-contain max-h-40" />
                      </div>
                    )}
                  </div>
                  {aiRenders.length > 0 && (
                    <div className="grid grid-cols-3 gap-2 mt-2">
                      {aiRenders.slice(0, 3).map((r) => (
                        <img key={r.id} src={aiAssetUrl(r.image_url)} alt={r.room_name || "Render"} className="w-full aspect-square rounded-lg border border-stroke bg-bg object-cover" />
                      ))}
                    </div>
                  )}
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <span className="font-display uppercase text-[9px] bg-bg border border-stroke rounded-full px-2 py-1 text-fog">
                      Stato: {aiJob.status || "-"}
                    </span>
                    {aiReport?.image_url && (
                      <a href={aiAssetUrl(aiReport.image_url)} target="_blank" rel="noreferrer"
                        className="font-display uppercase text-[10px] text-brand inline-flex items-center gap-1 hover:text-ink">
                        <Download className="w-3 h-3" /> Report PDF
                      </a>
                    )}
                  </div>
                </>
              ) : (
                <p className="font-body text-xs text-fog">Caricamento progetto AI…</p>
              )}
            </div>
          )}
        </div>

        {/* RIGHT: timeline */}
        <div className="space-y-5">
          <div className="bg-surface border border-stroke rounded-2xl p-6">
            <div className="flex items-center justify-between mb-3">
              <h4 className="font-display font-semibold uppercase text-sm text-ink">Prossima azione</h4>
              <button data-testid="ai-suggest" onClick={() => suggest.mutate()} disabled={suggest.isPending}
                className="font-display uppercase text-[10px] bg-brand/15 text-brand px-3 py-1.5 rounded-full inline-flex items-center gap-1 hover:bg-brand/25 transition-colors disabled:opacity-60">
                {suggest.isPending ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />} Suggerisci AI
              </button>
            </div>
            <p className="font-body text-sm text-ink bg-bg border border-stroke rounded-xl p-3 min-h-[60px]">
              {lead.prossima_azione || "Nessun suggerimento. Genera con l'AI."}
            </p>
          </div>

          <div className="bg-surface border border-stroke rounded-2xl p-6">
            <h4 className="font-display font-semibold uppercase text-sm text-ink mb-4">Timeline</h4>
            <Tabs value={noteType} onValueChange={setNoteType}>
              <TabsList className="bg-bg border border-stroke">
                <TabsTrigger value="nota">Nota</TabsTrigger>
                <TabsTrigger value="chiamata">Chiamata</TabsTrigger>
                <TabsTrigger value="messaggio">Messaggio</TabsTrigger>
              </TabsList>
              <TabsContent value={noteType} className="mt-3">
                <div className="flex gap-2">
                  <input data-testid="timeline-input" value={note} onChange={(e) => setNote(e.target.value)}
                    placeholder={`Aggiungi ${noteType}…`}
                    className="flex-1 bg-bg border border-stroke rounded-xl px-3 py-2 text-sm text-ink placeholder:text-fog focus:outline-none focus:border-brand" />
                  <button data-testid="timeline-add" onClick={() => note && addEvent.mutate({ tipo: noteType, testo: note })}
                    className="bg-brand text-white rounded-xl px-3 hover:scale-105 transition-transform"><Send className="w-4 h-4" /></button>
                </div>
              </TabsContent>
            </Tabs>

            <div className="mt-5 space-y-3 max-h-[400px] overflow-y-auto pr-1">
              {(lead.timeline || []).map((ev) => (
                <div key={ev.id} className="relative pl-5 border-l border-stroke">
                  <span className="absolute -left-[5px] top-1 w-2.5 h-2.5 rounded-full bg-brand" />
                  <div className="font-body text-sm text-ink">{ev.testo}</div>
                  <div className="font-body text-[10px] text-fog mt-0.5">{formatDateTime(ev.ts)} {ev.autore ? `· ${ev.autore}` : ""}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Info({ label, value }) {
  return (
    <div>
      <div className="font-display uppercase text-[10px] text-fog">{label}</div>
      <div className="text-ink capitalize">{value ?? "—"}</div>
    </div>
  );
}
