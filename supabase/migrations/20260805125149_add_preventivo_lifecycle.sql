-- Ciclo di vita e storico append-only dei preventivi EdilOS.

alter table public.preventivi
  add column rifiutato_at timestamptz,
  add column scaduto_at timestamptz,
  add column ultimo_destinatario text,
  add column ultimo_email_provider text
    check (ultimo_email_provider is null or ultimo_email_provider in ('resend', 'smtp')),
  add column ultimo_email_id text;

drop policy if exists tenant_write on public.preventivi;
create policy preventivi_staff_insert on public.preventivi
  for insert to authenticated
  with check (
    public.has_role(
      tenant_id,
      array['owner','admin','staff','operations']::public.tenant_role[]
    )
  );

create policy preventivi_staff_update on public.preventivi
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

create policy preventivi_staff_delete on public.preventivi
  for delete to authenticated
  using (
    public.has_role(
      tenant_id,
      array['owner','admin','staff','operations']::public.tenant_role[]
    )
  );

alter table public.preventivi
  add constraint preventivi_tenant_id_id_key unique (tenant_id, id);

create table public.preventivo_eventi (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  preventivo_id uuid not null,
  tipo text not null
    check (tipo in ('creato','stato','email_inviata')),
  stato_precedente text,
  stato_successivo text,
  destinatario text,
  oggetto text,
  provider text,
  provider_message_id text,
  idempotency_key text,
  dettaglio text,
  autore text,
  created_at timestamptz not null default now(),
  constraint preventivo_eventi_preventivo_tenant_fk
    foreign key (tenant_id, preventivo_id)
    references public.preventivi(tenant_id, id) on delete cascade,
  unique (tenant_id, idempotency_key)
);

create index preventivo_eventi_tenant_preventivo_created_idx
  on public.preventivo_eventi (tenant_id, preventivo_id, created_at desc);

alter table public.preventivo_eventi enable row level security;
alter table public.preventivo_eventi force row level security;

create policy preventivo_eventi_read on public.preventivo_eventi
  for select to authenticated
  using (public.is_member(tenant_id));

create policy preventivo_eventi_staff_insert on public.preventivo_eventi
  for insert to authenticated
  with check (
    public.has_role(
      tenant_id,
      array['owner','admin','staff','operations']::public.tenant_role[]
    )
  );

revoke all privileges on table public.preventivo_eventi from anon, authenticated, public;
grant select, insert on table public.preventivo_eventi to authenticated;
grant all on table public.preventivo_eventi to service_role;

insert into public.preventivo_eventi (
  tenant_id,
  preventivo_id,
  tipo,
  stato_successivo,
  dettaglio,
  autore,
  created_at
)
select
  tenant_id,
  id,
  'creato',
  stato,
  'Storico inizializzato dalla migrazione del ciclo preventivo',
  'sistema',
  created_at
from public.preventivi;

comment on table public.preventivo_eventi is
  'Storico append-only delle transizioni e degli invii dei preventivi.';
