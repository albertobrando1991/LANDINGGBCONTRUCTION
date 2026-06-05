import { useState } from "react";
import { motion } from "framer-motion";
import { SlidersHorizontal, ArrowLeft, ArrowRight } from "lucide-react";

// Domande semplici e NON tecniche per chi non carica una planimetria.
// Ogni risposta mappa 1:1 su un flag del motore predittivo GB (LeadConfig).
// Lasciare una domanda senza risposta e' lecito: il backend applica il default per fascia.
const QUESTIONS = [
  {
    key: "redistribuzione",
    label: "Disposizione degli spazi",
    hint: "Vuoi mantenere la pianta attuale o spostare pareti?",
    options: [
      { value: false, label: "Mantieni com'e" },
      { value: true, label: "Sposta pareti" },
    ],
  },
  {
    key: "rifacimento_elettrico",
    label: "Impianto elettrico",
    options: [
      { value: true, label: "Da rifare" },
      { value: false, label: "Lascia com'e" },
    ],
  },
  {
    key: "rifacimento_idrico",
    label: "Impianto idrico e bagni",
    options: [
      { value: true, label: "Da rifare" },
      { value: false, label: "Lascia com'e" },
    ],
  },
  {
    key: "rifacimento_termico",
    label: "Riscaldamento / caldaia",
    options: [
      { value: true, label: "Da rifare" },
      { value: false, label: "Lascia com'e" },
    ],
  },
  {
    key: "clima",
    label: "Climatizzazione",
    options: [
      { value: "no", label: "No" },
      { value: "predisposizione", label: "Predisposizione" },
      { value: "completo", label: "Completa" },
    ],
  },
  {
    key: "infissi",
    label: "Infissi / finestre",
    options: [
      { value: "no", label: "No" },
      { value: "parziale", label: "Alcuni" },
      { value: "completo", label: "Tutti" },
    ],
  },
  {
    key: "controsoffitto",
    label: "Controsoffitti / cartongesso",
    options: [
      { value: true, label: "Si" },
      { value: false, label: "No" },
    ],
  },
  {
    key: "forniture_incluse",
    label: "Forniture e arredi",
    options: [
      { value: false, label: "Escluse" },
      { value: true, label: "Incluse" },
    ],
  },
];

export default function QuickDetails({ baseConfig, onComplete, onBack }) {
  const [answers, setAnswers] = useState({});

  const pick = (key, value) => setAnswers((a) => ({ ...a, [key]: value }));
  const answeredCount = Object.keys(answers).length;

  return (
    <section
      id="quick-details"
      className="relative min-h-screen bg-bg px-5 py-20 sm:px-6"
    >
      <div className="absolute inset-0 blueprint-grid opacity-[0.03]" />
      <div className="relative mx-auto w-full max-w-3xl min-w-0">
        <div className="text-center mb-8">
          <p className="font-display font-semibold uppercase tracking-[0.3em] text-xs text-brand mb-3">
            Dettagli per una stima piu precisa
          </p>
          <h2 className="font-display font-bold uppercase text-3xl md:text-5xl tracking-tight text-ink">
            Poche domande, niente tecnicismi
          </h2>
          <p className="font-body text-fog mt-3">
            Senza planimetria bastano questi dettagli per affinare il preventivo.
            Puoi anche saltarli: useremo stime di massima per la tua fascia.
          </p>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-surface border border-stroke rounded-3xl p-5 md:p-8 space-y-6"
        >
          <div className="flex items-center gap-3">
            <SlidersHorizontal className="w-5 h-5 text-brand" />
            <h3 className="font-display font-bold uppercase text-lg text-ink">
              Intervento previsto
            </h3>
          </div>

          {QUESTIONS.map((question) => (
            <div key={question.key}>
              <p className="font-display font-semibold uppercase text-sm text-ink">
                {question.label}
              </p>
              {question.hint && (
                <p className="font-body text-xs text-fog mt-1">{question.hint}</p>
              )}
              <div className="flex flex-wrap gap-2 mt-3">
                {question.options.map((option) => {
                  const active = answers[question.key] === option.value;
                  return (
                    <button
                      key={String(option.value)}
                      type="button"
                      onClick={() => pick(question.key, option.value)}
                      className={`font-display font-semibold uppercase text-sm rounded-full px-5 py-2.5 border transition-all ${
                        active
                          ? "bg-brand text-white border-brand"
                          : "bg-bg text-ink border-stroke hover:border-brand"
                      }`}
                    >
                      {option.label}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}

          <div className="flex items-center justify-between pt-2">
            <button
              type="button"
              onClick={onBack}
              className="font-display font-semibold uppercase text-sm text-fog hover:text-ink inline-flex items-center gap-2"
            >
              <ArrowLeft className="w-4 h-4" /> Indietro
            </button>
            <button
              type="button"
              onClick={() => onComplete(answers)}
              className="bg-brand text-white rounded-full px-8 py-4 font-display font-semibold uppercase tracking-wider inline-flex items-center gap-2"
            >
              {answeredCount > 0 ? "Continua al preventivo" : "Salta e continua"}
              <ArrowRight className="w-5 h-5" />
            </button>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
