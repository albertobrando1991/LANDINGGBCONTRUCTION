import { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowLeft,
  ArrowRight,
  AlertTriangle,
  Brain,
  CheckCircle2,
  Download,
  FileText,
  Image as ImageIcon,
  Layers3,
  Loader2,
  MessageCircle,
  RotateCw,
  Sparkles,
  UploadCloud,
} from "lucide-react";
import { toast } from "sonner";
import client, { BACKEND_URL, formatApiErrorDetail } from "@/lib/api";
import { WHATSAPP } from "@/lib/assets";

const PLAN_TYPES = [
  { id: "existing_state", label: "Stato attuale dell'immobile" },
  { id: "defined_project", label: "Progetto gia definito" },
  { id: "auto", label: "Non lo so, analizzala automaticamente" },
];

const STYLES = [
  "Moderno luxury",
  "Minimal contemporaneo",
  "Japandi",
  "Wabi-sabi",
  "Classico contemporaneo",
  "Industrial",
  "Mediterraneo",
  "Su misura GB Construction",
];

const GOALS = [
  "Ristrutturazione completa",
  "Nuova distribuzione degli spazi",
  "Restyling",
  "Arredo e interior design",
  "Valorizzazione per vendita/affitto",
  "Hospitality/B&B",
];

const PROJECT_VARIANTS = [
  {
    id: "conservative",
    label: "Conservativa",
    detail: "Minimi interventi, rischio tecnico e costi controllati.",
  },
  {
    id: "premium_suite",
    label: "Premium suite",
    detail: "Suite matrimoniale, bagno padronale e valore percepito alto.",
  },
  {
    id: "investment",
    label: "Investimento",
    detail: "Spazi flessibili, affittabilita e ROI.",
  },
  {
    id: "family",
    label: "Family",
    detail: "Camere vere, contenimento e lavanderia funzionale.",
  },
  {
    id: "smart_working",
    label: "Smart working",
    detail: "Studio forte, ospiti flessibili e living ordinato.",
  },
];

const PRIORITIES = [
  "piu spazio",
  "piu luce",
  "cucina piu grande",
  "open space",
  "piu camere",
  "cabina armadio",
  "bagno aggiuntivo",
  "lavanderia",
  "piu contenimento",
  "immagine luxury",
];

const PROCESS_STEPS = [
  { key: "upload", label: "Upload planimetria", Icon: UploadCloud },
  { key: "analysis", label: "Analisi architettonica", Icon: Brain },
  { key: "proposal_2d", label: "Generazione proposta 2D", Icon: FileText },
  { key: "review", label: "Approvazione concept", Icon: CheckCircle2 },
  { key: "topdown_3d", label: "Generazione planimetria 3D", Icon: Layers3 },
  { key: "renders", label: "Generazione render", Icon: ImageIcon },
  { key: "advice", label: "Consigli finali", Icon: Sparkles },
];

const DEFAULT_LAYOUT_2D_WARNING =
  "La planimetria 2D e un concept preliminare generato da un agente AI specializzato. Nonostante la precisione del sistema, possono esserci errori su misure, aperture, muri, arredi o rapporti tra ambienti. In fase di sopralluogo puoi chiedere allo staff GB Construction di verificare e, se necessario, modificare la planimetria collegata al progetto.";

const initialForm = {
  file: null,
  planType: "auto",
  projectVariant: "premium_suite",
  style: "Moderno luxury",
  goal: "Ristrutturazione completa",
  priorities: ["piu luce", "open space", "immagine luxury"],
  sqm: "",
  residents: "",
  budget: "",
  notes: "",
};

function assetUrl(url) {
  if (!url) return "";
  if (url.startsWith("http")) return url;
  return `${BACKEND_URL}${url}`;
}

function byType(outputs, type) {
  return outputs.filter((o) => o.output_type === type);
}

function latest(outputs, type) {
  const items = byType(outputs, type);
  return items[items.length - 1];
}

function ToggleButton({ active, children, onClick, className = "" }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full border px-4 py-2.5 font-display text-xs font-semibold uppercase tracking-wide transition-colors ${
        active
          ? "border-brand bg-brand text-white"
          : "border-stroke bg-surface text-ink hover:border-brand"
      } ${className}`}
    >
      {children}
    </button>
  );
}

export default function AIArchitect({ baseConfig, leadId, onComplete, onSkip }) {
  const [step, setStep] = useState(1);
  const [form, setForm] = useState(initialForm);
  const [job, setJob] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [approving, setApproving] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [conceptFeedback, setConceptFeedback] = useState("");

  const outputs = job?.outputs || [];
  const analysis = latest(outputs, "analysis");
  const professionalOutput = latest(outputs, "professional_floorplan");
  const automationOutput = latest(outputs, "floor_plan_automation");
  const technicalJsonOutput = latest(outputs, "technical_floor_plan_json");
  const optimizedJsonOutput = latest(outputs, "optimized_floor_plan_json");
  const clean2d = latest(outputs, "clean_2d_plan");
  const redistributed2d = latest(outputs, "redistributed_2d_plan");
  const topdown = latest(outputs, "topdown_3d_plan");
  const advice = latest(outputs, "advice");
  const report = latest(outputs, "pdf_report");
  const renders = byType(outputs, "room_render");
  const professionalFloorplan =
    job?.professional_floorplan || professionalOutput?.json_content || {};
  const technicalFindings = professionalFloorplan.technical_findings || [];
  const optimizationStrategy =
    professionalFloorplan.optimization_strategy || [];
  const floorplanBrief = professionalFloorplan.floorplan_2d || {};
  const floorPlanAutomation =
    job?.floor_plan_automation || automationOutput?.json_content || {};
  const technicalFloorPlan =
    job?.technical_floor_plan_json || technicalJsonOutput?.json_content || {};
  const optimizedFloorPlan =
    job?.optimized_floor_plan_json || optimizedJsonOutput?.json_content || {};
  const selectedAutomationVariant =
    floorPlanAutomation.variant_generation?.selected_variant || {};
  const pipelineGate = floorPlanAutomation.pipeline_gate || {};
  const analysisBusy = ["queued", "processing", "analysis_failed"].includes(
    job?.status,
  );
  const renderWaitActive =
    ["queued", "processing"].includes(job?.status) &&
    ["topdown_3d", "renders"].includes(job?.current_step);
  const uploadedPlanUrl = job?.processed_file_url || job?.uploaded_file_url;
  const concept2d = redistributed2d || clean2d;
  const conceptPayload = concept2d?.json_content || {};
  const conceptApprovable = conceptPayload.approvable_for_render === true;
  const layoutRegenerationLimit = Number(job?.layout_regeneration_limit ?? 1);
  const layoutRegenerationCount = Number(job?.layout_regeneration_count ?? 0);
  const layoutRegenerationAvailable =
    job?.layout_regeneration_available ??
    layoutRegenerationCount < layoutRegenerationLimit;
  const layout2dWarning = job?.layout_2d_warning || DEFAULT_LAYOUT_2D_WARNING;
  const redistributionBlocked =
    job?.status === "needs_confirmation" &&
    /redistribuzione 2d bloccata|sagome 2d sintetiche|planimetria migliore|revisione tecnica/i.test(
      job?.error_message || "",
    );

  const currentProcessIndex = useMemo(() => {
    if (!job) return 0;
    if (job.status === "completed") return PROCESS_STEPS.length;
    return Math.max(
      0,
      PROCESS_STEPS.findIndex((s) => s.key === job.current_step),
    );
  }, [job]);

  useEffect(() => {
    if (!job || !["queued", "processing"].includes(job.status))
      return undefined;
    const id = setInterval(async () => {
      try {
        const { data } = await client.get(`/ai-architect/jobs/${job.id}`);
        setJob(data);
        if (data.status === "completed") setStep(4);
      } catch (err) {
        toast.error(formatApiErrorDetail(err.response?.data?.detail));
      }
    }, 1400);
    return () => clearInterval(id);
  }, [job]);

  const update = (patch) => setForm((current) => ({ ...current, ...patch }));

  const togglePriority = (priority) => {
    update({
      priorities: form.priorities.includes(priority)
        ? form.priorities.filter((p) => p !== priority)
        : [...form.priorities, priority],
    });
  };

  const canGoNext = () => {
    if (step === 1)
      return (
        !!form.file &&
        !!form.planType &&
        !!form.projectVariant &&
        !!form.style &&
        !!form.goal
      );
    return true;
  };

  const createJob = async () => {
    if (!form.file) return;
    setSubmitting(true);
    try {
      const payload = new FormData();
      payload.append("planimetria", form.file);
      payload.append("plan_type_selected", form.planType);
      payload.append("project_variant_selected", form.projectVariant);
      payload.append("style_selected", form.style);
      payload.append("project_goal", form.goal);
      payload.append("priorities", JSON.stringify(form.priorities));
      if (form.sqm) payload.append("sqm", form.sqm);
      if (form.residents) payload.append("residents", form.residents);
      if (form.budget) payload.append("budget", form.budget);
      if (form.notes) payload.append("notes", form.notes);
      if (leadId) payload.append("lead_id", leadId);
      const { data } = await client.post("/ai-architect/jobs", payload, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setJob(data);
      setConceptFeedback("");
      setStep(3);
      toast.success("Analisi AI Architect avviata");
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setSubmitting(false);
    }
  };

  const approveConcept = async () => {
    if (!job) return;
    if (!conceptApprovable) {
      toast.error(
        "Concept 2D non approvabile: serve planimetria migliore o revisione tecnica.",
      );
      return;
    }
    setApproving(true);
    try {
      const { data } = await client.post(
        `/ai-architect/jobs/${job.id}/approve`,
        {
          reviewer: "GB Construction",
          notes: "Concept 2D approvato per generazione render.",
        },
      );
      setJob(data);
      toast.success("Concept approvato. Generazione render avviata.");
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setApproving(false);
    }
  };

  const restartWithBetterPlan = () => {
    setJob(null);
    setStep(1);
  };

  const confirmPlanType = async (planType) => {
    if (!job) return;
    setConfirming(true);
    try {
      const { data } = await client.post(
        `/ai-architect/jobs/${job.id}/confirm`,
        {
          plan_type_selected: planType,
        },
      );
      setJob(data);
      toast.success(
        planType === "defined_project"
          ? "Planimetria mantenuta identica."
          : "Redistribuzione avviata.",
      );
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setConfirming(false);
    }
  };

  const regenerateStyle = async () => {
    if (!job) return;
    setRegenerating(true);
    try {
      const { data } = await client.post(
        `/ai-architect/jobs/${job.id}/regenerate`,
        {
          style_selected: form.style,
          output_types: [
            "topdown_3d_plan",
            "room_render",
            "advice",
            "pdf_report",
          ],
        },
      );
      setJob(data);
      setStep(3);
      toast.success("Rigenerazione stile avviata");
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setRegenerating(false);
    }
  };

  const regenerateConcept2d = async () => {
    if (!job) return;
    if (!layoutRegenerationAvailable) {
      toast.error(
        "La rigenerazione 2D e disponibile una sola volta. Per altre modifiche chiedi allo staff durante il sopralluogo.",
      );
      return;
    }
    const correctionNotes = conceptFeedback.trim();
    if (!correctionNotes) {
      toast.error("Inserisci una correzione prima di rigenerare il 2D.");
      return;
    }
    setRegenerating(true);
    try {
      const { data } = await client.post(
        `/ai-architect/jobs/${job.id}/regenerate`,
        {
          correction_notes: correctionNotes,
          output_types: ["concept_2d"],
        },
      );
      setJob(data);
      setStep(3);
      toast.success("Correzione inviata. Concept 2D in rigenerazione.");
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail));
    } finally {
      setRegenerating(false);
    }
  };

  const downloadReport = () => {
    if (!job) return;
    window.open(
      `${BACKEND_URL}/api/ai-architect/jobs/${job.id}/report`,
      "_blank",
      "noopener,noreferrer",
    );
  };

  const continueToQuote = () => {
    if (!job) return;
    onComplete({
      ...job,
      ai_architect_job_id: job.id,
      ai_architect_summary: `${form.goal} - ${form.style}`,
      selected_style: form.style,
    });
  };

  const goNext = () => {
    if (step === 1) setStep(2);
    if (step === 2) createJob();
  };

  return (
    <section
      id="ai-architect"
      className="relative min-h-screen py-20 px-6 bg-bg overflow-hidden"
    >
      <div className="absolute inset-0 blueprint-grid opacity-[0.025]" />
      <div className="relative max-w-7xl mx-auto">
        <div className="grid grid-cols-1 lg:grid-cols-[0.85fr_1.15fr] gap-10 items-start">
          <div className="lg:sticky lg:top-8">
            <p className="font-display font-semibold uppercase tracking-[0.3em] text-xs text-brand mb-3">
              AI Architect Layout & Render
            </p>
            <h2 className="font-display font-bold uppercase text-4xl md:text-6xl tracking-tight text-ink leading-none">
              Carica la tua planimetria e visualizza il progetto con l'AI
            </h2>
            <p className="font-body text-fog mt-5 max-w-xl">
              Analisi preliminare, concept 2D, vista top-down e render degli
              ambienti principali prima della richiesta preventivo.
            </p>
            <div className="mt-8">
              <div className="flex justify-between font-display text-xs uppercase text-fog mb-2">
                <span>Step {step} di 4</span>
                <span>{Math.round((step / 4) * 100)}%</span>
              </div>
              <div className="h-1.5 rounded-full bg-stroke overflow-hidden">
                <div
                  className="h-full accent-gradient transition-all"
                  style={{ width: `${(step / 4) * 100}%` }}
                />
              </div>
            </div>
            <p className="font-body text-xs text-fog mt-5">
              Concept preliminare generato con AI, da verificare con tecnico
              abilitato.
            </p>
          </div>

          <div className="bg-surface border border-stroke rounded-3xl p-5 md:p-8">
            <AnimatePresence mode="wait">
              {step === 1 && (
                <motion.div
                  key="ai-step-1"
                  initial={{ opacity: 0, y: 18 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -18 }}
                >
                  <div className="flex items-center gap-3 mb-6">
                    <UploadCloud className="w-6 h-6 text-brand" />
                    <h3 className="font-display font-bold uppercase text-2xl text-ink">
                      Planimetria e direzione creativa
                    </h3>
                  </div>

                  <label className="block rounded-2xl border-2 border-dashed border-stroke bg-bg/60 px-6 py-10 cursor-pointer hover:border-brand transition-colors">
                    <input
                      type="file"
                      accept=".pdf,.png,.jpg,.jpeg,.webp,.dwg,.dxf,.ifc"
                      className="hidden"
                      onChange={(e) =>
                        update({ file: e.target.files?.[0] || null })
                      }
                    />
                    <UploadCloud className="w-11 h-11 text-brand mx-auto mb-4" />
                    <p className="font-display font-semibold uppercase text-center text-ink">
                      {form.file ? form.file.name : "Upload planimetria"}
                    </p>
                    <p className="font-body text-xs text-fog text-center mt-2">
                      PDF, PNG, JPG, JPEG, WEBP, DWG, DXF, IFC
                    </p>
                  </label>

                  <div className="mt-4 rounded-2xl border border-stroke bg-bg/40 px-5 py-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                    <p className="font-body text-sm text-fog">
                      L'analisi della planimetria è opzionale: il tuo preventivo è
                      già pronto.
                    </p>
                    <button
                      type="button"
                      onClick={onSkip}
                      className="shrink-0 font-display font-semibold uppercase text-sm text-brand hover:text-ink inline-flex items-center gap-2"
                    >
                      Torna al preventivo <ArrowRight className="w-4 h-4" />
                    </button>
                  </div>

                  <div className="mt-7 space-y-6">
                    <div>
                      <p className="font-display font-semibold uppercase text-sm text-ink mb-3">
                        Tipo planimetria
                      </p>
                      <div className="flex flex-wrap gap-3">
                        {PLAN_TYPES.map((item) => (
                          <ToggleButton
                            key={item.id}
                            active={form.planType === item.id}
                            onClick={() => update({ planType: item.id })}
                          >
                            {item.label}
                          </ToggleButton>
                        ))}
                      </div>
                    </div>

                    <div>
                      <p className="font-display font-semibold uppercase text-sm text-ink mb-3">
                        Stile desiderato
                      </p>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        {STYLES.map((style) => (
                          <ToggleButton
                            key={style}
                            active={form.style === style}
                            onClick={() => update({ style })}
                            className="w-full"
                          >
                            {style}
                          </ToggleButton>
                        ))}
                      </div>
                    </div>

                    <div>
                      <p className="font-display font-semibold uppercase text-sm text-ink mb-3">
                        Obiettivo
                      </p>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        {GOALS.map((goal) => (
                          <ToggleButton
                            key={goal}
                            active={form.goal === goal}
                            onClick={() => update({ goal })}
                            className="w-full"
                          >
                            {goal}
                          </ToggleButton>
                        ))}
                      </div>
                    </div>

                    <div>
                      <p className="font-display font-semibold uppercase text-sm text-ink mb-3">
                        Variante da generare
                      </p>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        {PROJECT_VARIANTS.map((variant) => (
                          <button
                            key={variant.id}
                            type="button"
                            onClick={() =>
                              update({ projectVariant: variant.id })
                            }
                            className={`text-left rounded-2xl border px-4 py-4 transition-colors ${
                              form.projectVariant === variant.id
                                ? "border-brand bg-brand/10"
                                : "border-stroke bg-bg hover:border-brand"
                            }`}
                          >
                            <span className="block font-display text-xs font-semibold uppercase text-ink">
                              {variant.label}
                            </span>
                            <span className="block font-body text-xs text-fog mt-1 leading-relaxed">
                              {variant.detail}
                            </span>
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                </motion.div>
              )}

              {step === 2 && (
                <motion.div
                  key="ai-step-2"
                  initial={{ opacity: 0, y: 18 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -18 }}
                >
                  <div className="flex items-center gap-3 mb-6">
                    <Sparkles className="w-6 h-6 text-brand" />
                    <h3 className="font-display font-bold uppercase text-2xl text-ink">
                      Priorita e dati utili
                    </h3>
                  </div>

                  <p className="font-display font-semibold uppercase text-sm text-ink mb-3">
                    Priorita progettuali
                  </p>
                  <div className="flex flex-wrap gap-3 mb-7">
                    {PRIORITIES.map((priority) => (
                      <ToggleButton
                        key={priority}
                        active={form.priorities.includes(priority)}
                        onClick={() => togglePriority(priority)}
                      >
                        {priority}
                      </ToggleButton>
                    ))}
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <input
                      value={form.sqm}
                      onChange={(e) => update({ sqm: e.target.value })}
                      type="number"
                      min="1"
                      placeholder="Metri quadri (opz.)"
                      className="bg-bg border border-stroke rounded-xl px-4 py-3 text-ink placeholder:text-fog focus:outline-none focus:border-brand"
                    />
                    <input
                      value={form.residents}
                      onChange={(e) => update({ residents: e.target.value })}
                      type="number"
                      min="1"
                      placeholder="Persone in casa (opz.)"
                      className="bg-bg border border-stroke rounded-xl px-4 py-3 text-ink placeholder:text-fog focus:outline-none focus:border-brand"
                    />
                    <input
                      value={form.budget}
                      onChange={(e) => update({ budget: e.target.value })}
                      placeholder="Budget indicativo (opz.)"
                      className="bg-bg border border-stroke rounded-xl px-4 py-3 text-ink placeholder:text-fog focus:outline-none focus:border-brand"
                    />
                  </div>
                  <textarea
                    value={form.notes}
                    onChange={(e) => update({ notes: e.target.value })}
                    placeholder="Note del cliente, vincoli, desideri, stanze da valorizzare..."
                    rows={5}
                    className="mt-4 w-full bg-bg border border-stroke rounded-xl px-4 py-3 text-ink placeholder:text-fog focus:outline-none focus:border-brand resize-none"
                  />
                </motion.div>
              )}

              {step === 3 && (
                <motion.div
                  key="ai-step-3"
                  initial={{ opacity: 0, y: 18 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -18 }}
                >
                  <div className="flex items-center justify-between gap-4 mb-6">
                    <div>
                      <h3 className="font-display font-bold uppercase text-2xl text-ink">
                        AI Architect al lavoro
                      </h3>
                      <p className="font-body text-sm text-fog mt-1">
                        Analisi professionale della planimetria in corso.
                      </p>
                    </div>
                    {analysisBusy ? (
                      <Loader2 className="w-7 h-7 text-brand animate-spin" />
                    ) : null}
                  </div>

                  <div className="h-2 rounded-full bg-bg overflow-hidden mb-6">
                    <div
                      className="h-full accent-gradient transition-all"
                      style={{ width: `${job?.progress_percentage || 0}%` }}
                    />
                  </div>

                  {renderWaitActive && (
                    <div className="mb-6 rounded-2xl border border-gold/40 bg-gold/10 p-5">
                      <div className="flex items-start gap-4">
                        <div className="relative mt-0.5 shrink-0">
                          <Sparkles className="w-6 h-6 text-gold" />
                          <span className="absolute -inset-2 rounded-full border border-gold/30 animate-ping" />
                        </div>
                        <div>
                          <p className="font-display font-semibold uppercase text-sm text-ink">
                            Mentre avviene la magia
                          </p>
                          <p className="mt-1 font-body text-sm leading-relaxed text-fog">
                            Stiamo generando i render del tuo progetto. Questa
                            fase puo richiedere il tempo necessario per
                            l'elaborazione delle immagini: attendi il
                            completamento senza ricaricare la pagina.
                          </p>
                          <div className="mt-4 flex flex-wrap items-center gap-3">
                            <span className="inline-flex items-center gap-2 rounded-full border border-gold/35 bg-bg/60 px-4 py-2 font-display text-[10px] font-semibold uppercase tracking-wider text-gold">
                              <Loader2 className="w-3.5 h-3.5 animate-spin" />
                              Generazione render in corso
                            </span>
                            <span className="font-body text-xs text-fog">
                              Il sistema aggiornera automaticamente i risultati.
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  {(selectedAutomationVariant.label || job?.project_variant_selected) && (
                    <div className="mb-6 rounded-2xl border border-stroke bg-bg p-4">
                      <div className="grid gap-3 sm:grid-cols-3">
                        <div>
                          <p className="font-display uppercase text-[10px] text-fog">
                            Variante scelta
                          </p>
                          <p className="font-display uppercase text-xs text-ink mt-1">
                            {selectedAutomationVariant.label ||
                              job?.project_variant_selected}
                          </p>
                        </div>
                        <div>
                          <p className="font-display uppercase text-[10px] text-fog">
                            Semaforo
                          </p>
                          <p className="font-display uppercase text-xs text-ink mt-1">
                            {pipelineGate.status || "In analisi"}
                          </p>
                        </div>
                        <div>
                          <p className="font-display uppercase text-[10px] text-fog">
                            Varianti generate
                          </p>
                          <p className="font-display uppercase text-xs text-ink mt-1">
                            {floorPlanAutomation.variant_generation
                              ?.generated_variant_count || 1}
                          </p>
                        </div>
                      </div>
                    </div>
                  )}

                  {analysisBusy && (
                    <div className="mb-6 rounded-2xl border border-brand/40 bg-brand/10 p-4">
                      <div className="flex items-start gap-3">
                        <Brain className="w-5 h-5 text-brand mt-0.5 shrink-0" />
                        <div>
                          <p className="font-display font-semibold uppercase text-sm text-ink">
                            Lettura avanzata in corso
                          </p>
                          <p className="mt-1 font-body text-xs leading-relaxed text-fog">
                            Stiamo leggendo ambienti, aperture, vincoli e
                            priorita progettuali per generare un concept
                            preliminare coerente.
                          </p>
                        </div>
                      </div>
                    </div>
                  )}

                  <div className="grid gap-3">
                    {PROCESS_STEPS.map(({ key, label, Icon }, index) => {
                      const done =
                        job?.status === "completed" ||
                        index < currentProcessIndex;
                      const active = key === job?.current_step;
                      return (
                        <div
                          key={key}
                          className={`flex items-center gap-4 rounded-2xl border px-4 py-4 ${active ? "border-brand bg-brand/10" : "border-stroke bg-bg/40"}`}
                        >
                          <div
                            className={`w-10 h-10 rounded-full grid place-items-center ${done ? "bg-success/20 text-success" : active ? "bg-brand/20 text-brand" : "bg-surface-2 text-fog"}`}
                          >
                            {done ? (
                              <CheckCircle2 className="w-5 h-5" />
                            ) : (
                              <Icon className="w-5 h-5" />
                            )}
                          </div>
                          <span className="font-display font-semibold uppercase text-sm text-ink">
                            {label}
                          </span>
                        </div>
                      );
                    })}
                  </div>

                  {job?.status === "needs_confirmation" && (
                    <div className="mt-6 rounded-2xl border border-warning/50 bg-warning/10 p-5">
                      <div className="flex items-start gap-3">
                        <AlertTriangle className="w-6 h-6 text-warning shrink-0" />
                        <div className="w-full">
                          <p className="font-display font-semibold uppercase text-ink">
                            Verifica planimetria richiesta
                          </p>
                          <p className="font-body text-sm text-fog mt-1">
                            {job.error_message ||
                              "La lettura AI non e abbastanza affidabile per approvare un nuovo 2D. La planimetria allegata resta il riferimento vincolante."}
                          </p>
                          {uploadedPlanUrl && (
                            <img
                              src={assetUrl(uploadedPlanUrl)}
                              alt="Planimetria allegata"
                              className="mt-4 w-full max-h-72 rounded-xl border border-stroke object-contain bg-bg"
                            />
                          )}
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-4">
                            <button
                              type="button"
                              onClick={() => confirmPlanType("defined_project")}
                              disabled={confirming}
                              className="bg-brand text-white rounded-full px-5 py-3 font-display font-semibold uppercase text-xs inline-flex items-center justify-center gap-2 disabled:opacity-60"
                            >
                              {confirming ? (
                                <Loader2 className="w-4 h-4 animate-spin" />
                              ) : (
                                <CheckCircle2 className="w-4 h-4" />
                              )}
                              E' stato di progetto: mantieni identica
                            </button>
                            <button
                              type="button"
                              onClick={
                                redistributionBlocked
                                  ? restartWithBetterPlan
                                  : () => confirmPlanType("existing_state")
                              }
                              disabled={confirming}
                              className="bg-surface border border-stroke text-ink rounded-full px-5 py-3 font-display font-semibold uppercase text-xs inline-flex items-center justify-center gap-2 disabled:opacity-60"
                            >
                              <FileText className="w-4 h-4" />
                              {redistributionBlocked
                                ? "Carica planimetria migliore"
                                : "E' stato attuale: genera nuova 2D"}
                            </button>
                          </div>
                          <p className="font-body text-xs text-fog mt-3">
                            I render partono solo quando il concept 2D coincide
                            con la planimetria allegata o con una
                            redistribuzione approvabile.
                          </p>
                        </div>
                      </div>
                    </div>
                  )}

                  {job?.status === "needs_review" && (
                    <div className="mt-6 rounded-2xl border border-brand/50 bg-brand/10 p-5">
                      <div className="flex items-start gap-3">
                        <CheckCircle2 className="w-6 h-6 text-brand shrink-0" />
                        <div className="w-full">
                          <p className="font-display font-semibold uppercase text-ink">
                            Concept pronto per approvazione
                          </p>
                          <p className="font-body text-sm text-fog mt-1">
                            Controlla che il 2D coincida con la planimetria
                            allegata. Se e uno stato di progetto, deve restare
                            identico: i render partiranno solo dopo questa
                            approvazione.
                          </p>
                          {uploadedPlanUrl &&
                            concept2d?.image_url !== uploadedPlanUrl && (
                              <div className="mt-4">
                                <p className="font-display font-semibold uppercase text-[10px] tracking-wider text-fog mb-2">
                                  Planimetria allegata
                                </p>
                                <img
                                  src={assetUrl(uploadedPlanUrl)}
                                  alt="Planimetria allegata"
                                  className="w-full max-h-56 rounded-xl border border-stroke object-contain bg-bg"
                                />
                              </div>
                            )}
                          {concept2d?.image_url && (
                            <div className="mt-4">
                              <p className="font-display font-semibold uppercase text-[10px] tracking-wider text-fog mb-2">
                                {conceptApprovable
                                  ? "Concept 2D da approvare"
                                  : "2D non approvabile"}
                              </p>
                              <img
                                src={assetUrl(concept2d.image_url)}
                                alt="Concept 2D da approvare"
                                className="w-full max-h-72 rounded-xl border border-stroke object-contain bg-bg"
                              />
                              <div className="mt-3 rounded-xl border border-warning/40 bg-warning/10 p-4">
                                <div className="flex items-start gap-3">
                                  <AlertTriangle className="w-5 h-5 text-warning shrink-0" />
                                  <p className="font-body text-xs leading-relaxed text-fog">
                                    {layout2dWarning}
                                  </p>
                                </div>
                              </div>
                            </div>
                          )}
                          {!conceptApprovable && (
                            <div className="mt-4 rounded-xl border border-danger/35 bg-danger/10 p-4">
                              <p className="font-display font-semibold uppercase text-[10px] tracking-wider text-danger mb-2">
                                Blocco sicurezza
                              </p>
                              <p className="font-body text-xs leading-relaxed text-fog">
                                Questo output non puo far partire i render: la
                                redistribuzione non e stata prodotta da una
                                geometria affidabile. Serve una planimetria piu
                                leggibile o una revisione tecnica.
                              </p>
                            </div>
                          )}
                          {(optimizationStrategy.length > 0 ||
                            floorplanBrief.approval_checklist?.length > 0) && (
                            <div className="mt-4 grid gap-3 md:grid-cols-2">
                              {optimizationStrategy.length > 0 && (
                                <div className="rounded-xl border border-stroke bg-bg p-4">
                                  <p className="font-display font-semibold uppercase text-[10px] tracking-wider text-brand mb-2">
                                    Strategia 2D
                                  </p>
                                  <div className="space-y-2">
                                    {optimizationStrategy
                                      .slice(0, 3)
                                      .map((item, index) => (
                                        <p
                                          key={`${item.title}-${index}`}
                                          className="font-body text-xs leading-relaxed text-fog"
                                        >
                                          <span className="text-ink font-semibold">
                                            {item.title}
                                          </span>{" "}
                                          {item.expected_effect}
                                        </p>
                                      ))}
                                  </div>
                                </div>
                              )}
                              {floorplanBrief.approval_checklist?.length > 0 && (
                                <div className="rounded-xl border border-warning/35 bg-warning/10 p-4">
                                  <p className="font-display font-semibold uppercase text-[10px] tracking-wider text-warning mb-2">
                                    Checklist approvazione
                                  </p>
                                  <div className="space-y-1">
                                    {floorplanBrief.approval_checklist
                                      .slice(0, 5)
                                      .map((item) => (
                                        <p
                                          key={item}
                                          className="font-body text-xs leading-relaxed text-fog"
                                        >
                                          {item}
                                        </p>
                                      ))}
                                  </div>
                                </div>
                              )}
                            </div>
                          )}
                          {layoutRegenerationAvailable ? (
                            <div className="mt-4 rounded-xl border border-stroke bg-bg p-4">
                              <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2">
                                <label
                                  htmlFor="concept-feedback"
                                  className="font-display font-semibold uppercase text-[10px] tracking-wider text-ink"
                                >
                                  Correzione concept 2D
                                </label>
                                <span className="font-display uppercase text-[9px] tracking-wider text-warning">
                                  1 rigenerazione disponibile
                                </span>
                              </div>
                              <textarea
                                id="concept-feedback"
                                value={conceptFeedback}
                                onChange={(e) => setConceptFeedback(e.target.value)}
                                rows={3}
                                placeholder="Esempio: la cabina armadio deve avere accesso dalla camera da letto, non dal bagno; non chiudere il passaggio camera-cabina."
                                className="mt-2 w-full resize-none rounded-xl border border-stroke bg-surface px-4 py-3 font-body text-sm text-ink outline-none transition-colors placeholder:text-fog focus:border-brand"
                              />
                              <div className="mt-3 flex flex-col sm:flex-row sm:items-center gap-3">
                                <button
                                  type="button"
                                  onClick={regenerateConcept2d}
                                  disabled={!conceptFeedback.trim() || regenerating}
                                  className="bg-surface border border-stroke text-ink rounded-full px-5 py-3 font-display font-semibold uppercase text-xs inline-flex items-center justify-center gap-2 disabled:opacity-50"
                                >
                                  <RotateCw
                                    className={`w-4 h-4 ${regenerating ? "animate-spin" : ""}`}
                                  />
                                  Correggi e rigenera 2D
                                </button>
                                {job?.layout_correction_notes && (
                                  <p className="font-body text-xs text-fog leading-relaxed">
                                    Ultima correzione: {job.layout_correction_notes}
                                  </p>
                                )}
                              </div>
                            </div>
                          ) : (
                            <div className="mt-4 rounded-xl border border-stroke bg-bg p-4">
                              <p className="font-display font-semibold uppercase text-[10px] tracking-wider text-ink">
                                Rigenerazione 2D gia utilizzata
                              </p>
                              <p className="font-body text-xs leading-relaxed text-fog mt-2">
                                Ogni utente puo rigenerare la planimetria una sola volta. Per ulteriori modifiche, chiedi allo staff GB Construction durante il sopralluogo.
                              </p>
                              {job?.layout_correction_notes && (
                                <p className="font-body text-xs text-fog leading-relaxed mt-2">
                                  Ultima correzione: {job.layout_correction_notes}
                                </p>
                              )}
                            </div>
                          )}
                          <div className="flex flex-wrap gap-3 mt-4">
                            {conceptApprovable ? (
                              <button
                                type="button"
                                onClick={approveConcept}
                                disabled={approving}
                                className="bg-brand text-white rounded-full px-5 py-3 font-display font-semibold uppercase text-xs inline-flex items-center gap-2 disabled:opacity-60"
                              >
                                {approving ? (
                                  <Loader2 className="w-4 h-4 animate-spin" />
                                ) : (
                                  <CheckCircle2 className="w-4 h-4" />
                                )}
                                Approva e genera render
                              </button>
                            ) : (
                              <button
                                type="button"
                                onClick={restartWithBetterPlan}
                                className="bg-brand text-white rounded-full px-5 py-3 font-display font-semibold uppercase text-xs inline-flex items-center gap-2"
                              >
                                <FileText className="w-4 h-4" />
                                Carica planimetria migliore
                              </button>
                            )}
                            <button
                              type="button"
                              onClick={downloadReport}
                              className="bg-surface border border-stroke text-ink rounded-full px-5 py-3 font-display font-semibold uppercase text-xs inline-flex items-center gap-2"
                            >
                              <Download className="w-4 h-4" /> Scarica report
                              preliminare
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  {job?.status === "completed" && (
                    <button
                      type="button"
                      onClick={() => setStep(4)}
                      className="mt-6 w-full bg-brand text-white rounded-full py-4 font-display font-semibold uppercase tracking-wider inline-flex items-center justify-center gap-2"
                    >
                      Vedi anteprima risultati{" "}
                      <ArrowRight className="w-5 h-5" />
                    </button>
                  )}
                </motion.div>
              )}

              {step === 4 && (
                <motion.div
                  key="ai-step-4"
                  initial={{ opacity: 0, y: 18 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -18 }}
                >
                  <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-5 mb-7">
                    <div>
                      <p className="font-display font-semibold uppercase tracking-[0.2em] text-xs text-brand mb-2">
                        Anteprima risultati
                      </p>
                      <h3 className="font-display font-bold uppercase text-3xl text-ink">
                        Concept AI pronto
                      </h3>
                      <p className="font-body text-sm text-fog mt-2">
                        {analysis?.text_content ||
                          "Analisi completata e output collegati al job."}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-3">
                      <select
                        value={form.style}
                        onChange={(e) => update({ style: e.target.value })}
                        className="bg-bg border border-stroke rounded-full px-4 py-3 font-display font-semibold uppercase text-xs text-ink focus:outline-none focus:border-brand"
                      >
                        {STYLES.map((style) => (
                          <option key={style} value={style}>
                            {style}
                          </option>
                        ))}
                      </select>
                      <button
                        type="button"
                        onClick={downloadReport}
                        className="bg-surface border border-stroke text-ink rounded-full px-4 py-3 font-display font-semibold uppercase text-xs inline-flex items-center gap-2"
                      >
                        <Download className="w-4 h-4" /> Scarica report PDF
                      </button>
                      <button
                        type="button"
                        onClick={regenerateStyle}
                        disabled={regenerating}
                        className="bg-surface border border-stroke text-ink rounded-full px-4 py-3 font-display font-semibold uppercase text-xs inline-flex items-center gap-2 disabled:opacity-60"
                      >
                        <RotateCw
                          className={`w-4 h-4 ${regenerating ? "animate-spin" : ""}`}
                        />{" "}
                        Rigenera stile
                      </button>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                    {[redistributed2d || clean2d, topdown]
                      .filter(Boolean)
                      .map((output) => (
                        <div
                          key={output.id}
                          className="rounded-2xl overflow-hidden border border-stroke bg-bg"
                        >
                          <img
                            src={assetUrl(output.image_url)}
                            alt={output.output_type}
                            className="w-full aspect-[4/3] object-cover"
                          />
                          <div className="p-4">
                            <p className="font-display font-semibold uppercase text-sm text-ink">
                              {output.output_type === "topdown_3d_plan"
                                ? "Planimetria 3D/top-down"
                                : "Planimetria 2D"}
                            </p>
                            <p className="font-body text-xs text-fog mt-1">
                              {output.text_content}
                            </p>
                          </div>
                        </div>
                      ))}
                  </div>

                  {renders.length > 0 && (
                    <div className="mt-6">
                      <p className="font-display font-semibold uppercase text-sm text-ink mb-3">
                        Render ambienti principali
                      </p>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        {renders.map((render) => (
                          <div
                            key={render.id}
                            className="rounded-2xl overflow-hidden border border-stroke bg-bg"
                          >
                            <img
                              src={assetUrl(render.image_url)}
                              alt={render.room_name || "Render ambiente"}
                              className="w-full aspect-video object-cover"
                            />
                            <div className="p-3">
                              <p className="font-display font-semibold uppercase text-xs text-brand">
                                {render.room_name}
                              </p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {(selectedAutomationVariant.label || pipelineGate.status) && (
                    <div className="mt-6 rounded-2xl border border-stroke bg-bg p-5">
                      <p className="font-display font-semibold uppercase text-sm text-ink mb-3">
                        Contratto automazione
                      </p>
                      <div className="grid gap-3 md:grid-cols-3">
                        <div className="rounded-xl border border-stroke bg-surface p-4">
                          <p className="font-display uppercase text-[10px] text-fog">
                            Variante scelta
                          </p>
                          <p className="font-display uppercase text-sm text-ink mt-1">
                            {selectedAutomationVariant.label ||
                              job?.project_variant_selected ||
                              "Da definire"}
                          </p>
                        </div>
                        <div className="rounded-xl border border-stroke bg-surface p-4">
                          <p className="font-display uppercase text-[10px] text-fog">
                            Semaforo
                          </p>
                          <p className="font-display uppercase text-sm text-ink mt-1">
                            {pipelineGate.status || "Da verificare"}
                          </p>
                        </div>
                        <div className="rounded-xl border border-stroke bg-surface p-4">
                          <p className="font-display uppercase text-[10px] text-fog">
                            Varianti generate
                          </p>
                          <p className="font-display uppercase text-sm text-ink mt-1">
                            {floorPlanAutomation.variant_generation
                              ?.generated_variant_count || 1}
                          </p>
                        </div>
                      </div>
                      {pipelineGate.reason && (
                        <p className="font-body text-xs text-fog mt-3 leading-relaxed">
                          {pipelineGate.reason}
                        </p>
                      )}
                      {(technicalFloorPlan.schema || optimizedFloorPlan.schema) && (
                        <div className="mt-3 grid gap-3 md:grid-cols-2">
                          <div className="rounded-xl border border-stroke bg-surface p-4">
                            <p className="font-display uppercase text-[10px] text-fog">
                              JSON tecnico
                            </p>
                            <p className="font-display uppercase text-sm text-ink mt-1">
                              {technicalFloorPlan.source || "-"}
                            </p>
                            <p className="font-body text-xs text-fog mt-1">
                              Ambienti:{" "}
                              {(technicalFloorPlan.rooms || []).length || 0}
                            </p>
                          </div>
                          <div className="rounded-xl border border-stroke bg-surface p-4">
                            <p className="font-display uppercase text-[10px] text-fog">
                              JSON ottimizzato
                            </p>
                            <p className="font-display uppercase text-sm text-ink mt-1">
                              {optimizedFloorPlan.metadata?.selected_variant
                                ?.label || "-"}
                            </p>
                            <p className="font-body text-xs text-fog mt-1">
                              Prompt visuale vincolato al JSON tecnico
                            </p>
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {technicalFindings.length > 0 && (
                    <div className="mt-6 rounded-2xl border border-stroke bg-bg p-5">
                      <p className="font-display font-semibold uppercase text-sm text-ink mb-3">
                        Verifiche tecniche preliminari
                      </p>
                      <div className="grid gap-3 md:grid-cols-2">
                        {technicalFindings.slice(0, 4).map((finding, index) => (
                          <div
                            key={`${finding.title}-${index}`}
                            className="rounded-xl border border-stroke bg-surface p-4"
                          >
                            <div className="flex items-center justify-between gap-2">
                              <p className="font-display uppercase text-xs text-ink">
                                {finding.title}
                              </p>
                              <span className="rounded-full bg-brand/10 px-2 py-1 font-display text-[9px] uppercase text-brand">
                                {finding.severity}
                              </span>
                            </div>
                            <p className="font-body text-xs text-fog leading-relaxed mt-2">
                              {finding.recommendation}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {advice?.text_content && (
                    <div className="mt-6 rounded-2xl border border-stroke bg-bg p-5">
                      <p className="font-display font-semibold uppercase text-sm text-ink mb-2">
                        Consigli progettuali
                      </p>
                      <p className="font-body text-sm text-fog leading-relaxed">
                        {advice.text_content}
                      </p>
                    </div>
                  )}

                  <div className="mt-7 rounded-3xl border border-brand/40 bg-brand/10 p-6 text-center">
                    <h4 className="font-display font-bold uppercase text-2xl text-ink">
                      Progetto collegato alla tua richiesta
                    </h4>
                    <p className="font-body text-sm text-fog mt-2">
                      Analisi e render sono collegati al preventivo già inviato.
                      GB Construction ti ricontatta per la consulenza.
                    </p>
                    <div className="flex flex-col sm:flex-row justify-center gap-3 mt-5">
                      <button
                        type="button"
                        onClick={continueToQuote}
                        className="bg-brand text-white rounded-full px-7 py-4 font-display font-semibold uppercase tracking-wider inline-flex items-center justify-center gap-2"
                      >
                        Torna al preventivo aggiornato{" "}
                        <ArrowRight className="w-5 h-5" />
                      </button>
                      <a
                        href={WHATSAPP}
                        target="_blank"
                        rel="noreferrer"
                        className="bg-surface border border-stroke text-ink rounded-full px-7 py-4 font-display font-semibold uppercase tracking-wider inline-flex items-center justify-center gap-2"
                      >
                        <MessageCircle className="w-5 h-5 text-success" /> Parla
                        con un consulente
                      </a>
                    </div>
                    {report?.image_url && (
                      <p className="font-body text-xs text-fog mt-4">
                        Report e output salvati nel job AI Architect.
                      </p>
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {step < 3 && (
              <div className="flex items-center justify-between mt-8">
                <button
                  type="button"
                  onClick={() =>
                    step === 1 ? onSkip() : setStep((s) => s - 1)
                  }
                  className="font-display font-semibold uppercase text-sm text-fog hover:text-ink inline-flex items-center gap-2"
                >
                  <ArrowLeft className="w-4 h-4" />{" "}
                  {step === 1 ? "Torna al preventivo" : "Indietro"}
                </button>
                <button
                  type="button"
                  onClick={goNext}
                  disabled={!canGoNext() || submitting}
                  className="bg-brand text-white rounded-full px-8 py-4 font-display font-semibold uppercase tracking-wider inline-flex items-center gap-2 disabled:opacity-40"
                >
                  {submitting
                    ? "Avvio..."
                    : step === 2
                      ? "Avvia AI Architect"
                      : "Continua"}{" "}
                  <ArrowRight className="w-5 h-5" />
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
