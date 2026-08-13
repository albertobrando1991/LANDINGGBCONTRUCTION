/**
 * Identità visiva e anagrafica dell'impresa.
 * Per un nuovo cliente si aggiorna QUESTO file + i token in index.css.
 * Non è il motore: le funzioni restano in landing/, dashboard/, backend/.
 */
export const brand = {
  slug: "gbconstruction",
  name: "GB Construction",
  legalName: "GB Construction S.R.L.S.",
  sidebarName: "Construction",
  initials: "GB",
  tagline: "Costruiamo valore. Trasformiamo spazi.",
  description:
    "Impresa di ristrutturazioni chiavi in mano a Napoli e in tutta la Campania. Oltre 200 cantieri completati in 15 anni.",
  pageTitle: "GB Construction | Ristrutturazioni",
  mark: "initials",
  logoSrc: `${process.env.PUBLIC_URL || ""}/brand/gb-logo.png`,
  email: "info@gbconstruction.it",
  phone: "+39 389 658 4125",
  whatsapp: "393896584125",
  domain: "https://gbconstruction.it",
  areaServed: "Napoli e Campania",
  colors: {
    primary: "#C41E3A",
    secondary: "#D4AF37",
    background: "#0B0B0B",
  },
  fonts: {
    display: "Oswald",
    body: "Montserrat",
  },
};
