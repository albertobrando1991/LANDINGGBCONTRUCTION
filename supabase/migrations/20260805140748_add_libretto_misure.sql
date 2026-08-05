-- Fase 3.1: fondazione dati append-only del Libretto di misura.

alter table public.cantieri
  add constraint cantieri_tenant_id_id_key unique (tenant_id, id);

alter table public.computo_voci
  add constraint computo_voci_tenant_id_id_key unique (tenant_id, id);

create table public.libretto_misure (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  cantiere_id uuid not null,
  computo_voce_id uuid,
  data_misura date not null default current_date,
  rilevata_da uuid default auth.uid()
    references auth.users(id) on delete set null,
  descrizione text,
  parti integer not null default 1
    check (parti > 0),
  lunghezza numeric(10,3)
    check (lunghezza is null or lunghezza >= 0),
  larghezza numeric(10,3)
    check (larghezza is null or larghezza >= 0),
  altezza numeric(10,3)
    check (altezza is null or altezza >= 0),
  qta numeric(12,3) not null
    check (qta <> 0),
  foto_paths text[] not null default '{}'::text[]
    check (array_position(foto_paths, null) is null),
  client_uuid uuid not null,
  created_at timestamptz not null default now(),
  constraint libretto_misure_cantiere_tenant_fk
    foreign key (tenant_id, cantiere_id)
    references public.cantieri(tenant_id, id) on delete restrict,
  constraint libretto_misure_computo_voce_tenant_fk
    foreign key (tenant_id, computo_voce_id)
    references public.computo_voci(tenant_id, id)
    on delete set null (computo_voce_id),
  constraint libretto_misure_tenant_client_uuid_key
    unique (tenant_id, client_uuid)
);

create index libretto_misure_tenant_cantiere_data_idx
  on public.libretto_misure (
    tenant_id,
    cantiere_id,
    data_misura desc,
    created_at desc
  );

create index libretto_misure_tenant_computo_voce_idx
  on public.libretto_misure (tenant_id, computo_voce_id)
  where computo_voce_id is not null;

create index libretto_misure_rilevata_da_idx
  on public.libretto_misure (rilevata_da)
  where rilevata_da is not null;

alter table public.libretto_misure enable row level security;
alter table public.libretto_misure force row level security;

create policy libretto_misure_staff_read on public.libretto_misure
  for select to authenticated
  using (
    public.has_role(
      tenant_id,
      array['owner','admin','staff','operations']::public.tenant_role[]
    )
  );

create policy libretto_misure_staff_insert on public.libretto_misure
  for insert to authenticated
  with check (
    public.has_role(
      tenant_id,
      array['owner','admin','staff','operations']::public.tenant_role[]
    )
    and rilevata_da = (select auth.uid())
  );

revoke all privileges on table public.libretto_misure
  from anon, authenticated, public;
grant select, insert on table public.libretto_misure to authenticated;
grant all on table public.libretto_misure to service_role;

comment on table public.libretto_misure is
  'Misure di cantiere append-only; una correzione e una nuova riga di segno opposto.';
comment on column public.libretto_misure.client_uuid is
  'UUID generato dal client per rendere idempotenti i retry della sincronizzazione offline.';
