import {
  Instagram,
  Facebook,
  MapPin,
  Phone,
  Mail,
  MessageCircle,
} from "lucide-react";
import HlsVideo from "@/components/HlsVideo";
import { ASSETS, WHATSAPP } from "@/lib/assets";
import BrandMark from "@/brand/BrandMark";
import { brand } from "@/brand/identity";

const MARQUEE = `${brand.tagline.replace(/\./g, "").toUpperCase()} · `;

export default function Footer() {
  return (
    <footer className="relative bg-bg pt-20 pb-10 overflow-hidden border-t border-stroke">
      <HlsVideo
        className="absolute inset-0 w-full h-full object-cover scale-y-[-1] opacity-30"
        src={ASSETS.heroVideo}
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
          <BrandMark
            size="md"
            showName
            name={brand.name}
            className="mb-4"
            nameClassName="font-display font-bold uppercase text-lg text-ink"
          />
          <p className="font-display uppercase tracking-[0.2em] text-xs text-brand mb-3">
            {brand.tagline}
          </p>
          <p className="font-body text-sm text-fog">{brand.description}</p>
        </div>

        <div>
          <h4 className="font-display font-semibold uppercase tracking-[0.15em] text-sm text-ink mb-4">
            Servizi
          </h4>
          <ul className="space-y-2 font-body text-sm text-fog">
            {[
              "Ristrutturazioni complete",
              "Ristrutturazione bagni",
              "Rifacimento impianti",
              "Cartongesso e controsoffitti",
              "Infissi e serramenti",
              "Chiavi in mano",
            ].map((s) => (
              <li
                key={s}
                className="hover:text-ink transition-colors cursor-pointer"
              >
                {s}
              </li>
            ))}
          </ul>
        </div>

        <div>
          <h4 className="font-display font-semibold uppercase tracking-[0.15em] text-sm text-ink mb-4">
            Contatti
          </h4>
          <ul className="space-y-3 font-body text-sm text-fog">
            <li className="flex items-start gap-2">
              <MapPin className="w-4 h-4 text-brand mt-0.5" /> Via San Giacomo
              35, 80013 Casalnuovo di Napoli (NA)
            </li>
            <li className="flex items-center gap-2">
              <Phone className="w-4 h-4 text-brand" />{" "}
              <a href="tel:+393896584125" className="hover:text-ink">
                +39 389 658 4125
              </a>
            </li>
            <li className="flex items-center gap-2">
              <MessageCircle className="w-4 h-4 text-brand" />{" "}
              <a
                href={WHATSAPP}
                target="_blank"
                rel="noreferrer"
                className="hover:text-ink"
              >
                WhatsApp Business
              </a>
            </li>
            <li className="flex items-center gap-2">
              <Mail className="w-4 h-4 text-brand" />{" "}
              <a
                href="mailto:info@gbconstruction.it"
                className="hover:text-ink"
              >
                info@gbconstruction.it
              </a>
            </li>
          </ul>
        </div>

        <div>
          <h4 className="font-display font-semibold uppercase tracking-[0.15em] text-sm text-ink mb-4">
            Hai un progetto?
          </h4>
          <p className="font-body text-sm text-fog mb-4">
            Scrivici su WhatsApp: risponde direttamente il team GB Construction.
          </p>
          <a
            href={`${WHATSAPP}?text=${encodeURIComponent("Ciao GB Construction, vorrei parlarvi del mio progetto di ristrutturazione.")}`}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 bg-brand text-white rounded-full px-5 py-3 font-display font-semibold uppercase tracking-wider text-xs hover:scale-105 transition-transform"
          >
            <MessageCircle className="w-4 h-4" aria-hidden="true" />
            Parla con noi
          </a>
        </div>
      </div>

      <div className="relative max-w-7xl mx-auto px-6 mt-14 pt-6 border-t border-stroke flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          {[
            {
              Icon: Instagram,
              href: "https://www.instagram.com/gbconstructionsrl/",
              label: "GB Construction su Instagram",
            },
            {
              Icon: Facebook,
              href: "https://www.facebook.com/gbconstructionsrls",
              label: "GB Construction su Facebook",
            },
          ].map(({ Icon, href, label }) => (
            <a
              key={label}
              href={href}
              target="_blank"
              rel="noreferrer"
              aria-label={label}
              className="inline-flex h-11 w-11 items-center justify-center rounded-full text-fog hover:text-brand transition-colors touch-manipulation"
            >
              <Icon className="w-5 h-5" aria-hidden="true" />
            </a>
          ))}
        </div>
        <div className="flex items-center gap-2 font-display uppercase tracking-[0.15em] text-xs text-ink">
          <span className="w-2.5 h-2.5 rounded-full bg-success animate-pulse-dot" />
          Sopralluoghi disponibili questa settimana
        </div>
        <div className="font-body text-xs text-fog text-center">
          P.IVA 09965211213 · © 2026 GB Construction S.R.L.S. · Casalnuovo di
          Napoli (NA) ·{" "}
          <a href="/privacy-policy" className="underline hover:text-ink">
            Privacy
          </a>{" "}
          ·{" "}
          <a href="/cookie-policy" className="underline hover:text-ink">
            Cookie
          </a>{" "}
          ·{" "}
          <a href="/manuale" className="underline hover:text-ink">
            Manuale
          </a>
        </div>
      </div>
    </footer>
  );
}
