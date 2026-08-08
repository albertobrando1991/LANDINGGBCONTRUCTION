---
name: GB Construction
colors:
  surface: '#171719'
  surface-dim: '#0C0C0F'
  surface-bright: '#242426'
  surface-container-lowest: '#08080A'
  surface-container-low: '#121214'
  surface-container: '#171719'
  surface-container-high: '#242426'
  surface-container-highest: '#303033'
  on-surface: '#F5F3EF'
  on-surface-variant: '#888888'
  inverse-surface: '#F3F1ED'
  inverse-on-surface: '#202226'
  outline: '#49494D'
  outline-variant: '#2E2E31'
  surface-tint: '#C4272F'
  primary: '#C4272F'
  on-primary: '#FDF9F7'
  primary-container: '#731B20'
  on-primary-container: '#FFD9D8'
  inverse-primary: '#A91F27'
  secondary: '#C3A44F'
  on-secondary: '#211B0A'
  secondary-container: '#4B3D17'
  on-secondary-container: '#F8E3A2'
  tertiary: '#AEB0B7'
  on-tertiary: '#171719'
  tertiary-container: '#383A40'
  on-tertiary-container: '#ECECF0'
  error: '#FF5A61'
  on-error: '#260003'
  background: '#0C0C0F'
  on-background: '#F5F3EF'
  surface-variant: '#242426'
typography:
  display-xl:
    fontFamily: Oswald
    fontSize: 80px
    fontWeight: '700'
    lineHeight: 74px
    letterSpacing: -0.02em
  display-lg:
    fontFamily: Oswald
    fontSize: 64px
    fontWeight: '700'
    lineHeight: 60px
    letterSpacing: -0.015em
  headline-lg:
    fontFamily: Oswald
    fontSize: 40px
    fontWeight: '600'
    lineHeight: 44px
    letterSpacing: '0'
  headline-md:
    fontFamily: Oswald
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 34px
    letterSpacing: 0.01em
  body-base:
    fontFamily: Montserrat
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 26px
    letterSpacing: '0'
  body-bold:
    fontFamily: Montserrat
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: '0'
  label-caps:
    fontFamily: Oswald
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.18em
---

# Design System: GB Construction

## 1. Visual Theme & Atmosphere

Un sistema materico e cinematografico, costruito come l'incontro tra un cantiere contemporaneo al crepuscolo e una pubblicazione professionale di architettura. Il nero non è digitale puro: è un minerale profondo e leggermente caldo. Il rosso GB taglia le composizioni come una trave strutturale; l'oro ottone compare soltanto nei passaggi di valore, nelle firme e nei totali.

L'esperienza alterna immagini architettoniche decisive, grandi titoli compressi e superfici tecniche dense. Landing e documenti comunicano; dashboard e tabelle servono il lavoro. Tutto condivide la stessa voce: decisa, leggibile, priva di ornamenti gratuiti.

## 2. Color Palette & Roles

### Primary Foundation

- **Nero minerale** (`#0C0C0F`): fondale immersivo, copertine e hero.
- **Grafite operativo** (`#171719`): pannelli, navigazione e superfici principali.
- **Acciaio profondo** (`#242426`): livelli secondari e righe alternate.
- **Carta calda** (`#F3F1ED`): documenti stampabili e sezioni di contrasto.

### Accent & Interactive

- **Rosso GB strutturale** (`#C4272F`): call to action, titoli chiave, indicatori attivi e fasce editoriali.
- **Rosso fondazione** (`#731B20`): stati premuti e profondità tonale.
- **Ottone di cantiere** (`#C3A44F`): totali, separatori e dettagli premium, mai come riempimento dominante.

### Typography & Text Hierarchy

- **Bianco cemento** (`#F5F3EF`): testo primario su scuro.
- **Nebbia metallica** (`#888888`): metadati e informazioni secondarie.
- **Inchiostro grafite** (`#202226`): testo primario su carta.

### Functional States

- **Verde verifica** (`#22C55E`): successo e completamento.
- **Ambra controllo** (`#F59E0B`): attenzione operativa.
- **Rosso errore** (`#FF5A61`): errore, distinto dal rosso brand tramite luminosità.

## 3. Typography Rules

### Hierarchy & Weights

Oswald è il carattere strutturale: titoli molto grandi, compatti, spesso maiuscoli, con interlinea serrata. Montserrat è il carattere umano e operativo: testi, dati, moduli e didascalie. I titoli passano da 28 a 80 px con salti visibili; il corpo resta tra 14 e 18 px. Le etichette maiuscole sono brevi e spaziate, mai usate per paragrafi.

### Spacing Principles

Titoli e immagini possono essere stretti e tesi; il testo narrativo respira con 65-72 caratteri per riga. Nei documenti A4, usare gerarchie equivalenti e ridotte proporzionalmente, mantenendo il contrasto tra display compresso e corpo neutro.

## 4. Component Stylings

### Buttons

Le azioni primarie sono pillole solide rosso GB con testo Oswald bianco e area tattile generosa. Le azioni secondarie usano bordo metallico sottile su grafite. Hover con traslazione o scala minima, senza bagliori o gradienti.

### Cards & Document Modules

Le card operative hanno angoli da 12-16 px, fondo grafite e bordo hairline. Le pagine editoriali evitano griglie di card identiche: usano immagini a pieno taglio, grandi numeri di capitolo e blocchi asimmetrici. Nei PDF, le tabelle hanno testata antracite, righe carta alternate e totale in fascia rossa piena.

### Navigation

Sidebar scura, voci Oswald maiuscole, icone lineari e stato attivo rosso. Su mobile diventa un drawer; l'azione principale resta sempre raggiungibile senza coprire i contenuti.

### Inputs & Forms

Campi scuri con bordo acciaio, altezza minima 44 px e focus rosso ben visibile. Errori espliciti con testo, non solo colore. Nei documenti, i campi firma e accettazione sono ampi e privi di decorazioni.

### Preventivi, Computi e SAL

Copertina fotografica a piena pagina, barra rossa verticale, titolo dominante e investimento in primo piano. Le pagine interne aprono con numeri di capitolo oversize, poi dati strutturati. Tabelle ripetono l'intestazione su ogni pagina; quantità e denaro sono allineati a destra. La filigrana BOZZA resta discreta ma riconoscibile.

## 5. Layout Principles

### Grid & Structure

Desktop su massimo 1280 px con griglia a 12 colonne. Marketing e documenti usano asimmetrie intenzionali 7/5 o 8/4; la dashboard usa struttura più regolare. A4 adotta margini interni da 18 mm e moduli basati su 4 mm.

### Whitespace Strategy

Scala base 4/8 px. Sezioni narrative distanziate 64-120 px; gruppi operativi 16-32 px. Il ritmo alterna grandi pause e aggregazioni dense, evitando padding uniforme ovunque.

### Alignment & Visual Balance

Testo prevalentemente allineato a sinistra. Immagini scure e pesanti bilanciate da grandi campi di carta o titoli chiari. Il rosso crea assi visivi verticali e orizzontali, mai cornici decorative casuali.

### Responsive Behavior & Touch

Breakpoints 640, 768, 1024, 1280 e 1536 px. Titoli fluidi tramite scale equivalenti a `clamp`; griglie si riducono senza tagliare testi; target tattili almeno 44 px; motion ridotto quando richiesto dal sistema.

## 6. Design System Notes for Stitch Generation

### Language to Use

Usare: materico, cinematografico, architettura contemporanea, cantiere al crepuscolo, griglia editoriale rigorosa, rosso strutturale, carta tecnica premium, fotografia reale, contrasto deciso.

Evitare: template SaaS, luxury beige, glassmorphism, gradient text, card grid uniforme, icone decorative, minimalismo vuoto, brochure immobiliare generica.

### Color References

Fondale `#0C0C0F`, grafite `#171719`, rosso `#C4272F`, ottone `#C3A44F`, carta `#F3F1ED`, inchiostro `#202226`.

### Component Prompts

1. “Crea una copertina A4 verticale per una proposta economica GB Construction, fotografia di cantiere contemporaneo a pieno taglio, barra rossa strutturale, titolo Oswald dominante, cliente e investimento in un blocco asimmetrico, nessun effetto lusso generico.”
2. “Crea una pagina interna di computo con apertura numerata oversize, introduzione breve, tabella tecnica multipagina e totale in fascia rossa piena; carta calda, testo Montserrat, precisione da capitolato.”
3. “Crea una dashboard scura per preventivi e SAL, densa ma leggibile, sidebar grafite, azioni rosse, dati economici in Montserrat e titoli Oswald; niente griglia di card ripetitive.”

### Incremental Iteration

Generare prima copertina, pagina dettaglio e dashboard preventivi. Verificare contrasto, leggibilità dei prezzi e coerenza del rosso. Solo dopo aggiungere SAL, portale cliente e varianti mobile, mantenendo invariati palette e gerarchia tipografica.
