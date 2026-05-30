import Tilt3D from "@/components/Tilt3D";
import { STAFF_PHOTOS } from "@/lib/assets";

const TEAM = [
  { name: "Giuseppe Brancale", role: "Founder | Geometra", desc: "Fondatore e anima tecnica di GB Construction. Segue ogni progetto dal sopralluogo alla consegna chiavi in mano, con attenzione maniacale al dettaglio." },
  { name: "Giovanni Brancale", role: "Capo Cantiere", desc: "Esperienza e mani in cantiere. Coordina le squadre e garantisce tempi, sicurezza e finiture impeccabili su ogni lavoro." },
  { name: "Vincenzo Brancale", role: "Coordinatore Cantieri & Fornitori", desc: "Responsabile gestione fornitori e materiali. Coordina operai e cantieri assicurando qualità delle forniture e rispetto del capitolato." },
];

export default function Team() {
  return (
    <section id="team" className="py-24 bg-bg px-6 relative overflow-hidden">
      <div className="absolute inset-0 blueprint-grid opacity-[0.03] pointer-events-none" />
      <div className="relative max-w-7xl mx-auto">
        <p className="font-display font-semibold uppercase tracking-[0.3em] text-xs text-brand mb-3 text-center">Il team GB</p>
        <h2 className="font-display font-bold uppercase text-4xl md:text-6xl tracking-tight text-ink text-center mb-4">
          Persone vere, <span className="text-brand">non slogan.</span>
        </h2>
        <p className="font-body text-fog text-center max-w-2xl mx-auto mb-14">
          Un'impresa di famiglia con oltre 15 anni di cantieri in Campania. Ci metti la casa, noi ci mettiamo la faccia.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-7">
          {TEAM.map((m) => (
            <Tilt3D key={m.name} max={10} radius="rounded-3xl">
              <div className="relative bg-surface border border-stroke">
                <div className="aspect-[4/5] overflow-hidden">
                  <img src={STAFF_PHOTOS[m.name]} alt={m.name} className="w-full h-full object-cover" loading="lazy" />
                </div>
                <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/10 to-transparent pointer-events-none" />
                <div className="absolute bottom-0 left-0 right-0 p-6">
                  <div className="font-display font-bold uppercase text-xl text-ink">{m.name}</div>
                  <div className="font-display uppercase tracking-wider text-xs text-brand mt-1 mb-3">{m.role}</div>
                  <p className="font-body text-sm text-ink/75">{m.desc}</p>
                </div>
              </div>
            </Tilt3D>
          ))}
        </div>
      </div>
    </section>
  );
}
