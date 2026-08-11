import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Sparkles,
  UploadCloud,
} from "lucide-react";
import { toast } from "sonner";
import client, { formatApiErrorDetail } from "@/lib/api";

const MAX_PLAN_FILE_BYTES = 20 * 1024 * 1024;

const PLAN_TYPES = [
  { id: "existing_state", label: "Stato attuale dell'immobile" },
  { id: "defined_project", label: "Progetto già definito" },
  { id: "auto", label: "Non lo so, la valuterà il team GB" },
];

const STYLES = [
  "Moderno minimal",
  "Contemporaneo caldo",
  "Classico elegante",
  "Japandi",
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

const PROJECT_DIRECTIONS = [
  {
    id: "conservative",
    label: "Conservativa",
    detail: "Interventi mirati e costi controllati.",
  },
  {
    id: "premium_suite",
    label: "Premium",
    detail: "Comfort, finiture e valore percepito elevato.",
  },
  {
    id: "investment",
    label: "Investimento",
    detail: "Spazi flessibili e valorizzazione immobiliare.",
  },
  {
    id: "family",
    label: "Family",
    detail: "Funzionalità, contenimento e vita quotidiana.",
  },
  {
    id: "smart_working",
    label: "Smart working",
    detail: "Studio, ospiti e ambienti multifunzione.",
  },
];

const PRIORITIES = [
  "più spazio",
  "più luce",
  "cucina più grande",
  "open space",
  "più camere",
  "cabina armadio",
  "bagno aggiuntivo",
  "lavanderia",
  "più contenimento",
  "immagine luxury",
];

const RENDER_ROOMS = [
  "Soggiorno",
  "Cucina",
  "Camera matrimoniale",
  "Cameretta",
  "Bagno",
  "Ingresso",
  "Studio",
  "Cabina armadio",
  "Lavanderia",
  "Terrazzo",
];

const INITIAL_FORM = {
  file: null,
  planType: "auto",
  projectDirection: "premium_suite",
  style: "Moderno minimal",
  goal: "Ristrutturazione completa",
  priorities: ["più luce", "open space", "immagine luxury"],
  rooms: ["Soggiorno", "Cucina", "Camera matrimoniale", "Bagno"],
  sqm: "",
  residents: "",
  budget: "",
  notes: "",
};

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

export default function RenderRequest({
  baseConfig,
  leadId,
  onComplete,
  onSkip,
}) {
  const [step, setStep] = useState(1);
  const [submitting, setSubmitting] = useState(false);
  const [request, setRequest] = useState(null);
  const [form, setForm] = useState(() => ({
    ...INITIAL_FORM,
    sqm: baseConfig?.mq ? String(baseConfig.mq) : "",
    style: baseConfig?.stile || INITIAL_FORM.style,
  }));

  const update = (patch) => setForm((current) => ({ ...current, ...patch }));

  const selectPlanFile = (file) => {
    if (file && file.size > MAX_PLAN_FILE_BYTES) {
      toast.error("Il file supera il limite di 20 MB.");
      update({ file: null });
      return;
    }
    update({ file: file || null });
  };

  const toggleListItem = (field, value) => {
    const values = form[field];
    update({
      [field]: values.includes(value)
        ? values.filter((item) => item !== value)
        : [...values, value],
    });
  };

  const canContinue =
    step === 1
      ? Boolean(form.file && form.planType && form.style)
      : form.rooms.length > 0;

  const submitRequest = async () => {
    if (!form.file || !leadId || form.rooms.length === 0) return;
    setSubmitting(true);
    try {
      const payload = new FormData();
      payload.append("planimetria", form.file);
      payload.append("plan_type_selected", form.planType);
      payload.append("project_variant_selected", form.projectDirection);
      payload.append("style_selected", form.style);
      payload.append("project_goal", form.goal);
      payload.append("priorities", JSON.stringify(form.priorities));
      payload.append("requested_rooms", JSON.stringify(form.rooms));
      payload.append("lead_id", leadId);
      if (form.sqm) payload.append("sqm", form.sqm);
      if (form.residents) payload.append("residents", form.residents);
      if (form.budget) payload.append("budget", form.budget);
      if (form.notes) payload.append("notes", form.notes);

      const { data } = await client.post("/render-requests", payload, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setRequest(data);
      setStep(3);
      toast.success("Richiesta render inviata allo staff");
    } catch (error) {
      toast.error(formatApiErrorDetail(error.response?.data?.detail));
    } finally {
      setSubmitting(false);
    }
  };

  const goNext = () => {
    if (step === 1) setStep(2);
    if (step === 2) submitRequest();
  };

  const goBack = () => {
    if (step === 2) {
      setStep(1);
      return;
    }
    onSkip?.();
  };

  return (
    <section
      id="render-request"
      className="relative min-h-screen overflow-hidden bg-bg px-6 py-20"
    >
      <div className="blueprint-grid absolute inset-0 opacity-[0.025]" />
      <div className="relative mx-auto grid max-w-7xl grid-cols-1 items-start gap-10 lg:grid-cols-[0.85fr_1.15fr]">
        <div className="lg:sticky lg:top-8">
          <p className="mb-3 font-display text-xs font-semibold uppercase tracking-[0.3em] text-brand">
            Render personalizzati GB Construction · €300
          </p>
          <h2 className="font-display text-4xl font-bold uppercase leading-none tracking-tight text-ink md:text-6xl">
            Raccontaci come vuoi trasformare ogni ambiente
          </h2>
          <p className="mt-5 max-w-xl font-body text-fog">
            Carica la planimetria e scegli stile, ambienti e priorità. Il team
            GB preparerà i render personalizzati e te li invierà dopo la
            verifica interna.
          </p>
          <div className="mt-8">
            <div className="mb-2 flex justify-between font-display text-xs uppercase text-fog">
              <span>Step {step} di 3</span>
              <span>{Math.round((step / 3) * 100)}%</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-stroke">
              <div
                className="h-full accent-gradient transition-all"
                style={{ width: `${(step / 3) * 100}%` }}
              />
            </div>
          </div>
          <p className="mt-5 font-body text-xs text-fog">
            Servizio premium da €300. Conferma e pagamento saranno concordati
            con lo staff dopo la verifica del materiale.
          </p>
        </div>

        <div className="rounded-3xl border border-stroke bg-surface p-5 md:p-8">
          <AnimatePresence mode="wait">
            {step === 1 && (
              <motion.div
                key="render-step-1"
                initial={{ opacity: 0, y: 18 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -18 }}
              >
                <div className="mb-6 flex items-center gap-3">
                  <UploadCloud className="h-6 w-6 text-brand" />
                  <h3 className="font-display text-2xl font-bold uppercase text-ink">
                    Planimetria e stile
                  </h3>
                </div>

                <label className="block cursor-pointer rounded-2xl border-2 border-dashed border-stroke bg-bg/60 px-6 py-10 transition-colors hover:border-brand">
                  <input
                    type="file"
                    accept=".pdf,.png,.jpg,.jpeg,.webp,.dwg,.dxf,.ifc"
                    className="hidden"
                    onChange={(event) =>
                      selectPlanFile(event.target.files?.[0])
                    }
                  />
                  <UploadCloud className="mx-auto mb-4 h-11 w-11 text-brand" />
                  <p className="text-center font-display font-semibold uppercase text-ink">
                    {form.file ? form.file.name : "Carica la planimetria"}
                  </p>
                  <p className="mt-2 text-center font-body text-xs text-fog">
                    PDF, PNG, JPG, WEBP, DWG, DXF, IFC · massimo 20 MB
                  </p>
                </label>

                <div className="mt-4 flex flex-col gap-3 rounded-2xl border border-stroke bg-bg/40 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
                  <p className="font-body text-sm text-fog">
                    Il servizio render è opzionale: il preventivo è già pronto.
                  </p>
                  <button
                    type="button"
                    onClick={onSkip}
                    className="inline-flex shrink-0 items-center gap-2 font-display text-sm font-semibold uppercase text-brand hover:text-ink"
                  >
                    Torna al preventivo <ArrowRight className="h-4 w-4" />
                  </button>
                </div>

                <div className="mt-7 space-y-6">
                  <div>
                    <p className="mb-3 font-display text-sm font-semibold uppercase text-ink">
                      Tipo di planimetria
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
                    <p className="mb-3 font-display text-sm font-semibold uppercase text-ink">
                      Stile desiderato
                    </p>
                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
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
                </div>
              </motion.div>
            )}

            {step === 2 && (
              <motion.div
                key="render-step-2"
                initial={{ opacity: 0, y: 18 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -18 }}
              >
                <div className="mb-6 flex items-center gap-3">
                  <Sparkles className="h-6 w-6 text-brand" />
                  <h3 className="font-display text-2xl font-bold uppercase text-ink">
                    Ambienti e indicazioni
                  </h3>
                </div>

                <div className="space-y-7">
                  <div>
                    <p className="mb-3 font-display text-sm font-semibold uppercase text-ink">
                      Obiettivo del progetto
                    </p>
                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
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
                    <p className="mb-3 font-display text-sm font-semibold uppercase text-ink">
                      Direzione progettuale
                    </p>
                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                      {PROJECT_DIRECTIONS.map((direction) => (
                        <button
                          key={direction.id}
                          type="button"
                          onClick={() =>
                            update({ projectDirection: direction.id })
                          }
                          className={`rounded-2xl border px-4 py-4 text-left transition-colors ${
                            form.projectDirection === direction.id
                              ? "border-brand bg-brand/10"
                              : "border-stroke bg-bg hover:border-brand"
                          }`}
                        >
                          <span className="block font-display text-xs font-semibold uppercase text-ink">
                            {direction.label}
                          </span>
                          <span className="mt-1 block font-body text-xs leading-relaxed text-fog">
                            {direction.detail}
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <p className="mb-1 font-display text-sm font-semibold uppercase text-ink">
                      Quali ambienti vuoi ricevere?
                    </p>
                    <p className="mb-3 font-body text-xs text-fog">
                      È previsto un render personalizzato per ogni ambiente
                      selezionato.
                    </p>
                    <div className="flex flex-wrap gap-3">
                      {RENDER_ROOMS.map((room) => (
                        <ToggleButton
                          key={room}
                          active={form.rooms.includes(room)}
                          onClick={() => toggleListItem("rooms", room)}
                        >
                          {room}
                        </ToggleButton>
                      ))}
                    </div>
                  </div>

                  <div>
                    <p className="mb-3 font-display text-sm font-semibold uppercase text-ink">
                      Priorità
                    </p>
                    <div className="flex flex-wrap gap-3">
                      {PRIORITIES.map((priority) => (
                        <ToggleButton
                          key={priority}
                          active={form.priorities.includes(priority)}
                          onClick={() => toggleListItem("priorities", priority)}
                        >
                          {priority}
                        </ToggleButton>
                      ))}
                    </div>
                  </div>

                  <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                    <input
                      value={form.sqm}
                      onChange={(event) => update({ sqm: event.target.value })}
                      type="number"
                      min="1"
                      placeholder="Metri quadri"
                      className="rounded-xl border border-stroke bg-bg px-4 py-3 text-ink placeholder:text-fog focus:border-brand focus:outline-none"
                    />
                    <input
                      value={form.residents}
                      onChange={(event) =>
                        update({ residents: event.target.value })
                      }
                      type="number"
                      min="1"
                      placeholder="Persone in casa"
                      className="rounded-xl border border-stroke bg-bg px-4 py-3 text-ink placeholder:text-fog focus:border-brand focus:outline-none"
                    />
                    <input
                      value={form.budget}
                      onChange={(event) =>
                        update({ budget: event.target.value })
                      }
                      placeholder="Budget indicativo"
                      className="rounded-xl border border-stroke bg-bg px-4 py-3 text-ink placeholder:text-fog focus:border-brand focus:outline-none"
                    />
                  </div>
                  <textarea
                    value={form.notes}
                    onChange={(event) => update({ notes: event.target.value })}
                    placeholder="Colori, materiali, vincoli, desideri e indicazioni per gli ambienti..."
                    rows={5}
                    className="w-full resize-none rounded-xl border border-stroke bg-bg px-4 py-3 text-ink placeholder:text-fog focus:border-brand focus:outline-none"
                  />
                </div>
              </motion.div>
            )}

            {step === 3 && (
              <motion.div
                key="render-request-complete"
                initial={{ opacity: 0, y: 18 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -18 }}
              >
                <div className="mb-6 grid h-16 w-16 place-items-center rounded-full border border-success/40 bg-success/15">
                  <CheckCircle2 className="h-8 w-8 text-success" />
                </div>
                <p className="mb-2 font-display text-xs font-semibold uppercase tracking-[0.2em] text-success">
                  Richiesta ricevuta
                </p>
                <h3 className="font-display text-3xl font-bold uppercase text-ink">
                  Ora se ne occupa il team GB
                </h3>
                <p className="mt-4 font-body text-sm leading-relaxed text-fog">
                  Lo staff controllerà la planimetria e le indicazioni,
                  confermerà il servizio da €300 e ti contatterà per pagamento,
                  tempi di consegna e invio dei render personalizzati.
                </p>
                <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <div className="rounded-2xl border border-stroke bg-bg p-4">
                    <p className="font-display text-[10px] uppercase tracking-wider text-fog">
                      Stile scelto
                    </p>
                    <p className="mt-1 font-body text-sm text-ink">
                      {form.style}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-stroke bg-bg p-4">
                    <p className="font-display text-[10px] uppercase tracking-wider text-fog">
                      Servizio
                    </p>
                    <p className="mt-1 font-body text-sm text-ink">
                      {form.rooms.length} ambienti personalizzati · €300
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  data-testid="render-request-complete"
                  onClick={() => onComplete?.(request)}
                  className="mt-7 inline-flex w-full items-center justify-center gap-2 rounded-full bg-brand px-8 py-4 font-display font-semibold uppercase tracking-wider text-white"
                >
                  Torna alla stima <ArrowRight className="h-5 w-5" />
                </button>
              </motion.div>
            )}
          </AnimatePresence>

          {step < 3 && (
            <div className="mt-8 flex items-center justify-between">
              <button
                type="button"
                onClick={goBack}
                className="inline-flex items-center gap-2 font-display text-sm font-semibold uppercase text-fog hover:text-ink"
              >
                <ArrowLeft className="h-4 w-4" />
                {step === 1 ? "Torna al preventivo" : "Indietro"}
              </button>
              <button
                type="button"
                onClick={goNext}
                disabled={!canContinue || submitting}
                className="inline-flex items-center gap-2 rounded-full bg-brand px-8 py-4 font-display font-semibold uppercase tracking-wider text-white disabled:opacity-40"
              >
                {submitting
                  ? "Invio..."
                  : step === 2
                    ? "Invia richiesta · €300"
                    : "Continua"}{" "}
                <ArrowRight className="h-5 w-5" />
              </button>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
