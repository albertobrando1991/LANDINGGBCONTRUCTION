-- Personale interno/subappaltatori, assegnazioni ai cantieri e costi fissi.
-- I costi fissi restano separati dalla marginalita del singolo cantiere.

create table public.personale (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  tipo text not null check (tipo in ('interno', 'subappaltatore')),
  nome text not null check (length(btrim(nome)) between 2 and 200),
  ruolo text,
  fornitore_id uuid,
  telefono text,
  email text,
  costo_giornaliero numeric(10,2)
    check (costo_giornaliero is null or costo_giornaliero >= 0),
  costo_orario numeric(10,2)
    check (costo_orario is null or costo_orario >= 0),
  attivo boolean not null default true,
  note text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint personale_tenant_id_id_key unique (tenant_id, id),
  constraint personale_fornitore_tenant_fk
    foreign key (tenant_id, fornitore_id)
    references public.fornitori(tenant_id, id)
    on delete set null (fornitore_id)
);

create index personale_tenant_tipo_attivo_idx
  on public.personale (tenant_id, tipo, attivo, nome);
create index personale_tenant_fornitore_idx
  on public.personale (tenant_id, fornitore_id)
  where fornitore_id is not null;

create table public.cantiere_personale (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  cantiere_id uuid not null,
  personale_id uuid not null,
  ruolo_in_cantiere text,
  data_da date not null default current_date,
  data_a date,
  stato text not null default 'assegnato'
    check (stato in ('assegnato', 'in_corso', 'concluso')),
  note text,
  created_by uuid default auth.uid() references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint cantiere_personale_tenant_id_id_key unique (tenant_id, id),
  constraint cantiere_personale_cantiere_tenant_fk
    foreign key (tenant_id, cantiere_id)
    references public.cantieri(tenant_id, id) on delete restrict,
  constraint cantiere_personale_personale_tenant_fk
    foreign key (tenant_id, personale_id)
    references public.personale(tenant_id, id) on delete cascade,
  constraint cantiere_personale_periodo_check
    check (data_a is null or data_a >= data_da)
);

create index cantiere_personale_tenant_cantiere_idx
  on public.cantiere_personale (tenant_id, cantiere_id, stato);
create index cantiere_personale_tenant_personale_idx
  on public.cantiere_personale (tenant_id, personale_id);
create index cantiere_personale_created_by_idx
  on public.cantiere_personale (created_by)
  where created_by is not null;

create table public.costi_fissi (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  categoria text not null default 'altro'
    check (categoria in (
      'affitto', 'assicurazioni', 'leasing', 'software',
      'stipendi_amministrativi', 'utenze_sede', 'consulenze', 'altro'
    )),
  descrizione text not null
    check (length(btrim(descrizione)) between 2 and 300),
  importo_mensile numeric(14,2) not null check (importo_mensile >= 0),
  data_inizio date not null default current_date,
  data_fine date,
  attivo boolean not null default true,
  note text,
  created_by uuid default auth.uid() references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint costi_fissi_tenant_id_id_key unique (tenant_id, id),
  constraint costi_fissi_periodo_check
    check (data_fine is null or data_fine >= data_inizio)
);

create index costi_fissi_tenant_attivo_idx
  on public.costi_fissi (tenant_id, attivo, categoria);
create index costi_fissi_created_by_idx
  on public.costi_fissi (created_by)
  where created_by is not null;

alter table public.personale enable row level security;
alter table public.personale force row level security;
alter table public.cantiere_personale enable row level security;
alter table public.cantiere_personale force row level security;
alter table public.costi_fissi enable row level security;
alter table public.costi_fissi force row level security;

do $$
declare table_name text;
begin
  foreach table_name in array array['personale', 'cantiere_personale']
  loop
    execute format(
      'create policy %I on public.%I for select to authenticated using '
      '((select public.has_role(tenant_id, array[''owner'',''admin'',''staff'',''operations'']::public.tenant_role[])))',
      table_name || '_roster_read', table_name
    );
    execute format(
      'create policy %I on public.%I for insert to authenticated with check '
      '((select public.has_role(tenant_id, array[''owner'',''admin'']::public.tenant_role[])))',
      table_name || '_roster_insert', table_name
    );
    execute format(
      'create policy %I on public.%I for update to authenticated using '
      '((select public.has_role(tenant_id, array[''owner'',''admin'']::public.tenant_role[]))) '
      'with check ((select public.has_role(tenant_id, array[''owner'',''admin'']::public.tenant_role[])))',
      table_name || '_roster_update', table_name
    );
    execute format(
      'create policy %I on public.%I for delete to authenticated using '
      '((select public.has_role(tenant_id, array[''owner'',''admin'']::public.tenant_role[])))',
      table_name || '_roster_delete', table_name
    );
  end loop;
end $$;

create policy costi_fissi_finance_read on public.costi_fissi
  for select to authenticated
  using ((select public.has_role(
    tenant_id, array['owner','admin']::public.tenant_role[]
  )));
create policy costi_fissi_finance_insert on public.costi_fissi
  for insert to authenticated
  with check ((select public.has_role(
    tenant_id, array['owner','admin']::public.tenant_role[]
  )));
create policy costi_fissi_finance_update on public.costi_fissi
  for update to authenticated
  using ((select public.has_role(
    tenant_id, array['owner','admin']::public.tenant_role[]
  )))
  with check ((select public.has_role(
    tenant_id, array['owner','admin']::public.tenant_role[]
  )));
create policy costi_fissi_finance_delete on public.costi_fissi
  for delete to authenticated
  using ((select public.has_role(
    tenant_id, array['owner','admin']::public.tenant_role[]
  )));

create trigger personale_touch before update on public.personale
  for each row execute function public.touch_updated_at();
create trigger cantiere_personale_touch before update on public.cantiere_personale
  for each row execute function public.touch_updated_at();
create trigger costi_fissi_touch before update on public.costi_fissi
  for each row execute function public.touch_updated_at();

revoke all privileges on table
  public.personale, public.cantiere_personale, public.costi_fissi
from public, anon, authenticated;

grant select, insert, update, delete on table
  public.personale, public.cantiere_personale, public.costi_fissi
to authenticated;

grant all on table
  public.personale, public.cantiere_personale, public.costi_fissi
to service_role;

comment on table public.personale is
  'Anagrafica tenant-scoped di personale interno e subappaltatori.';
comment on table public.cantiere_personale is
  'Assegnazioni del personale ai cantieri, senza dati di geolocalizzazione.';
comment on table public.costi_fissi is
  'Costi fissi mensili aziendali separati dalla marginalita di cantiere.';
