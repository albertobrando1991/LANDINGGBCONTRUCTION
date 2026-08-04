# Implementation Plan: EdilOS AI — piattaforma tenant-scoped per GB Construction

**Database di riferimento**: Supabase (Postgres + RLS + Auth + Storage)
**Domini di produzione**: `gbconstruction.it` (frontend) e `api.gbconstruction.it` (backend)
**Prezzario base**: Regione Campania, duplicabile e personalizzabile per tenant
**Metodo**: vibe-coding — migration SQL first, types generati, UI dopo
**Complessità**: LARGE (~5 mesi, 1 sviluppatore)
**Stato**: Fase 0 + Fase 1 in beta tecnica; hardening verificato locale e remoto

### Aggiornamento implementazione — 4 agosto 2026

La roadmap completa è circa al **25%**: le Fasi 3-6 non sono iniziate. Lo scope
Fase 0 + Fase 1 è circa al **75%** e produce già prezzari, computi, ponte AI e
preventivi, ma non ha ancora superato tutti i gate per una release SaaS.

| Area | Stato verificato | Evidenza / limite attuale |
|---|---|---|
| Schema Supabase, seed, RLS | **Verde locale e remoto** | `supabase db reset --local` ricostruisce 9 migration + seed; la migration di hardening è applicata al progetto EdilOS remoto e le postcondizioni di sicurezza sono verificate |
| Isolamento tenant | **Verde in locale** | Test transazionale A/B su lettura, scrittura e view `computi_totali`; ad `anon` sono negati P.IVA/piano/crediti |
| Prezzario e ponte AI | **Verde in locale** | Il listino duplicato diventa default e le regole AI risolvono le voci personalizzate per codice, usando i prezzi calibrati |
| Computo → preventivo | **Hardening completato** | Conversione consentita solo da computo `confermato`; voci AI non validate restano un blocco server-side |
| Bridge Mongo → Postgres | **Transitorio implementato** | Gli ObjectId lead vengono sincronizzati on-demand in UUID tenant-scoped; Mongo resta comunque presente fino a Fase 2 |
| Tenant branding | **Implementato sul dominio corrente** | `/api/tenant/config` usa whitelist e privilegi per colonna; `TenantContext` carica tema/meta. Il dominio non seleziona il tenant e non è richiesto alcun wildcard DNS |
| CI | **Verde** | Run `30891017246` sul commit `6332869`: build, test Supabase/RLS, `rls-guard` e `service-role-guard` completati con successo |
| Ground truth | **Bloccante release** | Esistono 10 casi sintetici, ma manca il set di 10 planimetrie PDF reali con preventivi storici per provare il gate 8/10 entro 15% |
| Auth frontend | **Dual-mode implementato** | Il browser usa Supabase Auth quando configurato e conserva il login legacy come fallback temporaneo; il Bearer JWT prevale sul cookie legacy |
| Storage frontend | **Primo flusso implementato** | I documenti di cantiere usano bucket privato, path tenant-scoped, limiti MIME/dimensione e download con URL firmato di 5 minuti; restano da migrare gli asset AI legacy |

La migration `20260803175957_edilos_release_hardening.sql` è stata applicata e
testata sia sul Supabase locale sia sul progetto EdilOS remoto. Il deploy
applicativo della patch resta da completare dopo la validazione del branch `develop`.

---

## 1. Requirements restatement

Trasformare l'attuale Lead Engine GB Construction (single-tenant) in **EdilOS AI**: piattaforma SaaS replicabile che ogni impresa edile acquista e ottiene:

1. **Front-office GB Construction** — landing + configuratore + AI Architect su `gbconstruction.it`
2. **Back-office operativo** — prezzario, computi metrici, cantieri, libretto di misura, SAL, varianti, economics
3. **Portale cliente finale** — read-only su avanzamento lavori + approvazione varianti

Nota storica: `memory/PRD.md` riga 8 documenta che lo stack richiesto in origine era Next.js+Supabase, poi adattato a Mongo. Questo piano chiude quel cerchio.

Vincoli decisi nella fase di critica, confermati:

| Decisione | Motivo |
|---|---|
| **NO fatturazione elettronica SDI** — solo economics + export verso Fatture in Cloud/Aruba | Responsabilità fiscale, conservazione 10 anni, mesi di lavoro. Valore percepito uguale, rischio zero |
| **Prezzario-first** — nessun modulo computi senza prezzario calibrato | Senza listino strutturato il computo AI sbaglia e si perde fiducia al primo uso |
| **Ponte AI planimetria→computo in Fase 1** | È l'unico differenziatore reale vs Restruct. È il motivo per cui comprano |
| **Multi-tenant enforced dal DB (RLS), non dal codice** | Un `find()` dimenticato = leak dati tra imprese concorrenti. Irreversibile |
| **PWA offline-first per libretto di misura** | Si compila in cantiere, spesso senza rete. Senza mobile il SAL non si popola e il modulo muore |
| **Subdomini di default**, dominio custom solo su piano alto | Onboarding manuale non scala a 50 clienti |

---

## 2. Decisione architetturale: Supabase come system of record

### 2.1 Cosa va su Supabase

**Tutto il dato di dominio.** Postgres è la scelta corretta per computi → voci → SAL → varianti: relazioni forti, aggregazioni monetarie, vincoli d'integrità. Un SAL sbagliato di 3.000€ per desincronizzazione = cliente perso.

| Componente Supabase | Uso |
|---|---|
| **Postgres** | Tenant, utenti, prezzari, computi, preventivi, cantieri, libretto, SAL, varianti, spese, incassi, lead |
| **RLS** | Isolamento tenant enforced dal database, non dal codice applicativo |
| **Auth** | Identità unica per staff + clienti finali. Il JWT porta i claim tenant |
| **Storage** | Planimetrie, render AI, foto cantiere, PDF generati |
| **pg_cron** | Pulizia cache AI scaduta, reminder scadenze, ricalcoli notturni |

### 2.2 Destino di MongoDB

**Dismesso a fine Fase 2.** Ragione: due DB = due modelli di sicurezza, due backup, due migrazioni. Contrario a "ripetibile e scalabile".

| Collection attuale | Destinazione |
|---|---|
| `leads`, `users`, `cantieri` | → tabelle Postgres con RLS (migrazione dati) |
| `ai_architect_outputs`, `ai_architect_jobs`, `ai_architect_errors`, `ai_architect_quality_logs` | → Postgres, payload in colonne `jsonb` |
| `ai_credit_buckets`, `ai_credit_ledger`, `ai_usage_events` | → Postgres (ledger contabile: serve transazionalità, oggi non ce l'ha) |
| `ai_architect_cache` | → tabella con `expires_at` + job `pg_cron` |
| `meta_webhook_events` | → Postgres, append-only con retention 90gg |
| `sopralluogo_slots` | → Postgres |

**Bonus**: Supabase Storage elimina il problema noto del volume effimero Railway (`/app/storage`). I file diventano URL firmati, il backend smette di essere stateful.

### 2.3 Chi parla con il database

Modello **ibrido**, scelto per massimizzare velocità di vibe-coding senza perdere il controllo sulla logica di dominio:

```
┌─────────────────────────────────────────────────────────┐
│ Frontend React (CRA + craco)                            │
│                                                          │
│  ├─ CRUD semplice ────────────► supabase-js + RLS       │
│  │  (anagrafiche, prezzario, note, filtri, realtime)    │
│  │                                                       │
│  └─ Operazioni di dominio ────► FastAPI /api/*          │
│     (genera SAL, AI→computo, PDF, crediti, webhook)     │
└─────────────────────────────────────────────────────────┘
                                        │
                          FastAPI apre connessione Postgres
                          con SET LOCAL request.jwt.claims
                          ⇒ RLS attiva anche lato server
```

**Regola dura**: `service_role` (che bypassa RLS) è ammesso **solo** in job di sistema che non hanno un utente — webhook Meta, cron. Mai in un endpoint raggiungibile da un utente autenticato.

### 2.4 Autenticazione: migrazione da JWT proprietario a Supabase Auth

Oggi `backend/auth.py:28` firma JWT propri con `JWT_SECRET` e cookie httpOnly. RLS ha bisogno di `auth.uid()` e dei claim nel JWT, quindi la sostituzione è obbligata.

**Custom Access Token Hook** — inietta i tenant nel JWT così le policy non fanno subquery per riga:

```sql
create or replace function public.custom_access_token_hook(event jsonb)
returns jsonb language plpgsql stable as $$
declare claims jsonb; tenants jsonb;
begin
  select coalesce(jsonb_agg(jsonb_build_object('t', tenant_id, 'r', role)), '[]'::jsonb)
    into tenants
  from public.tenant_members
  where user_id = (event->>'user_id')::uuid;

  claims := coalesce(event->'claims', '{}'::jsonb);
  claims := jsonb_set(claims, '{app_tenants}', tenants);
  return jsonb_set(event, '{claims}', claims);
end; $$;
```

Retrocompatibilità: durante la Fase 2 FastAPI accetta **entrambi** i token (vecchio JWT + Supabase JWT via JWKS). Il vecchio path si rimuove a migrazione completata.

---

## 3. Pattern da rispettare (grounding sul codice esistente)

| Categoria | Sorgente | Pattern da riusare |
|---|---|---|
| Naming API | `backend/server.py:40` | `APIRouter(prefix="/api")`, path in italiano snake_case (`/cantieri`, `/preventivi`) |
| Errori | `backend/server.py:104`, `backend/auth.py:65` | `HTTPException(status_code=..., detail="messaggio italiano rivolto all'utente")` |
| Validazione ID | `backend/server.py:102` | Helper dedicato che alza 400 — replicare come `uuid_or_400()` |
| Serializzazione | `backend/server.py:77` | Helper `serialize()` per `_id` Mongo — su Postgres diventa superfluo, **rimuovere non sostituire** |
| Logging | `backend/server.py:43` | `logging.getLogger("gb")`, livello INFO |
| Costanti dominio | `backend/server.py:45-63` | Tuple `(chiave, Label)` + dict labels. Replicare per stati computo/SAL |
| Test backend | `backend/tests/conftest.py:26` | Integration test HTTP con `requests.Session` autenticata contro API live |
| UI | `frontend/src/components/ui/`, `frontend/src/dashboard/pages/` | shadcn/Radix + Tailwind, una pagina per file in `dashboard/pages/` |
| Data fetching FE | `frontend/package.json` | TanStack Query 5 già presente — **standardizzare su questo, rimuovere SWR** (oggi coesistono) |
| PDF | `reportlab` + `PyMuPDF` in `backend/requirements.txt` | Già disponibili: SAL/preventivi/libretti generati con reportlab, no nuove dipendenze |
| Prezzi seed | `backend/predictive_data.py` (`COEFFICIENTI`, 86 voci) | Base reale per il prezzario preconfezionato |

**Non esiste oggi**: nessun pattern di tenancy, nessun repository layer, nessuna migration versionata. Vanno creati da zero — sono i deliverable della Fase 0.

---

## 4. Roadmap

### Fase 0 — Fondamenta Supabase (settimana 1-2)

Nessuna feature utente. Serve la base su cui tutto il resto poggia.

**Deliverable**

- Progetto Supabase + `supabase/` in repo con CLI e migration versionate (`supabase/migrations/*.sql`)
- Schema tenancy:

```sql
create table public.tenants (
  id uuid primary key default gen_random_uuid(),
  slug text unique not null
    check (slug ~ '^[a-z0-9][a-z0-9-]{1,30}[a-z0-9]$'
           and slug not in ('app','api','www','admin','docs','mail','staging','cdn','static')),
  ragione_sociale text not null,
  piva text,
  custom_domain text unique,   -- riservato a un'eventuale estensione futura; non usato in produzione
  theme jsonb not null default '{}'::jsonb,    -- logo_url, primary, secondary, font
  contatti jsonb not null default '{}'::jsonb, -- whatsapp, email, telefono
  piano text not null default 'starter',
  ai_credits integer not null default 0,
  created_at timestamptz not null default now()
);

create type tenant_role as enum ('owner','admin','staff','operations','client');

create table public.tenant_members (
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  user_id   uuid not null references auth.users(id) on delete cascade,
  role      tenant_role not null default 'staff',
  created_at timestamptz not null default now(),
  primary key (tenant_id, user_id)
);
```

- Helper + policy standard, applicata identica a **ogni** tabella di dominio:

```sql
create or replace function public.is_member(t uuid)
returns boolean language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from public.tenant_members
    where tenant_id = t and user_id = auth.uid()
  );
$$;

-- template applicato a ogni tabella con tenant_id
alter table public.<tabella> enable row level security;
alter table public.<tabella> force row level security;

create policy tenant_read  on public.<tabella> for select using (public.is_member(tenant_id));
create policy tenant_write on public.<tabella> for all
  using (public.is_member(tenant_id)) with check (public.is_member(tenant_id));
```

- **Test di isolamento tenant** — il test più importante del progetto:
  `backend/tests/test_tenant_isolation.py` crea Tenant A e Tenant B, popola entrambi, e verifica che ogni singola tabella restituisca **0 righe** cross-tenant. Fallisce → build rossa. Si estende con una riga per ogni nuova tabella.
- Script CI che vieta `service_role` fuori da `backend/system_jobs/`
- Tabelle di dominio base — `clienti`, `leads`, `cantieri` — con backfill da Mongo. **Anticipate qui dalla Fase 2**: i `computi` di Fase 1 hanno FK verso `leads` e `cantieri`, e una FK verso una tabella inesistente non si scrive
- Supabase Storage: bucket `planimetrie`, `render`, `foto-cantiere`, `documenti` — tutti privati, accesso via URL firmati. Path obbligatorio `<tenant_id>/<risorsa>/<file>`: il primo segmento è ciò su cui discrimina la policy
- Type generation: `supabase gen types typescript` → `frontend/src/lib/database.types.ts`, script npm `db:types`

**Validazione**: `pytest backend/tests/test_tenant_isolation.py` verde, `supabase db reset` ricostruisce lo schema da zero.

---

### Fase 1 — Prezzario + Computo metrico + Ponte AI (settimana 3-7)

**La fase che rende il prodotto vendibile.** Nient'altro serve per la prima vendita.

#### 1a. Prezzario

```sql
create table public.prezzari (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  nome text not null,
  fonte text not null default 'campania'
    check (fonte in ('campania','custom','importato')),
  anno integer,
  is_default boolean not null default false,
  is_sistema boolean not null default false,  -- true = base Campania, non editabile: si duplica
  created_at timestamptz not null default now()
);
-- un solo prezzario di default per tenant
create unique index on public.prezzari (tenant_id) where is_default;

create table public.prezzario_voci (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  prezzario_id uuid not null references public.prezzari(id) on delete cascade,
  codice text,
  super_categoria text not null,
  categoria text not null,
  sub_categoria text,
  descrizione text not null,
  um text not null,                  -- mq, ml, cad, corpo, kg, h
  prezzo_unitario numeric(12,2) not null check (prezzo_unitario >= 0),
  tipo text not null default 'a_misura' check (tipo in ('a_misura','a_corpo')),
  attiva boolean not null default true
);
create index on public.prezzario_voci (tenant_id, prezzario_id, categoria);
```

**Modello a due livelli — base Campania + personalizzazione**

| Livello | Chi lo possiede | Comportamento |
|---|---|---|
| **Prezzario Campania** (`is_sistema = true`) | Seed condiviso, uguale per tutti i tenant | Sola lettura. Aggiornato una volta l'anno da noi, l'aggiornamento non tocca i computi esistenti (snapshot) |
| **Prezzario dell'impresa** (`fonte = 'custom'`) | Il tenant | Nasce come duplicato del Campania, poi l'impresa lo modifica liberamente. Diventa il `is_default` |
| **Prezzario importato** (`fonte = 'importato'`) | Il tenant | Da CSV/Excel proprio. Percorso avanzato |

Un tenant può avere **N prezzari** (es. "Ristrutturazioni 2026", "Nuove costruzioni", "Cliente XY convenzionato"), uno solo marcato default. Il computo registra da quale è nato.

**Wizard di calibrazione** — la parte che decide l'adozione. Non "importa CSV": le imprese non hanno un CSV.

1. Al signup il tenant riceve il **Prezzario Regione Campania** precaricato (~400 voci), già duplicato in una copia sua modificabile
2. Il wizard mostra **solo le 28 voci chiave** che coprono ~85% del valore di una ristrutturazione (demolizioni, tramezzi, intonaci, massetti, pavimenti, rivestimenti, impianto elettrico a punto, idraulico a punto, infissi, serramenti, tinteggiatura, smaltimenti)
3. L'impresa conferma o corregge in ~30 minuti. Le restanti voci della stessa categoria scalano proporzionalmente al delta applicato
4. Import CSV/Excel disponibile come opzione avanzata, non come percorso principale
5. In qualsiasi momento: "Ripristina prezzo Campania" su singola voce o categoria

Seed iniziale dal Prezzario Regione Campania, incrociato con i dati reali già in `backend/predictive_data.py` (86 voci + 18 coefficienti) e con la calibrazione prezzi GB (54 preventivi storici) per validare che le 28 voci chiave siano coerenti col mercato locale.

#### 1b. Computo metrico

```sql
create table public.computi (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  lead_id uuid references public.leads(id) on delete set null,
  cantiere_id uuid references public.cantieri(id) on delete set null,
  parent_computo_id uuid references public.computi(id) on delete set null,
  prezzario_id uuid references public.prezzari(id) on delete set null,  -- tracciabilità listino di origine
  tipo text not null default 'estimativo'
    check (tipo in ('estimativo','esecutivo','variante')),
  stato text not null default 'bozza'
    check (stato in ('bozza','ai_da_revisionare','confermato','archiviato')),
  numero text,
  note text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.computo_voci (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  computo_id uuid not null references public.computi(id) on delete cascade,
  origine_voce_id uuid references public.prezzario_voci(id) on delete set null,
  ordine integer not null default 0,
  -- SNAPSHOT: copiati alla creazione, mai letti dal prezzario a runtime
  super_categoria text not null,
  categoria text not null,
  sub_categoria text,
  descrizione text not null,
  um text not null,
  tipo text not null default 'a_misura',
  qta numeric(12,3) not null default 0,
  prezzo_unitario numeric(12,2) not null default 0,
  totale numeric(14,2) generated always as (round(qta * prezzo_unitario, 2)) stored,
  generata_da_ai boolean not null default false,
  validata_umano boolean not null default false
);
create index on public.computo_voci (tenant_id, computo_id, ordine);

create view public.computi_totali as
  select c.id as computo_id, c.tenant_id,
         coalesce(sum(v.totale), 0) as totale
  from public.computi c
  left join public.computo_voci v on v.computo_id = c.id
  group by c.id, c.tenant_id;
```

> **Snapshot obbligatorio**: descrizione, UM e prezzo sono **copiati** nella voce di computo, non referenziati. Aggiornare il prezzario non deve mai alterare un preventivo già inviato al cliente. `origine_voce_id` resta solo per tracciabilità e per il ricalcolo esplicito su richiesta.

#### 1c. Ponte AI planimetria → bozza computo — **la killer feature**

Principio di design non negoziabile: **l'AI estrae quantità, non prezzi.** L'LLM non deve mai produrre un importo. I prezzi arrivano sempre dal prezzario del tenant, la moltiplicazione è deterministica.

```
Planimetria caricata
      │
      ▼
ai_architect_service.py  ──► METRICHE STRUTTURATE
      │                      { mq_calpestabile, mq_pavimento, ml_tramezzi_demolire,
      │                        mq_intonaco, n_bagni, n_camere, n_punti_luce_stimati,
      │                        n_punti_acqua, ml_battiscopa, mq_rivestimento }
      ▼
mapping_engine.py (nuovo, deterministico)
      │  per ogni regola del tenant: qta = metrica × moltiplicatore
      │  prezzo = prezzario_voci.prezzo_unitario
      ▼
computo (tipo='estimativo', stato='ai_da_revisionare')
      │  ogni voce: generata_da_ai=true, validata_umano=false
      ▼
Dashboard impresa → revisione → conferma → Preventivo PDF
```

```sql
create table public.mapping_regole (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  metrica text not null,          -- chiave dell'output AI
  prezzario_voce_id uuid not null references public.prezzario_voci(id) on delete cascade,
  moltiplicatore numeric(10,4) not null default 1,
  condizione jsonb,               -- es. {"livello": ["premium","luxury"]}
  attiva boolean not null default true
);
```

Set di regole di default fornito al signup, modificabile dall'impresa. Ogni voce AI resta `validata_umano=false` finché un umano non la conferma — coerente col messaging di validazione umana già introdotto nel branch corrente (commit `98b6b65`).

#### 1d. Preventivo

Conversione computo → preventivo con snapshot completo, numerazione per tenant, PDF via `reportlab` (già in requirements), stati `bozza|inviato|accettato|rifiutato|scaduto`.

**Validazione Fase 1**
```bash
pytest backend/tests/test_tenant_isolation.py backend/tests/test_prezzario.py \
       backend/tests/test_computo.py backend/tests/test_ai_mapping.py
```
Criterio di accettazione funzionale: da planimetria PDF reale GB → bozza computo con scostamento < 15% rispetto al preventivo storico effettivamente emesso, su almeno 8 dei 10 casi del set ground-truth già presente in `scripts/ai_architect_ground_truth/`.

---

### Fase 2 — Tenant hardening + migrazione Mongo (settimana 8-11)

Si fa **quando arriva il cliente #2**, non prima. GB Construction è il design partner della Fase 1.

- Migrazione delle collection residue Mongo → Postgres (AI architect, credit ledger, cache, webhook events, sopralluoghi). `clienti`/`leads`/`cantieri` sono già migrate in Fase 0
- `TenantContext.jsx` — creato già in Fase 1 (serve alla dashboard), mantiene il tenant GB predefinito sui domini di produzione
- Endpoint pubblico `GET /api/tenant/config` — **espone solo campi brand**. Mai P.IVA, mai crediti, mai piano. Whitelist esplicita, non blacklist
- **Domini di produzione invariati**: `gbconstruction.it` per il frontend e `api.gbconstruction.it` per il backend. Nessun sottodominio tenant, wildcard DNS o dominio alternativo da configurare
- Riservare gli slug di sistema: `app`, `api`, `www`, `admin`, `docs`, `mail`, `staging` — constraint sulla tabella `tenants`
- Rate limiting per tenant sull'upload pubblico AI (estende `backend/tests/test_ai_architect_rate_limit.py`)
- CORS: consentire esplicitamente solo gli origin GB Construction previsti, oltre agli origin locali di sviluppo
- Dismissione Mongo, rimozione `motor`/`pymongo` da requirements
- Rimozione del path JWT legacy in `backend/auth.py`

**Validazione**: flusso end-to-end GB sul dominio corrente, con isolamento dati tenant e senza modifiche DNS.

---

### Fase 3 — Cantiere + Libretto di misura PWA + SAL (settimana 12-16)

L'ordine conta: **il libretto alimenta il SAL**, quindi il mobile viene prima del SAL.

```sql
create table public.libretto_misure (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  cantiere_id uuid not null references public.cantieri(id) on delete cascade,
  computo_voce_id uuid references public.computo_voci(id) on delete set null,
  data_misura date not null,
  rilevata_da uuid references auth.users(id),
  descrizione text,
  parti integer default 1, lunghezza numeric(10,3), larghezza numeric(10,3), altezza numeric(10,3),
  qta numeric(12,3) not null,
  foto_paths text[] default '{}',
  client_uuid text unique,          -- idempotenza sync offline
  created_at timestamptz not null default now()
);
```

**PWA `/campo`** — superficie minima, solo ciò che serve in cantiere:
- Service worker (CRA 5 include workbox) + IndexedDB via `idb-keyval`
- Coda di sync: misure e foto accodate offline, inviate al rientro in rete
- **Design anti-conflitto: le misure sono append-only.** Mai update, mai delete da mobile. Correzione = nuova riga di segno opposto. Elimina l'intera classe di conflitti di sincronizzazione
- `client_uuid` garantisce idempotenza su retry
- Foto: upload resumable su Supabase Storage, compresse client-side prima dell'accodamento

**SAL** derivato, non inserito a mano:

```sql
create table public.sal (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  cantiere_id uuid not null references public.cantieri(id) on delete cascade,
  numero integer not null,
  periodo_da date not null, periodo_a date not null,
  stato text not null default 'bozza' check (stato in ('bozza','emesso','approvato')),
  unique (cantiere_id, numero)
);

create table public.sal_righe (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  sal_id uuid not null references public.sal(id) on delete cascade,
  computo_voce_id uuid not null references public.computo_voci(id),
  qta_periodo numeric(12,3) not null,
  qta_progressiva numeric(12,3) not null,
  prezzo_unitario numeric(12,2) not null,
  importo_periodo numeric(14,2) generated always as (round(qta_periodo * prezzo_unitario, 2)) stored
);
```

Regola di dominio: se `qta_progressiva > qta` contrattuale della voce → il SAL **non si blocca**, segnala eccedenza e propone l'apertura di una variante. Blocco duro = utenti che aggirano il sistema.

Export PDF SAL + libretto con `reportlab`.

---

### Fase 4 — Varianti + quadro di confronto (settimana 17-18)

Riusa le strutture esistenti: variante = `computi` con `tipo='variante'` e `parent_computo_id` valorizzato. Nessuna tabella nuova.

Quadro di confronto = view con full outer join tra voci del computo base e della variante, che classifica ogni riga in `invariata | modificata | nuova | soppressa` con delta importo e delta percentuale sul totale contrattuale.

---

### Fase 5 — Economics cantiere (settimana 19-21)

**Nessuna fatturazione elettronica.** Tabelle `fornitori`, `spese` (allegato su Storage), `incassi`, `scadenze`.

View `marginalita_cantiere`: ricavi maturati da SAL − spese registrate, con margine assoluto e percentuale, per cantiere e aggregato.

Export contabile: CSV standard + integrazione opzionale via API con Fatture in Cloud. L'impresa emette la fattura sul suo gestionale fiscale, EdilOS conosce l'importo e lo stato incasso.

---

### Fase 6 — Portale cliente finale (settimana 22-24)

Utente Supabase Auth con `tenant_members.role = 'client'`, più tabella ponte `cantiere_clienti (cantiere_id, user_id)`. Policy RLS dedicata: legge **solo** il proprio cantiere, e solo le viste pubbliche (avanzamento %, foto, documenti condivisi, SAL approvati).

Unica azione in scrittura consentita: approvazione varianti (`varianti_approvazioni`, append-only con timestamp e IP). Nessuna app nativa, web responsive.

---

## 5. Metodo di lavoro vibe-coding

Ciclo fisso per ogni feature, in quest'ordine:

1. **Migration SQL** in `supabase/migrations/` — include sempre `enable row level security` + `force row level security` + policy. Una tabella senza policy non esiste
2. **Riga nel test di isolamento** — prima del codice applicativo
3. **`npm run db:types`** — types TypeScript rigenerati
4. **Backend** se serve logica di dominio, altrimenti si va diretti da `supabase-js`
5. **UI** in `frontend/src/dashboard/pages/`, un file per pagina, componenti shadcn esistenti
6. **Smoke test HTTP** nello stile di `backend/tests/conftest.py`

Regole permanenti:
- `supabase db reset` deve ricostruire tutto da zero in ogni momento. Se si rompe, si ripara subito
- Ogni feature che richiede configurazione manuale per singolo cliente è **rifiutata**. È il filtro che decide se il prodotto scala a 50 tenant
- Seed di un tenant demo completo sempre allineato: è insieme ambiente di sviluppo e demo commerciale

---

## 6. File impattati (Fase 0 + 1)

| File | Azione | Motivo |
|---|---|---|
| `supabase/config.toml`, `supabase/migrations/*.sql` | CREATE | Schema versionato, base di tutto |
| `supabase/seed.sql` | CREATE | Tenant demo + prezzario base + regole mapping default |
| `backend/db.py` | CREATE | Client Postgres asyncpg con `SET LOCAL request.jwt.claims` |
| `backend/auth.py` | UPDATE | Verifica JWT Supabase via JWKS; path legacy in dual-mode fino a Fase 2 |
| `backend/tenancy.py` | CREATE | Estrazione tenant dal token, dependency `current_tenant` |
| `backend/prezzario_service.py` | CREATE | CRUD prezzario, wizard calibrazione, import CSV |
| `backend/boq_service.py` | CREATE | Computi, voci, conversione a preventivo |
| `backend/mapping_engine.py` | CREATE | Metriche AI → voci di computo, deterministico |
| `backend/ai_architect_service.py` | UPDATE | Output metriche strutturate consumabili dal mapping engine |
| `backend/server.py` | UPDATE | Router nuovi, rimozione accesso Mongo diretto |
| `backend/system_jobs/` | CREATE | Unico luogo autorizzato all'uso di `service_role` |
| `backend/tests/test_tenant_isolation.py` | CREATE | Gate di sicurezza, cresce a ogni tabella |
| `frontend/src/lib/supabase.js` | CREATE | Client browser con sessione Auth |
| `frontend/src/lib/storage.js` | CREATE | Upload/lista e URL firmati per bucket privati tenant-scoped |
| `frontend/src/lib/database.types.ts` | CREATE | Generato, non editato a mano |
| `frontend/src/context/TenantContext.jsx` | CREATE | Risoluzione tenant + theming |
| `frontend/src/dashboard/pages/Prezzario.jsx` | CREATE | Gestione listino + wizard |
| `frontend/src/dashboard/pages/Computi.jsx` | CREATE | Editor computo metrico |
| `frontend/src/dashboard/CantiereDocuments.jsx` | CREATE | Archivio documenti privato per cantiere |
| `frontend/src/dashboard/pages/AIArchitectReview.jsx` | UPDATE | Aggiunge revisione bozza computo generata |

---

## 7. Rischi

| Rischio | Prob. | Impatto | Mitigazione |
|---|---|---|---|
| **Leak dati cross-tenant** | Media | **Critico** — imprese concorrenti | RLS + `force row level security` + test isolamento in CI + divieto `service_role` fuori da `system_jobs/` |
| Migrazione Mongo→Postgres con perdita dati | Media | Alto | Script idempotente, verifica conteggi per collection, Mongo in sola lettura per 30gg dopo il cutover |
| Prezzario non calibrato → computi AI sbagliati | **Alta** | **Alto** — perdita di fiducia irreversibile | Wizard 28 voci obbligatorio al signup, computo AI bloccato finché non completato |
| Refactor auth rompe la produzione GB | Media | Alto | Dual-mode: entrambi i token accettati per tutta la Fase 2 |
| Capocantiere non usa la PWA → SAL vuoto | **Alta** | Alto | Superficie minima (3 schermate), append-only, funzionamento offline testato in campo reale |
| Scope creep verso la fatturazione SDI | Alta | Alto | Decisione documentata. Se un cliente la chiede: integrazione FIC, non implementazione |
| CRA in maintenance mode | Bassa | Medio | Non bloccante ora. Eventuale migrazione a Vite fuori scope, valutare dopo Fase 2 |
| `ai_architect_service.py` a 6469 righe | Media | Medio | Estrarre il layer metriche durante la Fase 1, non riscrivere tutto |

---

## 8. Stima

| Fase | Durata | Vendibile a fine fase |
|---|---|---|
| 0 — Fondamenta Supabase | 2 sett. | No |
| 1 — Prezzario + Computi + Ponte AI | 5 sett. | **Sì** |
| 2 — Hardening multi-tenant + migrazione | 4 sett. | Sì, a più clienti |
| 3 — Cantiere + PWA + SAL | 5 sett. | Sì, upsell |
| 4 — Varianti | 2 sett. | Sì, upsell |
| 5 — Economics | 3 sett. | Sì, upsell |
| 6 — Portale cliente | 3 sett. | Retention |

**Totale ~24 settimane (~5 mesi)**, con un prodotto vendibile già alla settimana 7.

---

## 9. Accettazione

- [x] `supabase db reset` ricostruisce l'intero schema da zero (verificato in locale il 2026-08-03)
- [x] Test di isolamento tenant verde, con dati A/B su ogni tabella di dominio e sulla view aggregata
- [x] Nessun `service_role` fuori da `backend/system_jobs/` (verificato in CI)
- [ ] Bozza computo da planimetria entro 15% dal preventivo storico su 8/10 casi ground-truth
- [ ] Flusso GB end-to-end su `gbconstruction.it` e `api.gbconstruction.it`, senza dipendenze da domini tenant o wildcard DNS
- [x] Slug di sistema (`app`, `api`, `www`, …) rifiutati dal constraint
- [x] Prezzario Campania duplicabile: copia modificabile/default, base di sistema protetta e prezzi custom usati dal mapping AI
- [ ] Zero riferimenti a Mongo nel codice a fine Fase 2
- [x] Endpoint `/api/tenant/config` espone solo campi brand; privilegi anon sensibili negati da test locale

---

**PROSSIMO GATE** — completamento e verifica su `develop`, smoke pre-merge e
acquisizione dei 10 casi ground-truth reali. I domini di produzione restano invariati.
