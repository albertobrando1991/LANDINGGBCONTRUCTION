-- ============================================================
-- 0007 — Preventivi con numerazione per tenant/anno
-- ============================================================

create table public.preventivi (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  computo_id uuid not null references public.computi(id) on delete restrict,
  lead_id uuid references public.leads(id) on delete set null,
  cliente_id uuid references public.clienti(id) on delete set null,
  numero text not null,
  anno integer not null,
  progressivo integer not null,
  stato text not null default 'bozza'
    check (stato in ('bozza','inviato','accettato','rifiutato','scaduto')),
  totale_imponibile numeric(14,2) not null default 0,
  sconto_percentuale numeric(5,2) not null default 0 check (sconto_percentuale >= 0 and sconto_percentuale <= 100),
  iva_percentuale numeric(5,2) not null default 10 check (iva_percentuale >= 0),
  totale_iva numeric(14,2) not null default 0,
  totale_documento numeric(14,2) not null default 0,
  snapshot_voci jsonb not null default '[]'::jsonb,
  pdf_path text,
  note text,
  validita_giorni integer not null default 30,
  inviato_at timestamptz,
  accettato_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id, anno, progressivo)
);
create index on public.preventivi (tenant_id, stato, created_at desc);
create index on public.preventivi (tenant_id, computo_id);

alter table public.preventivi enable row level security;
alter table public.preventivi force row level security;

create policy tenant_read on public.preventivi
  for select using (public.is_member(tenant_id));
create policy tenant_write on public.preventivi
  for all using (public.is_member(tenant_id))
  with check (public.is_member(tenant_id));

create trigger preventivi_touch before update on public.preventivi
  for each row execute function public.touch_updated_at();
