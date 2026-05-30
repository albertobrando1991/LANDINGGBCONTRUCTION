import { Instagram, Facebook, Linkedin, Youtube, MapPin, Phone, Mail, MessageCircle } from "lucide-react";
import { ASSETS, WHATSAPP } from "@/lib/assets";

const MARQUEE = "COSTRUIAMO VALORE · TRASFORMIAMO SPAZI · ";

export default function Footer() {
  return (
    <footer className="relative bg-bg pt-20 pb-10 overflow-hidden border-t border-stroke">
      <video
        className="absolute inset-0 w-full h-full object-cover scale-y-[-1] opacity-30"
        src={ASSETS.heroVideo}
        autoPlay
        muted
        loop
        playsInline
      />
      <div className="absolute inset-0 bg-black/75" />

      {/* Marquee */}
      <div className="relative overflow-hidden mb-16 whitespace-nowrap">
        <div className="inline-flex animate-marquee">
          {[0, 1].map((k) => (
            <span
              key={k}
              className="font-display font-bold uppercase text-5xl md:text-7xl tracking-[0.2em] text-outline pr-8"
            >
              {MARQUEE.repeat(5)}
            </span>
          ))}
        </div>
      </div>

      <div className="relative max-w-7xl mx-auto px-6 grid grid-cols-1 md:grid-cols-4 gap-10">
        <div>
          <div className="flex items-center gap-3 mb-4">
            <div className="w-11 h-11 rounded-full p-[2px] accent-metallic">
              <div className="w-full h-full rounded-full bg-bg flex items-center justify-center font-display font-bold text-ink">
                GB
              </div>
            </div>
            <span className="font-display font-bold uppercase text-lg text-ink">GB Construction</span>
          </div>
          <p className="font-display uppercase tracking-[0.2em] text-xs text-brand mb-3">
            Costruiamo valore. Trasformiamo spazi.
          </p>
          <p className="font-body text-sm text-fog">
            Impresa di ristrutturazioni chiavi in mano a Napoli e in tutta la Campania.
            Oltre 200 cantieri completati in 15 anni.
          </p>
        </div>

        <div>
          <h4 className="font-display font-semibold uppercase tracking-[0.15em] text-sm text-ink mb-4">Servizi</h4>
          <ul className="space-y-2 font-body text-sm text-fog">
            {["Ristrutturazioni complete", "Ristrutturazione bagni", "Rifacimento impianti", "Cartongesso e controsoffitti", "Infissi e serramenti", "Chiavi in mano"].map((s) => (
              <li key={s} className="hover:text-ink transition-colors cursor-pointer">{s}</li>
            ))}
          </ul>
        </div>

        <div>
          <h4 className="font-display font-semibold uppercase tracking-[0.15em] text-sm text-ink mb-4">Contatti</h4>
          <ul className="space-y-3 font-body text-sm text-fog">
            <li className="flex items-start gap-2"><MapPin className="w-4 h-4 text-brand mt-0.5" /> Via Toledo 256, Napoli (NA)</li>
            <li className="flex items-center gap-2"><Phone className="w-4 h-4 text-brand" /> +39 333 123 4567</li>
            <li className="flex items-center gap-2"><MessageCircle className="w-4 h-4 text-brand" /> WhatsApp Business</li>
            <li className="flex items-center gap-2"><Mail className="w-4 h-4 text-brand" /> info@gbconstruction.it</li>
          </ul>
        </div>

        <div>
          <h4 className="font-display font-semibold uppercase tracking-[0.15em] text-sm text-ink mb-4">Newsletter</h4>
          <p className="font-body text-sm text-fog mb-4">Ispirazioni progetti e bonus fiscali ogni mese.</p>
          <div className="flex gap-2">
            <input
              type="email"
              placeholder="La tua email"
              className="flex-1 bg-surface border border-stroke rounded-full px-4 py-2 text-sm text-ink placeholder:text-fog focus:outline-none focus:border-brand"
            />
            <button className="bg-brand text-white rounded-full px-5 py-2 font-display font-semibold uppercase tracking-wider text-xs hover:scale-105 transition-transform">
              Iscriviti
            </button>
          </div>
        </div>
      </div>

      <div className="relative max-w-7xl mx-auto px-6 mt-14 pt-6 border-t border-stroke flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          {[Instagram, Facebook, Linkedin, Youtube].map((Icon, i) => (
            <a key={i} href={WHATSAPP} target="_blank" rel="noreferrer" className="text-fog hover:text-brand transition-colors">
              <Icon className="w-5 h-5" />
            </a>
          ))}
        </div>
        <div className="flex items-center gap-2 font-display uppercase tracking-[0.15em] text-xs text-ink">
          <span className="w-2.5 h-2.5 rounded-full bg-success animate-pulse-dot" />
          Sopralluoghi disponibili questa settimana
        </div>
        <div className="font-body text-xs text-fog text-center">
          P.IVA 09876543210 · Privacy · Cookie · © 2026 GB Construction S.R.L.
        </div>
      </div>
    </footer>
  );
}
