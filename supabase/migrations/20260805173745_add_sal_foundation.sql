-- Fase 3.4: fondazione dati tenant-safe per SAL derivati dal libretto misure.

create table public.sal (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  cantiere_id uuid not null,
  numero integer not null check (numero > 0),
  periodo_da date not null,
  periodo_a date not null,
  stato text not null default 'bozza'
    check (stato in ('bozza', 'emesso', 'approvato')),
  created_by uuid default auth.uid()
    references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint sal_periodo_valido check (periodo_da <= periodo_a),
  constraint sal_cantiere_tenant_fk
    foreign key (tenant_id, cantiere_id)
    references public.cantieri(tenant_id, id) on delete restrict,
  constraint sal_tenant_cantiere_numero_key
    unique (tenant_id, cantiere_id, numero),
  constraint sal_tenant_id_id_key
    unique (tenant_id, id)
);

create index sal_tenant_cantiere_periodo_idx
  on public.sal (tenant_id, cantiere_id, periodo_a desc, numero desc);

create index sal_created_by_idx
  on public.sal (created_by)
  where created_by is not null;

create table public.sal_righe (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  sal_id uuid not null,
  computo_voce_id uuid not null,
  descrizione text not null,
  um text not null,
  qta_periodo numeric(12,3) not null,
  qta_progressiva numeric(12,3) not null,
  prezzo_unitario numeric(12,2) not null
    check (prezzo_unitario >= 0),
  importo_periodo numeric(14,2)
    generated always as (round(qta_periodo * prezzo_unitario, 2)) stored,
  created_at timestamptz not null default now(),
  constraint sal_righe_sal_tenant_fk
    foreign key (tenant_id, sal_id)
    references public.sal(tenant_id, id) on delete cascade,
  constraint sal_righe_computo_voce_tenant_fk
    foreign key (tenant_id, computo_voce_id)
    references public.computo_voci(tenant_id, id) on delete restrict,
  constraint sal_righe_tenant_sal_voce_key
    unique (tenant_id, sal_id, computo_voce_id)
);

create index sal_righe_tenant_voce_idx
  on public.sal_righe (tenant_id, computo_voce_id);

alter table public.sal enable row level security;
alter table public.sal force row level security;
alter table public.sal_righe enable row level security;
alter table public.sal_righe force row level security;

create policy sal_staff_read on public.sal
  for select to authenticated
  using (
    public.has_role(
      tenant_id,
      array['owner','admin','staff','operations']::public.tenant_role[]
    )
  );

create policy sal_staff_insert on public.sal
  for insert to authenticated
  with check (
    public.has_role(
      tenant_id,
      array['owner','admin','staff','operations']::public.tenant_role[]
    )
    and created_by = (select auth.uid())
  );

create policy sal_staff_update on public.sal
  for update to authenticated
  using (
    public.has_role(
      tenant_id,
      array['owner','admin','staff','operations']::public.tenant_role[]
    )
  )
  with check (
    public.has_role(
      tenant_id,
      array['owner','admin','staff','operations']::public.tenant_role[]
    )
  );

create policy sal_righe_staff_read on public.sal_righe
  for select to authenticated
  using (
    public.has_role(
      tenant_id,
      array['owner','admin','staff','operations']::public.tenant_role[]
    )
  );

create policy sal_righe_staff_insert on public.sal_righe
  for insert to authenticated
  with check (
    public.has_role(
      tenant_id,
      array['owner','admin','staff','operations']::public.tenant_role[]
    )
  );

create or replace function public.valida_transizione_sal()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.stato = old.stato then
    return new;
  end if;

  if not (
    (old.stato = 'bozza' and new.stato = 'emesso')
    or (old.stato = 'emesso' and new.stato = 'approvato')
  ) then
    raise exception 'Transizione SAL non valida: % -> %', old.stato, new.stato;
  end if;

  return new;
end;
$$;

create trigger sal_transizione
  before update of stato on public.sal
  for each row execute function public.valida_transizione_sal();

create trigger sal_touch before update on public.sal
  for each row execute function public.touch_updated_at();

revoke all privileges on table public.sal, public.sal_righe
  from anon, authenticated, public;
grant select, insert on table public.sal to authenticated;
grant update (stato) on table public.sal to authenticated;
grant select, insert on table public.sal_righe to authenticated;
grant all on table public.sal, public.sal_righe to service_role;

revoke execute on function public.valida_transizione_sal()
  from public, anon, authenticated;

comment on table public.sal is
  'Testata SAL derivata dal libretto misure e numerata per cantiere.';
comment on table public.sal_righe is
  'Snapshot economico delle quantita misurate per voce alla generazione del SAL.';
comment on column public.sal_righe.qta_progressiva is
  'Quantita cumulata fino al periodo_a; eventuali eccedenze non bloccano il SAL.';
