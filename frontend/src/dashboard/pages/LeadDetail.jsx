import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Phone, MessageCircle, Mail, ArrowLeft, Sparkles, Loader2, Send,
  AlertTriangle, FileText, MapPin, Home, Brain, Download, ExternalLink, Unlock, Trash2,
  Building2,
} from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";
import client, { BACKEND_URL, formatApiErrorDetail } from "@/lib/api";
import { formatArrivalDateTime, formatEuro, formatDateTime } from "@/lib/format";
import { buildWhatsappUrl } from "@/lib/whatsapp";
import { openEmailCompose } from "@/lib/emailCompose";
import { refreshLeadViews } from "@/lib/leadSync";
import { normalizeLeadList } from "@/lib/leadData";
import { STATI, PIPELINE_ORDER, priority, initials } from "@/dashboard/leadMeta";
import LeadPortalAccess from "@/dashboard/LeadPortalAccess";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";

export default function LeadDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { user } = useAuth();
  const [note, setNote] = useState("");
  const [noteType, setNoteType] = useState("nota");

  const { data: lead, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["lead", id],
    queryFn: async () => (await client.get(`/leads/${id}`)).data,
  });

  const { data: commercial = { preventivo: null, cantiere: null } } = useQuery({
    queryKey: ["lead-commerciale", id],
    queryFn: async () => (await client.get(`/leads/${id}/commerciale`)).data,
  });

  const patch = useMutation({
    mutationFn: async (body) => (await client.patch(`/leads/${id}`, body)).data,
    onSuccess: (updatedLead) => {
      refreshLeadViews(qc, {
        leadId: id,
        updatedLead,
        includeAppointments: true,
      });
      toast.success("Lead aggiornato");
    },
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

  const removeLead = useMutation({
    mutationFn: () => client.delete(`/leads/${id}/with-artifacts`),
    onSuccess: (response) => {
      qc.invalidateQueries({ queryKey: ["lead-counts"] });
      const deleted = response?.data || {};
      toast.success(
        `Lead eliminato con ${deleted.preventivi || 0} preventivi e ${deleted.computi || 0} computi`,
      );
      navigate("/dashboard/inbox");
    },
    onError: (e) => toast.error(formatApiErrorDetail(e.response?.data?.detail)),
  });

  const createCantiere = useMutation({
    mutationFn: async (preventivoId) =>
      (
        await client.post(`/leads/${id}/cantiere-da-preventivo`, {
          preventivo_id: preventivoId,
        })
      ).data,
    onSuccess: (created) => {
      void qc.invalidateQueries({ queryKey: ["lead", id] });
      void qc.invalidateQueries({ queryKey: ["lead-commerciale", id] });
      void qc.invalidateQueries({ queryKey: ["cantieri"] });
      toast.success("Cantiere attivo creato dal preventivo confermato");
      navigate(`/dashboard/cantieri/${created.cantiere_id}`);
    },
    onError: (e) => toast.error(formatApiErrorDetail(e.response?.data?.detail)),
  });

  const openPreventivoPdf = useMutation({
    mutationFn: async (preventivoId) =>
      (
        await client.get(`/preventivi/${preventivoId}/pdf`, {
          responseType: "blob",
        })
      ).data,
    onSuccess: (blob) => {
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.target = "_blank";
      anchor.rel = "noopener noreferrer";
      anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 60000);
    },
    onError: (e) => toast.error(formatApiErrorDetail(e.response?.data?.detail)),
  });

  const aiJobId = lead?.ai_architect_job_id;
  const { data: aiJob } = useQuery({
    queryKey: ["lead-ai-job", aiJobId],
    enabled: Boolean(aiJobId),
    queryFn: async () => (await client.get(`/ai-architect/jobs/${aiJobId}`)).data,
  });

  if (isLoading) return <div className="text-fog font-display uppercase animate-pulse">Caricamento…</div>;
  if (isError || !lead) {
    return (
      <div className="bg-surface border border-danger/40 rounded-2xl p-6 space-y-3">
        <div className="font-display font-semibold uppercase text-danger">
          Impossibile aprire la scheda lead
        </div>
        <p className="font-body text-sm text-fog">
          {formatApiErrorDetail(error?.response?.data?.detail)}
        </p>
        <button
          type="button"
          onClick={() => refetch()}
          className="rounded-full bg-brand px-4 py-2 font-display text-xs uppercase text-white"
        >
          Riprova
        </button>
      </div>
    );
  }

  const est = lead.estimate?.pacchetti || {};
  const pkg = est[lead.livello] || {};
  const alerts = normalizeLeadList(lead.estimate?.alerts);
  const ambienti = normalizeLeadList(lead.ambienti);
  const tags = normalizeLeadList(lead.tags);
  const categorie = normalizeLeadList(pkg.categorie);
  const timeline = normalizeLeadList(lead.timeline);
  const whatsappUrl = buildWhatsappUrl(lead.telefono, lead.nome);
  const preventivoConfermato = commercial?.preventivo;
  const cantiereAttivo = commercial?.cantiere;

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

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
        {/* LEFT: cliente */}
        <div className="space-y-5 min-w-0">
          <div className="bg-surface border border-stroke rounded-2xl p-4 sm:p-6 min-w-0">
            <div className="flex items-center gap-3 mb-4 min-w-0">
              <div className="w-12 h-12 rounded-full bg-brand/20 text-brand flex items-center justify-center font-display font-bold shrink-0">{initials(lead.nome)}</div>
              <div className="min-w-0 flex-1">
                <div className="font-display font-bold uppercase text-ink text-base sm:text-lg truncate">{lead.nome}</div>
                <div className="font-body text-xs text-fog flex items-center gap-1 truncate"><MapPin className="w-3 h-3 shrink-0" /> {lead.citta || "—"}</div>
              </div>
            </div>
            <div className="grid grid-cols-3 gap-2 mb-4">
              <a href={`tel:${lead.telefono}`} className="flex flex-col items-center gap-1 bg-bg border border-stroke rounded-xl py-2 px-1 text-fog hover:text-ink hover:border-brand transition-colors min-w-0"><Phone className="w-4 h-4 shrink-0" /><span className="text-[10px] font-display uppercase truncate">Chiama</span></a>
              {whatsappUrl ? (
                <a href={whatsappUrl} target="_blank" rel="noreferrer" className="flex flex-col items-center gap-1 bg-bg border border-stroke rounded-xl py-2 px-1 text-fog hover:text-success hover:border-success transition-colors min-w-0"><MessageCircle className="w-4 h-4 shrink-0" /><span className="text-[10px] font-display uppercase truncate">WhatsApp</span></a>
              ) : (
                <span className="flex flex-col items-center gap-1 bg-bg border border-stroke rounded-xl py-2 px-1 text-fog/40 min-w-0"><MessageCircle className="w-4 h-4 shrink-0" /><span className="text-[10px] font-display uppercase truncate">WhatsApp</span></span>
              )}
              {lead.email ? (
                <button type="button" onClick={() => openEmailCompose({ leadId: lead.id, email: lead.email, nome: lead.nome })} className="flex flex-col items-center gap-1 bg-bg border border-stroke rounded-xl py-2 px-1 text-fog hover:text-ink hover:border-brand transition-colors min-w-0"><Mail className="w-4 h-4 shrink-0" /><span className="text-[10px] font-display uppercase truncate">Email</span></button>
              ) : (
                <span className="flex flex-col items-center gap-1 bg-bg border border-stroke rounded-xl py-2 px-1 text-fog/40 min-w-0"><Mail className="w-4 h-4 shrink-0" /><span className="text-[10px] font-display uppercase truncate">Email</span></span>
              )}
            </div>
            <div className="space-y-1.5 font-body text-xs text-fog min-w-0">
              <div className="truncate">📞 {lead.telefono || "—"}</div>
              <div className="break-all">✉ {lead.email || "—"}</div>
              {lead.indirizzo && (
                <div className="flex items-start gap-1 break-words">
                  <MapPin className="w-3 h-3 mt-0.5 shrink-0" /> {lead.indirizzo}
                </div>
              )}
              <div className="truncate"><span className="capitalize">Origine: {lead.origine}</span> · Arrivato il {formatArrivalDateTime(lead.data_arrivo || lead.created_at)}</div>
            </div>
            {lead.email && (
              <div className="mt-3 flex flex-wrap sm:flex-nowrap items-center justify-between gap-2 bg-bg border border-stroke rounded-xl px-3 py-2 min-w-0">
                <span className="font-body text-[11px] text-fog min-w-0 leading-snug">
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
            <LeadPortalAccess leadId={lead.id} email={lead.email} />
            <div className="mt-4 flex items-center justify-between bg-bg border border-stroke rounded-xl px-3 py-2 min-w-0">
              <span className="font-display uppercase text-xs text-fog">Lead score</span>
              <span className={`font-display font-bold text-lg ${priority(lead.score).text}`}>{lead.score}/100</span>
            </div>
            <div className="mt-4 min-w-0">
              <Select value={lead.status} onValueChange={(v) => patch.mutate({ status: v })}>
                <SelectTrigger data-testid="lead-status-select" className="bg-bg border-stroke text-ink min-w-0"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {PIPELINE_ORDER.map((s) => <SelectItem key={s} value={s}>{STATI[s].label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            {lead.status === "preventivo_preparazione" && (
              <button
                type="button"
                onClick={() =>
                  navigate(`/dashboard/computi?lead=${encodeURIComponent(lead.id)}&import=1`)
                }
                className="mt-3 w-full rounded-xl bg-brand px-4 py-3 font-display text-xs uppercase tracking-wider text-white hover:brightness-110"
              >
                Prepara preventivo per il cliente
              </button>
            )}
          </div>

          <div className="bg-surface border border-stroke rounded-2xl p-4 sm:p-6 min-w-0">
            <h4 className="font-display font-semibold uppercase text-sm text-ink mb-3">Tag</h4>
            <div className="flex flex-wrap gap-2">
              {tags.map((t) => (
                <span key={t} className="font-display uppercase text-[10px] bg-brand/15 text-brand px-3 py-1 rounded-full break-words">{t}</span>
              ))}
              {tags.length === 0 && <span className="font-body text-xs text-fog">Nessun tag</span>}
            </div>
          </div>

          {user?.role === "admin" && (
            <button
              onClick={() => {
                if (
                  window.confirm(
                    `Eliminare definitivamente il lead di ${lead.nome}, i preventivi e i computi collegati?`,
                  )
                )
                  removeLead.mutate();
              }}
              disabled={removeLead.isPending}
              className="w-full bg-danger/10 border border-danger/40 text-danger rounded-2xl py-3 font-display uppercase text-xs inline-flex items-center justify-center gap-2 hover:bg-danger/20 transition-colors disabled:opacity-60"
            >
              {removeLead.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
              Elimina lead
            </button>
          )}
        </div>

        {/* CENTER: configurazione + stima */}
        <div className="space-y-5 min-w-0">
          <div className="bg-surface border border-stroke rounded-2xl p-4 sm:p-6 min-w-0">
            <h4 className="font-display font-semibold uppercase text-sm text-ink mb-4 flex items-center gap-2"><Home className="w-4 h-4 text-brand shrink-0" /> Dati immobile</h4>
            <div className="grid grid-cols-2 gap-3 sm:gap-4 font-body text-sm min-w-0">
              <Info label="Tipo" value={lead.tipo_immobile} />
              <Info label="Superficie" value={`${lead.mq} mq`} />
              <Info label="Ristrutturazione" value={lead.tipo_ristrutturazione} />
              <Info label="Stato immobile" value={lead.stato_immobile} />
              <Info label="Budget indicativo" value={lead.budget_indicativo} />
              <Info label="Livello stima" value={lead.livello} />
              <Info label="Bagni" value={lead.bagni} />
              <Info label="Camere" value={lead.camere} />
              <Info label="Stile" value={lead.stile} />
              <Info label="Tempistiche" value={lead.tempistiche} />
              <Info label="File" value={lead.has_files ? "Sì" : "No"} />
            </div>
            <div className="mt-3 min-w-0"><Info label="Ambienti" value={ambienti.join(", ")} /></div>
          </div>

          <div className="bg-surface border border-stroke rounded-2xl p-4 sm:p-6 min-w-0">
            <h4 className="font-display font-semibold uppercase text-sm text-ink mb-4 flex items-center gap-2"><FileText className="w-4 h-4 text-brand shrink-0" /> Stima predittiva</h4>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mb-4 min-w-0">
              {["essenziale", "premium", "luxury"].map((k) => (
                <div key={k} className={`rounded-xl p-2.5 sm:p-3 border min-w-0 ${lead.livello === k ? "border-brand bg-brand/10" : "border-stroke bg-bg"}`}>
                  <div className="font-display uppercase text-[10px] text-fog capitalize truncate">{k}</div>
                  <div className="font-display font-bold text-xs sm:text-sm text-brand truncate">{formatEuro(est[k]?.range_basso)}</div>
                  <div className="font-body text-[10px] text-fog truncate">{formatEuro(est[k]?.range_alto)}</div>
                </div>
              ))}
            </div>

            {categorie.length > 0 && (
              <Accordion type="single" collapsible className="min-w-0">
                <AccordionItem value="computo" className="border-stroke">
                  <AccordionTrigger data-testid="computo-toggle" className="font-display uppercase text-xs text-ink hover:no-underline">
                    Vedi dettaglio computo ({pkg.n_voci} voci)
                  </AccordionTrigger>
                  <AccordionContent>
                    <div className="space-y-1 min-w-0">
                      {categorie.map((c) => (
                        <div key={c.categoria} className="flex justify-between items-center font-body text-xs py-1.5 border-b border-stroke/50 gap-2 min-w-0">
                          <span className="text-fog truncate min-w-0">{c.categoria} <span className="text-stroke">({c.voci})</span></span>
                          <span className="text-ink shrink-0 font-medium">{formatEuro(c.totale)}</span>
                        </div>
                      ))}
                    </div>
                  </AccordionContent>
                </AccordionItem>
              </Accordion>
            )}

            {alerts.length > 0 && (
              <div className="mt-4 space-y-2 min-w-0">
                {alerts.map((a, i) => (
                  <div key={i} className="flex items-start gap-2 bg-bg border border-stroke rounded-xl px-3 py-2 min-w-0">
                    <AlertTriangle className={`w-4 h-4 mt-0.5 shrink-0 ${a.tipo === "warning" ? "text-warning" : "text-fog"}`} />
                    <span className="font-body text-xs text-fog break-words">{a.testo}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {preventivoConfermato && (
            <div className="bg-surface border border-brand/40 rounded-2xl p-4 sm:p-6 min-w-0">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-display uppercase text-[10px] tracking-wider text-brand">
                    Valore confermato ed effettivo
                  </p>
                  <p className="mt-2 font-display text-2xl font-bold text-ink">
                    {formatEuro(preventivoConfermato.totale_documento)}
                  </p>
                  <p className="mt-1 font-body text-xs text-fog">
                    Preventivo {preventivoConfermato.numero} · {preventivoConfermato.stato}
                    {preventivoConfermato.inviato_at
                      ? ` · inviato il ${formatDateTime(preventivoConfermato.inviato_at)}`
                      : ""}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => openPreventivoPdf.mutate(preventivoConfermato.id)}
                  disabled={openPreventivoPdf.isPending}
                  className="inline-flex items-center gap-2 rounded-xl border border-stroke px-3 py-2 font-display text-[10px] uppercase text-ink disabled:opacity-50"
                >
                  {openPreventivoPdf.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Download className="h-4 w-4" />
                  )}
                  Apri PDF
                </button>
              </div>

              {cantiereAttivo?.legacy_mongo_id ? (
                <button
                  type="button"
                  onClick={() =>
                    navigate(`/dashboard/cantieri/${cantiereAttivo.legacy_mongo_id}`)
                  }
                  className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-brand px-4 py-3 font-display text-xs uppercase tracking-wider text-white hover:brightness-110"
                >
                  <Building2 className="h-4 w-4" /> Apri cantiere attivo
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => createCantiere.mutate(preventivoConfermato.id)}
                  disabled={createCantiere.isPending}
                  className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-brand px-4 py-3 font-display text-xs uppercase tracking-wider text-white hover:brightness-110 disabled:opacity-60"
                >
                  {createCantiere.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Building2 className="h-4 w-4" />
                  )}
                  Crea cantiere attivo
                </button>
              )}
            </div>
          )}

          {aiJobId && (
            <div className="bg-surface border border-stroke rounded-2xl p-4 sm:p-6 min-w-0">
              <div className="flex items-center justify-between mb-4 min-w-0">
                <h4 className="font-display font-semibold uppercase text-sm text-ink flex items-center gap-2">
                  <Brain className="w-4 h-4 text-brand shrink-0" /> AI Architect
                </h4>
                <button
                  onClick={() => navigate(`/dashboard/ai-architect?job=${aiJobId}`)}
                  className="font-display uppercase text-[10px] text-brand inline-flex items-center gap-1 hover:text-ink shrink-0"
                >
                  Apri revisione <ExternalLink className="w-3 h-3" />
                </button>
              </div>
              {lead.ai_architect_summary && (
                <p className="font-body text-xs text-fog mb-3 break-words">{lead.ai_architect_summary}</p>
              )}
              {aiJob ? (
                <>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 min-w-0">
                    {aiConcept?.image_url && (
                      <div className="min-w-0">
                        <div className="font-display uppercase text-[9px] text-fog mb-1">Concept 2D</div>
                        <img src={aiAssetUrl(aiConcept.image_url)} alt="Concept 2D" className="w-full rounded-lg border border-stroke bg-bg object-contain max-h-40" />
                      </div>
                    )}
                    {aiTopdown?.image_url && (
                      <div className="min-w-0">
                        <div className="font-display uppercase text-[9px] text-fog mb-1">Top-down 3D</div>
                        <img src={aiAssetUrl(aiTopdown.image_url)} alt="Top-down" className="w-full rounded-lg border border-stroke bg-bg object-contain max-h-40" />
                      </div>
                    )}
                  </div>
                  {aiRenders.length > 0 && (
                    <div className="grid grid-cols-3 gap-2 mt-2 min-w-0">
                      {aiRenders.slice(0, 3).map((r) => (
                        <img key={r.id} src={aiAssetUrl(r.image_url)} alt={r.room_name || "Render"} className="w-full aspect-square rounded-lg border border-stroke bg-bg object-cover" />
                      ))}
                    </div>
                  )}
                  <div className="mt-3 flex flex-wrap items-center gap-2 min-w-0">
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

        {/* RIGHT: timeline (spans full width on tablets md/lg) */}
        <div className="space-y-5 min-w-0 md:col-span-2 xl:col-span-1">
          <div className="bg-surface border border-stroke rounded-2xl p-4 sm:p-6 min-w-0">
            <div className="flex flex-wrap sm:flex-nowrap items-center justify-between gap-2 mb-3 min-w-0">
              <h4 className="font-display font-semibold uppercase text-sm text-ink">Prossima azione</h4>
              <button data-testid="ai-suggest" onClick={() => suggest.mutate()} disabled={suggest.isPending}
                className="font-display uppercase text-[10px] bg-brand/15 text-brand px-3 py-1.5 rounded-full inline-flex items-center gap-1 hover:bg-brand/25 transition-colors disabled:opacity-60 shrink-0">
                {suggest.isPending ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />} Suggerisci AI
              </button>
            </div>
            <p className="font-body text-sm text-ink bg-bg border border-stroke rounded-xl p-3 min-h-[60px] break-words">
              {lead.prossima_azione || "Nessun suggerimento. Genera con l'AI."}
            </p>
          </div>

          <div className="bg-surface border border-stroke rounded-2xl p-4 sm:p-6 min-w-0">
            <h4 className="font-display font-semibold uppercase text-sm text-ink mb-4">Timeline</h4>
            <Tabs value={noteType} onValueChange={setNoteType} className="min-w-0">
              <TabsList className="bg-bg border border-stroke w-full grid grid-cols-3 h-auto p-1 min-w-0">
                <TabsTrigger value="nota" className="text-xs py-1.5 px-1 truncate">Nota</TabsTrigger>
                <TabsTrigger value="chiamata" className="text-xs py-1.5 px-1 truncate">Chiamata</TabsTrigger>
                <TabsTrigger value="messaggio" className="text-xs py-1.5 px-1 truncate">Messaggio</TabsTrigger>
              </TabsList>
              <TabsContent value={noteType} className="mt-3 min-w-0">
                <div className="flex gap-2 min-w-0">
                  <input data-testid="timeline-input" value={note} onChange={(e) => setNote(e.target.value)}
                    placeholder={`Aggiungi ${noteType}…`}
                    className="flex-1 bg-bg border border-stroke rounded-xl px-3 py-2 text-sm text-ink placeholder:text-fog focus:outline-none focus:border-brand min-w-0" />
                  <button data-testid="timeline-add" onClick={() => note && addEvent.mutate({ tipo: noteType, testo: note })}
                    className="bg-brand text-white rounded-xl px-3 py-2 hover:scale-105 transition-transform shrink-0"><Send className="w-4 h-4" /></button>
                </div>
              </TabsContent>
            </Tabs>

            <div className="mt-5 space-y-3 max-h-[400px] overflow-y-auto pr-1 min-w-0">
              {timeline.map((ev) => (
                <div key={ev.id} className="relative pl-5 border-l border-stroke min-w-0">
                  <span className="absolute -left-[5px] top-1 w-2.5 h-2.5 rounded-full bg-brand" />
                  <div className="font-body text-sm text-ink break-words min-w-0">{ev.testo}</div>
                  <div className="font-body text-[10px] text-fog mt-0.5 break-words min-w-0">{formatDateTime(ev.ts)} {ev.autore ? `· ${ev.autore}` : ""}</div>
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
    <div className="min-w-0">
      <div className="font-display uppercase text-[10px] text-fog tracking-wider truncate">{label}</div>
      <div className="text-ink capitalize font-medium text-xs sm:text-sm break-words">{value ?? "—"}</div>
    </div>
  );
}
