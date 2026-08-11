-- Presenze giornaliere dichiarate da staff/capocantiere, senza GPS.
create table public.presenze_cantiere (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  cantiere_id uuid not null,
  personale_id uuid not null,
  data date not null default current_date,
  unita_presenti smallint not null default 1
    check (unita_presenti between 1 and 999),
  tipo_giornata text not null default 'intera'
    check (tipo_giornata in ('intera', 'mezza', 'ore')),
  ore_lavorate numeric(5,2)
    check (ore_lavorate is null or ore_lavorate between 0 and 24),
  ora_ingresso time,
  ora_uscita time,
  note text check (note is null or length(note) <= 2000),
  registrato_da uuid default auth.uid() references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint presenze_cantiere_tenant_id_id_key unique (tenant_id, id),
  constraint presenze_cantiere_cantiere_tenant_fk
    foreign key (tenant_id, cantiere_id)
    references public.cantieri(tenant_id, id) on delete restrict,
  constraint presenze_cantiere_personale_tenant_fk
    foreign key (tenant_id, personale_id)
    references public.personale(tenant_id, id) on delete restrict,
  constraint presenze_cantiere_uscita_check
    check (ora_uscita is null or ora_ingresso is null or ora_uscita > ora_ingresso),
  constraint presenze_cantiere_giorno_unique
    unique (tenant_id, cantiere_id, personale_id, data)
);

create index presenze_cantiere_tenant_data_idx
  on public.presenze_cantiere (tenant_id, data desc, cantiere_id);
create index presenze_cantiere_personale_data_idx
  on public.presenze_cantiere (tenant_id, personale_id, data desc);
create index presenze_cantiere_registrato_da_idx
  on public.presenze_cantiere (registrato_da)
  where registrato_da is not null;

alter table public.presenze_cantiere enable row level security;
alter table public.presenze_cantiere force row level security;

create policy presenze_cantiere_internal_read on public.presenze_cantiere
  for select to authenticated
  using ((select public.has_role(
    tenant_id,
    array['owner','admin','staff','operations']::public.tenant_role[]
  )));
create policy presenze_cantiere_internal_insert on public.presenze_cantiere
  for insert to authenticated
  with check ((select public.has_role(
    tenant_id,
    array['owner','admin','staff','operations']::public.tenant_role[]
  )));
create policy presenze_cantiere_internal_update on public.presenze_cantiere
  for update to authenticated
  using ((select public.has_role(
    tenant_id,
    array['owner','admin','staff','operations']::public.tenant_role[]
  )))
  with check ((select public.has_role(
    tenant_id,
    array['owner','admin','staff','operations']::public.tenant_role[]
  )));
create policy presenze_cantiere_internal_delete on public.presenze_cantiere
  for delete to authenticated
  using ((select public.has_role(
    tenant_id,
    array['owner','admin','staff','operations']::public.tenant_role[]
  )));

create trigger presenze_cantiere_touch before update on public.presenze_cantiere
  for each row execute function public.touch_updated_at();

revoke all privileges on table public.presenze_cantiere
  from public, anon, authenticated;
grant select, insert, update, delete on table public.presenze_cantiere
  to authenticated;
grant all on table public.presenze_cantiere to service_role;

comment on table public.presenze_cantiere is
  'Presenze giornaliere dichiarate sui cantieri; non contiene geolocalizzazione.';
