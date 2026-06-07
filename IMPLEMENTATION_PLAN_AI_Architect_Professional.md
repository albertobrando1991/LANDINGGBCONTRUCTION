# Piano di Implementazione Operativo Focalizzato
## AI Architect Professional-Grade: Analisi Planimetria Dettagliata, 2D Professionale, Consigli Realistici e Render Ultra Fedeli

**Versione:** Rivista secondo feedback utente  
**Data:** Basata su analisi del blueprint architetturale e codebase attuale (GB Construction Lead Engine)  
**Obiettivo principale dell'utente:** Rendere la funzione di analisi della planimetria **super dettagliata e professionale**, con:
- Analisi strutturata super dettagliata (classificazione, ambienti, aperture, muri, bagni, cucina, corridoi, esposizione, criticità, confidence per elemento, dichiarazione esplicita di cosa non è verificabile, output tecnico strutturato).
- Rigenerazione della planimetria in **2D professionale** con spazi ottimizzati (se "stato di fatto": nuova planimetria ottimizzata; se "progetto definito": pulire e rendere professionale senza inventare redistribuzioni; mantenere perimetro, accessi, finestre e vincoli visibili; output SVG/PNG professionale con stanze, quote indicative, legenda, note tecniche).
- Consigli tecnici **effettivamente realistici** (motivazione tecnica concreta per luce, corridoi, bagni, cucina, impianti, demolizioni, spazi inutilizzati; sempre con disclaimer forte: da validare con tecnico abilitato e sopralluogo).
- Generazione di **render ultra fedeli** (vincolati alla planimetria 2D validata; generare prima top-down/zenithal, poi viste interne; vietare al render engine di aggiungere stanze, finestre, muri o arredi incoerenti).

**Principi guida (da applicare in ogni fase):**
- Preservare il monolite modulare.
- Non rompere l'AI Architect esistente: strangolamento graduale tramite feature flag e adapter di compatibilità in `ai_architect_service.py`.
- Estendere (non riscrivere) il motore preventivi (`predictive_engine.py` con le 86 voci e coefficienti reali) in fasi successive.
- Rendere la pipeline asincrona in modo incrementale (prima BackgroundTasks con contratti chiari, poi worker).
- Costruire un **quality harness** e un dataset di ground truth (10-20 planimetrie reali con expected output) prima di spingere su modelli locali pesanti.
- Provider-first per vision e render (Claude/OpenRouter/Fal/OpenAI prima di ultralytics/CubiCasa locali su Railway).
- Ogni nuova dipendenza deve arrivare con un caso d'uso concreto, test e rollback chiaro.
- Trattare i vincoli normativi come **warning/verifica** (non certificazione automatica).
- Milestone verificabili (non stime temporali): output sempre JSON Pydantic validato, genera 2D professionale da dati strutturati, render non contraddicono la 2D, ecc.
- Cost cap per AI/render per lead (log e limiti semplici).
- Rollback operativo per R2/worker/provider.
- Esplicito: Railway richiederà almeno due servizi (backend FastAPI + worker) in futuro.

**Architettura proposta (modulare, senza riscrivere tutto subito):**
- `backend/engines/` (nuovi moduli):
  - `schemas.py` (Pydantic: PlanAnalysis, Room, Opening, TechnicalIssue, OptimizedPlan2D, RenderContract, QualityGateResult, ecc.).
  - `vision.py` / `plan_classifier.py`.
  - `floorplan_2d.py`.
  - `technical_advice.py`.
  - `render.py`.
  - `quality_gate.py`.
- Transizione graduale in `backend/ai_architect_service.py` tramite feature flag:
  - `AI_FLOORPLAN_PROFESSIONAL_ANALYSIS=true`
  - `AI_REQUIRE_PROFESSIONAL_2D=true`
  - `AI_REQUIRE_RENDER_FIDELITY=true`
  - `AI_USE_STRUCTURED_OUTPUT=true`
- Storage: R2 come priorità reale (sostituisce gradualmente `backend/storage/ai_architect/` locale instabile su Railway). Struttura semplice: uploads/, processed/, renders/, reports/.
- Evitare PostGIS nella prima release (basta GeoJSON in Mongo + R2 per MVP; PostGIS solo quando servono vere query spaziali).
- Per layout avanzati (OR-Tools, multiple varianti complesse, scoring admin): posticipare dopo MVP professionale.

**MVP Separato dalla Target Architecture (per evitare scope creep):**
- MVP = Analisi super dettagliata strutturata + 2D professionale (stato di fatto vs definito) + consigli realistici + render ultra fedeli vincolati.
- Target a lungo termine = 8 engine completi (Vision, Geometry, Semantic, Layout con OR-Tools, Scoring, Cost esteso, Render, CRM Filter), PostGIS, varianti multiple, analytics, ecc.
- Il MVP fornisce valore commerciale immediato (consulenza tecnica credibile per lead) senza bloccare tutto su un engine troppo complesso.

---

## Fase 1: Fondamenta — Analisi Super Dettagliata e Strutturata (Milestone Verificabile: Output Sempre JSON Pydantic Validato + Quality Gate)

**Obiettivo:** L'AI Architect produce sempre un `PlanAnalysis` Pydantic valido e completo. Nessun testo libero. Confidence esplicita per elemento + dichiarazione di cosa non è verificabile. Quality gate blocca o richiede conferma su bassa confidence. Flusso legacy continua via adapter.

**Dipendenze minime da introdurre (solo se caso d'uso):**
- Provider LLM/Vision esistenti (Claude/OpenRouter/OpenAI — già in uso).
- Pydantic (già usato).
- R2 per upload originali (priorità reale per instabilità attuale su Railway — introduci qui).

**Task dettagliati:**

1. **Definisci Schemi Dati Professionali** (`backend/engines/schemas.py` — nuovo):
   - `PlanAnalysis`: job_id, plan_type (existing_state | defined_project | ambiguous), overall_confidence (0-1), rooms: list[Room], openings: list[Opening], technical_issues: list[TechnicalIssue], scale_info, unverifiable_elements: list[str], raw_vision_output (per audit), confidence_overall.
   - `Room`: name (es. "soggiorno", "cucina"), approx_area_sqm (opzionale), position_description, confidence (0-1), evidence (testo da visione), verification_required: bool, bounding_box (opzionale {x,y,width,height} normalizzato 0-1), notes.
   - `Opening`: type ("door" | "window"), position, width (opzionale), orientation, confidence, evidence.
   - `TechnicalIssue`: category ("light" | "circulation" | "plumbing" | "structural" | "norm" | "other"), severity ("low"|"medium"|"high"), description (tecnica), recommendation (con motivazione), confidence, disclaimer.
   - Aggiungi validatori strict (no extra fields, confidence range, ecc.).
   - Esporta anche response models per API/frontend.

2. **Rifattorizza Analisi Attuale verso Output Strutturato** (in `backend/ai_architect_service.py` + nuovo `backend/engines/vision.py` e `plan_classifier.py`):
   - Isola la logica di chiamata LLM/vision attuale (prompts, provider chain già presenti).
   - Crea adapter che mappa output grezzo (testo/JSON parziale) in `PlanAnalysis` validato.
   - Prompt forte: "Analizza come architetto senior. Estrai SOLO elementi visibili. Per ogni stanza/apertura: nome, posizione, area stimata, confidence 0-1, evidence testuale, verification_required. Classifica plan_type. Elenca esplicitamente unverifiable_elements. Output SOLO JSON strutturato."
   - Classificazione plan_type: combina nome file + selezione utente + confidence modello (fallback Claude se < soglia).
   - Per ambienti/aperture: estrazione strutturata (rooms + openings).
   - Post-processing: calcola overall_confidence, lista unverifiable_elements, technical_issues base (es. da incoerenze luce/scarichi visibili).
   - Feature flag `AI_USE_STRUCTURED_OUTPUT`: se true usa nuovo path, else fallback legacy (per non rompere nulla subito).

3. **Aggiungi Quality Gate** (`backend/engines/quality_gate.py` — nuovo):
   - Regole iniziali:
     - Se overall_confidence < VISION_MIN_ACCEPTABLE_CONFIDENCE (es. 0.62) → richiede conferma utente o safe mode (non procedere a 2D/render automatici).
     - Per ogni Room/Opening: se confidence < soglia specifica → marca verification_required e genera TechnicalIssue.
     - Coerenza minima: stanze ragionevoli vs mq, presenza logica bagni/cucina, aperture esterne per abitabili.
     - Se troppi unverifiable o bassa confidence su critici (muri portanti, scarichi) → blocca render e 2D ottimizzata.
   - Integra dopo analisi, prima di 2D o render.
   - Esponi risultato gate nel job payload (per UI e audit).

4. **Introduci R2 per Upload (priorità reale)**:
   - Utility minimale `backend/storage/r2_storage.py` (upload, get_url, delete, signed URLs).
   - Modifica `create_job` per salvare originale su R2 (path: uploads/{job_id}/original.{ext}).
   - Aggiungi campi al job: uploaded_file_r2_key.
   - Per ora mantieni output intermedi su local o estendi a R2 processed/.
   - Aggiorna serving file endpoint.
   - Aggiungi limiti upload (size, type) e retention policy semplice.
   - Logging: correlation_id + step dettagliato.

5. **Feature Flag e Adapter di Compatibilità** (in `ai_architect_service.py`):
   - Implementa i flag elencati sopra.
   - Adapter legacy: se flag off, usa comportamento attuale (con fallback SVG se necessario).
   - Prepara strangolamento graduale (nuovi engine chiamati solo se flag on).

**Criteri di accettazione Fase 1 (verifica):**
- Ogni job produce `PlanAnalysis` Pydantic valido e serializzabile.
- Analisi dichiara esplicitamente incertezze e unverifiable_elements.
- Quality gate blocca o richiede conferma su bassa confidence.
- Upload originali su R2 funzionante (verificato con test).
- Feature flag permette rollback immediato al legacy.
- Nessun breaking change su flussi esistenti (configuratore, lead creation, dashboard base, endpoint attuali).
- Cost cap base: logga costo LLM/vision per job; blocca se supera soglia configurabile.

**Rischi & Mitigazioni:**
- Dipendenze: solo provider esistenti + Pydantic + R2 (libreria leggera). Evita ultralytics/OCR/PostGIS qui.
- Railway: usa BackgroundTasks per ora (contratto job chiaro per futuro worker).
- Accuratezza: inizia con provider LLM (più affidabile su planimetrie italiane reali); dataset ground truth in Fase 2+.

**Integrazione con codice attuale:**
- Estende `ai_architect_service.py` (non riscrive).
- Preserva `predictive_engine.py` (bridge futuro).
- Aggiorna test esistenti (`backend/tests/test_ai_architect_local_analysis.py`, `test_gb_backend.py`).

---

## Fase 2: Rigenerazione Planimetria 2D Professionale (Milestone: Output 2D Ottimizzato/Pulito Leggibile da Dati Strutturati)

**Obiettivo:** Da `PlanAnalysis` validato + gate passato, genera `OptimizedPlan2D` professionale. Se stato di fatto: ottimizzata (nuova distribuzione realistica). Se progetto definito: pulita/professionalizzata (nessuna invenzione). Mantiene perimetro, accessi, finestre, vincoli visibili. Output SVG/PNG professionale con stanze, quote indicative, legenda, note tecniche + disclaimer.

**Dipendenze minime:** Librerie leggere per SVG (string building o svgwrite) + rendering PNG (cairosvg o Pillow). Evita OR-Tools qui.

**Task dettagliati:**

1. **Motore floorplan_2d.py** (`backend/engines/floorplan_2d.py` — nuovo):
   - Input: `PlanAnalysis`, config utente (stile, priorità).
   - Logica:
     - Se "defined_project": pulisci e professionalizza (mantieni perimetro/accessi/finestre/muri visibili; riorganizza etichette/quote; layout pulito).
     - Se "existing_state": genera proposta ottimizzata (mantieni perimetro e vincoli visibili; ottimizza flussi/luce/separazione notte-giorno/posizionamento cucina-bagni rispetto scarichi; evita invenzioni su non-visibili).
     - Se ambiguo: richiedi conferma o genera versione "pulita".
   - Output `OptimizedPlan2D`:
     - rooms (con posizioni suggerite, coordinate indicative o normalizzate).
     - constraints_respected: list[str].
     - technical_notes: list[str].
     - svg_content: stringa SVG professionale (muri spessi con spessore, simboli porte/finestre standard, etichette stanze, quote indicative, legenda, titolo "Proposta preliminare GB Construction — non valida per esecuzione", disclaimer).
     - png_preview_url (generato da SVG).
   - Regole: mantieni perimetro, accessi, finestre, vincoli dichiarati. Per ottimizzazione: usa dati da analisi (es. sposta cucina vicino scarico se visibile, migliora luce in soggiorno).
   - Aggiungi disclaimer forte nel SVG e metadati.

2. **Quality Gate 2D** (estendi `quality_gate.py`):
   - Se troppi unverifiable critici o gate analisi fallito → genera solo "versione pulita della planimetria caricata" + avviso (non ottimizzata).
   - Verifica coerenza minima (es. stanze abitabili con aperture).

3. **Integrazione e Persistenza**:
   - Chiamato dopo analisi + gate in `ai_architect_service.py` (se flag `AI_REQUIRE_PROFESSIONAL_2D`).
   - Salva SVG su R2 (processed/{job_id}/optimized_2d.svg), PNG preview, metadati nel job o collection layout (semplice, senza PostGIS).
   - Estendi payload job con `optimized_plan_2d`.

4. **Frontend: Visualizzazione 2D** (`frontend/src/landing/AIArchitect.jsx`, `Output.jsx`, dashboard `AIArchitectReview.jsx`):
   - Mostra anteprima PNG della 2D ottimizzata/pulita.
   - Pulsante "Scarica SVG professionale".
   - Evidenzia: "Rispetto allo stato di fatto: [cambiamenti]".
   - In Output: integra 2D come base per pacchetti (opzionale, per futuro bridge con predictive).
   - Usa componenti shadcn (Card, Dialog per lightbox, Button) + motion per transizioni.

**Criteri di accettazione Fase 2:**
- Da analisi valida + gate passa si genera sempre `OptimizedPlan2D` (SVG leggibile + PNG preview).
- La 2D mantiene perimetro, accessi, finestre e vincoli visibili dichiarati.
- Per stato di fatto: proposta mostra ottimizzazione realistica (non random; motivata da note tecniche).
- Output include note tecniche + disclaimer forte.
- Nessuna invenzione di elementi non supportati dall'analisi.
- UI mostra preview/download.

**Rischi & Mitigazioni:**
- Accuratezza 2D: valida su ground truth dataset (prepara 10-20 planimetrie reali con expected 2D).
- Complessità generazione SVG: parti da template controllato + elementi standard (non AI gen pura per la 2D tecnica).
- Costi: nessun LLM extra qui (usa dati strutturati dall'analisi).

**Integrazione con codice attuale:**
- Estende il flusso AI Architect esistente (non lo sostituisce).
- Prepara dati strutturati per futuro bridge al `predictive_engine.py` (es. rooms/posizioni per voci più precise).

---

## Fase 3: Consigli Tecnici Realistici e Strutturati (Milestone: Issues Motivati Tecnicamente + Disclaimer)

**Obiettivo:** Da `PlanAnalysis` + `OptimizedPlan2D`, genera lista `TechnicalIssue` con motivazioni concrete e sempre disclaimer.

**Task dettagliati:**

1. **Motore technical_advice.py** (`backend/engines/technical_advice.py` — nuovo):
   - Input: `PlanAnalysis` + `OptimizedPlan2D`.
   - Genera `technical_issues`:
     - Regole deterministiche iniziali (da analisi + 2D):
       - Luce/aero-illuminante (basato su aperture dichiarate vs stanze).
       - Circolazione (corridoi troppo lunghi/stretti).
       - Posizionamento bagni/cucina (rispetto scarichi/fumi visibili nell'analisi/2D).
       - Spazi inutilizzati o sovradimensionati.
       - Impianti da rifare (elettrico/idrico termico).
       - Demolizioni consigliate vs da evitare (per ottimizzazione 2D).
     - Per ogni issue: category, severity, description (tecnica), recommendation (con motivazione chiara), confidence, disclaimer ("Da validare con tecnico abilitato e sopralluogo prima di qualsiasi intervento").
   - Usa LLM solo per formulazione testo professionale in italiano (prompt template fisso + dati strutturati in input; non per inventare issues).
   - Salva in job.

2. **Integrazione:**
   - Chiamato dopo 2D (se flag).
   - Esposto nel payload.
   - UI: sezione dedicata "Consigli tecnici preliminari" (lista con severity badge, motivazione, disclaimer visibile).

**Criteri di accettazione Fase 3:**
- Issues sempre motivati tecnicamente e legati ai dati dell'analisi/2D.
- Disclaimer presente e prominente.
- Nessun consiglio generico.

**Rischi:** Evita over-promising; è "preliminare".

---

## Fase 4: Render Ultra Fedeli Vincolati alla Planimetria 2D (Milestone: Render Generati Solo Dopo 2D Validata e Rispettano la 2D)

**Obiettivo:** Render generati solo dopo 2D validata. Usano la 2D ottimizzata come reference vincolante. Genera prima zenithal/top-down, poi viste interne. Vieta aggiunte incoerenti.

**Dipendenze:** Provider esistente (Fal.ai/OpenAI con ControlNet dove possibile).

**Task dettagliati:**

1. **Motore render.py con Fidelity Gate** (`backend/engines/render.py` — nuovo):
   - Prima di chiamare provider:
     - Esegui quality_gate per fidelity (verifica che la 2D di riferimento esista e sia validata; controlla coerenza stile).
     - Se fallisce → non generare o safe fallback (es. preview 2D ingrandita + nota "Render non generati per bassa fedeltà alla planimetria").
   - Prompt vincolante: "Usa ESATTAMENTE questa planimetria 2D [descrizione o reference] come base vincolante. Mantieni perimetro, posizioni porte/finestre, dimensioni relative stanze, aperture. Non aggiungere stanze, finestre, muri o arredi non presenti. Stile: {style}. Vista: zenithal / internal 3/4 soggiorno / internal 3/4 cucina."
   - Strategia: genera prima zenithal/top-down (per validare coerenza), poi viste interne.
   - Salva con metadata (reference plan_2d hash/id).
   - Usa ControlNet depth + segmentation per aumentare fedeltà (se provider supporta).
   - Cost cap: limite per job (es. max 3 render per variante; logga costo).

2. **Integrazione:**
   - Orchestrato dopo 2D approvata/validata (flag `AI_REQUIRE_RENDER_FIDELITY`).
   - Salva su R2 renders/{job_id}/{variant_id}/...
   - Estendi payload con renders.

3. **Frontend:**
   - In AIArchitect results / Output / dashboard review:
     - Mostra renders solo se fidelity gate passato.
     - Evidenzia "Render generati dalla planimetria 2D ottimizzata".
     - Opzione rigenera (stesso vincolo 2D, stile diverso).
     - Galleria: zenithal prima, poi interne.

**Criteri di accettazione Fase 4:**
- Nessun render senza 2D di riferimento validata.
- Render rispettano geometria/elementi della 2D (verificato su sample).
- Zenithal generato prima delle viste interne.

**Rischi & Mitigazioni:**
- Fedeltà: usa prompt + ControlNet forti; quality gate.
- Costi: cap + logging + fallback.

---

## Fase 5: Integrazione Frontend, Flusso e Rollout Graduale

**Task:**
- Aggiorna `frontend/src/landing/AIArchitect.jsx`: sezioni per Analisi (strutturata), Planimetria 2D (preview + download SVG), Consigli tecnici, Render (con loading asincrono).
- Aggiorna `Output.jsx` e dashboard `AIArchitectReview.jsx`: integra output professionali (2D, consigli, render fedeli). Aggiungi azioni (accetta 2D per preventivo, rigenera render, etc.).
- Integra con flussi esistenti: il percorso configuratore → AI Architect → gate → output continua; quando flag on, usa i nuovi campi.
- Feature flag rollout: attiva per job specifici o %; rollback in 1 deploy.
- Prepara ground truth dataset (10-20 planimetrie reali + expected) per validazione.

**Criteri di accettazione Fase 5:**
- Flusso end-to-end funziona: upload → analisi strutturata dettagliata → 2D professionale → consigli realistici → render ultra fedeli vincolati.
- Utente/staff vede e scarica output professionali credibili.
- Tutto dietro flag, con rollback.
- Integrazione minimale con predictive (dati strutturati disponibili per estensione futura).

---

## Trasversali (Introdurre con Cautela e Milestone)

- **R2 Storage:** In Fase 1 (upload). Estendi a 2D e render nelle fasi successive. Aggiungi signed URLs, retention, limiti upload, logging.
- **Asincrono:** Usa BackgroundTasks con contratti job chiari per task lunghi (analisi, 2D, render). Definisci job state machine (queued, processing, completed, failed, review_required). Quando volume cresce, aggiungi worker Redis/arq (dopo Fase 2/3). Esplicito: Railway avrà backend + worker.
- **Cost Cap:** Logga e limita costo AI/render per lead (es. max X chiamate/vision per job). Blocca o avvisa se superato.
- **Rollback Operativo:** Feature flag + backup path legacy + script per revert R2 (se necessario) + monitoring provider.
- **Testing:** Unit per engine (mock provider). Integration con sample. Accuracy harness sul ground truth. Fidelity test (render non contraddicono 2D). E2E frontend (flusso con flag on/off).
- **Sicurezza/Compliance:** Validazione input, rate limit upload, disclaimer ovunque, audit log per job (soprattutto incertezze).
- **Documentazione:** Aggiorna prompts, regole hard, e `docs/ai-architect-professional.md`.
- **Evita in queste fasi:** PostGIS (usa GeoJSON), OR-Tools completo, dashboard scoring admin, routing avanzato, analytics varianti, automazioni comm.

**Integrazione End-to-End MVP:**
Upload (con gate regione se vogliamo, ma secondario) → Job → Analisi strutturata (Pydantic + gate) → 2D professionale → Consigli realistici → Render vincolati → Payload esteso per lead/output/dashboard.

Questo piano porta valore professionale sull'analisi della planimetria il prima possibile (consulente tecnico credibile), riduce scope creep, rispetta le priorità utente, e mantiene la strada aperta verso l'architettura target completa in fasi successive.

File salvato per riferimento del team. 

Prossimi passi: posso espandere task in codice (es. schemas.py + adapter), applicare modifiche graduali ai file esistenti, o creare i moduli engines/ iniziali. Dimmi.