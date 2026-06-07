# Piano di Implementazione Dettagliato
## AI Floorplan & Lead Engine — Potenziamento e Integrazione

**Progetto:** GB Construction — Costruzioni & Ristrutturazioni (Campania)  
**Documento di riferimento:** "Documento tecnico architetturale per GB Construction.pdf" (Blueprint Tecnico di Integrazione e Potenziamento v1.0)  
**Obiettivo:** Migliorare in maniera capillare le funzioni integrate del sistema attuale (configuratore, AI Architect, motore predittivo, pipeline CRM, landing immersiva, dashboard staff) trasformandolo in un motore AI end-to-end modulare per analisi planimetrie, generazione varianti layout, render e preventivi qualificati.  
**Principi guida (da preservare e applicare in ogni task):**  
- Monolite modulare (nessun microservizio prematuro).  
- Async-first (tutta la pipeline AI non bloccante).  
- Job idempotenti (rieseguibili senza duplicazioni o inconsistenze).  
- Region-locked (filtro Campania come invariante assoluto di sistema, applicato il prima possibile).  
- Backward compatible (nessun breaking change su endpoint, flussi e dati esistenti della piattaforma staff e landing).  
- Estensione, non riscrittura, degli asset esistenti (soprattutto `predictive_engine.py` + `predictive_data.py` con le 86 voci e coefficienti reali GB).  
- Testabilità e osservabilità capillare in ogni modulo.  
- Integrazione invisibile nel funnel di acquisizione lead (upload → varianti → render → preventivo → lead CRM qualificato).

Questo piano è **granulare e capillare**: ogni workstream è scomposto in task atomici con riferimenti a file specifici del codebase attuale, contratti di input/output, punti di integrazione, considerazioni di implementazione, testing e rischi. Non contiene stime temporali.

---

## Workstream 0: Analisi, Inventario e Compatibilità di Base

**Obiettivo:** Garantire visibilità completa sullo stato attuale, preparare il terreno per modifiche senza rotture, e implementare quick-win di qualità.

### Task 0.1 — Inventario e Mappatura Completa
- Esegui scansione completa del codebase (frontend/src, backend/, storage esempi, test, public assets cantieri).
- Mappa tutti i riferimenti a:
  - AI Architect attuale (`frontend/src/landing/AIArchitect.jsx`, `frontend/src/dashboard/pages/AIArchitectReview.jsx`, `backend/ai_architect_service.py`, endpoint in `backend/server.py`).
  - Motore predittivo (`backend/predictive_engine.py`, `backend/predictive_data.py`, chiamate da `/estimate`, creazione lead, `/quote/from-ai-project`).
  - Flusso landing ( `Landing.jsx`, `Configurator.jsx` 6 step, `ImmersiveHero.jsx` GSAP, `Output.jsx`, `ContactGate.jsx`).
  - Dashboard CRM (LeadDetail con suggest AI, Pipeline Kanban, Report con insights, Settings per coefficienti/voci/staff).
  - Storage attuale (`backend/storage/ai_architect/` con uploads/outputs misti SVG/PNG/PDF).
  - Integrazioni Meta (`backend/meta_leads_service.py`, webhook in server.py).
- Documenta in un file `docs/current-state-inventory.md` (o aggiorna `memory/AI_Architect_Stato_Attuale.md`).
- Identifica tutti i punti di "shadow logic" o fallback (es. SVG statici quando image gen fallisce).

### Task 0.2 — Setup Strumenti di Base per Sviluppo Futuro
- Aggiungi Redis locale (o Upstash per dev) e configura `arq` (o alternativa semplice come Celery/RQ se preferita per semplicità iniziale) nel backend.
- Crea cartella `backend/engines/` con struttura modulare (`__init__.py`, `base.py` per interfacce comuni).
- Aggiungi dipendenze necessarie (ultralytics, opencv-python-headless, shapely, ortools, psycopg2-binary o asyncpg per PostGIS, boto3 o librerie R2 compatibili, pytesseract).
- Configura variabili d'ambiente per provider (FAL, OpenAI, Anthropic, OpenRouter) con fallback chiari.
- Implementa un semplice job queue wrapper (anche se temporaneo) in `backend/orchestrator/` per isolare la logica asincrona.

### Task 0.3 — Layer di Compatibilità e Feature Flag
- In `backend/server.py` e `ai_architect_service.py`: introduci feature flag (env var `AI_FLOORPLAN_ENGINE_ENABLED=true/false` o DB config).
- Crea adapter `engines/compat.py` che permette al flusso attuale di continuare a funzionare mentre i nuovi engine vengono sviluppati.
- Aggiungi logging strutturato (con correlation ID per job) in tutti i moduli esistenti.
- Aggiorna test esistenti (`backend/tests/`) per coprire il comportamento legacy durante le modifiche.

**Output atteso:** Inventario completo, ambiente pronto per engine modulari, nessun breaking change sul flusso attuale.

---

## Workstream 1: Filtro Regione Campania (Critico per Business Value)

**Obiettivo:** Rendere il filtro Campania un invariante di sistema (multi-livello) per qualificare lead alla fonte, riducendo sprechi commerciali. Integrarlo capillarmente in tutti i touchpoint esistenti.

### Task 1.1 — Whitelist e Validazione Centralizzata
- Crea `backend/config/region.py` (o estendi `predictive_data.py`):
  - `CAMPANIA_PROVINCES = ["NA", "CE", "SA", "AV", "BN"]`
  - `CAMPANIA_CAP_RANGE = (80010, 84099)` (o lookup table più precisa).
  - Funzioni `is_serviceable(province: str, cap: str) -> bool` e `get_serviceable_reason(...)`.
- Aggiungi collection Mongo `region_whitelist` (per override futuri) con seed iniziale.

### Task 1.2 — Integrazione Frontend (Landing)
- In `frontend/src/landing/Configurator.jsx`:
  - Aggiungi campo "Provincia" (select o input con validazione) obbligatorio prima di sbloccare step successivi o upload.
  - Blocca UI con tooltip: "Attualmente i nostri servizi sono attivi esclusivamente in Campania (NA, CE, SA, AV, BN)."
  - Integra validazione client-side + chiamata a nuovo endpoint `/public/check-region`.
- In `frontend/src/landing/AIArchitect.jsx` (wizard upload planimetria):
  - Ripeti il gate "Provincia/CAP" prima di permettere upload (o eredita da config del Configurator).
  - Se job AI già esistente, valida regione sul lead associato.
- In `frontend/src/landing/ContactGate.jsx` e `Output.jsx`:
  - Passa regione nei payload ai backend.
- Aggiungi componenti riutilizzabili in `frontend/src/components/region/` (usando shadcn/ui Select/Input già attivi).

### Task 1.3 — Integrazione Backend (Gateway e Webhook)
- In `backend/server.py`:
  - Middleware o dependency `require_campania_region` applicato su `/leads`, `/ai-architect/jobs`, `/estimate`, `/quote/from-ai-project`.
  - Su POST `/leads` e creazione job AI: valida `citta/provincia/cap` (o da form config).
  - Su webhook Meta (`/webhooks/meta`): parsing `city/region` + reverse geocoding (Nominatim/OpenStreetMap) per casi ambigui. Respingi con log passivo (`status="out_of_scope"`).
- Estendi modello Lead (in creazione e update) con campi: `region`, `province`, `cap`, `out_of_scope_flag`, `ai_job_id`.
- In `backend/meta_leads_service.py`: aggiungi filtro e arricchimento (budget_estimated, urgency_score, ai_project_score).

### Task 1.4 — Routing e Arricchimento Lead
- Logica di assegnazione:
  - Round-robin base su team (Giovanni, Giuseppe, Vincenzo) — configurabile in Settings.
  - Preferenza geo-zonale (es. Hinterland est a risorsa X) — memorizzata in `region_whitelist` o Settings.
- Arricchimento automatico della card lead in dashboard:
  - `budget_estimated` (dal Cost Engine o predictive).
  - `urgency_score` (incrocio tempistiche + azioni utente).
  - `quality_tier` e `ai_project_score`.
- In `frontend/src/dashboard/pages/LeadInbox.jsx` e `LeadDetail.jsx`: filtri e badge per "In scope Campania" vs out_of_scope. Indicatore dashboard per lead fuori zona (senza notifiche invasive).

### Task 1.5 — Testing e Logging
- Test unitari per validazione regione (inclusi edge case CAP ambigui, Meta payload).
- Test di integrazione: creazione lead/job con regione invalida → respinto con flag corretto.
- Audit log capillare (in `ai_architect_errors` o nuova collection) per tutti i respinti.
- Aggiorna `backend/tests/test_gb_backend.py` e test Meta.

**Punti di integrazione chiave con codice attuale:**
- Non rompe il flusso Configurator → Predictive → Lead (lo arricchisce).
- Si applica anche al percorso AI Architect (upload planimetria).
- Out-of-scope popolano indicatore in Report/Settings per future espansioni.

---

## Workstream 2: Infrastruttura Asincrona, Orchestrator e Job Management

**Obiettivo:** Rendere l'intera pipeline AI (soprattutto vision, layout solving, render) non bloccante e resiliente.

### Task 2.1 — Setup Orchestrator
- Installa e configura `arq` (o RQ/Celery) con Redis.
- Crea `backend/orchestrator/`:
  - `jobs.py`: definizioni job (es. `process_vision`, `generate_layout_variants`, `enqueue_renders`).
  - `worker.py`: entrypoint worker.
  - `progress.py`: tracker con step (upload, analysis, proposal_2d, review, topdown_3d, renders, advice, complete) + percentuali e SSE per frontend.
- Refactor `backend/ai_architect_service.py`:
  - `create_job` rimane sincrono (crea record Mongo).
  - `process_job` diventa dispatcher che sottomette task asincroni con retry policy e dead-letter.
- Aggiungi gestione idempotency (usa `ai_job_id` come key).

### Task 2.2 — Retry, Timeout, Monitoring
- Policy: exponential backoff, max attempts configurabili per sub-task (vision può fallire più facilmente di geometry).
- Integrazione Sentry (o logging strutturato) per job falliti.
- Dashboard admin per coda job (stato, retry manuali) — nuova pagina o tab in AIArchitectReview.

### Task 2.3 — Integrazione con Flusso Esistente
- Mantiene polling attuale (`/ai-architect/jobs/{id}` ogni 1.4s) durante transizione.
- Aggiungi supporto SSE (Server Sent Events) opzionale per progress real-time (in Layer 2).

**Integrazione con codice attuale:**
- Sostituisce gradualmente i `BackgroundTasks` attuali in server.py.
- Preserva endpoint esistenti (`/ai-architect/jobs`, confirm, approve, regenerate, report).

---

## Workstream 3: Storage Scalabile e Persistenza

**Obiettivo:** Sostituire filesystem locale instabile con R2 + strutturare output.

### Task 3.1 — Migrazione a Cloudflare R2 (o S3 compatibile)
- Configura credenziali R2 in env.
- Crea utility `backend/storage/r2.py` (upload, download, signed URL, delete).
- Refactor `ai_architect_service.py` e job:
  - Upload originale → R2 `uploads/{job_id}/original.{ext}`.
  - Output intermedi (wireframe SVG, geometry GeoJSON) → `processed/{job_id}/...`.
  - Render → `renders/{job_id}/{variant_id}/zenithal.jpg` ecc.
  - Report PDF → `reports/{job_id}/preventivo_{variant_id}.pdf`.
- Aggiorna serving file (static o proxy tramite backend per auth se necessario).
- Script di migrazione per job esistenti da local storage a R2 (one-time).

### Task 3.2 — Estensioni MongoDB
- Aggiungi campi a collezioni esistenti (senza migration distruttive):
  - `leads`: `region`, `province`, `cap`, `out_of_scope_flag`, `ai_job_id`, `ai_architect_summary` (già parzialmente presenti).
  - `ai_jobs`: `variants[]` (array di LayoutVariant), `render_jobs[]`, `scoring_preset_id`, `region`.
- Nuove collezioni:
  - `scoring_presets`: pesi formula (efficienzas_spaziale, valore_immobile, ecc.), override globali/clienti/geografici.
  - `render_jobs`: tracking callback da Fal.ai/Replicate (status, urls, cost).
  - `layout_variants`: (opzionale embedding in ai_jobs o separata).
  - `region_whitelist`: province/CAP attivi + note.

### Task 3.3 — PostGIS Side-Store (per geometrie)
- Setup PostgreSQL + PostGIS (locale per dev, gestito in prod).
- Tabella `floorplans_geometry` (da spec PDF):
  ```sql
  CREATE TABLE floorplans_geometry (
    id BIGSERIAL PRIMARY KEY,
    ai_job_id TEXT NOT NULL,
    variant_id TEXT,
    feature_type TEXT NOT NULL CHECK (feature_type IN ('wall','door','window','room')),
    room_label TEXT,
    geom GEOMETRY(GEOMETRY, 4326) NOT NULL,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
  );
  CREATE INDEX idx_floorplans_geom_gist ON floorplans_geometry USING GIST (geom);
  CREATE INDEX idx_floorplans_ai_job ON floorplans_geometry (ai_job_id);
  ```
- Utility per insert/query poligoni (shapely → PostGIS).

**Integrazione:**
- R2 sostituisce `backend/storage/ai_architect/`.
- Mongo espansioni mantengono compatibilità con lead attuali e dashboard.

---

## Workstream 4: Engine Modulari (Layer 4)

Crea `backend/engines/` con base comune (interfaccia, logging, metrics).

### 4.1 Vision Engine
- File nuovo: `backend/engines/vision.py`.
- Task:
  - Preprocessing: denoise, deskewing (OpenCV).
  - Inferenza: integrazione ultralytics con pesi CubiCasa5K (o modello equivalente).
  - Post-processing: vettorializzazione segmenti (muri spessore, porte/finestre con orientamento).
  - OCR: pytesseract per quote, etichette stanze, scale.
  - Fallback: se confidence < soglia (muri 0.7, porte/finestre 0.6) → Claude Sonnet (Anthropic SDK) con prompt strutturato + schema Pydantic.
  - Output: Pydantic `VisionResult` (walls[], doors[], windows[], ocr_labels[], scale_ratio_px_per_meter, fallback_used, confidence_overall).
  - Esempi input/output come da spec PDF.
- Integrazione: chiamato da orchestrator nel job AI. Aggiorna `ai_architect_service.py` per usare questo invece della logica attuale.
- Testing: test di accuratezza su 10-20 planimetrie reali (da storage o PUBLIC/). Metriche precision/recall per muri/porte.

### 4.2 Geometry Engine
- File: `backend/engines/geometry.py`.
- Task:
  - Snap walls (tolerance ±5px equivalenti scala).
  - Correzione geometrie, rimozione duplicati.
  - Costruzione grafo planare (networkx).
  - Flood-fill / algoritmi per identificare aree chiuse (stanze).
  - Output: GeoJSON FeatureCollection (poligoni stanze + segmenti adiacenza).
- Persistenza: scrivi in PostGIS `floorplans_geometry`.
- Integrazione: input da VisionResult → output per Semantic e Layout.

### 4.3 Semantic Engine
- File: `backend/engines/semantic.py`.
- Task:
  - Classificazione tipologica usando area, posizione relativa, OCR labels + regole hard (matrice R1-R6 da spec: bagno <6mq con scarico, cucina 9-14mq con sfogo fumi, ecc.).
  - Fallback LLM (Claude Sonnet 4.5) solo per ambiguità (prompt rigoroso, schema strutturato, no hallucination).
  - Tassonomia completa italiana (soggiorno, cucina, cucinino, bagno, antibagno, camera matrimoniale, cameretta, studio, ripostiglio, balcone, terrazzo, ingresso, corridoio, lavanderia).
- Output: stanze con label semantico + confidence + verification_required.
- Integrazione: arricchisce geometrie per Layout Engine.

### 4.4 Layout Engine (Cuore Generativo)
- File: `backend/engines/layout.py`.
- Task:
  - Modellazione come CSP (Constraint Satisfaction Problem) con Google OR-Tools CP-SAT.
  - 4 strategie obbligatorie (parametrizzabili):
    1. Livability (luce/area max, separa notte/giorno).
    2. Valore immobile (cucina abitabile, 2° bagno se fattibile, walk-in).
    3. Max stanze (frazionamento per affitti/famiglie).
    4. Cost-optimized (minimo abbattimento muri e spostamenti impianti).
  - Vincoli hard inviolabili (da spec):
    - Bagno adiacente o pendenza verso colonna scarico fecale.
    - Zona fuochi con sfogo verticale fumi.
    - Stanze abitabili con aperture esterne ≥1/8 aero-illuminante.
    - Nessun bagno diretto su cucina (antibagno obbligatorio).
    - Corridoi ≥90cm, porte interne ≥70cm.
  - Per ogni variante: calcola vettori nuovi, demolitions, metratura finiture.
  - Componente narrativa: LLM (Claude) genera paragrafo commerciale "Perché conviene questo layout...".
  - Output: array `LayoutVariant` (3-5) con geometria, score preliminare, costo stimato (delegato a Cost Engine), id per render futuri.
- Integrazione: usa output Semantic + Geometry. Passa a Scoring + Cost.

### 4.5 Scoring Engine
- File: `backend/engines/scoring.py`.
- Task:
  - Formula base: `Score = 0.30 × efficienza_spaziale + 0.20 × valore_immobile + 0.15 × fattibilità + 0.15 × costo + 0.10 × luce + 0.10 × flessibilità`.
  - Storage e override in `scoring_presets` (Mongo): pesi globali, per cliente ("Budget Premium" → alza valore_immobile), preset geografici (centro vs provincia Campania).
  - Admin UI in dashboard per edit pesi (nuova sezione in Settings.jsx usando shadcn form).
- Output: score 0-100 per variante + breakdown.
- Integrazione: dopo Layout, prima di Cost/Render. Arricchisce lead.

### 4.6 Cost Engine (Estensione Critica dell'Esistente)
- **Non riscrivere** — estendi `backend/predictive_engine.py`.
- File: `backend/engines/cost.py` (adapter).
- Task:
  - Input: `LayoutVariant` (rooms, demolitions, finiture area).
  - Mapping: trasla in voci di capitolato (usa le 86 voci da `predictive_data.py`).
  - Applicazione coefficienti iper-locali Campania (Napoli Centro Storico +15% Belle Arti/cantieristica complessa, Vomero/Posillipo +10%, zone interne standard, Hinterland standard, provincia esterna -5% logistico).
  - Struttura output: range min/max per macrocategorie (Demolizioni, Opere Murarie, Idrico, Elettrico, Pavimenti, Bagni, Infissi, Tinteggiature, Smaltimento).
  - Chiama `calcola_preventivo` esistente o estensione per clamping €/mq e enforce ordine (Ess < Prem < Lux).
  - Export PDF: usa/extendi reportlab attuale con branding GB, impaginazione, logo, footer legale. Salva su R2.
- Integrazione: chiamato da Layout e dal bridge `/quote/from-ai-project` (aggiungi `variant_id` per selezionare variante specifica).
- Preserva tutti i test e la logica attuale del configuratore 6-step.

### 4.7 Render Engine
- File: `backend/engines/render.py`.
- Task:
  - Provider primario: Fal.ai (latenza bassa, datacenter EU). Fallback Replicate.
  - Modello: SDXL + multi ControlNet (Depth + Semantic Segmentation dalla planimetria target/variante).
  - Per ogni `LayoutVariant`: genera 3 viste:
    1. Zenithal / top-down (tutta la pianta).
    2. Prospettiva interna 3/4 Soggiorno principale.
    3. Prospettiva interna 3/4 Cucina principale.
  - Preset stili (heritage dal brand attuale):
    - Classico Elegante (modanature, stucchi, parquet spina, toni caldi).
    - Contemporaneo Caldo (legni chiari, palette neutre).
    - Industrial Loft (microcemento, ferro crudo).
    - Moderno Minimal (bianco dominante, linee tese, pulizia estrema).
    (Riferimenti video in `frontend/public` o assets esistenti).
  - Tracking: `render_jobs` collection per callback asincroni.
  - Persistenza: R2 `renders/{job_id}/{variant_id}/...`.
  - Costo target: ~€0.30-0.50 per batch 3 render.
- Integrazione: orchestrator sottomette dopo Layout + Scoring. Frontend (Output.jsx, AIArchitect results) mostra galleria con selettore stile per rigenerazione.

### 4.8 CRM Filter Engine (già coperto in Workstream 1, ma integrato qui)
- Estendi con logica di arricchimento lead post-engine (budget, score, urgency da varianti).
- Routing round-robin + geo-zonale su staff (config in Settings).

**Per tutti gli engine:**
- Definisci Pydantic models condivisi in `backend/engines/schemas.py`.
- Logging, metrics (tempo per step, confidence), error handling con fallback graceful.
- Unit test per logica deterministica (regole semantic, vincoli layout, mapping cost).
- Integrazione test end-to-end con sample planimetrie reali.

---

## Workstream 5: Modello Dati e API

### Task 5.1 — Espansioni Mongo (mantenendo compatibilità)
- Aggiorna modelli Pydantic in `server.py` o `models.py`.
- Script di migrazione (non distruttiva) per campi opzionali su lead e ai_jobs esistenti.
- Indici nuovi su `ai_job_id`, `out_of_scope_flag`, etc.

### Task 5.2 — PostGIS e R2 (come Workstream 3).

### Task 5.3 — Nuovi Endpoint (mantenendo esistenti)
- Mantieni rigorosamente: tutte `/auth/*`, root `/ai-architect/jobs/*` (confirm/approve/regenerate/report), dashboard base, `/estimate`, creazione lead base.
- Nuovi:
  - `GET /ai-architect/jobs/{id}/layouts` → array LayoutVariant.
  - `POST /ai-architect/jobs/{id}/layouts/{variant_id}/select`.
  - `POST /ai-architect/jobs/{id}/renders` (con variant_id + views[]).
  - `GET /ai-architect/jobs/{id}/renders/{variant_id}`.
  - Admin: `/admin/scoring-presets` (GET/PUT), `/admin/region-whitelist`.
  - Public: `POST /public/check-region`, `GET /public/results/{token}` (per sharing risultati?).
- Potenzia `/quote/from-ai-project`: accetta `variant_id`, restituisce PDF brandizzato su R2 + estimate specifico variante.
- Potenzia webhook Meta con filtro Campania.
- Aggiungi validazione Pydantic su provincia in creazione job/lead.

### Task 5.4 — Documentazione API
- Aggiorna OpenAPI/Swagger con nuovi endpoint e esempi (inclusi variant).

---

## Workstream 6: Frontend e UX Integrata

**Obiettivo:** Esporre le nuove capacità in modo capillare nel funnel esistente senza rompere l'esperienza attuale.

### Task 6.1 — Landing Flow
- Configurator e AIArchitect: gate regione (Workstream 1).
- Dopo AI Architect o Configurator avanzato: mostra varianti (3-5 LayoutVariant) con:
  - Mini preview (SVG wireframe o thumbnail).
  - Score + breakdown.
  - Cost range (da Cost Engine).
  - Narrativa "Perché conviene...".
  - Selezione variante → trigger render jobs asincroni.
- In Output.jsx: galleria render (zenithal + 2 prospettive) per variante selezionata, selettore stile per rigenera, download PDF specifico variante, CTA preventivo con variant_id.
- Usa componenti esistenti (Tilt3D, motion, shadcn Dialog/Lightbox per poster/render).

### Task 6.2 — Dashboard Staff
- AIArchitectReview.jsx: espandi per mostrare varianti per job, stato render, approve/select variante, re-gen.
- LeadDetail.jsx: card arricchita con ai_project_score, variante selezionata, link a render/PDF.
- Nuova o estesa sezione in Report.jsx per insight su varianti generate (conversioni per strategia layout).
- Settings.jsx: tab "AI Floorplan" per:
  - Editor scoring_presets (form shadcn con pesi).
  - Region whitelist (table + edit CAP/province).
  - Monitor job queue e costi render.

### Task 6.3 — Componenti e Design System
- Riutilizza/estendi shadcn/ui (già in `frontend/src/components/ui/`).
- Nuovi: `VariantCard`, `RenderGallery`, `RegionGate`, `ScoreBreakdown`.
- Integra con GSAP/Tilt3D esistenti dove sensato (es. card varianti 3D tilt).
- Accessibilità e responsive capillare.

---

## Workstream 7: Integrazioni Esterne e Pipeline End-to-End

- Meta Lead Ads: filtro + arricchimento (già in 1 e 5).
- WhatsApp/Email (Resend/SES): placeholder attuali → integra per notifica lead qualificati o invio PDF preventivo (dopo selezione variante).
- Bridge completo: da variante selezionata → lead CRM con estimate specifico + PDF.
- Pipeline end-to-end: documenta sequence diagram (testuale o Mermaid) in docs/. Collega upload landing → job → engines → renders → lead + notifica staff.

---

## Workstream 8: Testing, Sicurezza, Compliance, Migrazione

### Testing (capillare)
- Unit: ogni engine (regole semantic, CSP layout constraints, mapping cost, scoring formula).
- Integration: full pipeline con sample data (planimetrie reali + expected outputs).
- E2E: frontend (Playwright se configurato) per flusso upload → variante → preventivo.
- Accuracy: metriche su Vision/Geometry/Semantic vs ground truth (da cantieri passati).
- Load: job queue con render multipli.
- Aggiorna/estendi `backend/tests/` (test_ai_architect_local_analysis.py, test_gb_backend.py, ecc.).

### Sicurezza & Compliance
- Region filter come controllo accesso (non solo business).
- Validazione input stretta (Pydantic ovunque).
- Rate limiting su endpoint pubblici.
- Logging audit per tutte le azioni AI/job (soprattutto fuori Campania).
- Privacy: non persistere dati sensibili oltre necessario; GDPR consideration per lead.

### Migrazione
- Script one-time per job esistenti (ricalcolo varianti dove possibile, o mark come legacy).
- Feature flag per rollout graduale (nuovo engine solo per % di traffic o utenti staff).
- Rollback plan: revert a flusso attuale via flag.

---

## Workstream 9: Considerazioni Trasversali e Pulizia

- Refactor graduale di `ai_architect_service.py` e parti di server.py per usare i nuovi engine (mantieni wrapper per compat).
- Monitoring: aggiungi metriche per ogni engine (latenza, confidence media, costo per job, tasso successo).
- Documentazione: aggiorna README, memory/, aggiungi `docs/ai-engines.md` con diagrammi (usa Mermaid per layer e pipeline).
- Dipendenze: gestisci versioni pin (es. ortools, ultralytics) e licenze (CubiCasa5K MIT).
- Performance: caching per planimetrie simili (hash geometrico), parallelismo per render batch.
- Error handling: graceful degradation (se un engine fallisce, fornisci variante base + avviso).

**Integrazione End-to-End Finale:**
Il flusso diventa:
Landing (Config + AIArchitect con gate regione) → Job → Orchestrator → Vision → Geometry → Semantic → Layout (4 strategie) → Scoring + Cost (estende predictive) → Render jobs async → Variante selezionata → Lead CRM arricchito + PDF → Dashboard staff (con assegnazione, timeline, suggest AI).

Questo piano garantisce miglioramenti capillari: ogni funzione esistente (configuratore, predictive, AI attuale, dashboard, funnel lead) viene estesa/integrata in modo modulare e misurabile, preservando ciò che funziona (motore preventivi reali GB) e aggiungendo le capacità mancanti (vision professionale, layout deterministico, render scalabili, filtro geo).

---

**File generato:** Questo piano è salvato in `IMPLEMENTATION_PLAN_AI_Floorplan_Lead_Engine.md` nella root del progetto per riferimento del team.

Per procedere, posso:
- Espandere un workstream specifico con codice bozza (es. scheletro di un engine).
- Aggiornare file esistenti del progetto con i task.
- Creare diagrammi Mermaid aggiuntivi.
- Analizzare rischi in maggior dettaglio per un engine.

Fammi sapere il prossimo passo.