import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Brain,
  CheckCircle2,
  Download,
  Eye,
  FileText,
  Image as ImageIcon,
  Loader2,
  Search,
  ShieldCheck,
} from "lucide-react";
import { toast } from "sonner";
import client, { BACKEND_URL, formatApiErrorDetail } from "@/lib/api";
import { relativeDate } from "@/lib/format";

const TABS = [
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

function assetUrl(url) {
  if (!url) return "";
  if (url.startsWith("http")) return url;
  return `${BACKEND_URL}${url}`;
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
  const [tab, setTab] = useState("needs_review");
  const [q, setQ] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const qc = useQueryClient();

  const { data: jobs = [], isLoading } = useQuery({
    queryKey: ["ai-architect-jobs", tab, q],
    queryFn: async () =>
      (
        await client.get("/ai-architect/jobs", {
          params: { status: tab, q: q || undefined },
        })
      ).data,
  });

  useEffect(() => {
    if (!selectedId && jobs.length > 0) setSelectedId(jobs[0].id);
    if (
      selectedId &&
      jobs.length > 0 &&
      !jobs.some((job) => job.id === selectedId)
    )
      setSelectedId(jobs[0].id);
  }, [jobs, selectedId]);

  const { data: selectedJob, isFetching: loadingJob } = useQuery({
    queryKey: ["ai-architect-job", selectedId],
    enabled: Boolean(selectedId),
    queryFn: async () =>
      (await client.get(`/ai-architect/jobs/${selectedId}`)).data,
  });

  const approve = useMutation({
    mutationFn: (jobId) =>
      client.post(`/ai-architect/jobs/${jobId}/approve`, {
        reviewer: "Dashboard staff",
        notes: "Concept approvato da dashboard staff.",
      }),
    onSuccess: async (_, jobId) => {
      toast.success("Concept approvato. Render avviati.");
      await qc.invalidateQueries({ queryKey: ["ai-architect-jobs"] });
      await qc.invalidateQueries({ queryKey: ["ai-architect-job", jobId] });
    },
    onError: (err) =>
      toast.error(formatApiErrorDetail(err.response?.data?.detail)),
  });

  const outputs = selectedJob?.outputs || [];
  const analysis = latest(outputs, "analysis");
  const clean2d = latest(outputs, "clean_2d_plan");
  const redistributed2d = latest(outputs, "redistributed_2d_plan");
  const topdown = latest(outputs, "topdown_3d_plan");
  const report = latest(outputs, "pdf_report");
  const renders = outputs.filter((item) => item.output_type === "room_render");
  const concept = redistributed2d || clean2d;
  const uploadedPlanUrl =
    selectedJob?.processed_file_url || selectedJob?.uploaded_file_url;
  const analysisJson =
    analysis?.json_content || selectedJob?.vision_analysis || {};
  const status = STATUS[selectedJob?.status] || STATUS.queued;

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
                    job.vision_analysis?.confidence ?? job.plan_type_confidence;
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
                    {selectedJob.status === "needs_review" && (
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
                        <img
                          src={assetUrl(uploadedPlanUrl)}
                          alt="Planimetria allegata"
                          className="w-full rounded-xl border border-stroke bg-bg object-contain max-h-[300px]"
                        />
                      </div>
                    )}
                  {concept?.image_url ? (
                    <div>
                      <p className="font-display uppercase text-[10px] tracking-wider text-fog mb-2">
                        2D da approvare
                      </p>
                      <img
                        src={assetUrl(concept.image_url)}
                        alt="Concept 2D"
                        className="w-full rounded-xl border border-stroke bg-bg object-contain max-h-[460px]"
                      />
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
                </div>
              </div>

              <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
                <div className="rounded-2xl border border-stroke bg-surface p-5">
                  <div className="flex items-center gap-2 mb-4">
                    <Eye className="w-5 h-5 text-brand" />
                    <h3 className="font-display font-semibold uppercase text-sm text-ink">
                      Top-down
                    </h3>
                  </div>
                  {topdown?.image_url ? (
                    <img
                      src={assetUrl(topdown.image_url)}
                      alt="Top-down"
                      className="w-full rounded-xl border border-stroke bg-bg object-contain max-h-80"
                    />
                  ) : (
                    <div className="aspect-video rounded-xl border border-stroke bg-bg grid place-items-center text-fog text-sm">
                      Generato dopo approvazione.
                    </div>
                  )}
                </div>

                <div className="rounded-2xl border border-stroke bg-surface p-5">
                  <div className="flex items-center gap-2 mb-4">
                    <ImageIcon className="w-5 h-5 text-brand" />
                    <h3 className="font-display font-semibold uppercase text-sm text-ink">
                      Render ambienti
                    </h3>
                  </div>
                  {renders.length > 0 ? (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      {renders.slice(0, 4).map((render) => (
                        <div
                          key={render.id}
                          className="rounded-xl border border-stroke bg-bg overflow-hidden"
                        >
                          <img
                            src={assetUrl(render.image_url)}
                            alt={render.room_name || "Render"}
                            className="w-full aspect-video object-cover"
                          />
                          <div className="px-3 py-2 font-display uppercase text-[10px] text-brand">
                            {render.room_name}
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

              {loadingJob && (
                <div className="fixed bottom-5 right-5 rounded-full bg-surface border border-stroke px-4 py-2 text-fog text-xs inline-flex items-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin" /> Aggiornamento job
                </div>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
