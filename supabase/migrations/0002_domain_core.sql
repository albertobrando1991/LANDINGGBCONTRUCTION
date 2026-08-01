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
  config jsonb not null default '{}'::jsonb,
  stima jsonb,
  tracking jsonb not null default '{}'::jsonb,
  timeline jsonb not null default '[]'::jsonb,
  note_cliente text,
  prossima_azione text,
  ai_architect_job_id text,
  legacy_mongo_id text unique,
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
