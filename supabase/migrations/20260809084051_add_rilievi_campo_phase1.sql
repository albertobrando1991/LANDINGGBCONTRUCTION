-- Fase 1 del Primo rilievo Campo: schede modificabili, ambienti e foto.
-- Il libretto_misure resta append-only e dedicato alla contabilita/SAL.

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'leads_tenant_id_id_key'
      and conrelid = 'public.leads'::regclass
  ) then
    alter table public.leads
      add constraint leads_tenant_id_id_key unique (tenant_id, id);
  end if;
end $$;

create table public.rilievi (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  lead_id uuid,
  cantiere_id uuid,
  sopralluogo_legacy_id text,
  client_uuid uuid not null,
  cliente text not null check (char_length(btrim(cliente)) between 2 and 200),
  indirizzo text check (indirizzo is null or char_length(indirizzo) <= 500),
  data_rilievo date not null default current_date,
  tecnico text check (tecnico is null or char_length(tecnico) <= 200),
  note text check (note is null or char_length(note) <= 5000),
  stato text not null default 'bozza'
    check (stato in ('bozza', 'completato')),
  created_by uuid default auth.uid()
    references auth.users(id) on delete set null,
  archived_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint rilievi_tenant_id_id_key unique (tenant_id, id),
  constraint rilievi_tenant_client_uuid_key unique (tenant_id, client_uuid),
  constraint rilievi_lead_tenant_fk
    foreign key (tenant_id, lead_id)
    references public.leads(tenant_id, id) on delete set null (lead_id),
  constraint rilievi_cantiere_tenant_fk
    foreign key (tenant_id, cantiere_id)
    references public.cantieri(tenant_id, id) on delete set null (cantiere_id)
);

create index rilievi_tenant_data_idx
  on public.rilievi (tenant_id, data_rilievo desc, updated_at desc)
  where archived_at is null;
create index rilievi_lead_idx
  on public.rilievi (tenant_id, lead_id)
  where lead_id is not null and archived_at is null;
create index rilievi_cantiere_idx
  on public.rilievi (tenant_id, cantiere_id)
  where cantiere_id is not null and archived_at is null;

create table public.rilievo_ambienti (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  rilievo_id uuid not null,
  client_uuid uuid not null,
  nome text not null check (char_length(btrim(nome)) between 1 and 200),
  tipologia text check (tipologia is null or char_length(tipologia) <= 100),
  piano text check (piano is null or char_length(piano) <= 100),
  ordine integer not null default 0 check (ordine >= 0),
  lunghezza numeric(10,3) check (lunghezza is null or lunghezza >= 0),
  larghezza numeric(10,3) check (larghezza is null or larghezza >= 0),
  altezza numeric(10,3) check (altezza is null or altezza >= 0),
  superficie numeric(12,3) check (superficie is null or superficie >= 0),
  misure_extra jsonb not null default '[]'::jsonb
    check (jsonb_typeof(misure_extra) = 'array'),
  note text check (note is null or char_length(note) <= 3000),
  foto_paths text[] not null default '{}'::text[]
    check (array_position(foto_paths, null) is null),
  archived_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint rilievo_ambienti_rilievo_tenant_fk
    foreign key (tenant_id, rilievo_id)
    references public.rilievi(tenant_id, id) on delete cascade,
  constraint rilievo_ambienti_tenant_client_uuid_key
    unique (tenant_id, rilievo_id, client_uuid)
);

create index rilievo_ambienti_rilievo_ordine_idx
  on public.rilievo_ambienti (tenant_id, rilievo_id, ordine, created_at)
  where archived_at is null;

alter table public.rilievi enable row level security;
alter table public.rilievi force row level security;
alter table public.rilievo_ambienti enable row level security;
alter table public.rilievo_ambienti force row level security;

create policy rilievi_staff_read on public.rilievi
  for select to authenticated
  using (
    public.has_role(
      tenant_id,
      array['owner','admin','staff','operations']::public.tenant_role[]
    )
  );
create policy rilievi_staff_insert on public.rilievi
  for insert to authenticated
  with check (
    public.has_role(
      tenant_id,
      array['owner','admin','staff','operations']::public.tenant_role[]
    )
    and created_by = (select auth.uid())
  );
create policy rilievi_staff_update on public.rilievi
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

create policy rilievo_ambienti_staff_read on public.rilievo_ambienti
  for select to authenticated
  using (
    public.has_role(
      tenant_id,
      array['owner','admin','staff','operations']::public.tenant_role[]
    )
  );
create policy rilievo_ambienti_staff_insert on public.rilievo_ambienti
  for insert to authenticated
  with check (
    public.has_role(
      tenant_id,
      array['owner','admin','staff','operations']::public.tenant_role[]
    )
  );
create policy rilievo_ambienti_staff_update on public.rilievo_ambienti
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

revoke all privileges on table public.rilievi, public.rilievo_ambienti
  from anon, authenticated, public;
grant select, insert, update on table public.rilievi, public.rilievo_ambienti
  to authenticated;
grant all on table public.rilievi, public.rilievo_ambienti to service_role;

create trigger rilievi_touch before update on public.rilievi
  for each row execute function public.touch_updated_at();
create trigger rilievo_ambienti_touch before update on public.rilievo_ambienti
  for each row execute function public.touch_updated_at();

comment on table public.rilievi is
  'Primo rilievo modificabile e offline-first, separato dal libretto contabile SAL.';
comment on table public.rilievo_ambienti is
  'Ambienti, misure manuali e foto del primo rilievo.';
