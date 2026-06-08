import { useEffect, useMemo, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Brain,
  CheckCircle2,
  Download,
  ExternalLink,
  Eye,
  FileText,
  Image as ImageIcon,
  Loader2,
  RotateCw,
  Search,
  ShieldCheck,
} from "lucide-react";
import { toast } from "sonner";
import client, { BACKEND_URL, formatApiErrorDetail } from "@/lib/api";
import { relativeDate } from "@/lib/format";
import AIArchitect from "@/landing/AIArchitect";

const TABS = [
  { key: "new", label: "Nuovo" },
  { key: "needs_review", label: "Da approvare" },
  { key: "processing", label: "In lavorazione" },
  { key: "needs_confirmation", label: "Da confermare" },
  { key: "completed", label: "Completati" },
  { key: "tutti", label: "Tutti" },
];

const STATUS = {
  queued: { label: "In coda", cls: "bg-fog/10 text-fog" },
  processing: { label: "In lavorazione", cls: "bg-brand/15 text-brand" },
  needs_confirmation: {
    label: "Da confermare",
    cls: "bg-warning/15 text-warning",
  },
  needs_review: { label: "Da approvare", cls: "bg-warning/15 text-warning" },
  completed: { label: "Completato", cls: "bg-success/15 text-success" },
  failed: { label: "Da controllare", cls: "bg-danger/15 text-danger" },
};

const DEFAULT_LAYOUT_2D_WARNING =
  "La planimetria 2D e un concept preliminare generato da un agente AI specializzato. Nonostante la precisione del sistema, possono esserci errori su misure, aperture, muri, arredi o rapporti tra ambienti. In fase di sopralluogo puoi chiedere allo staff GB Construction di verificare e, se necessario, modificare la planimetria collegata al progetto.";

function assetUrl(url) {
  if (!url) return "";
  if (url.startsWith("http")) return url;
  return `${BACKEND_URL}${url}`;
}

function isPdfUrl(url) {
  return (
    typeof url === "string" && url.split("?")[0].toLowerCase().endsWith(".pdf")
  );
}

// Immagine asset robusta: i PDF non sono renderizzabili in <img> (planimetrie
// caricate come PDF) e gli asset possono mancare se lo storage e stato ripulito.
// In entrambi i casi mostra una card con link "Apri/Scarica" invece dell'icona rotta.
function AssetImage({ url, alt, className }) {
  const [failed, setFailed] = useState(false);
  const full = assetUrl(url);

  useEffect(() => {
    setFailed(false);
  }, [url]);

  if (!url) return null;

  if (isPdfUrl(url) || failed) {
    return (
      <div
        className={`grid place-items-center text-center p-4 rounded-xl border border-stroke bg-bg ${className || ""}`}
      >
        <div className="space-y-2">
          <FileText className="w-6 h-6 text-fog mx-auto" />
          <p className="font-body text-xs text-fog">
            {isPdfUrl(url)
              ? "Anteprima PDF non incorporabile."
              : "Immagine non disponibile."}
          </p>
          <a
            href={full}
            target="_blank"
            rel="noreferrer"
            className="font-display uppercase text-[10px] text-brand hover:text-ink inline-flex items-center gap-1"
          >
            <ExternalLink className="w-3 h-3" /> Apri {alt || "file"}
          </a>
        </div>
      </div>
    );
  }

  return (
    <img
      src={full}
      alt={alt}
      onError={() => setFailed(true)}
      className={className}
    />
  );
}

function latest(outputs, type) {
  const items = (outputs || []).filter((item) => item.output_type === type);
  return items[items.length - 1];
}

function qualityLabel(value) {
  if (typeof value !== "number") return "Da verificare";
  if (value >= 0.78) return "Professionale";
  if (value >= 0.62) return "Da validare";
  return "Da controllare";
}

export default function AIArchitectReview() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const deepLinkJob = searchParams.get("job");
  const [tab, setTab] = useState(deepLinkJob ? "tutti" : "needs_review");
  const [q, setQ] = useState("");
  const [selectedId, setSelectedId] = useState(deepLinkJob || null);
  const [conceptFeedback, setConceptFeedback] = useState("");
  const qc = useQueryClient();

  const { data: jobs = [], isLoading } = useQuery({
    queryKey: ["ai-architect-jobs", tab, q],
    enabled: tab !== "new",
    queryFn: async () =>
      (
        await client.get("/ai-architect/jobs", {
          params: { status: tab, q: q || undefined },
        })
      ).data,
  });

  useEffect(() => {
    if (tab === "new") return;
    if (!selectedId && jobs.length > 0) setSelectedId(jobs[0].id);
    if (
      selectedId &&
      selectedId !== deepLinkJob &&
      jobs.length > 0 &&
      !jobs.some((job) => job.id === selectedId)
    )
      setSelectedId(jobs[0].id);
  }, [jobs, selectedId, deepLinkJob, tab]);

  const { data: selectedJob, isFetching: loadingJob } = useQuery({
    queryKey: ["ai-architect-job", selectedId],
    enabled: Boolean(selectedId),
    queryFn: async () =>
      (await client.get(`/ai-architect/jobs/${selectedId}`)).data,
    refetchInterval: (query) =>
      ["processing", "queued"].includes(query.state.data?.status)
        ? 3000
        : false,
  });

  useEffect(() => {
    setConceptFeedback(selectedJob?.layout_correction_notes || "");
  }, [selectedJob?.id, selectedJob?.layout_correction_notes]);

  const invalidateJob = async (jobId) => {
    await qc.invalidateQueries({ queryKey: ["ai-architect-jobs"] });
    await qc.invalidateQueries({ queryKey: ["ai-architect-job", jobId] });
  };

  const approve = useMutation({
    mutationFn: (jobId) =>
      client.post(`/ai-architect/jobs/${jobId}/approve`, {
        reviewer: "Dashboard staff",
        notes: "Concept approvato da dashboard staff.",
      }),
    onSuccess: async (_, jobId) => {
      toast.success("Concept approvato. Render avviati.");
      await invalidateJob(jobId);
    },
    onError: (err) =>
      toast.error(formatApiErrorDetail(err.response?.data?.detail)),
  });

  const confirmPlan = useMutation({
    mutationFn: ({ jobId, planType }) =>
      client.post(`/ai-architect/jobs/${jobId}/confirm`, {
        plan_type_selected: planType,
      }),
    onSuccess: async (_, { jobId }) => {
      toast.success("Tipo planimetria confermato. Elaborazione avviata.");
      await invalidateJob(jobId);
    },
    onError: (err) =>
      toast.error(formatApiErrorDetail(err.response?.data?.detail)),
  });

  const regenerate = useMutation({
    mutationFn: ({ jobId, outputTypes, correctionNotes }) =>
      client.post(`/ai-architect/jobs/${jobId}/regenerate`, {
        output_types: outputTypes,
        correction_notes: correctionNotes,
      }),
    onSuccess: async (_, { jobId, outputTypes }) => {
      const isConcept = outputTypes?.includes("concept_2d");
      toast.success(
        isConcept
          ? "Correzione inviata. Concept 2D in rigenerazione."
          : "Rigenerazione avviata.",
      );
      await invalidateJob(jobId);
    },
    onError: (err) =>
      toast.error(formatApiErrorDetail(err.response?.data?.detail)),
  });

  const reanalyze = useMutation({
    mutationFn: (jobId) => client.post(`/ai-architect/jobs/${jobId}/reanalyze`),
    onSuccess: async (_, jobId) => {
      toast.success("Ri-analisi planimetria avviata.");
      await invalidateJob(jobId);
    },
    onError: (err) =>
      toast.error(formatApiErrorDetail(err.response?.data?.detail)),
  });

  const outputs = selectedJob?.outputs || [];
  const analysis = latest(outputs, "analysis");
  const professionalOutput = latest(outputs, "professional_floorplan");
  const automationOutput = latest(outputs, "floor_plan_automation");
  const technicalJsonOutput = latest(outputs, "technical_floor_plan_json");
  const optimizedJsonOutput = latest(outputs, "optimized_floor_plan_json");
  const clean2d = latest(outputs, "clean_2d_plan");
  const redistributed2d = latest(outputs, "redistributed_2d_plan");
  const topdown = latest(outputs, "topdown_3d_plan");
  const report = latest(outputs, "pdf_report");
  const renders = outputs.filter((item) => item.output_type === "room_render");
  const concept = redistributed2d || clean2d;
  const conceptPayload = concept?.json_content || {};
  const conceptApprovable = conceptPayload.approvable_for_render === true;
  const uploadedPlanUrl =
    selectedJob?.processed_file_url || selectedJob?.uploaded_file_url;
  const analysisJson =
    analysis?.json_content || selectedJob?.vision_analysis || {};
  const professionalFloorplan =
    selectedJob?.professional_floorplan ||
    professionalOutput?.json_content ||
    {};
  const technicalFindings = professionalFloorplan.technical_findings || [];
  const optimizationStrategy =
    professionalFloorplan.optimization_strategy || [];
  const floorplanBrief = professionalFloorplan.floorplan_2d || {};
  const floorPlanAutomation =
    selectedJob?.floor_plan_automation || automationOutput?.json_content || {};
  const technicalFloorPlan =
    selectedJob?.technical_floor_plan_json ||
    technicalJsonOutput?.json_content ||
    {};
  const optimizedFloorPlan =
    selectedJob?.optimized_floor_plan_json ||
    optimizedJsonOutput?.json_content ||
    {};
  const selectedAutomationVariant =
    floorPlanAutomation.variant_generation?.selected_variant || {};
  const pipelineGate = floorPlanAutomation.pipeline_gate || {};
  const layoutRegenerationLimit = Number(
    selectedJob?.layout_regeneration_limit ?? 1,
  );
  const layoutRegenerationCount = Number(
    selectedJob?.layout_regeneration_count ?? 0,
  );
  const layoutRegenerationAvailable =
    selectedJob?.layout_regeneration_available ??
    layoutRegenerationCount < layoutRegenerationLimit;
  const layout2dWarning =
    selectedJob?.layout_2d_warning || DEFAULT_LAYOUT_2D_WARNING;
  const status = STATUS[selectedJob?.status] || STATUS.queued;
  const estimate = selectedJob?.estimate;
  const estPacchetti = estimate?.pacchetti || {};
  const estReliable = selectedJob?.estimate_basis === "ai_floorplan_quoted";
  const euro = (value) =>
    typeof value === "number"
      ? "EUR " + Math.round(value).toLocaleString("it-IT")
      : "—";

  const counts = useMemo(() => {
    return jobs.reduce(
      (acc, job) => {
        acc.total += 1;
        acc.needsReview += job.status === "needs_review" ? 1 : 0;
        acc.completed += job.status === "completed" ? 1 : 0;
        acc.failed += job.status === "failed" ? 1 : 0;
        return acc;
      },
      { total: 0, needsReview: 0, completed: 0, failed: 0 },
    );
  }, [jobs]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">
        <div>
          <p className="font-display font-semibold uppercase tracking-[0.25em] text-xs text-brand mb-2">
            AI Architect
          </p>
          <h1 className="font-display font-bold uppercase text-3xl text-ink">
            Revisione concept
          </h1>
          <p className="font-body text-sm text-fog mt-2 max-w-2xl">
            Approva la proposta 2D prima di generare render e report finali. I
            costi AI partono solo dopo validazione.
          </p>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {[
            ["Totale", counts.total],
            ["Da approvare", counts.needsReview],
            ["Completati", counts.completed],
            ["Da controllare", counts.failed],
          ].map(([label, value]) => (
            <div
              key={label}
              className="rounded-xl border border-stroke bg-surface px-4 py-3"
            >
              <div className="font-display uppercase text-[10px] tracking-wider text-fog">
                {label}
              </div>
              <div className="font-display font-bold text-xl text-ink">
                {value}
              </div>
            </div>
          ))}
        </div>
      </div>

      {tab === "new" ? (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-2">
            {TABS.map((item) => (
              <button
                key={item.key}
                onClick={() => setTab(item.key)}
                className={`font-display uppercase text-xs tracking-wider px-4 py-2 rounded-full border transition-colors ${
                  tab === item.key
                    ? "bg-brand text-white border-brand"
                    : "bg-surface text-fog border-stroke hover:text-ink"
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>
          <div className="rounded-2xl border border-stroke bg-surface p-4 md:p-6">
            <AIArchitect
              staffMode
              embedded
              onComplete={async (aiJob) => {
                await qc.invalidateQueries({ queryKey: ["ai-architect-jobs"] });
                setSelectedId(aiJob.id);
                setTab("tutti");
              }}
            />
          </div>
        </div>
      ) : (
        <div className="flex flex-col lg:flex-row gap-5">
          <section className="lg:w-[430px] space-y-4">
            <div className="flex flex-wrap gap-2">
              {TABS.map((item) => (
                <button
                  key={item.key}
                  onClick={() => setTab(item.key)}
                  className={`font-display uppercase text-xs tracking-wider px-4 py-2 rounded-full border transition-colors ${
                    tab === item.key
                      ? "bg-brand text-white border-brand"
                      : "bg-surface text-fog border-stroke hover:text-ink"
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-2 bg-surface border border-stroke rounded-full px-4 py-2">
              <Search className="w-4 h-4 text-fog" />
              <input
                value={q}
                onChange={(event) => setQ(event.target.value)}
                placeholder="Cerca file, stile, obiettivo..."
                className="bg-transparent outline-none text-ink placeholder:text-fog w-full text-sm"
              />
            </div>

            <div className="bg-surface border border-stroke rounded-2xl overflow-hidden">
              {isLoading ? (
                <div className="px-4 py-10 text-center font-display uppercase text-xs tracking-wider text-fog animate-pulse">
                  Caricamento...
                </div>
              ) : jobs.length === 0 ? (
                <div className="px-4 py-10 text-center font-body text-sm text-fog">
                  Nessun job in questa vista.
                </div>
              ) : (
                <div className="divide-y divide-stroke/70">
                  {jobs.map((job) => {
                    const meta = STATUS[job.status] || STATUS.queued;
                    const confidence =
                      job.vision_analysis?.confidence ??
                      job.plan_type_confidence;
                    return (
                      <button
                        key={job.id}
                        onClick={() => setSelectedId(job.id)}
                        className={`w-full text-left px-4 py-4 transition-colors ${
                          selectedId === job.id
                            ? "bg-brand/10"
                            : "hover:bg-surface-2/60"
                        }`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <div className="font-display uppercase text-xs text-ink truncate">
                              {job.project_goal || "Progetto AI Architect"}
                            </div>
                            <div className="font-body text-[11px] text-fog truncate mt-1">
                              {job.original_filename}
                            </div>
                            {job.project_variant_selected && (
                              <div className="font-body text-[11px] text-brand truncate mt-1">
                                Variante {job.project_variant_selected}
                              </div>
                            )}
                          </div>
                          <span
                            className={`shrink-0 rounded-full px-2 py-1 font-display text-[9px] uppercase ${meta.cls}`}
                          >
                            {meta.label}
                          </span>
                        </div>
                        <div className="mt-3 flex flex-wrap items-center gap-2 font-body text-[11px] text-fog">
                          <span>{job.style_selected}</span>
                          <span>Qualita {qualityLabel(confidence)}</span>
                          <span>{relativeDate(job.updated_at)}</span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </section>

          <section className="flex-1 min-w-0">
            {!selectedJob ? (
              <div className="rounded-2xl border border-stroke bg-surface px-6 py-12 text-center text-fog">
                Seleziona un job AI Architect.
              </div>
            ) : (
              <div className="space-y-5">
                <div className="rounded-2xl border border-stroke bg-surface p-5">
                  <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
                    <div>
                      <div className="flex flex-wrap items-center gap-2 mb-2">
                        <span
                          className={`rounded-full px-3 py-1 font-display text-[10px] uppercase ${status.cls}`}
                        >
                          {status.label}
                        </span>
                        {selectedJob.review_status && (
                          <span className="rounded-full bg-bg border border-stroke px-3 py-1 font-display text-[10px] uppercase text-fog">
                            Review {selectedJob.review_status}
                          </span>
                        )}
                      </div>
                      <h2 className="font-display font-bold uppercase text-2xl text-ink">
                        {selectedJob.project_goal}
                      </h2>
                      <p className="font-body text-sm text-fog mt-1">
                        {selectedJob.original_filename}
                      </p>
                      {(selectedAutomationVariant.label ||
                        selectedJob.project_variant_selected) && (
                        <p className="font-body text-xs text-brand mt-2">
                          Variante scelta:{" "}
                          {selectedAutomationVariant.label ||
                            selectedJob.project_variant_selected}
                        </p>
                      )}
                      {selectedJob.linked_lead && (
                        <button
                          onClick={() =>
                            navigate(
                              `/dashboard/lead/${selectedJob.linked_lead.id}`,
                            )
                          }
                          className="mt-2 font-display uppercase text-[10px] text-brand inline-flex items-center gap-1 hover:text-ink"
                        >
                          Lead collegato: {selectedJob.linked_lead.nome}
                          {typeof selectedJob.linked_lead.score === "number"
                            ? ` (${selectedJob.linked_lead.score}/100)`
                            : ""}{" "}
                          <ExternalLink className="w-3 h-3" />
                        </button>
                      )}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {report?.image_url && (
                        <a
                          href={assetUrl(report.image_url)}
                          target="_blank"
                          rel="noreferrer"
                          className="bg-surface-2 border border-stroke text-ink rounded-full px-4 py-2 font-display uppercase text-xs inline-flex items-center gap-2"
                        >
                          <Download className="w-4 h-4" /> Report
                        </a>
                      )}
                      {selectedJob.status === "needs_review" &&
                        conceptApprovable && (
                          <button
                            onClick={() => approve.mutate(selectedJob.id)}
                            disabled={approve.isPending}
                            className="bg-brand text-white rounded-full px-4 py-2 font-display uppercase text-xs inline-flex items-center gap-2 disabled:opacity-60"
                          >
                            {approve.isPending ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <ShieldCheck className="w-4 h-4" />
                            )}
                            Approva render
                          </button>
                        )}
                      {selectedJob.status === "needs_confirmation" && (
                        <>
                          <button
                            onClick={() =>
                              confirmPlan.mutate({
                                jobId: selectedJob.id,
                                planType: "existing_state",
                              })
                            }
                            disabled={confirmPlan.isPending}
                            className="bg-brand text-white rounded-full px-4 py-2 font-display uppercase text-xs inline-flex items-center gap-2 disabled:opacity-60"
                          >
                            <CheckCircle2 className="w-4 h-4" /> Stato di fatto
                          </button>
                          <button
                            onClick={() =>
                              confirmPlan.mutate({
                                jobId: selectedJob.id,
                                planType: "defined_project",
                              })
                            }
                            disabled={confirmPlan.isPending}
                            className="bg-surface-2 border border-stroke text-ink rounded-full px-4 py-2 font-display uppercase text-xs inline-flex items-center gap-2 disabled:opacity-60"
                          >
                            <CheckCircle2 className="w-4 h-4" /> Progetto
                            definito
                          </button>
                        </>
                      )}
                      {(selectedJob.status === "completed" ||
                        selectedJob.status === "needs_review") && (
                        <>
                          <button
                            onClick={() =>
                              regenerate.mutate({
                                jobId: selectedJob.id,
                                outputTypes: ["topdown_3d_plan"],
                              })
                            }
                            disabled={regenerate.isPending}
                            className="bg-surface-2 border border-stroke text-ink rounded-full px-4 py-2 font-display uppercase text-xs inline-flex items-center gap-2 disabled:opacity-60"
                          >
                            {regenerate.isPending ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <Eye className="w-4 h-4" />
                            )}
                            Rigenera 3D
                          </button>
                          <button
                            onClick={() =>
                              regenerate.mutate({
                                jobId: selectedJob.id,
                                outputTypes: ["room_render"],
                              })
                            }
                            disabled={regenerate.isPending}
                            className="bg-surface-2 border border-stroke text-ink rounded-full px-4 py-2 font-display uppercase text-xs inline-flex items-center gap-2 disabled:opacity-60"
                          >
                            <ImageIcon className="w-4 h-4" /> Rigenera render
                          </button>
                        </>
                      )}
                      <button
                        onClick={() => reanalyze.mutate(selectedJob.id)}
                        disabled={reanalyze.isPending}
                        className="bg-surface-2 border border-stroke text-fog hover:text-ink rounded-full px-4 py-2 font-display uppercase text-xs inline-flex items-center gap-2 disabled:opacity-60"
                      >
                        {reanalyze.isPending ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Brain className="w-4 h-4" />
                        )}
                        Ri-analizza
                      </button>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 xl:grid-cols-[1.05fr_0.95fr] gap-5">
                  <div className="rounded-2xl border border-stroke bg-surface p-5">
                    <div className="flex items-center gap-2 mb-4">
                      <FileText className="w-5 h-5 text-brand" />
                      <h3 className="font-display font-semibold uppercase text-sm text-ink">
                        Concept 2D
                      </h3>
                    </div>
                    {uploadedPlanUrl &&
                      concept?.image_url !== uploadedPlanUrl && (
                        <div className="mb-4">
                          <p className="font-display uppercase text-[10px] tracking-wider text-fog mb-2">
                            Planimetria allegata
                          </p>
                          <AssetImage
                            url={uploadedPlanUrl}
                            alt="planimetria allegata"
                            className="w-full rounded-xl border border-stroke bg-bg object-contain max-h-[300px]"
                          />
                        </div>
                      )}
                    {concept?.image_url ? (
                      <div>
                        <div className="flex items-center justify-between gap-2 mb-2">
                          <p className="font-display uppercase text-[10px] tracking-wider text-fog">
                            {conceptApprovable
                              ? "2D da approvare"
                              : "2D non approvabile"}
                          </p>
                          <a
                            href={assetUrl(concept.image_url)}
                            download
                            target="_blank"
                            rel="noreferrer"
                            className="font-display uppercase text-[10px] text-brand hover:text-ink inline-flex items-center gap-1"
                          >
                            <Download className="w-3 h-3" /> Scarica
                          </a>
                        </div>
                        <AssetImage
                          url={concept.image_url}
                          alt="concept 2D"
                          className="w-full rounded-xl border border-stroke bg-bg object-contain max-h-[460px]"
                        />
                        <div className="mt-3 rounded-xl border border-warning/40 bg-warning/10 p-3">
                          <div className="flex items-start gap-2">
                            <AlertTriangle className="w-4 h-4 text-warning shrink-0 mt-0.5" />
                            <p className="font-body text-xs leading-relaxed text-fog">
                              {layout2dWarning}
                            </p>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="aspect-video rounded-xl border border-stroke bg-bg grid place-items-center text-fog text-sm">
                        Concept 2D non disponibile.
                      </div>
                    )}
                    {concept?.text_content && (
                      <p className="font-body text-xs text-fog mt-3">
                        {concept.text_content}
                      </p>
                    )}
                    {concept && !conceptApprovable && (
                      <div className="mt-3 rounded-xl border border-danger/35 bg-danger/10 p-3">
                        <p className="font-display uppercase text-[10px] tracking-wider text-danger">
                          Blocco sicurezza
                        </p>
                        <p className="font-body text-xs text-fog mt-1 leading-relaxed">
                          Output non approvabile per render: planimetria
                          sintetica, reference semplice o geometria non
                          verificata. Richiedere planimetria migliore o
                          revisione tecnica.
                        </p>
                      </div>
                    )}
                    {selectedJob.status === "needs_review" && (
                      <div className="mt-4 rounded-xl border border-stroke bg-bg p-4">
                        {layoutRegenerationAvailable ? (
                          <>
                            <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2">
                              <label
                                htmlFor="dashboard-concept-feedback"
                                className="font-display uppercase text-[10px] tracking-wider text-ink"
                              >
                                Correzione concept 2D
                              </label>
                              <span className="font-display uppercase text-[9px] tracking-wider text-warning">
                                1 rigenerazione disponibile
                              </span>
                            </div>
                            <textarea
                              id="dashboard-concept-feedback"
                              value={conceptFeedback}
                              onChange={(event) =>
                                setConceptFeedback(event.target.value)
                              }
                              rows={3}
                              placeholder="Esempio: la cabina armadio deve avere accesso dalla camera da letto, non dal bagno; non chiudere il passaggio camera-cabina."
                              className="mt-2 w-full resize-none rounded-xl border border-stroke bg-surface px-4 py-3 font-body text-sm text-ink outline-none transition-colors placeholder:text-fog focus:border-brand"
                            />
                            <div className="mt-3 flex flex-col sm:flex-row sm:items-center gap-3">
                              <button
                                type="button"
                                onClick={() => {
                                  const correctionNotes =
                                    conceptFeedback.trim();
                                  if (!correctionNotes) {
                                    toast.error(
                                      "Inserisci una correzione prima di rigenerare il 2D.",
                                    );
                                    return;
                                  }
                                  regenerate.mutate({
                                    jobId: selectedJob.id,
                                    outputTypes: ["concept_2d"],
                                    correctionNotes,
                                  });
                                }}
                                disabled={
                                  !conceptFeedback.trim() ||
                                  regenerate.isPending
                                }
                                className="bg-surface-2 border border-stroke text-ink rounded-full px-4 py-2 font-display uppercase text-xs inline-flex items-center justify-center gap-2 disabled:opacity-60"
                              >
                                <RotateCw
                                  className={`w-4 h-4 ${regenerate.isPending ? "animate-spin" : ""}`}
                                />
                                Correggi e rigenera 2D
                              </button>
                              {selectedJob.layout_correction_notes && (
                                <p className="font-body text-xs text-fog leading-relaxed">
                                  Ultima correzione:{" "}
                                  {selectedJob.layout_correction_notes}
                                </p>
                              )}
                            </div>
                          </>
                        ) : (
                          <>
                            <p className="font-display uppercase text-[10px] tracking-wider text-ink">
                              Rigenerazione 2D gia utilizzata
                            </p>
                            <p className="font-body text-xs text-fog leading-relaxed mt-2">
                              Ogni utente puo rigenerare la planimetria una sola
                              volta. Ulteriori modifiche vanno gestite dallo
                              staff in fase di sopralluogo.
                            </p>
                            {selectedJob.layout_correction_notes && (
                              <p className="font-body text-xs text-fog leading-relaxed mt-2">
                                Ultima correzione:{" "}
                                {selectedJob.layout_correction_notes}
                              </p>
                            )}
                          </>
                        )}
                      </div>
                    )}
                    {(selectedAutomationVariant.label ||
                      pipelineGate.status) && (
                      <div className="mt-4 rounded-xl border border-stroke bg-bg p-3">
                        <div className="grid grid-cols-3 gap-2">
                          <div>
                            <div className="font-display uppercase text-[9px] text-fog">
                              Variante
                            </div>
                            <div className="font-display uppercase text-xs text-ink mt-1">
                              {selectedAutomationVariant.label ||
                                selectedJob.project_variant_selected ||
                                "-"}
                            </div>
                          </div>
                          <div>
                            <div className="font-display uppercase text-[9px] text-fog">
                              Semaforo
                            </div>
                            <div className="font-display uppercase text-xs text-ink mt-1">
                              {pipelineGate.status || "-"}
                            </div>
                          </div>
                          <div>
                            <div className="font-display uppercase text-[9px] text-fog">
                              Varianti
                            </div>
                            <div className="font-display uppercase text-xs text-ink mt-1">
                              {floorPlanAutomation.variant_generation
                                ?.generated_variant_count || 1}
                            </div>
                          </div>
                        </div>
                        {pipelineGate.reason && (
                          <p className="font-body text-xs text-fog mt-2 leading-relaxed">
                            {pipelineGate.reason}
                          </p>
                        )}
                        {(technicalFloorPlan.schema ||
                          optimizedFloorPlan.schema) && (
                          <div className="mt-3 grid grid-cols-2 gap-2">
                            <div className="rounded-lg border border-stroke bg-surface p-2">
                              <div className="font-display uppercase text-[9px] text-fog">
                                JSON tecnico
                              </div>
                              <div className="font-display uppercase text-xs text-ink mt-1">
                                {technicalFloorPlan.source || "-"}
                              </div>
                              <div className="font-body text-[11px] text-fog mt-1">
                                Ambienti:{" "}
                                {(technicalFloorPlan.rooms || []).length || 0}
                              </div>
                            </div>
                            <div className="rounded-lg border border-stroke bg-surface p-2">
                              <div className="font-display uppercase text-[9px] text-fog">
                                JSON ottimizzato
                              </div>
                              <div className="font-display uppercase text-xs text-ink mt-1">
                                {optimizedFloorPlan.metadata?.selected_variant
                                  ?.label || "-"}
                              </div>
                              <div className="font-body text-[11px] text-fog mt-1">
                                Prompt visuale vincolato
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                    {(optimizationStrategy.length > 0 ||
                      floorplanBrief.approval_checklist?.length > 0) && (
                      <div className="mt-4 grid gap-3">
                        {optimizationStrategy.slice(0, 3).map((item, index) => (
                          <div
                            key={`${item.title}-${index}`}
                            className="rounded-xl border border-stroke bg-bg p-3"
                          >
                            <div className="font-display uppercase text-xs text-ink">
                              {item.title}
                            </div>
                            <p className="font-body text-xs text-fog mt-1 leading-relaxed">
                              {item.rationale}
                            </p>
                          </div>
                        ))}
                        {floorplanBrief.approval_checklist?.length > 0 && (
                          <div className="rounded-xl border border-warning/40 bg-warning/10 p-3">
                            <div className="font-display uppercase text-xs text-warning mb-2">
                              Checklist staff
                            </div>
                            <div className="grid gap-1">
                              {floorplanBrief.approval_checklist
                                .slice(0, 5)
                                .map((item) => (
                                  <p
                                    key={item}
                                    className="font-body text-xs text-fog"
                                  >
                                    {item}
                                  </p>
                                ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  <div className="rounded-2xl border border-stroke bg-surface p-5 space-y-4">
                    <div className="flex items-center gap-2">
                      <Brain className="w-5 h-5 text-brand" />
                      <h3 className="font-display font-semibold uppercase text-sm text-ink">
                        Analisi architettonica
                      </h3>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="rounded-xl border border-stroke bg-bg px-4 py-3">
                        <div className="font-display uppercase text-[10px] text-fog">
                          Qualita lettura
                        </div>
                        <div className="font-display font-bold text-sm text-ink uppercase">
                          {qualityLabel(analysisJson.confidence)}
                        </div>
                      </div>
                      <div className="rounded-xl border border-stroke bg-bg px-4 py-3">
                        <div className="font-display uppercase text-[10px] text-fog">
                          Tipo
                        </div>
                        <div className="font-display font-bold text-sm text-ink uppercase">
                          {analysisJson.plan_type_detected || "-"}
                        </div>
                      </div>
                    </div>
                    {analysisJson.dynamic_disclaimer && (
                      <div className="rounded-xl border border-warning/40 bg-warning/10 p-4">
                        <div className="flex items-start gap-2">
                          <AlertTriangle className="w-4 h-4 text-warning shrink-0 mt-0.5" />
                          <p className="font-body text-xs leading-relaxed text-fog">
                            {analysisJson.dynamic_disclaimer}
                          </p>
                        </div>
                      </div>
                    )}
                    <div>
                      <p className="font-display uppercase text-xs text-ink mb-2">
                        Ambienti rilevati
                      </p>
                      <div className="space-y-2">
                        {(analysisJson.detected_rooms || [])
                          .slice(0, 5)
                          .map((room, index) => (
                            <div
                              key={`${room.name}-${index}`}
                              className="rounded-xl border border-stroke bg-bg p-3"
                            >
                              <div className="flex items-center justify-between gap-2">
                                <span className="font-display uppercase text-xs text-ink">
                                  {room.name}
                                </span>
                                <span className="font-body text-xs text-brand">
                                  {qualityLabel(room.confidence)}
                                </span>
                              </div>
                              <p className="font-body text-xs text-fog mt-1">
                                {room.evidence}
                              </p>
                            </div>
                          ))}
                        {(analysisJson.detected_rooms || []).length === 0 && (
                          <p className="font-body text-sm text-fog">
                            Nessun ambiente rilevato con qualita sufficiente.
                          </p>
                        )}
                      </div>
                    </div>
                    {technicalFindings.length > 0 && (
                      <div>
                        <p className="font-display uppercase text-xs text-ink mb-2">
                          Verifiche tecniche
                        </p>
                        <div className="space-y-2">
                          {technicalFindings
                            .slice(0, 5)
                            .map((finding, index) => (
                              <div
                                key={`${finding.title}-${index}`}
                                className="rounded-xl border border-stroke bg-bg p-3"
                              >
                                <div className="flex items-center justify-between gap-2">
                                  <span className="font-display uppercase text-xs text-ink">
                                    {finding.title}
                                  </span>
                                  <span className="rounded-full bg-brand/10 px-2 py-1 font-display text-[9px] uppercase text-brand">
                                    {finding.severity}
                                  </span>
                                </div>
                                <p className="font-body text-xs text-fog mt-1 leading-relaxed">
                                  {finding.recommendation}
                                </p>
                              </div>
                            ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
                  <div className="rounded-2xl border border-stroke bg-surface p-5">
                    <div className="flex items-center justify-between gap-2 mb-4">
                      <div className="flex items-center gap-2">
                        <Eye className="w-5 h-5 text-brand" />
                        <h3 className="font-display font-semibold uppercase text-sm text-ink">
                          Top-down
                        </h3>
                      </div>
                      {topdown?.image_url && (
                        <a
                          href={assetUrl(topdown.image_url)}
                          download
                          target="_blank"
                          rel="noreferrer"
                          className="font-display uppercase text-[10px] text-brand hover:text-ink inline-flex items-center gap-1"
                        >
                          <Download className="w-3 h-3" /> Scarica
                        </a>
                      )}
                    </div>
                    {topdown?.image_url ? (
                      <AssetImage
                        url={topdown.image_url}
                        alt="vista top-down"
                        className="w-full rounded-xl border border-stroke bg-bg object-contain max-h-80"
                      />
                    ) : (
                      <div className="aspect-video rounded-xl border border-stroke bg-bg grid place-items-center text-fog text-sm">
                        Generato dopo approvazione.
                      </div>
                    )}
                  </div>

                  <div className="rounded-2xl border border-stroke bg-surface p-5">
                    <div className="flex items-center justify-between gap-2 mb-4">
                      <div className="flex items-center gap-2">
                        <ImageIcon className="w-5 h-5 text-brand" />
                        <h3 className="font-display font-semibold uppercase text-sm text-ink">
                          Render ambienti
                        </h3>
                      </div>
                      {renders.length > 0 && (
                        <span className="font-display uppercase text-[10px] text-fog">
                          {renders.length} render
                        </span>
                      )}
                    </div>
                    {renders.length > 0 ? (
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        {renders.map((render) => (
                          <div
                            key={render.id}
                            className="rounded-xl border border-stroke bg-bg overflow-hidden group relative"
                          >
                            <a
                              href={assetUrl(render.image_url)}
                              download
                              target="_blank"
                              rel="noreferrer"
                              className="absolute top-2 right-2 z-10 bg-bg/90 border border-stroke rounded-full p-1.5 text-brand hover:text-ink opacity-0 group-hover:opacity-100 transition-opacity"
                              title="Scarica render"
                            >
                              <Download className="w-3.5 h-3.5" />
                            </a>
                            <a
                              href={assetUrl(render.image_url)}
                              target="_blank"
                              rel="noreferrer"
                            >
                              <AssetImage
                                url={render.image_url}
                                alt={render.room_name || "render"}
                                className="w-full aspect-video object-cover"
                              />
                            </a>
                            <div className="px-3 py-2 flex items-center justify-between gap-2">
                              <span className="font-display uppercase text-[10px] text-brand truncate">
                                {render.room_name}
                              </span>
                              <a
                                href={assetUrl(render.image_url)}
                                download
                                target="_blank"
                                rel="noreferrer"
                                className="shrink-0 font-display uppercase text-[9px] text-fog hover:text-ink inline-flex items-center gap-1"
                              >
                                <Download className="w-3 h-3" /> Scarica
                              </a>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="aspect-video rounded-xl border border-stroke bg-bg grid place-items-center text-fog text-sm">
                        Nessun render generato.
                      </div>
                    )}
                  </div>
                </div>

                {estimate?.pacchetti && (
                  <div className="rounded-2xl border border-stroke bg-surface p-5">
                    <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
                      <div className="flex items-center gap-2">
                        <FileText className="w-5 h-5 text-brand" />
                        <h3 className="font-display font-semibold uppercase text-sm text-ink">
                          Computo predittivo
                        </h3>
                      </div>
                      <span
                        className={`rounded-full px-3 py-1 font-display text-[9px] uppercase ${
                          estReliable
                            ? "bg-success/15 text-success"
                            : "bg-warning/15 text-warning"
                        }`}
                      >
                        {estReliable
                          ? "Stima da planimetria quotata"
                          : "Stima AI da verificare in sopralluogo"}
                      </span>
                    </div>
                    <div className="grid grid-cols-3 gap-3">
                      {["essenziale", "premium", "luxury"].map((key) => {
                        const p = estPacchetti[key] || {};
                        return (
                          <div
                            key={key}
                            className="rounded-xl border border-stroke bg-bg p-3"
                          >
                            <div className="font-display uppercase text-[10px] text-fog capitalize">
                              {key}
                            </div>
                            <div className="font-display font-bold text-sm text-brand mt-1">
                              {euro(p.range_basso)}
                            </div>
                            <div className="font-body text-[10px] text-fog">
                              {euro(p.range_alto)}
                            </div>
                            {p.costo_mq && (
                              <div className="font-body text-[10px] text-fog mt-1">
                                ~{euro(p.costo_mq)}/mq
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                    {typeof selectedJob?.estimate_confidence === "number" && (
                      <p className="font-body text-[11px] text-fog mt-3">
                        Affidabilita lettura:{" "}
                        {Math.round(selectedJob.estimate_confidence * 100)}% ·
                        origine stima da AI Architect, da confermare con misure
                        e distribuzione in sopralluogo.
                      </p>
                    )}
                  </div>
                )}

                {loadingJob && (
                  <div className="fixed bottom-5 right-5 rounded-full bg-surface border border-stroke px-4 py-2 text-fog text-xs inline-flex items-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin" /> Aggiornamento
                    job
                  </div>
                )}
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
