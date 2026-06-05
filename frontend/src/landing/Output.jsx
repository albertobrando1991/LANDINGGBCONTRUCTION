import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { AlertTriangle, BarChart3, Calculator, Check, ClipboardList, X, Calendar, MessageCircle, ShieldCheck } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import Tilt3D from "@/components/Tilt3D";
import { formatEuro } from "@/lib/format";
import { WHATSAPP, PROPOSAL_POSTERS } from "@/lib/assets";
import { BACKEND_URL } from "@/lib/api";
import { openBooking } from "@/lib/booking";

const PACKAGES = [
  {
    key: "essenziale", titolo: "Soluzione Essenziale", tagline: "Pratica. Concreta. Subito.",
    border: "border-brand", color: "text-brand",
    incl: ["Demolizioni e rimozioni", "Impianti a norma DM 37/08", "Pavimenti e rivestimenti", "Tinteggiatura completa"],
    escl: ["Forniture e arredi", "Redistribuzione spazi"], fornitureTag: "Forniture escluse",
  },
  {
    key: "premium", titolo: "Soluzione Premium", tagline: "Trasforma. Ridisegna. Personalizza.",
    border: "border-fog", color: "text-ink", badge: "Più scelto",
    incl: ["Tutto l'Essenziale", "Redistribuzione interna", "Controsoffitti e cartongesso", "Finiture di qualità", "Climatizzazione predisposta"],
    escl: ["Forniture e arredi"], fornitureTag: "Forniture escluse",
  },
  {
    key: "luxury", titolo: "Soluzione Luxury", tagline: "Tutto incluso. Chiavi in mano.",
    border: "border-gold", color: "text-gold", luxury: true,
    incl: ["Tutto il Premium", "Sanitari e rubinetterie premium", "Porte e pavimenti inclusi", "Illuminazione di design", "Domotica base"],
    escl: [], fornitureTag: "Forniture incluse",
  },
];

function assetUrl(url) {
  if (!url) return "";
  if (url.startsWith("http")) return url;
  return `${BACKEND_URL}${url}`;
}

function estimateMidpoint(data = {}) {
  const low = Number(data.range_basso || 0);
  const high = Number(data.range_alto || 0);
  return low && high ? Math.round((low + high) / 2 / 100) * 100 : Number(data.totale || low || high || 0);
}

function synthEssenzialeCategories(data = {}, estimate = {}) {
  const midpoint = estimateMidpoint(data);
  const input = estimate?.input || {};
  const manyBathrooms = Number(input.bagni || 0) > 1;
  return [
    { categoria: "Demolizioni e preparazioni", totale: Math.round(midpoint * 0.16), voci: 4 },
    { categoria: "Impianti base", totale: Math.round(midpoint * (manyBathrooms ? 0.29 : 0.24)), voci: manyBathrooms ? 8 : 6 },
    { categoria: "Pavimenti e rivestimenti", totale: Math.round(midpoint * 0.27), voci: 5 },
    { categoria: "Finiture e tinteggiature", totale: Math.round(midpoint * 0.18), voci: 4 },
    { categoria: "Gestione cantiere", totale: Math.round(midpoint * 0.10), voci: 3 },
  ];
}

function packageCategories(key, data, estimate) {
  const categories = data?.categorie || [];
  return categories.length ? categories : synthEssenzialeCategories(data, estimate);
}

function packageRows(key, data, estimate) {
  const rows = data?.dettaglio || [];
  if (rows.length) return rows.slice().sort((a, b) => (b.totale || 0) - (a.totale || 0)).slice(0, 9);
  const input = estimate?.input || {};
  const mq = Number(input.mq || 80);
  return [
    { id: "ESS-01", categoria: "Preparazioni", voce: "Demolizioni, rimozioni e smaltimenti", u_m: "mq", quantita: mq, pu: 85, totale: Math.round(mq * 85) },
    { id: "ESS-02", categoria: "Impianti", voce: "Adeguamento impianto elettrico e certificazione", u_m: "mq", quantita: mq, pu: 95, totale: Math.round(mq * 95) },
    { id: "ESS-03", categoria: "Bagni", voce: "Rifacimento servizi principali", u_m: "cad", quantita: input.bagni || 1, pu: 4200, totale: Math.round((input.bagni || 1) * 4200) },
    { id: "ESS-04", categoria: "Finiture", voce: "Pavimenti, rivestimenti e tinteggiatura", u_m: "mq", quantita: mq, pu: 135, totale: Math.round(mq * 135) },
  ];
}

function riskFactors(estimate = {}, data = {}, pkg = {}) {
  const input = estimate?.input || {};
  const alerts = (estimate?.alerts || []).map((a) => a.testo).filter(Boolean);
  const risks = [...alerts];
  if (input.redistribuzione) risks.push("Modifiche distributive: muri portanti, pratiche e impianti vanno confermati in sopralluogo.");
  if (data.forniture) risks.push("Forniture incluse: brand, formati e disponibilita possono spostare il range finale.");
  if (Number(input.mq || 0) > 120) risks.push("Superficie ampia: logistica, tempi e coordinamento subappalti aumentano.");
  if ((pkg.escl || []).length) risks.push(`Esclusioni da valutare separatamente: ${pkg.escl.join(", ")}.`);
  return [...new Set(risks)].slice(0, 6);
}

export default function Output({ estimate, aiProject, onStartArchitect, bookingContext }) {
  const [selectedPackage, setSelectedPackage] = useState(null);
  const pac = estimate?.pacchetti || {};
  const aiOutputs = aiProject?.outputs || [];
  const aiReport = aiOutputs.find((o) => o.output_type === "pdf_report");
  const aiTopdown = aiOutputs.find((o) => o.output_type === "topdown_3d_plan");
  const detailPackage = useMemo(
    () => PACKAGES.find((p) => p.key === selectedPackage),
    [selectedPackage],
  );
  const detailData = detailPackage ? pac[detailPackage.key] || {} : {};
  const detailCategories = detailPackage ? packageCategories(detailPackage.key, detailData, estimate) : [];
  const detailRows = detailPackage ? packageRows(detailPackage.key, detailData, estimate) : [];
  const detailRisks = detailPackage ? riskFactors(estimate, detailData, detailPackage) : [];
  const categoryTotal = detailCategories.reduce((sum, item) => sum + Number(item.totale || 0), 0) || estimateMidpoint(detailData) || 1;

  return (
    <section className="py-20 px-6 bg-bg">
      <div className="max-w-7xl mx-auto">
        <motion.div initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.8 }} className="text-center mb-12">
          <div className="w-16 h-16 rounded-full bg-success/20 border-2 border-success flex items-center justify-center mx-auto mb-4" style={{ boxShadow: "0 0 30px hsla(142,70%,45%,0.4)" }}>
            <Check className="w-8 h-8 text-success" />
          </div>
          <h2 className="font-display font-bold uppercase text-4xl md:text-5xl text-ink">Ecco la tua stima personalizzata.</h2>
        </motion.div>

        {onStartArchitect && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-12 rounded-3xl border-2 border-brand/40 bg-brand/5 p-6 md:p-8 flex flex-col md:flex-row md:items-center md:justify-between gap-5"
          >
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 rounded-2xl bg-brand/15 text-brand flex items-center justify-center shrink-0">
                <ClipboardList className="w-6 h-6" />
              </div>
              <div>
                <h3 className="font-display font-bold uppercase text-xl text-ink">
                  Sblocca l'analisi della planimetria
                </h3>
                <p className="font-body text-sm text-fog mt-1 max-w-xl">
                  La tua richiesta è registrata. Ora puoi caricare la planimetria
                  per ricevere analisi, concept 2D, vista 3D e render fotorealistici,
                  collegati a questo preventivo.
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={onStartArchitect}
              className="shrink-0 bg-brand text-white rounded-full px-7 py-4 font-display font-semibold uppercase tracking-wider inline-flex items-center justify-center gap-2 hover:scale-[1.02] transition-transform"
            >
              Procedi con l'analisi <BarChart3 className="w-5 h-5" />
            </button>
          </motion.div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {PACKAGES.map((p, idx) => {
            const data = pac[p.key] || {};
            return (
              <motion.div key={p.key} initial={{ opacity: 0, y: 30 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: idx * 0.1 }}
                data-testid={`output-card-${p.key}`}
                className={`relative bg-surface border-2 ${p.border} rounded-3xl p-7 ${p.luxury ? "gold-gradient/5" : ""}`}>
                {p.badge && <span className="absolute -top-3 left-1/2 -translate-x-1/2 gold-gradient text-bg font-display font-bold uppercase text-[10px] px-4 py-1 rounded-full">{p.badge}</span>}
                <Tilt3D className="mb-5" max={9} radius="rounded-2xl">
                  <div className="border border-stroke rounded-2xl overflow-hidden">
                    <img src={PROPOSAL_POSTERS[p.key]} alt={p.titolo} className="block w-full h-auto" loading="lazy" />
                  </div>
                </Tilt3D>
                <h3 className={`font-display font-bold uppercase text-xl ${p.color}`}>{p.titolo}</h3>
                <p className="font-display uppercase text-xs text-fog mt-1 mb-5">{p.tagline}</p>

                <div className="mb-1 font-body text-xs text-fog uppercase tracking-wider">Da</div>
                <div className={`font-display font-bold text-4xl ${p.luxury ? "text-gold" : "text-brand"}`}>
                  {formatEuro(data.range_basso)}
                </div>
                <div className="font-body text-sm text-fog">a {formatEuro(data.range_alto)}</div>
                <div className="font-display uppercase text-xs text-fog mt-2">≈ {formatEuro(data.costo_mq)}/mq · {data.tempistiche}</div>

                <div className="h-px bg-stroke my-5" />

                <ul className="space-y-2 mb-3">
                  {p.incl.map((f) => (
                    <li key={f} className="flex items-start gap-2 font-body text-sm text-ink/90">
                      <Check className="w-4 h-4 text-success mt-0.5 shrink-0" /> {f}
                    </li>
                  ))}
                  {p.escl.map((f) => (
                    <li key={f} className="flex items-start gap-2 font-body text-sm text-fog">
                      <X className="w-4 h-4 text-fog mt-0.5 shrink-0" /> {f}
                    </li>
                  ))}
                </ul>

                <span className={`font-display uppercase text-xs ${p.luxury ? "text-gold" : "text-fog"}`}>{p.fornitureTag}</span>
                <button onClick={() => setSelectedPackage(p.key)} className={`mt-5 w-full rounded-full py-3 font-display font-semibold uppercase text-sm tracking-wider transition-transform hover:scale-[1.02] ${p.luxury ? "gold-gradient text-bg" : "bg-brand text-white"}`}>
                  Approfondisci →
                </button>
              </motion.div>
            );
          })}
        </div>

        <p className="font-body text-xs text-fog max-w-3xl mx-auto text-center mt-8">
          Valori orientativi calcolati sui dati storici di 200+ cantieri GB Construction (range ±15/20%).
          La Soluzione Luxury include il pacchetto forniture standard da capitolato. Variazioni su richiesta valutate in sopralluogo gratuito.
        </p>

        {aiProject && (
          <div className="bg-surface border border-brand/40 rounded-2xl p-6 mt-12">
            <div className="grid grid-cols-1 lg:grid-cols-[0.9fr_1.1fr] gap-6 items-center">
              <div>
                <p className="font-display font-semibold uppercase tracking-[0.2em] text-xs text-brand mb-2">AI Architect collegato</p>
                <h3 className="font-display font-bold uppercase text-2xl text-ink">Il preventivo include il concept generato dalla tua planimetria.</h3>
                <p className="font-body text-sm text-fog mt-3">
                  Output salvati nel CRM: analisi, planimetria 2D, top-down 3D, render ambienti e report finale.
                </p>
                {aiReport?.image_url && (
                  <a
                    href={`${BACKEND_URL}/api/ai-architect/jobs/${aiProject.id}/report`}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-5 inline-flex bg-brand text-white rounded-full px-6 py-3 font-display font-semibold uppercase text-sm tracking-wider"
                  >
                    Scarica report AI
                  </a>
                )}
              </div>
              {aiTopdown?.image_url && (
                <img src={assetUrl(aiTopdown.image_url)} alt="Planimetria AI Architect" className="w-full rounded-xl border border-stroke" />
              )}
            </div>
          </div>
        )}

        {/* Render preview */}
        <div className="bg-surface border border-stroke rounded-2xl p-6 mt-12">
          <p className="font-display font-semibold uppercase text-sm text-ink mb-4">📷 Stiamo generando un'anteprima visiva del tuo progetto…</p>
          <div className="grid grid-cols-3 gap-3">
            {[0, 1, 2].map((i) => <Skeleton key={i} className="aspect-video rounded-xl bg-surface-2" />)}
          </div>
          <p className="font-body text-xs text-fog mt-4">L'anteprima sarà disponibile via email entro 5 minuti.</p>
        </div>

        {/* Dual CTA */}
        <div className="bg-gradient-to-r from-brand/15 to-transparent border border-brand/30 rounded-3xl p-8 mt-10 text-center">
          <h3 className="font-display font-bold uppercase text-2xl md:text-3xl text-ink mb-6">Il prossimo passo è il sopralluogo gratuito.</h3>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <button data-testid="output-prenota" onClick={() => openBooking(bookingContext)} className="bg-brand text-white rounded-full px-8 py-4 font-display font-semibold uppercase tracking-wider inline-flex items-center justify-center gap-2 hover:scale-105 transition-transform">
              <Calendar className="w-5 h-5" /> Prenota sopralluogo gratuito
            </button>
            <a data-testid="output-whatsapp" href={WHATSAPP} target="_blank" rel="noreferrer" className="bg-surface border border-stroke text-ink rounded-full px-8 py-4 font-display font-semibold uppercase tracking-wider inline-flex items-center justify-center gap-2 hover:border-success transition-colors">
              <MessageCircle className="w-5 h-5 text-success" /> Parla con un tecnico su WhatsApp
            </a>
          </div>
          <p className="font-display uppercase text-xs text-fog mt-5 inline-flex items-center gap-2 justify-center">
            <ShieldCheck className="w-4 h-4 text-success" /> Sopralluogo sempre gratuito e senza impegno
          </p>
        </div>
      </div>

      {detailPackage && (
        <div className="fixed inset-0 z-[80] bg-black/80 backdrop-blur-sm px-4 py-6 overflow-y-auto">
          <div className="mx-auto max-w-6xl bg-surface border border-stroke rounded-3xl shadow-2xl overflow-hidden">
            <div className="sticky top-0 z-10 bg-surface/95 backdrop-blur border-b border-stroke px-5 md:px-7 py-5 flex items-start justify-between gap-4">
              <div>
                <p className="font-display uppercase tracking-[0.2em] text-xs text-brand mb-2">Approfondimento preventivo predittivo</p>
                <h3 className={`font-display font-bold uppercase text-2xl md:text-3xl ${detailPackage.color}`}>{detailPackage.titolo}</h3>
                <p className="font-body text-sm text-fog mt-1">{detailPackage.tagline}</p>
              </div>
              <button onClick={() => setSelectedPackage(null)} className="shrink-0 w-10 h-10 rounded-full border border-stroke bg-bg text-fog hover:text-ink grid place-items-center">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-5 md:p-7 space-y-7">
              <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                <Metric label="Range da" value={formatEuro(detailData.range_basso)} />
                <Metric label="Range a" value={formatEuro(detailData.range_alto)} />
                <Metric label="Valore medio" value={formatEuro(estimateMidpoint(detailData))} />
                <Metric label="Costo/mq" value={`${formatEuro(detailData.costo_mq)}/mq`} />
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-[0.95fr_1.05fr] gap-5">
                <section className="bg-bg border border-stroke rounded-2xl p-5">
                  <div className="flex items-center gap-2 mb-4">
                    <BarChart3 className="w-5 h-5 text-brand" />
                    <h4 className="font-display font-semibold uppercase text-sm text-ink">Composizione stimata</h4>
                  </div>
                  <div className="space-y-3">
                    {detailCategories.map((cat) => {
                      const pct = Math.max(3, Math.round((Number(cat.totale || 0) / categoryTotal) * 100));
                      return (
                        <div key={cat.categoria}>
                          <div className="flex items-center justify-between gap-3 text-xs mb-1">
                            <span className="font-body text-ink truncate">{cat.categoria}</span>
                            <span className="font-display text-brand">{formatEuro(cat.totale)}</span>
                          </div>
                          <div className="h-2 rounded-full bg-surface-2 overflow-hidden">
                            <div className="h-full bg-brand" style={{ width: `${Math.min(pct, 100)}%` }} />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </section>

                <section className="bg-bg border border-stroke rounded-2xl p-5">
                  <div className="flex items-center gap-2 mb-4">
                    <Calculator className="w-5 h-5 text-brand" />
                    <h4 className="font-display font-semibold uppercase text-sm text-ink">Base calcolo</h4>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <Info label="Superficie" value={`${estimate?.input?.mq || "-"} mq`} />
                    <Info label="Bagni" value={estimate?.input?.bagni ?? "-"} />
                    <Info label="Camere" value={estimate?.input?.camere ?? "-"} />
                    <Info label="Tempistiche" value={detailData.tempistiche || "-"} />
                    <Info label="Forniture" value={detailData.forniture ? "Incluse" : "Escluse"} />
                    <Info label="Voci computo" value={detailData.n_voci || detailRows.length || "Predittive"} />
                  </div>
                  <p className="font-body text-xs text-fog mt-4">
                    Il range deriva da voci standard GB, coefficienti storici, superficie, livello finiture e complessita prevista. Il sopralluogo converte questa stima in capitolato definitivo.
                  </p>
                </section>
              </div>

              <section className="bg-bg border border-stroke rounded-2xl p-5">
                <div className="flex items-center gap-2 mb-4">
                  <ClipboardList className="w-5 h-5 text-brand" />
                  <h4 className="font-display font-semibold uppercase text-sm text-ink">Voci principali del computo</h4>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-stroke text-left font-display uppercase text-[10px] tracking-wider text-fog">
                        <th className="py-2 pr-3">Voce</th>
                        <th className="py-2 pr-3">Categoria</th>
                        <th className="py-2 pr-3">Q.ta</th>
                        <th className="py-2 pr-3">PU</th>
                        <th className="py-2 text-right">Totale</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detailRows.map((row) => (
                        <tr key={`${row.id}-${row.voce}`} className="border-b border-stroke/50">
                          <td className="py-2 pr-3 font-body text-ink">{row.voce}</td>
                          <td className="py-2 pr-3 font-body text-fog">{row.categoria}</td>
                          <td className="py-2 pr-3 font-display text-xs text-fog">{row.quantita} {row.u_m}</td>
                          <td className="py-2 pr-3 font-display text-xs text-fog">{formatEuro(row.pu)}</td>
                          <td className="py-2 font-display text-xs text-brand text-right">{formatEuro(row.totale)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                <section className="bg-bg border border-stroke rounded-2xl p-5">
                  <h4 className="font-display font-semibold uppercase text-sm text-ink mb-4">Incluso / escluso</h4>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      {detailPackage.incl.map((item) => (
                        <div key={item} className="flex items-start gap-2 font-body text-sm text-ink">
                          <Check className="w-4 h-4 text-success mt-0.5 shrink-0" /> {item}
                        </div>
                      ))}
                    </div>
                    <div className="space-y-2">
                      {(detailPackage.escl.length ? detailPackage.escl : ["Nessuna esclusione principale"]).map((item) => (
                        <div key={item} className="flex items-start gap-2 font-body text-sm text-fog">
                          <X className="w-4 h-4 text-fog mt-0.5 shrink-0" /> {item}
                        </div>
                      ))}
                    </div>
                  </div>
                </section>

                <section className="bg-bg border border-stroke rounded-2xl p-5">
                  <div className="flex items-center gap-2 mb-4">
                    <AlertTriangle className="w-5 h-5 text-brand" />
                    <h4 className="font-display font-semibold uppercase text-sm text-ink">Variabili da verificare</h4>
                  </div>
                  <div className="space-y-2">
                    {detailRisks.map((risk) => (
                      <div key={risk} className="font-body text-sm text-fog border-l-2 border-brand/60 pl-3">{risk}</div>
                    ))}
                  </div>
                </section>
              </div>

              {aiProject && (
                <section className="bg-brand/10 border border-brand/40 rounded-2xl p-5">
                  <h4 className="font-display font-semibold uppercase text-sm text-ink mb-2">Collegamento AI Architect</h4>
                  <p className="font-body text-sm text-fog">
                    Il preventivo puo essere affinato con ambienti, vincoli e concept emersi dalla planimetria caricata. Nel passaggio successivo il tecnico trasforma questa previsione in computo verificato.
                  </p>
                </section>
              )}

              <div className="bg-gradient-to-r from-brand/15 to-transparent border border-brand/30 rounded-2xl p-5 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                <div>
                  <h4 className="font-display font-bold uppercase text-lg text-ink">Approfondimento completato</h4>
                  <p className="font-body text-sm text-fog">Il prossimo step e confermare misure, stato impianti e finiture in sopralluogo gratuito.</p>
                </div>
                <div className="flex flex-col sm:flex-row gap-3">
                  <button onClick={() => openBooking(bookingContext)} className="bg-brand text-white rounded-full px-5 py-3 font-display font-semibold uppercase text-xs">Prenota sopralluogo</button>
                  <a href={WHATSAPP} target="_blank" rel="noreferrer" className="bg-surface border border-stroke text-ink rounded-full px-5 py-3 font-display font-semibold uppercase text-xs text-center">WhatsApp tecnico</a>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

function Metric({ label, value }) {
  return (
    <div className="bg-bg border border-stroke rounded-2xl p-4 min-h-[92px]">
      <p className="font-display uppercase tracking-wider text-[10px] text-fog mb-2">{label}</p>
      <p className="font-display font-bold text-xl text-ink break-words">{value || "-"}</p>
    </div>
  );
}

function Info({ label, value }) {
  return (
    <div className="bg-surface border border-stroke/70 rounded-xl p-3 min-h-[72px]">
      <p className="font-display uppercase tracking-wider text-[10px] text-fog mb-1">{label}</p>
      <p className="font-body text-sm text-ink break-words">{value || "-"}</p>
    </div>
  );
}
