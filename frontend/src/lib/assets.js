// GB Construction — asset pubblici (forniti dal cliente)
export const ASSETS = {
  logo: `${process.env.PUBLIC_URL || ""}/brand/gb-logo.png`,
  cemento: `${process.env.PUBLIC_URL || ""}/brand/cemento-scuro-premium.png`,
  heroVideo: `${process.env.PUBLIC_URL || ""}/brand/hero-construction-loop.mp4`,
  beforeAfter1: `${process.env.PUBLIC_URL || ""}/brand/before-after-1.mp4`,
  beforeAfter2: `${process.env.PUBLIC_URL || ""}/brand/before-after-2.mp4`,
};

// Video render per stile (configuratore step 5 + carousel) — uno per stile
export const STYLE_VIDEOS = {
  "Moderno minimal": `${process.env.PUBLIC_URL || ""}/brand/stile-moderno-minimal-preview.mp4`,
  "Classico elegante": `${process.env.PUBLIC_URL || ""}/brand/stile-classico-elegante-preview.mp4`,
  "Industrial loft": `${process.env.PUBLIC_URL || ""}/brand/stile-industrial-loft-preview.mp4`,
  "Contemporaneo caldo": `${process.env.PUBLIC_URL || ""}/brand/stile-contemporaneo-caldo-preview.mp4`,
};

export const STYLE_VIDEO_POSTERS = {
  "Moderno minimal": `${process.env.PUBLIC_URL || ""}/brand/stile-moderno-minimal-poster.jpg`,
  "Classico elegante": `${process.env.PUBLIC_URL || ""}/brand/stile-classico-elegante-poster.jpg`,
  "Industrial loft": `${process.env.PUBLIC_URL || ""}/brand/stile-industrial-loft-poster.jpg`,
  "Contemporaneo caldo": `${process.env.PUBLIC_URL || ""}/brand/stile-contemporaneo-caldo-poster.jpg`,
};

const cantiereAsset = (fileName) =>
  `${process.env.PUBLIC_URL || ""}/cantieri/${encodeURIComponent(
    fileName,
  ).replace(
    /[!'()*]/g,
    (char) => `%${char.charCodeAt(0).toString(16).toUpperCase()}`,
  )}`;

// Video reali dei cantieri presenti nella cartella root PUBLIC.
export const CANTIERE_VIDEOS = [
  {
    src: cantiereAsset("ACERRA.mp4"),
    poster: cantiereAsset("ACERRA.png"),
    nome: "Acerra",
    citta: "Acerra",
    label: "Video reale",
  },
  {
    src: cantiereAsset("CASALNUOVO.mp4"),
    poster: cantiereAsset("CASALNUOVO.png"),
    nome: "Casalnuovo",
    citta: "Casalnuovo di Napoli",
    label: "Video reale",
  },
  {
    src: cantiereAsset("CASALNUOVO 2.mp4"),
    poster: cantiereAsset("CASALNUOVO 2 (2).png"),
    nome: "Casalnuovo 2",
    citta: "Casalnuovo di Napoli",
    label: "Video reale",
  },
  {
    src: cantiereAsset("MEDAGLIE D'ORO.mp4"),
    poster: cantiereAsset("medaglie d'oro.png"),
    nome: "Medaglie d'Oro",
    citta: "Napoli",
    label: "Video reale",
  },
  {
    src: cantiereAsset("POMIGLIANO.mp4"),
    poster: cantiereAsset("POMIGLIANO.png"),
    nome: "Pomigliano",
    citta: "Pomigliano d'Arco",
    label: "Video reale",
  },
  {
    src: cantiereAsset("TAVERNANOVA.mp4"),
    poster: cantiereAsset("TAVERNANOVA.png"),
    nome: "Tavernanova",
    citta: "Casalnuovo di Napoli",
    label: "Video reale",
  },
  {
    src: cantiereAsset("VOLLA.mp4"),
    poster: cantiereAsset("VOLLA.png"),
    nome: "Volla",
    citta: "Volla",
    label: "Video reale",
  },
  {
    src: cantiereAsset("ZONA OSPEDALIERA.mp4"),
    poster: cantiereAsset("ZONA OSPEDALIERA.png"),
    nome: "Zona Ospedaliera",
    citta: "Napoli",
    label: "Video reale",
  },
];

// Foto staff GB Construction (nomi reali: famiglia Brancale)
export const STAFF_PHOTOS = {
  "Giuseppe Brancale": `${process.env.PUBLIC_URL || ""}/brand/staff-giuseppe.png`,
  "Giovanni Brancale": `${process.env.PUBLIC_URL || ""}/brand/staff-giovanni.png`,
  "Vincenzo Brancale": `${process.env.PUBLIC_URL || ""}/brand/staff-vincenzo.png`,
};

// Testimonianze (card grafiche fornite)
export const TESTIMONIAL_IMAGES = [
  {
    src: `${process.env.PUBLIC_URL || ""}/brand/testimonianza-1.png`,
    nome: "Alberto B.",
  },
  {
    src: `${process.env.PUBLIC_URL || ""}/brand/testimonianza-4.png`,
    nome: "Alessia C.",
  },
  {
    src: `${process.env.PUBLIC_URL || ""}/brand/testimonianza-2.png`,
    nome: "Alessia O.",
  },
  {
    src: `${process.env.PUBLIC_URL || ""}/brand/testimonianza-3.png`,
    nome: "Marianna D.",
  },
];

// Poster proposte commerciali (sezione pacchetti + output)
export const PROPOSAL_POSTERS = {
  essenziale: `${process.env.PUBLIC_URL || ""}/brand/gb-essenziale.png`,
  premium: `${process.env.PUBLIC_URL || ""}/brand/gb-premium.png`,
  luxury: `${process.env.PUBLIC_URL || ""}/brand/gb-luxury.png`,
};

// Immagini ambient cantiere/architettura (gallery + sfondi sezioni)
export const AMBIENT = [
  `${process.env.PUBLIC_URL || ""}/brand/ambient-1.png`,
  `${process.env.PUBLIC_URL || ""}/brand/ambient-2.png`,
  `${process.env.PUBLIC_URL || ""}/brand/ambient-3.png`,
];

export const WHATSAPP = "https://wa.me/393896584125";

// Città principali Campania + zone reali progetti GB
export const CITTA_CAMPANIA = [
  "Napoli",
  "Casalnuovo di Napoli",
  "Caserta",
  "Salerno",
  "Avellino",
  "Benevento",
  "Pozzuoli",
  "Quarto",
  "Casoria",
  "Aversa",
  "Castellammare di Stabia",
  "Giugliano in Campania",
  "Sorrento",
  "Altro",
];
