-- ============================================================
-- 0006 — Regole mapping metriche AI → voci prezzario
-- ============================================================

create table public.mapping_regole (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  metrica text not null,
  prezzario_voce_id uuid not null references public.prezzario_voci(id) on delete cascade,
  moltiplicatore numeric(10,4) not null default 1 check (moltiplicatore > 0),
  condizione jsonb,
  ordine integer not null default 0,
  attiva boolean not null default true,
  created_at timestamptz not null default now()
);
create index on public.mapping_regole (tenant_id, metrica) where attiva;

alter table public.mapping_regole enable row level security;
alter table public.mapping_regole force row level security;

create policy tenant_read on public.mapping_regole
  for select using (public.is_member(tenant_id));
create policy tenant_write on public.mapping_regole
  for all using (public.is_member(tenant_id))
  with check (public.is_member(tenant_id));
