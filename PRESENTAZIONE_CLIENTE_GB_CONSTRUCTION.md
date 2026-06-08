# GB Construction — Piattaforma Commerciale End-to-End
## Presentazione per il Cliente

**GB Construction S.R.L.** — *Napoli e Campania*

---

## Introduzione: Il vostro nuovo motore commerciale

Questo documento presenta la piattaforma digitale completa progettata su misura per **GB Construction S.R.L.**

Non stiamo parlando di un semplice "sito internet". Stiamo parlando di un **ecosistema commerciale integrato** che lavora per voi 24 ore su 24: cattura lead, qualifica automaticamente le richieste, calcola preventivi in tempo reale, gestisce il vostro funnel vendite e vi fornisce una dashboard operativa da cui comandare ogni fase del rapporto con il cliente, dal primo contatto alla consegna delle chiavi.

**Il risultato?** Meno tempo speso a fare preventivi a mano, meno lead persi, più appuntamenti qualificati e un'immagine aziendale da player professionale del settore.

---

## 1. La Prima Impressione: Una Landing che Vende

### Hero Cinematografica
La prima cosa che vede un visitatore è un'**esperienza visiva immersiva a schermo intero**. Abbiamo realizzato un hero scroll-driven che riproduce una sequenza fotogramma per fotogramma dei vostri cantieri reali — con effetti di profondità, parallasse al movimento del mouse, griglia tecnica stile blueprint e animazioni testuali sincronizzate con lo scroll.

Il messaggio è immediato: *"Non siamo un sito generico. Siamo costruttori."*

### Prova Sociale Integrata
Subito dopo l'hero, il visitatore trova:
- **Galleria cantieri reali**: video e fotografie dei lavori svolti ad Acerra, Casalnuovo, Pomigliano, Volla, Tavernanova, Medaglie d'Oro, Zona Ospedaliera.
- **Testimonianze clienti**: carousel con recensioni e storie reali.
- **Team aziendale**: presentazione dello staff (Giuseppe, Vincenzo, Giovanni Brancale) con foto professionali.
- **Footer dinamico**: marquee animato con i vostri marchi, certificazioni e claim.

### Design Premium Dark
L'intera interfaccia è progettata in **dark mode** con palette brandizzata:
- Rosso GB Construction come accento principale
- Oro per il pacchetto Luxury
- Tipografia Oswald (titoli, impatto) + Montserrat (corpo, leggibilità)
- Componenti UI di livello enterprise (shadcn/ui + Tailwind CSS)

**Perché convince:** il visitatore percepisce immediatamente professionalità, solidità e attenzione al dettaglio — esattamente ciò che cerca quando deve affidare la ristrutturazione della propria casa.

---

## 2. Il Configuratore Intelligente: Da Visitatore a Lead Qualificato in 6 Passaggi

Il cuore della landing è un **wizard interattivo a 6 step** che guida l'utente senza mai farlo sentire sopraffatto da moduli lunghi.

### Step 1 — Tipo di Immobile
Appartamento, villa, attico, monolocale? Il sistema adatta immediatamente le domande successive.

### Step 2 — Metri Quadri
Slider interattivo con feedback visivo istantaneo.

### Step 3 — Livello di Intervento
- Ristrutturazione parziale
- Ristrutturazione totale
- Intervento di lusso / chiavi in mano

### Step 4 — Ambienti da Ristrutturare
Selezione a chip interattiva con contatore: cucina, bagno, camere, soggiorno, balconi, ingresso, ripostigli.

### Step 5 — Stile di Design
Scelta visiva tra stili (moderno, classico, industriale, minimal...) con **video poster** di anteprima. I video vengono precaricati in background per garantire fluidità.

### Step 6 — Tempistiche
Quando vuole iniziare? Il sistema calcola la priorità e influenza lo scoring del lead.

### Domande Rapide di Affinamento
Dopo il wizard, una serie di domande tecniche ma semplici affina la stima:
- Vuole redistribuire gli spazi?
- Deve rifare gli impianti (elettrico/idraulico)?
- Riscaldamento a pavimento o radiatori?
- Infissi nuovi?
- Vuole che ci occupiamo anche delle forniture?

**Risultato:** alla fine di questo percorso, il sistema ha già raccolto tutto ciò che serve per generare una stima credibile. L'utente non ha ancora compilato un modulo di contatto, ma è già profilato.

---

## 3. Il Motore Predittivo GB: Tre Pacchetti, Una Stima Reale

Qui avviene la magia commerciale. Mentre l'utente completa il configuratore, il **motore predittivo deterministico a 7 fasi** elabora in tempo reale tre scenari economici:

### I Tre Pacchetti

| Pacchetto | Target | Promise |
|---|---|---|
| **Essenziale** | Budget contenuto | Ristrutturazione funzionale, materiali standard, rispetto delle normative |
| **Premium** | Qualità medio-alta | Finiture superiori, design curato, migliori materiali, gestione chiavi in mano |
| **Luxury** | Alto di gamma | Materiali top, design personalizzato, domotica, dettagli artigianali |

### Come funziona tecnicamente
Il motore si basa su:
- **Dataset di 86 voci standard di capitolato** (VS-001 ... VS-086): ogni voce ha trigger booleani e formule di quantità automatiche in base ai mq e agli ambienti scelti.
- **18 coefficienti economici GB**: costi al mq regionali (Campania), coefficienti di imprevisto, range di varianza, moltiplicatori per livello di lusso.
- **Lead Scoring automatico 1-100**: ogni lead viene punteggiato in base a tempistiche, livello di intervento, metriquadri, file allegati, richieste di redistribuzione. Più è alto il punteggio, più è urgente e qualificato.
- **Alert tecnici automatici**: se il sistema rileva che serve un sopralluogo obbligatorio (es. redistribuzione strutturale, impianti da rifare completamente), lo segnala immediatamente allo staff.

### La Presentazione al Cliente
I tre pacchetti vengono mostrati con:
- **Card 3D interattive**: effetto Tilt3D al movimento del mouse con parallasse e riflesso luminoso.
- **Poster visivi** dedicati per ogni pacchetto.
- **Dettaglio computo espandibile**: l'utente può aprire ogni pacchetto e vedere la composizione dei costi (manodopera, materiali, imprevisto, margine).
- **Range di prezzo realistico**: mai un numero fisso, ma una forbice professionale che gestisce le aspettative.

**Perché convince:** il cliente vede subito che non state "tirando a indovinare". I numeri sono fondati, strutturati e presentati con trasparenza. La forbicia di prezzo genera fiducia, non diffidenza.

---

## 4. La Chiusura del Funnel: Contatto Qualificato

### Il Gate di Contatto
Solo dopo aver visto i pacchetti e i prezzi, l'utente viene invitato a lasciare i propri dati. Questo è un punto psicologico cruciale: ha già investito tempo, ha già visto il valore, ora è motivato.

### Form di Lead
- Nome e cognome
- Email (con validazione e deduplicazione automatica)
- Telefono
- Città e indirizzo dell'immobile
- Checkbox privacy GDPR
- **Tracking automatico UTM**: il sistema cattura automaticamente da quale campagna, banner o post proviene il lead (fbclid, gclid, msclkid, parametri UTM).

### Fake Progress e Preventivi Offuscati
Durante l'invio, una barra di progresso simula l'elaborazione finale (3 secondi) per aumentare la percezione di valore. I preventivi rimangono visibili ma "offuscati" fino all'invio, creando un incentivo a completare.

### Seconda Chance
Se il visitatore esce senza completare, la pagina presenta comunque:
- Sezione progetti realizzati
- FAQ interattive
- Form richiamata telefonica ("Ti richiamiamo noi")
- Link diretto WhatsApp con messaggio precompilato

**Risultato:** massimizzazione della conversione. Non lasciamo nessuno indietro.

---

## 5. AI Architect: Il Vostro Architetto Virtuale

Questo è il modulo che vi distingue dalla concorrenza. Un potenziale cliente può caricare la planimetria della propria casa e ricevere in pochi minuti un **concept preliminare completo**.

### Flusso Utente
1. **Upload Planimetria**: supporta PDF, PNG, JPG, DWG, DXF, IFC.
2. **Configurazione**: seleziona lo stile, l'obiettivo (abitabilità, investimento, famiglia, smart working), la variante progettuale.
3. **Elaborazione Asincrona**: il sistema processa il file in background. L'utente vede una schermata di avanzamento con polling in tempo reale.
4. **Risultati**:
   - Analisi architettonica strutturata
   - Planimetria 2D pulita o redistribuita
   - Vista top-down 3D
   - Render fotorealistici per stanza (soggiorno, cucina, camera, bagno)
   - Consigli tecnici personalizzati
   - **Report PDF scaricabile**

### Integrazione con il CRM
Direttamente dalla pagina risultati, l'utente può:
- Richiedere un preventivo ufficiale (crea automaticamente un lead nel vostro CRM con tutti i dati del progetto allegati)
- Prenotare un sopralluogo
- Contattarvi via WhatsApp

### Stato Attuale e Roadmap
Il modulo AI Architect è **completamente operativo** con pipeline asincrona, storage dei file, generazione report PDF e integrazione CRM. La roadmap prevede l'evoluzione verso analisi planimetrica professionale con visione AI strutturata, planimetrie 2D professionali con quote e leggenda, e render ultra-fedeli vincolati alla geometria approvata.

**Perché convince:** nessuna azienda di ristrutturazione in Campania offre oggi uno strumento del genere al pubblico. Posizionate GB Construction come innovatore tecnologico del settore.

---

## 6. Dashboard Staff: Il Vostro CRM Verticale

Dietro la landing c'è una **dashboard operativa completa**, accessibile solo allo staff tramite login sicuro (JWT con cookie httpOnly).

### Ruoli e Sicurezza
- **Admin** (Giuseppe): controllo totale, gestione staff, coefficienti, pulizia dati.
- **Staff** (Vincenzo): gestione lead, preventivi, cantieri.
- **Operations** (Giovanni): gestione operativa, sopralluoghi, appuntamenti.

### 6.1 Oggi — La Homepage Operativa
Appena entrate, vedete:
- Nuovi lead urgenti da contattare
- Follow-up programmati per oggi
- Sopralluoghi della settimana
- Preventivi in attesa da troppo tempo
- **Alert automatici**: lead non gestiti da più di 18 ore

### 6.2 Lead Inbox — La Vostra Cassa di Risonanza
Tabella completa di tutti i lead con:
- Filtri per stato (nuovo, contattato, sopralluogo, in trattativa, vinto, perso, irraggiungibile)
- Filtro per origine (Meta Ads, Landing, Callback, AI Architect)
- Ricerca testuale istantanea
- Azioni rapide: chiama, WhatsApp, email, apri scheda
- Badge di scoring visivo (1-100)
- Pulizia lead di test (solo admin)

### 6.3 Scheda Lead — Il Dossier Completo
Ogni lead ha una scheda a **3 colonne**:
- **Colonna 1**: Dati cliente, contatti, punteggio, stato attuale, tag, assegnazione owner
- **Colonna 2**: Dati immobile, stima predittiva con i 3 pacchetti, dettaglio computo, sezione AI Architect se ha caricato una planimetria
- **Colonna 3**: Timeline interattiva (note, chiamate, messaggi, email), prossima azione suggerita dall'AI, tasti rapidi per cambiare stato

### 6.4 Pipeline Kanban — Il Flusso Visivo
Vista a colonne drag-and-drop per spostare i lead tra gli stati. Il sistema salva automaticamente le transizioni e aggiorna i contatori in tempo reale.

### 6.5 Sopralluoghi — Calendario Integrato
- Gestione slot liberi: aggiungete o rimuovete fasce orarie disponibili
- Lista appuntamenti prenotati con dati cliente, indirizzo e link Google Maps
- I clienti possono prenotare autonomamente dalla landing (calendario pubblico)

### 6.6 Preventivi — Tracciamento Offerte
- Lista preventivi con indicatori "giorni di silenzio" (quanto tempo è passato dall'ultimo contatto)
- Creazione manuale preventivo dallo staff con modale dedicata
- Stato preventivo collegato allo stato lead

### 6.7 Cantieri — Dalla Vendita alla Consegna
Gestione completa dei cantieri attivi:
- Creazione collegata al lead vinto
- Card cantiere con avanzamento percentuale
- Fasi predefinite: demolizioni, impianti, massetti, pavimenti, finiture, consegna
- Assegnazione capocantiere
- Flag criticità e note tecniche
- Stati: attivo, in pausa, completato

### 6.8 Report & KPI — I Numeri del Business
Dashboard analitica con:
- Grafici Recharts (linee, torta, barre verticali/orizzontali)
- KPI funnel: lead acquisiti, conversioni, valore pipeline, tempo medio di risposta
- **Insight AI**: il sistema genera automaticamente analisi testuali sui trend del business (es. "Questo mese i lead da Meta Ads hanno un 23% di conversione in più rispetto alla landing")

### 6.9 Impostazioni — Controllo Totale
- **Dati azienda**: ragione sociale, indirizzo, contatti
- **Gestione staff**: creazione utenti, ruoli, foto profilo
- **Integrazione Meta Ads**: stato connessione, riprocessamento eventi falliti
- **Coefficienti motore predittivo**: potete modificare i 18 coefficienti economici per adattare le stime al mercato in tempo reale
- **Voci standard**: catalogo delle 86 voci di capitolato

### Email Integrata
Direttamente dalla scheda lead, lo staff può comporre email brandizzate GB Construction con:
- Destinatario precompilato
- Oggetto e corpo personalizzabili
- Allegati multipli (fino a 15 MB)
- Layout HTML brandizzato con logo GB Construction

---

## 7. Integrazioni Automatiche: Il Sistema Lavora Anche Quando Dormite

### Meta Lead Ads
Il sistema è predisposto per l'integrazione con Facebook/Instagram Lead Ads:
- Webhook sicuro con verifica firma HMAC-SHA256
- Fetch automatico lead dalla Graph API
- Assegnazione round-robin agli operatori
- Deduplicazione per email e telefono
- Tracking completo della campagna di origine

### Email Transazionali
Il sistema invia automaticamente:
- Email di notifica allo staff quando arriva un nuovo lead
- Email di conferma al cliente quando richiede un preventivo, un callback o un sopralluogo
- Email brandizzate con logo GB Construction e layout professionale

### WhatsApp One-Click
Da ogni scheda lead, un clic genera il link `wa.me` con messaggio personalizzato:
> "Buongiorno [Nome], sono Giuseppe da GB Construction. Ho ricevuto la sua richiesta per la ristrutturazione a [Città]. Possiamo sentirci?"

### Tracking Avanzato
- **PostHog Analytics**: analisi comportamentale completa sulla landing
- **UTM Tracking**: ogni lead porta con sé la traccia esatta della campagna, del banner o del post che l'ha generato
- **Session storage**: i parametri di tracking persistono per tutta la navigazione

---

## 8. Tecnologia Enterprise: Solida, Scalabile, Sicura

### Stack Tecnologico
| Componente | Tecnologia | Perché è importante |
|---|---|---|
| Frontend | React 19 + Tailwind CSS + shadcn/ui | Interfaccia moderna, veloce, manutenibile |
| Backend | Python 3.11 + FastAPI | API performanti, async, validazione dati rigorosa |
| Database | MongoDB (async via Motor) | Flessibilità schema, scalabilità orizzontale |
| Auth | JWT + bcrypt + cookie httpOnly | Sicurezza bancaria, nessuna password in chiaro |
| AI Testo | OpenAI GPT-4o / Claude | Suggerimenti commerciali e insight di business |
| AI Immagini | OpenAI Images API / FAL.ai | Render e concept visivi |
| Deploy | Vercel (frontend) + Railway (backend) | CDN globale, uptime garantito, scaling automatico |
| Container | Docker | Build riproducibile, pronta per qualsiasi cloud |

### Sicurezza
- Password hashate con bcrypt
- Cookie JWT httpOnly e secure in produzione
- CORS configurato e ristretto
- Deduplicazione lead automatica
- Validazione input su ogni endpoint con Pydantic
- Ruoli e permessi granulari

---

## 9. Cosa Succede Dopo l'Acquisto

### Consegna
- Deploy completo su dominio cliente (es. `gbconstruction.it`)
- Configurazione produzione: CORS, SMTP, API keys, Meta token
- Caricamento asset video/foto cantieri
- Creazione credenziali staff personalizzate
- Collaudo con lead di test reali

### Formazione
- Sessione operativa di 90 minuti con lo staff
- Manuale d'uso della dashboard
- Best practice per la gestione lead

### Assistenza e Manutenzione
| Piano | Include |
|---|---|
| **Base (190 EUR/mese)** | Monitoraggio uptime, bugfix, backup database |
| **Standard (390 EUR/mese)** | Tutto il Base + modifiche testuali, aggiornamenti asset, supporto prioritario |
| **Growth (690 EUR/mese)** | Tutto lo Standard + sviluppo funzionalità custom, ottimizzazione conversione, report mensili dedicati |

### Roadmap Evolutiva (inclusa nei piani di manutenzione)
- Filtro automatico Regione Campania (whitelist province e CAP)
- Analisi planimetrica AI professionale con output strutturato
- Planimetrie 2D professionali con quote, legenda e note tecniche
- Render ultra-fedeli vincolati alla geometria approvata
- Storage scalabile Cloudflare R2
- Coda job asincrona con Redis per massima velocità
- Sequenze di follow-up automatiche per lead non convertiti
- Mappa interattiva Campania nei report

---

## 10. Proposta Economica Riassuntiva

### Opzioni di Acquisto

| Offerta | Prezzo | Cosa include |
|---|---|---|
| **Entry** | 4.900 EUR | Landing + configuratore + dashboard base, AI Architect limitato |
| **Avvio Completo** ⭐ | **7.900 EUR** | **Tutto incluso, 30 giorni di assistenza dedicata, formazione staff 90 min** |
| **Premium AI** | 9.800 EUR | Ottimizzazione asset, storage R2, cost cap AI, 20 job AI inclusi, 2 sessioni formative |

### Formula Consigliata
- **Setup**: 7.900 EUR + IVA (40% all'ordine, 40% alla consegna, 20% a collaudo superato)
- **Manutenzione**: 390 EUR/mese + IVA (Standard, consigliato)
- **Costi vivi** (hosting, API AI, Meta Ads): a carico cliente, trasparenti
- **Durata minima**: 6 mesi

**ROI atteso:** con una media di 2 lead qualificati in più al mese e un tasso di conversione migliorato del 15-20%, l'investimento si ripaga entro i primi 3-4 mesi di attività.

---

## Chiusura

Questa piattaforma non è un costo. È un **investimento commerciale strutturale**.

Vi sostituisce nel lavoro di primo filtro, vi dà strumenti da grande impresa, vi fa apparire professionali agli occhi di chi conta, e vi lascia il tempo di fare ciò che sapete fare meglio: **costruire e ristrutturare.**

**GB Construction merita un motore commerciale all'altezza della qualità dei suoi cantieri. Questo è quel motore.**

---

*Documento preparato per GB Construction S.R.L.*
*Stato piattaforma: operativa e pronta per produzione*
*Data: Giugno 2026*
