# Piano di implementazione per Codex — EdilOS AI, Fase 0 + Fase 1

> **Ruolo:** Codex esegue. Claude (Opus) rivede ogni PR.
> **Obiettivo:** portare il repo da single-tenant Mongo a SaaS multi-tenant su Supabase, fino al prodotto vendibile (planimetria → preventivo PDF).
> **Branch:** `feat/edilos-supabase-foundation`. Un commit per task. Test verdi prima di passare al task successivo.
> **Piano strategico di riferimento:** `IMPLEMENTATION_PLAN_EdilOS_Supabase.md` — leggilo per il "perché". Questo file è il "come".
> **Scope:** Fase 0 (fondamenta) + Fase 1 (prezzario, computi, ponte AI). Fasi 3-6 fuori scope, non anticiparle.

> **Stato verificato al 2026-08-03:** implementazione Fase 0+1 circa al 75%.
> Reset locale, seed, RLS A/B, prezzario custom→mapping AI, validazione
> computo→preventivo e build frontend sono verdi. Restano aperti: deploy della
> migration di hardening, run CI remoto, backfill con conteggi di produzione,
> PDF brandizzato E2E, Supabase Auth/Storage completi e ground truth su 10 PDF reali.

---

## Come usare questo documento

Esegui i task **in ordine numerico**. Ogni task termina quando il suo comando di validazione passa.

Non chiedere conferme intermedie: le decisioni sono prese e documentate qui. Se una decisione manca, applica la regola più conservativa fra quelle della sezione "Regole non negoziabili" e annotala in `DECISIONI_APERTE.md`.

Prima di ogni task leggi i file che stai per modificare. Non riscrivere file esistenti da zero: usa edit mirati.

---

## Contesto per Codex (leggi prima di toccare il codice)

Non assumere nulla oltre a questo elenco. È stato verificato sul repo.

| Aspetto | Realtà |
|---|---|
| Backend | FastAPI 0.110 + `motor` (Mongo). Entry: `backend/server.py` (2025 righe) |
| Auth attuale | JWT proprietario firmato con `JWT_SECRET`, cookie httpOnly — `backend/auth.py:28` |
| Ruoli attuali | `admin`, `staff`, `operations` (seed `backend/auth.py:83`) |
| Frontend | **CRA + craco** (`react-scripts` 5.0.1, script `craco start/build/test`). **NON Vite, NON Next.js** |
| React | 19.0.0, `react-router-dom` 7.5.1 |
| UI kit | Radix + Tailwind (shadcn) in `frontend/src/components/ui/` |
| Data fetching | TanStack Query 5.56 **e** SWR 2.3 coesistono. Standardizzare su TanStack Query |
| Env prefix frontend | `REACT_APP_*` (CRA). Un env senza questo prefisso non arriva al browser |
| PDF | `reportlab` + `PyMuPDF` già in `backend/requirements.txt`. Non aggiungere altre librerie PDF |
| Collection Mongo | `leads`, `users`, `cantieri`, `sopralluogo_slots`, `ai_architect_*` (5), `ai_credit_*` (2), `ai_usage_events`, `meta_webhook_events` |
| Test backend | Integration HTTP contro API live (`backend/tests/conftest.py:26`), `requests.Session` autenticata. **Non** unit test con DB in-memory |
| CI | **Non esiste.** `.github/workflows/` assente — va creata (TASK 0.7) |
| Deploy | Backend su Railway (`Dockerfile`), frontend su Vercel (`.vercel/`) |
| Tenancy | **Zero.** Nessun `tenant_id`, nessun repository layer, nessuna migration versionata |

Helper esistenti in `backend/server.py` da riusare o sostituire consapevolmente:
`serialize()` (:77, specifico per `_id` Mongo — **rimuovere** su Postgres, non adattare), `now_iso()` (:87), `object_id_or_400()` (:102), `current_user()` (:108), `require_admin()` (:112).

**Attenzione**: sul branch corrente `feat/ai-architect-launch-hardening` è in corso l'hardening AI Architect descritto in `PIANO_CODEX_AI_ARCHITECT_LANCIO.md`. Non reintrodurre né rimuovere quei guardrail. Sono ortogonali a questo lavoro.

---

## Deviazione approvata dal piano strategico

Il piano colloca la migrazione di `leads`/`cantieri` in Fase 2. **Anticipata a Fase 0**: i `computi` di Fase 1 hanno chiavi esterne verso quelle tabelle, e una FK verso una tabella che non esiste non si scrive.

Fase 2 resta responsabile di: collection AI, credit ledger, cache, webhook events, rimozione di `motor`/`pymongo`, rimozione del path JWT legacy.

---

## Regole non negoziabili

Vincono su qualsiasi altra considerazione, inclusa la velocità.

1. **Nessuna tabella senza RLS.** Ogni `create table` con `tenant_id` è seguito nella stessa migration da `enable row level security`, `force row level security` e le due policy. Una tabella senza policy è un bug bloccante.
2. **`service_role` solo in `backend/system_jobs/`.** Qualsiasi altro uso è vietato. Verificato da CI.
3. **Snapshot dei prezzi.** `computo_voci` copia descrizione, UM e prezzo. Non legge mai il prezzario a runtime. Modificare un listino non deve alterare un preventivo già emesso.
4. **L'AI non produce prezzi.** `ai_architect_service` restituisce solo quantità e metriche. Gli importi nascono dal prezzario, moltiplicati da codice deterministico.
5. **Ogni voce generata da AI nasce `validata_umano = false`.** Nessun percorso automatico la porta a `true`: serve un'azione esplicita di un utente.
6. **Migration solo in avanti.** Mai editare una migration già applicata: crearne una nuova.
7. **`supabase db reset` deve funzionare sempre.** Se si rompe, si ripara prima di procedere.
8. **Errori in italiano rivolti all'utente**, nel formato già in uso: `HTTPException(status_code=..., detail="Cantiere non trovato")`.
9. **Nessuna feature che richieda configurazione manuale per singolo cliente.** Se una soluzione la richiede, è la soluzione sbagliata.
10. **Import CSV non è il percorso principale del prezzario.** Il wizard lo è.

---

## Variabili d'ambiente

Aggiungi a `.env.example` (root) e `frontend/.env.example`. Mai committare valori reali.

```bash
# --- Backend (.env root) ---
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...        # SOLO backend/system_jobs/
SUPABASE_DB_URL=postgresql://postgres:...@db.xxxxx.supabase.co:5432/postgres
SUPABASE_JWKS_URL=https://xxxxx.supabase.co/auth/v1/.well-known/jwks.json
APP_BASE_DOMAIN=alantis.it

# --- Frontend (frontend/.env.example) — prefisso REACT_APP_ obbligatorio ---
REACT_APP_SUPABASE_URL=https://xxxxx.supabase.co
REACT_APP_SUPABASE_ANON_KEY=eyJ...
REACT_APP_BASE_DOMAIN=alantis.it
```

Nuove dipendenze — **solo queste**:
- backend: `asyncpg`, `supabase`, `pyjwt[crypto]` (l'extra serve per RS256/JWKS)
- frontend: `@supabase/supabase-js`

---

# FASE 0 — Fondamenta

## TASK 0.1 — Scaffolding Supabase

**Crea**
```
supabase/config.toml
supabase/migrations/
supabase/seed.sql
```

**Azioni**
- `supabase init` nella root del repo
- `.gitignore`: aggiungi `supabase/.branches`, `supabase/.temp`
- Script npm in `frontend/package.json`:
  ```json
  "db:types": "supabase gen types typescript --local > src/lib/database.types.ts"
  ```

**Validazione**: `supabase start` avvia lo stack locale; `supabase status` elenca i servizi.

---

## TASK 0.2 — Migration `0001_tenancy.sql`

**File**: `supabase/migrations/0001_tenancy.sql`

```sql
-- ============================================================
-- 0001 — Tenancy: tenants, membri, helper RLS, JWT hook
-- ============================================================

create extension if not exists pgcrypto;

create table public.tenants (
  id uuid primary key default gen_random_uuid(),
  slug text unique not null
    check (
      slug ~ '^[a-z0-9][a-z0-9-]{1,30}[a-z0-9]$'
      and slug not in ('app','api','www','admin','docs','mail','staging','cdn','static','assets','auth')
    ),
  ragione_sociale text not null,
  piva text,
  custom_domain text unique,
  theme jsonb not null default '{}'::jsonb,
  contatti jsonb not null default '{}'::jsonb,
  piano text not null default 'starter' check (piano in ('starter','pro','enterprise')),
  ai_credits integer not null default 0 check (ai_credits >= 0),
  attivo boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on column public.tenants.slug is
  'Il subdominio è <slug>.alantis.it — derivato, non memorizzato separatamente.';

create type public.tenant_role as enum ('owner','admin','staff','operations','client');

create table public.tenant_members (
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  user_id   uuid not null references auth.users(id) on delete cascade,
  role      public.tenant_role not null default 'staff',
  nome      text,
  photo_url text,
  created_at timestamptz not null default now(),
  primary key (tenant_id, user_id)
);
create index on public.tenant_members (user_id);

-- ---------- Helper RLS ----------
create or replace function public.is_member(t uuid)
returns boolean
language sql stable security definer set search_path = public, pg_temp as $$
  select exists (
    select 1 from public.tenant_members
    where tenant_id = t and user_id = auth.uid()
  );
$$;

create or replace function public.has_role(t uuid, roles public.tenant_role[])
returns boolean
language sql stable security definer set search_path = public, pg_temp as $$
  select exists (
    select 1 from public.tenant_members
    where tenant_id = t and user_id = auth.uid() and role = any(roles)
  );
$$;

-- ---------- RLS su tenants / tenant_members ----------
alter table public.tenants enable row level security;
alter table public.tenants force row level security;

create policy tenants_read on public.tenants
  for select using (public.is_member(id));
create policy tenants_update on public.tenants
  for update using (public.has_role(id, array['owner','admin']::public.tenant_role[]))
  with check   (public.has_role(id, array['owner','admin']::public.tenant_role[]));

alter table public.tenant_members enable row level security;
alter table public.tenant_members force row level security;

create policy members_read on public.tenant_members
  for select using (public.is_member(tenant_id));
create policy members_write on public.tenant_members
  for all using (public.has_role(tenant_id, array['owner','admin']::public.tenant_role[]))
  with check   (public.has_role(tenant_id, array['owner','admin']::public.tenant_role[]));

-- ---------- Custom Access Token Hook ----------
create or replace function public.custom_access_token_hook(event jsonb)
returns jsonb
language plpgsql stable security definer set search_path = public, pg_temp as $$
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

grant execute on function public.custom_access_token_hook(jsonb) to supabase_auth_admin;
revoke execute on function public.custom_access_token_hook(jsonb) from authenticated, anon, public;

-- ---------- trigger updated_at riusabile ----------
create or replace function public.touch_updated_at()
returns trigger language plpgsql as $$
begin new.updated_at := now(); return new; end; $$;

create trigger tenants_touch before update on public.tenants
  for each row execute function public.touch_updated_at();
```

**Poi** abilita l'hook in `supabase/config.toml`:
```toml
[auth.hook.custom_access_token]
enabled = true
uri = "pg-functions://postgres/public/custom_access_token_hook"
```

**Validazione**: `supabase db reset` completa senza errori.

---

## TASK 0.3 — Migration `0002_domain_core.sql`

Porta in Postgres i dati Mongo che servono come base per la Fase 1. Campi derivati dai modelli Pydantic in `backend/server.py:132-165` (`LeadConfig`, `LeadCreate`) e dagli endpoint cantieri (`backend/server.py:1737-1820`).

**File**: `supabase/migrations/0002_domain_core.sql`

```sql
-- ============================================================
-- 0002 — Clienti, lead, cantieri (migrati da MongoDB)
-- ============================================================

create table public.clienti (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  tipo text not null default 'privato' check (tipo in ('privato','azienda')),
  nome text not null,
  email text,
  telefono text,
  citta text,
  indirizzo text,
  piva text,
  cf text,
  note text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index on public.clienti (tenant_id, nome);

create table public.leads (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  cliente_id uuid references public.clienti(id) on delete set null,
  nome text not null,
  email text not null,
  telefono text not null,
  citta text,
  indirizzo text,
  privacy boolean not null default true,
  newsletter boolean not null default false,
  status text not null default 'nuovo' check (status in (
    'nuovo','qualificato','sopralluogo_fissato','sopralluogo_fatto',
    'preventivo_preparazione','preventivo_inviato','follow_up',
    'in_trattativa','chiuso_vinto','chiuso_perso'
  )),
  owner text,
  tags text[] not null default '{}',
  score integer check (score between 0 and 100),
  config jsonb not null default '{}'::jsonb,   -- LeadConfig serializzato
  stima jsonb,                                  -- output predictive_engine
  tracking jsonb not null default '{}'::jsonb,
  timeline jsonb not null default '[]'::jsonb,
  note_cliente text,
  prossima_azione text,
  ai_architect_job_id text,
  legacy_mongo_id text unique,                  -- idempotenza backfill
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index on public.leads (tenant_id, status, created_at desc);
create index on public.leads (tenant_id, email);

create table public.cantieri (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  lead_id uuid references public.leads(id) on delete set null,
  cliente_id uuid references public.clienti(id) on delete set null,
  cliente text not null,
  indirizzo text,
  stato text not null default 'attivo' check (stato in ('attivo','in_pausa','completato')),
  avanzamento integer not null default 0 check (avanzamento between 0 and 100),
  importo numeric(14,2),
  capocantiere text,
  milestone text,
  milestone_data date,
  criticita text,
  fasi jsonb not null default '[]'::jsonb,
  note text,
  legacy_mongo_id text unique,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index on public.cantieri (tenant_id, stato, milestone_data);

-- stesso vincolo oggi applicativo in server.py:1755, ora nel database
create unique index cantieri_un_attivo_per_lead
  on public.cantieri (lead_id) where stato <> 'completato' and lead_id is not null;

-- ---------- RLS ----------
do $$
declare t text;
begin
  foreach t in array array['clienti','leads','cantieri'] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('alter table public.%I force row level security', t);
    execute format(
      'create policy tenant_read on public.%I for select using (public.is_member(tenant_id))', t);
    execute format(
      'create policy tenant_write on public.%I for all
         using (public.is_member(tenant_id)) with check (public.is_member(tenant_id))', t);
    execute format(
      'create trigger %I_touch before update on public.%I
         for each row execute function public.touch_updated_at()', t, t);
  end loop;
end $$;
```

**Validazione**: `supabase db reset` verde.

---

## TASK 0.4 — Storage

**File**: `supabase/migrations/0003_storage.sql`

Bucket **tutti privati**, accesso via URL firmati. Convenzione di path obbligatoria: `<tenant_id>/<risorsa>/<file>` — il primo segmento è il tenant, ed è ciò su cui la policy discrimina.

```sql
insert into storage.buckets (id, name, public)
values ('planimetrie','planimetrie',false),
       ('render','render',false),
       ('foto-cantiere','foto-cantiere',false),
       ('documenti','documenti',false)
on conflict (id) do nothing;

create policy storage_tenant_read on storage.objects for select
  using (
    bucket_id in ('planimetrie','render','foto-cantiere','documenti')
    and public.is_member(((storage.foldername(name))[1])::uuid)
  );

create policy storage_tenant_write on storage.objects for insert
  with check (
    bucket_id in ('planimetrie','render','foto-cantiere','documenti')
    and public.is_member(((storage.foldername(name))[1])::uuid)
  );

create policy storage_tenant_delete on storage.objects for delete
  using (
    bucket_id in ('planimetrie','render','foto-cantiere','documenti')
    and public.has_role(((storage.foldername(name))[1])::uuid,
                        array['owner','admin']::public.tenant_role[])
  );
```

**Validazione**: upload di prova su `<tenant_A>/test.pdf` riesce con la sessione di A, fallisce con quella di B.

---

## TASK 0.5 — Layer database backend

### `backend/db.py` (nuovo)

```python
"""Accesso Postgres/Supabase con RLS attiva anche lato server."""

async def init_pool() -> None: ...
async def close_pool() -> None: ...

@asynccontextmanager
async def tenant_conn(access_token: str):
    """Connessione con i claim dell'utente impostati:
         SET LOCAL role = 'authenticated';
         SET LOCAL request.jwt.claims = <claims json>;
       ⇒ RLS filtra esattamente come per il client browser.
       Usare per QUALSIASI operazione originata da una richiesta utente."""

@asynccontextmanager
async def system_conn():
    """Connessione senza contesto utente, RLS bypassata.
       Import consentito SOLO da backend/system_jobs/.
       Ispeziona lo stack del chiamante e alza RuntimeError altrove."""
```

Il controllo runtime in `system_conn` è la prima difesa; la CI del TASK 0.7 è la seconda.

### `backend/tenancy.py` (nuovo)

```python
async def current_tenant(request: Request) -> dict:
    """Risolve il tenant da header X-Tenant-Slug oppure da hostname
       <slug>.alantis.it. Verifica che l'utente sia membro, 403 altrimenti."""

async def require_tenant_role(request: Request, roles: list[str]) -> dict:
    """Come sopra + controllo ruolo. 403 con detail italiano."""
```

### `backend/auth.py` (modifica) — dual-mode

```python
async def get_current_user(request, db) -> dict:
    token = _extract_token(request)          # cookie o Bearer, invariato
    if _looks_like_supabase_jwt(token):      # alg RS256 + iss Supabase
        return await _verify_supabase(token) # JWKS cachate, claim app_tenants
    return await _verify_legacy(token, db)   # percorso attuale, INVARIATO
```

Non toccare `_verify_legacy`: la produzione GB ci gira sopra.

**Validazione**: `pytest backend/tests/test_auth_dual_mode.py` — un token legacy e uno Supabase risolvono entrambi l'utente.

---

## TASK 0.6 — Test di isolamento tenant

**Il test più importante del progetto.** Crea `backend/tests/test_tenant_isolation.py`.

Struttura richiesta — estendibile aggiungendo **una sola riga** per ogni tabella futura:

```python
TABELLE_TENANT = [
    # (tabella, factory che crea una riga per il tenant dato)
    ("clienti",  make_cliente),
    ("leads",    make_lead),
    ("cantieri", make_cantiere),
    # Fase 1 aggiunge: prezzari, prezzario_voci, computi, computo_voci,
    #                  mapping_regole, preventivi
]

@pytest.mark.parametrize("tabella,factory", TABELLE_TENANT)
def test_nessuna_lettura_cross_tenant(tabella, factory, tenant_a, tenant_b):
    factory(tenant_a)
    righe = select_as(tenant_b, tabella)
    assert righe == [], f"LEAK: {tabella} visibile cross-tenant"

@pytest.mark.parametrize("tabella,factory", TABELLE_TENANT)
def test_nessuna_scrittura_cross_tenant(tabella, factory, tenant_a, tenant_b):
    with pytest.raises(PermissionError):
        insert_as(tenant_b, tabella, tenant_id=tenant_a)

def test_ogni_tabella_con_tenant_id_ha_rls():
    """Scopre le tabelle da pg_tables/pg_policies, non da una lista scritta a mano:
       se una tabella ha tenant_id ma non ha rowsecurity + almeno 2 policy,
       il test fallisce. Impedisce di dimenticare RLS su tabelle future."""
```

L'ultimo test è quello che rende il sistema a prova di dimenticanza.

**Fixture**: due tenant reali, due utenti Supabase Auth, sessioni separate. Stile HTTP coerente con `backend/tests/conftest.py:26`.

**Validazione**: `pytest backend/tests/test_tenant_isolation.py -v` tutto verde.

---

## TASK 0.7 — CI (non esiste, va creata)

**File**: `.github/workflows/ci.yml`

Job obbligatori:

1. **`rls-guard`** — fallisce se una migration contiene `create table` con `tenant_id` senza `enable row level security` nello stesso file
2. **`service-role-guard`**
   ```bash
   ! grep -rn "service_role\|SERVICE_ROLE_KEY" backend/ \
       --include="*.py" | grep -v "^backend/system_jobs/"
   ```
3. **`test`** — `supabase start`, `supabase db reset`, `pytest backend/tests/`
4. **`build`** — `cd frontend && npm ci && npm run build`

**Validazione**: push sul branch → i 4 job passano.

---

## TASK 0.8 — Client Supabase frontend

**`frontend/src/lib/supabase.js`** (nuovo)
```js
import { createClient } from '@supabase/supabase-js';

export const supabase = createClient(
  process.env.REACT_APP_SUPABASE_URL,
  process.env.REACT_APP_SUPABASE_ANON_KEY,
  { auth: { persistSession: true, autoRefreshToken: true } }
);
```

Genera `frontend/src/lib/database.types.ts` con `npm run db:types`. Non editarlo mai a mano.

**Rimuovi SWR** da `package.json` e converti gli usi a TanStack Query. Due librerie di data fetching nello stesso progetto sono debito, non flessibilità.

**Validazione**: `npm run build` passa; `grep -r "from 'swr'" frontend/src` vuoto.

---

## TASK 0.9 — Backfill da MongoDB

**`backend/system_jobs/backfill_mongo.py`** — unico posto dove `service_role` è lecito.

Requisiti:
- **Idempotente**: `legacy_mongo_id` con `on conflict do nothing`. Rieseguibile senza duplicare
- Ordine: `users` → `tenant_members`, poi `leads`, poi `cantieri` (rispetta le FK)
- Tutti i dati esistenti vanno al tenant `gbconstruction`
- Mappa i ruoli: `admin` → `owner`, `staff` → `staff`, `operations` → `operations`
- Utenti creati in Supabase Auth via Admin API. **Le password non sono migrabili** (hash bcrypt non importabile): genera un invito di reset per ciascuno e stampa la lista
- A fine run stampa una tabella di verifica conteggi Mongo vs Postgres. Se un conteggio diverge, esce con codice ≠ 0

**Validazione**: `python -m backend.system_jobs.backfill_mongo --dry-run`, poi run reale; conteggi allineati.

---

## TASK 0.10 — Seed

**File**: `supabase/seed.sql`

- Tenant `gbconstruction` — tema GB: Onyx / Construction Red / Gold, font Oswald + Montserrat (vedi `memory/PRD.md`)
- Tenant `demo` per sviluppo e demo commerciali
- Prezzario Campania di sistema (TASK 1.1)
- Regole di mapping di default (TASK 1.6)

**Validazione**: `supabase db reset` produce un ambiente navigabile con dati coerenti.

---

# FASE 1 — Prezzario, Computi, Ponte AI

## TASK 1.1 — Migration `0004_prezzario.sql`

```sql
create table public.prezzari (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  nome text not null,
  fonte text not null default 'campania' check (fonte in ('campania','custom','importato')),
  anno integer,
  is_default boolean not null default false,
  is_sistema boolean not null default false,   -- true = base Campania: sola lettura, si duplica
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create unique index prezzari_un_default_per_tenant
  on public.prezzari (tenant_id) where is_default;

create table public.prezzario_voci (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  prezzario_id uuid not null references public.prezzari(id) on delete cascade,
  codice text,
  super_categoria text not null,
  categoria text not null,
  sub_categoria text,
  descrizione text not null,
  um text not null check (um in ('mq','ml','mc','cad','corpo','kg','h','n')),
  prezzo_unitario numeric(12,2) not null check (prezzo_unitario >= 0),
  prezzo_riferimento numeric(12,2),            -- valore Campania originale, per "ripristina"
  tipo text not null default 'a_misura' check (tipo in ('a_misura','a_corpo')),
  chiave_wizard boolean not null default false, -- una delle 28 voci del wizard
  attiva boolean not null default true,
  created_at timestamptz not null default now()
);
create index on public.prezzario_voci (tenant_id, prezzario_id, categoria);
create index on public.prezzario_voci (tenant_id, prezzario_id) where chiave_wizard;

-- il prezzario di sistema non si modifica: si duplica
create or replace function public.blocca_prezzario_sistema()
returns trigger language plpgsql as $$
begin
  if exists (select 1 from public.prezzari p
             where p.id = coalesce(new.prezzario_id, old.prezzario_id) and p.is_sistema) then
    raise exception 'Il prezzario Campania è di sola lettura: duplicalo per modificarlo';
  end if;
  return coalesce(new, old);
end; $$;

create trigger prezzario_voci_no_sistema
  before insert or update or delete on public.prezzario_voci
  for each row execute function public.blocca_prezzario_sistema();
```

Più il blocco RLS standard (stesso pattern del TASK 0.3) e i trigger `touch_updated_at`.

**Dati**: popola il Prezzario Regione Campania in `supabase/seed.sql`. Marca `chiave_wizard = true` su queste 28 voci:

demolizione tramezzi · demolizione pavimenti · demolizione rivestimenti · smaltimento macerie · tramezzi in laterizio · tramezzi cartongesso · intonaco civile · rasatura · massetto · pavimento gres · pavimento parquet · battiscopa · rivestimento bagno · rivestimento cucina · controsoffitto · punto luce · punto presa · quadro elettrico · punto acqua · scarico · sanitari · caldaia · radiatori · split clima · infisso interno · infisso esterno · tinteggiatura · opere provvisionali

Incrocia con `backend/predictive_data.py` (86 voci + 18 coefficienti) per verificare che i prezzi Campania siano coerenti col mercato reale GB.

---

## TASK 1.2 — `backend/prezzario_service.py`

```python
async def lista_prezzari(tenant_id) -> list[dict]

async def duplica_prezzario(tenant_id, prezzario_id, nome) -> dict
    """Copia prezzario + tutte le voci. prezzo_riferimento = prezzo_unitario di
       origine. Il duplicato ha is_sistema=False, fonte='custom'."""

async def voci_wizard(tenant_id, prezzario_id) -> list[dict]
    """Le 28 voci chiave, ordinate per super_categoria."""

async def applica_wizard(tenant_id, prezzario_id, correzioni: dict[UUID, Decimal]) -> dict
    """Aggiorna le voci chiave. Per ogni categoria toccata calcola il delta %
       medio e lo applica proporzionalmente alle voci non-chiave della stessa
       categoria. Ritorna il riepilogo delle voci modificate."""

async def ripristina_campania(tenant_id, *, voce_ids=None, categoria=None) -> int
    """prezzo_unitario := prezzo_riferimento. Ritorna quante voci."""

async def importa_csv(tenant_id, prezzario_id, file) -> dict
    """Percorso avanzato. Valida con Pydantic riga per riga, riporta gli scarti
       con numero di riga. Non interrompe l'import al primo errore."""
```

Endpoint in `backend/server.py`, prefisso `/api/prezzario`, naming italiano coerente con l'esistente.

**Validazione**: `pytest backend/tests/test_prezzario.py` — copre duplicazione, wizard con propagazione, ripristino, e il rifiuto di scrittura sul prezzario di sistema.

---

## TASK 1.3 — Migration `0005_computi.sql`

Contenuto base già definito in `IMPLEMENTATION_PLAN_EdilOS_Supabase.md`, Fase 1b (tabelle `computi` e `computo_voci` con `totale` come generated column e snapshot dei prezzi). Riportalo integralmente, **più**:

```sql
create view public.computi_totali as
  select c.id as computo_id, c.tenant_id,
         coalesce(sum(v.totale), 0)::numeric(14,2) as totale,
         count(v.id) as n_voci,
         count(v.id) filter (where v.generata_da_ai and not v.validata_umano) as n_da_validare
  from public.computi c
  left join public.computo_voci v on v.computo_id = c.id
  group by c.id, c.tenant_id;

-- un computo confermato non accetta più modifiche alle voci
create or replace function public.blocca_computo_confermato()
returns trigger language plpgsql as $$
begin
  if exists (select 1 from public.computi c
             where c.id = coalesce(new.computo_id, old.computo_id)
               and c.stato in ('confermato','archiviato')) then
    raise exception 'Computo confermato: crea una variante per modificarlo';
  end if;
  return coalesce(new, old);
end; $$;

create trigger computo_voci_blocco
  before insert or update or delete on public.computo_voci
  for each row execute function public.blocca_computo_confermato();
```

Aggiungi `prezzari`, `prezzario_voci`, `computi`, `computo_voci` a `TABELLE_TENANT` in `test_tenant_isolation.py`.

---

## TASK 1.4 — `backend/boq_service.py`

```python
async def crea_computo(tenant_id, *, lead_id=None, cantiere_id=None,
                       prezzario_id=None, tipo='estimativo') -> dict

async def aggiungi_voce(tenant_id, computo_id, prezzario_voce_id, qta) -> dict
    """SNAPSHOT: copia descrizione, um, categorie e prezzo_unitario dalla voce
       di prezzario. origine_voce_id resta solo per tracciabilità."""

async def aggiorna_voce(tenant_id, voce_id, **campi) -> dict
async def riordina_voci(tenant_id, computo_id, ordine: list[UUID]) -> None
async def duplica_computo(tenant_id, computo_id, *, tipo=None) -> dict

async def conferma_computo(tenant_id, computo_id) -> dict
    """409 se restano voci generata_da_ai and not validata_umano."""

async def computo_to_preventivo(tenant_id, computo_id, *, sconto=0, iva=10) -> dict
```

**Regola chiave**: `conferma_computo` deve fallire finché esistono voci AI non validate. È il meccanismo che rende reale il claim di validazione umana già presente nel prodotto (commit `98b6b65`).

---

## TASK 1.5 — Metriche strutturate dall'AI

**Modifica `backend/ai_architect_service.py`** — 6469 righe: **estrai, non riscrivere**.

Nuovo modulo `backend/engines/metriche.py`:

```python
class MetricheComputo(BaseModel):
    """Quantità estratte dalla planimetria. NESSUN PREZZO, per contratto."""
    mq_calpestabile: float
    mq_pavimento: float
    mq_rivestimento: float
    mq_intonaco: float
    ml_tramezzi_demolire: float
    ml_tramezzi_nuovi: float
    ml_battiscopa: float
    n_bagni: int
    n_camere: int
    n_punti_luce: int
    n_punti_presa: int
    n_punti_acqua: int
    n_infissi_interni: int
    n_infissi_esterni: int
    confidenza: dict[str, float]   # per metrica, 0-1

def estrai_metriche(analisi_ai: dict) -> MetricheComputo: ...
```

Se un campo di `MetricheComputo` contenesse mai un prezzo o un importo, la spec è violata.

Le metriche vengono persistite nel job AI esistente, così il mapping può rigirare senza richiamare l'LLM.

---

## TASK 1.6 — `backend/mapping_engine.py` — il ponte

Migration `0006_mapping.sql`:

```sql
create table public.mapping_regole (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  metrica text not null,
  prezzario_voce_id uuid not null references public.prezzario_voci(id) on delete cascade,
  moltiplicatore numeric(10,4) not null default 1 check (moltiplicatore > 0),
  condizione jsonb,          -- es. {"livello": ["premium","luxury"]}
  ordine integer not null default 0,
  attiva boolean not null default true,
  created_at timestamptz not null default now()
);
create index on public.mapping_regole (tenant_id, metrica) where attiva;
```

Modulo:

```python
def genera_voci(metriche: MetricheComputo,
                regole: list[Regola],
                config_lead: dict) -> list[VoceComputo]:
    """Puro, deterministico, senza I/O. Per ogni regola attiva la cui condizione
       è soddisfatta da config_lead:
         qta = getattr(metriche, regola.metrica) * regola.moltiplicatore
       Salta le qta <= 0. Il prezzo arriva dalla voce di prezzario, mai dall'AI.
       Ordina per ordine, poi super_categoria."""

async def genera_computo_da_ai(tenant_id, job_id, *, lead_id=None) -> dict:
    """Orchestrazione: carica metriche, regole e prezzario default del tenant,
       chiama genera_voci, persiste il computo con stato='ai_da_revisionare'
       e ogni voce generata_da_ai=True, validata_umano=False."""
```

`genera_voci` è puro: si testa senza database, senza rete, senza LLM. Copertura test alta.

**Regole di default nel seed**, almeno: `mq_pavimento`→pavimento gres · `ml_tramezzi_demolire`→demolizione tramezzi · `mq_intonaco`→intonaco civile · `n_punti_luce`→punto luce · `n_punti_acqua`→punto acqua · `n_bagni`→sanitari (×1) · `mq_calpestabile`→smaltimento macerie (moltiplicatore calibrato sui dati GB).

**Validazione**: `pytest backend/tests/test_mapping_engine.py` — casi tabellari su `genera_voci`, incluso il test che nessun importo provenga dalle metriche.

---

## TASK 1.7 — Preventivo + PDF

Migration `0007_preventivi.sql`: tabella `preventivi` con numerazione progressiva per tenant e anno, snapshot del totale, sconto, IVA, `pdf_path` su Storage, stati `bozza|inviato|accettato|rifiutato|scaduto`.

PDF con `reportlab` (già in requirements). Template white-label: logo, colori e dati da `tenants.theme` e `tenants.contatti`. **Nessun riferimento hardcoded a GB Construction.**

**Validazione**: PDF generato per due tenant con temi diversi → branding diverso, stesso layout.

---

## TASK 1.8 — Frontend Fase 1

| File | Contenuto |
|---|---|
| `frontend/src/context/TenantContext.jsx` | Risolve il tenant da hostname (`<slug>.alantis.it`) o `?tenant=` in dev. Inietta `--brand-primary`, `--brand-secondary`, logo e font come CSS custom properties su `:root` |
| `frontend/src/dashboard/pages/Prezzario.jsx` | Lista prezzari, duplicazione, tabella voci con edit inline, "Ripristina Campania", import CSV |
| `frontend/src/dashboard/pages/PrezzarioWizard.jsx` | 28 voci in step per super_categoria, anteprima dell'impatto sulla categoria, salvataggio unico |
| `frontend/src/dashboard/pages/Computi.jsx` | Lista computi con totale da `computi_totali` e badge "N voci da validare" |
| `frontend/src/dashboard/pages/ComputoEditor.jsx` | Editor voci: aggiunta da prezzario con ricerca, edit qta/prezzo, riordino, totali per categoria |
| `frontend/src/dashboard/pages/AIArchitectReview.jsx` | **UPDATE** — pannello "Bozza computo generata": voci AI evidenziate, azione "Valida" per voce e "Valida tutte", conferma bloccata finché ne restano di non validate |

Usa i componenti già in `frontend/src/components/ui/`. Non introdurre un secondo design system. Data fetching solo con TanStack Query.

---

## TASK 1.9 — Accettazione Fase 1

Crea `backend/tests/test_ground_truth_computi.py`, basato sul set già presente in `scripts/ai_architect_ground_truth/`.

```python
def test_bozza_computo_entro_15_percento():
    """Per ciascun caso ground-truth: planimetria → metriche → mapping → computo.
       Confronta il totale con il preventivo storico realmente emesso.
       Criterio: scostamento < 15% su almeno 8 casi su 10."""
```

Se il criterio non passa, il problema è quasi sempre nella **calibrazione dei moltiplicatori di mapping**, non nel codice. Regolali sui dati GB prima di sospettare il motore.

---

# Definition of Done

- [x] `supabase db reset` ricostruisce l'intero schema da zero, senza intervento manuale (locale, 2026-08-03)
- [ ] `pytest backend/tests/` verde, incluso `test_tenant_isolation.py` — la selezione EdilOS è verde; la suite legacy completa non è ancora tutta verde
- [x] Il test che scopre le tabelle dal catalogo Postgres non trova tabelle con `tenant_id` prive di RLS
- [ ] CI: i 4 job passano. Verifica che `service-role-guard` fallisca davvero introducendo un uso illecito in un commit di prova, poi rimuovilo
- [x] `npm run build` passa; nessun import di SWR residuo
- [ ] Backfill Mongo idempotente, conteggi allineati, rieseguibile
- [x] Due tenant sullo stesso database: nessuna lettura né scrittura incrociata, incluse view e privilegi anon
- [x] Prezzario Campania non modificabile; duplicato modificabile/default; mapping AI usa i prezzi della copia
- [x] `conferma_computo` rifiuta con 409 se restano voci AI non validate; anche la conversione a preventivo richiede stato `confermato`
- [ ] PDF preventivo con branding del tenant, diverso fra i due tenant di test
- [ ] Ground truth: 8 casi su 10 entro il 15%
- [ ] Nessun prezzo prodotto dall'LLM in nessun percorso del codice

---

# Cosa NON fare

- Non implementare la fatturazione elettronica SDI. In nessuna forma, nemmeno "preparatoria"
- Non migrare da CRA a Vite in questa fase
- Non riscrivere `ai_architect_service.py`: estrai il layer metriche e basta
- Non toccare i guardrail AI Architect descritti in `PIANO_CODEX_AI_ARCHITECT_LANCIO.md`
- Non modificare il flusso landing pubblico oltre a ciò che il tenant context richiede
- Non aggiungere librerie oltre a quelle elencate in "Variabili d'ambiente"
- Non usare `service_role` per "sbloccare" un problema di RLS: il problema è la policy, e va corretta la policy
- Non creare astrazioni per le Fasi 3-6. Verranno progettate quando serviranno
