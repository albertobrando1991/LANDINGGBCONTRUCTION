-- Fase 6 - Portale cliente finale.
-- Il ruolo client non eredita mai la visibilita tenant-wide: accede soltanto
-- alle proiezioni esplicite del proprio cantiere e agli asset condivisi.

create or replace function public.is_internal_member(t uuid)
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select exists (
    select 1
    from public.tenant_members
    where tenant_id = t
      and user_id = (select auth.uid())
      and role = any(
        array['owner','admin','staff','operations']::public.tenant_role[]
      )
  );
$$;

revoke execute on function public.is_internal_member(uuid)
  from public, anon;
grant execute on function public.is_internal_member(uuid)
  to authenticated, service_role;

create table public.cantiere_clienti (
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  cantiere_id uuid not null,
  user_id uuid not null references auth.users(id) on delete cascade,
  email text,
  nome text check (nome is null or char_length(nome) <= 200),
  invitato_da uuid default auth.uid()
    references auth.users(id) on delete set null,
  attivo boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (tenant_id, cantiere_id, user_id),
  constraint cantiere_clienti_cantiere_tenant_fk
    foreign key (tenant_id, cantiere_id)
    references public.cantieri(tenant_id, id) on delete cascade
);

create index cantiere_clienti_user_active_idx
  on public.cantiere_clienti (user_id, tenant_id, cantiere_id)
  where attivo = true;

create or replace function public.is_cantiere_client(t uuid, c uuid)
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select exists (
    select 1
    from public.cantiere_clienti cc
    join public.tenant_members tm
      on tm.tenant_id = cc.tenant_id
     and tm.user_id = cc.user_id
     and tm.role = 'client'
    where cc.tenant_id = t
      and cc.cantiere_id = c
      and cc.user_id = (select auth.uid())
      and cc.attivo = true
  );
$$;

revoke execute on function public.is_cantiere_client(uuid, uuid)
  from public, anon;
grant execute on function public.is_cantiere_client(uuid, uuid)
  to authenticated, service_role;

create table public.cantiere_condivisioni (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  cantiere_id uuid not null,
  tipo text not null check (tipo in ('foto', 'documento')),
  bucket text not null check (bucket in ('foto-cantiere', 'documenti')),
  storage_path text not null,
  titolo text not null check (char_length(trim(titolo)) between 1 and 200),
  descrizione text check (descrizione is null or char_length(descrizione) <= 1000),
  condiviso_da uuid default auth.uid()
    references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  constraint cantiere_condivisioni_cantiere_tenant_fk
    foreign key (tenant_id, cantiere_id)
    references public.cantieri(tenant_id, id) on delete cascade,
  constraint cantiere_condivisioni_tipo_bucket_check check (
    (tipo = 'foto' and bucket = 'foto-cantiere')
    or (tipo = 'documento' and bucket = 'documenti')
  ),
  constraint cantiere_condivisioni_path_check check (
    storage_path like tenant_id::text || '/cantiere-' || cantiere_id::text || '/%'
  ),
  unique (tenant_id, cantiere_id, bucket, storage_path)
);

create index cantiere_condivisioni_cantiere_created_idx
  on public.cantiere_condivisioni (tenant_id, cantiere_id, created_at desc);

create unique index if not exists computi_tenant_cantiere_id_uidx
  on public.computi (tenant_id, cantiere_id, id);

create table public.varianti_approvazioni (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  cantiere_id uuid not null,
  variante_id uuid not null,
  user_id uuid not null default auth.uid()
    references auth.users(id) on delete restrict,
  decisione text not null default 'approvata'
    check (decisione = 'approvata'),
  ip inet not null,
  user_agent text check (user_agent is null or char_length(user_agent) <= 500),
  created_at timestamptz not null default now(),
  constraint varianti_approvazioni_cantiere_tenant_fk
    foreign key (tenant_id, cantiere_id)
    references public.cantieri(tenant_id, id) on delete restrict,
  constraint varianti_approvazioni_variante_cantiere_fk
    foreign key (tenant_id, cantiere_id, variante_id)
    references public.computi(tenant_id, cantiere_id, id) on delete restrict,
  unique (tenant_id, variante_id, user_id)
);

create index varianti_approvazioni_cantiere_created_idx
  on public.varianti_approvazioni (tenant_id, cantiere_id, created_at desc);
create index varianti_approvazioni_user_idx
  on public.varianti_approvazioni (user_id, created_at desc);

create or replace function public.is_approvable_client_variant(
  t uuid,
  c uuid,
  v uuid
)
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select public.is_cantiere_client(t, c)
    and exists (
      select 1
      from public.computi co
      where co.tenant_id = t
        and co.cantiere_id = c
        and co.id = v
        and co.tipo = 'variante'
        and co.stato = 'confermato'
    );
$$;

revoke execute on function public.is_approvable_client_variant(uuid, uuid, uuid)
  from public, anon;
grant execute on function public.is_approvable_client_variant(uuid, uuid, uuid)
  to authenticated, service_role;

alter table public.cantiere_clienti enable row level security;
alter table public.cantiere_clienti force row level security;
alter table public.cantiere_condivisioni enable row level security;
alter table public.cantiere_condivisioni force row level security;
alter table public.varianti_approvazioni enable row level security;
alter table public.varianti_approvazioni force row level security;

create policy cantiere_clienti_read on public.cantiere_clienti
  for select to authenticated
  using (
    (select public.is_internal_member(tenant_id))
    or (
      user_id = (select auth.uid())
      and attivo = true
      and (select public.is_cantiere_client(tenant_id, cantiere_id))
    )
  );
create policy cantiere_clienti_internal_insert on public.cantiere_clienti
  for insert to authenticated
  with check ((select public.is_internal_member(tenant_id)));
create policy cantiere_clienti_internal_update on public.cantiere_clienti
  for update to authenticated
  using ((select public.is_internal_member(tenant_id)))
  with check ((select public.is_internal_member(tenant_id)));
create policy cantiere_clienti_internal_delete on public.cantiere_clienti
  for delete to authenticated
  using ((select public.is_internal_member(tenant_id)));

create policy cantiere_condivisioni_read on public.cantiere_condivisioni
  for select to authenticated
  using (
    (select public.is_internal_member(tenant_id))
    or (select public.is_cantiere_client(tenant_id, cantiere_id))
  );
create policy cantiere_condivisioni_internal_insert on public.cantiere_condivisioni
  for insert to authenticated
  with check ((select public.is_internal_member(tenant_id)));
create policy cantiere_condivisioni_internal_update on public.cantiere_condivisioni
  for update to authenticated
  using ((select public.is_internal_member(tenant_id)))
  with check ((select public.is_internal_member(tenant_id)));
create policy cantiere_condivisioni_internal_delete on public.cantiere_condivisioni
  for delete to authenticated
  using ((select public.is_internal_member(tenant_id)));

create policy varianti_approvazioni_read on public.varianti_approvazioni
  for select to authenticated
  using (
    (select public.is_internal_member(tenant_id))
    or (
      user_id = (select auth.uid())
      and (select public.is_cantiere_client(tenant_id, cantiere_id))
    )
  );
create policy varianti_approvazioni_client_insert on public.varianti_approvazioni
  for insert to authenticated
  with check (
    user_id = (select auth.uid())
    and decisione = 'approvata'
    and (select public.is_approvable_client_variant(
      tenant_id, cantiere_id, variante_id
    ))
  );

create trigger cantiere_clienti_touch
  before update on public.cantiere_clienti
  for each row execute function public.touch_updated_at();

-- Le vecchie policy is_member includevano anche client. Da questo punto tutte
-- le tabelle operative sono riservate ai quattro ruoli interni.
do $$
declare t text;
begin
  foreach t in array array[
    'clienti','leads','cantieri','prezzari','prezzario_voci',
    'computi','computo_voci','mapping_regole'
  ] loop
    execute format('drop policy if exists tenant_read on public.%I', t);
    execute format('drop policy if exists tenant_write on public.%I', t);
    execute format(
      'create policy tenant_read on public.%I for select to authenticated '
      'using ((select public.is_internal_member(tenant_id)))', t
    );
    execute format(
      'create policy tenant_insert on public.%I for insert to authenticated '
      'with check ((select public.is_internal_member(tenant_id)))', t
    );
    execute format(
      'create policy tenant_update on public.%I for update to authenticated '
      'using ((select public.is_internal_member(tenant_id))) '
      'with check ((select public.is_internal_member(tenant_id)))', t
    );
    execute format(
      'create policy tenant_delete on public.%I for delete to authenticated '
      'using ((select public.is_internal_member(tenant_id)))', t
    );
  end loop;
end $$;

drop policy if exists tenant_read on public.preventivi;
create policy tenant_read on public.preventivi
  for select to authenticated
  using ((select public.is_internal_member(tenant_id)));

drop policy if exists preventivo_eventi_read on public.preventivo_eventi;
create policy preventivo_eventi_read on public.preventivo_eventi
  for select to authenticated
  using ((select public.is_internal_member(tenant_id)));

drop policy if exists tenants_read on public.tenants;
create policy tenants_read on public.tenants
  for select to authenticated
  using ((select public.is_internal_member(id)));

drop policy if exists members_read on public.tenant_members;
create policy members_read on public.tenant_members
  for select to authenticated
  using (
    user_id = (select auth.uid())
    or (select public.is_internal_member(tenant_id))
  );

drop policy if exists members_write on public.tenant_members;
create policy members_insert on public.tenant_members
  for insert to authenticated
  with check (
    (select public.has_role(
      tenant_id, array['owner','admin']::public.tenant_role[]
    ))
  );
create policy members_update on public.tenant_members
  for update to authenticated
  using (
    (select public.has_role(
      tenant_id, array['owner','admin']::public.tenant_role[]
    ))
  )
  with check (
    (select public.has_role(
      tenant_id, array['owner','admin']::public.tenant_role[]
    ))
  );
create policy members_delete on public.tenant_members
  for delete to authenticated
  using (
    (select public.has_role(
      tenant_id, array['owner','admin']::public.tenant_role[]
    ))
  );

drop index if exists public.computo_voci_tenant_id_id_uidx;

-- Proiezione minima usata anche dal backend per risolvere il tenant corrente.
-- E una view definer intenzionale: le colonne sensibili sono escluse e la
-- clausola auth.uid() e obbligatoria prima di qualsiasi riga restituita.
create or replace view public.utente_tenant_correnti
with (security_barrier = true) as
select
  t.id,
  t.slug,
  t.ragione_sociale,
  t.theme,
  t.contatti,
  case when tm.role = 'client' then null else t.piano end as piano,
  t.attivo,
  tm.role,
  tm.nome
from public.tenant_members tm
join public.tenants t on t.id = tm.tenant_id
where tm.user_id = (select auth.uid())
  and t.attivo = true;

create or replace view public.portale_cantieri
with (security_barrier = true) as
select
  c.tenant_id,
  c.id as cantiere_id,
  c.cliente as nome_cantiere,
  c.indirizzo,
  c.stato,
  c.avanzamento,
  c.milestone,
  c.milestone_data,
  c.updated_at
from public.cantiere_clienti cc
join public.cantieri c
  on c.tenant_id = cc.tenant_id and c.id = cc.cantiere_id
where cc.user_id = (select auth.uid())
  and cc.attivo = true;

create or replace view public.portale_sal_approvati
with (security_barrier = true) as
select
  s.tenant_id,
  s.cantiere_id,
  s.id as sal_id,
  s.numero,
  s.periodo_da,
  s.periodo_a,
  s.stato,
  coalesce(sum(sr.importo_periodo), 0)::numeric(14,2) as totale_periodo,
  coalesce(
    jsonb_agg(
      jsonb_build_object(
        'id', sr.id,
        'descrizione', sr.descrizione,
        'um', sr.um,
        'qta_periodo', sr.qta_periodo,
        'qta_progressiva', sr.qta_progressiva,
        'prezzo_unitario', sr.prezzo_unitario,
        'importo_periodo', sr.importo_periodo
      ) order by sr.descrizione, sr.id
    ) filter (where sr.id is not null),
    '[]'::jsonb
  ) as righe,
  s.updated_at as approvato_at
from public.cantiere_clienti cc
join public.sal s
  on s.tenant_id = cc.tenant_id and s.cantiere_id = cc.cantiere_id
left join public.sal_righe sr
  on sr.tenant_id = s.tenant_id and sr.sal_id = s.id
where cc.user_id = (select auth.uid())
  and cc.attivo = true
  and s.stato = 'approvato'
group by s.tenant_id, s.cantiere_id, s.id;

create or replace view public.portale_varianti
with (security_barrier = true) as
select
  v.tenant_id,
  v.cantiere_id,
  v.id as variante_id,
  v.numero as numero_variante,
  b.id as computo_base_id,
  b.numero as numero_base,
  coalesce(bt.totale, 0)::numeric(14,2) as totale_base,
  coalesce(vt.totale, 0)::numeric(14,2) as totale_variante,
  (coalesce(vt.totale, 0) - coalesce(bt.totale, 0))::numeric(14,2)
    as delta_importo,
  case
    when coalesce(bt.totale, 0) = 0 then null
    else round(((coalesce(vt.totale, 0) - bt.totale) / bt.totale) * 100, 2)
  end as delta_percentuale,
  v.updated_at,
  exists (
    select 1 from public.varianti_approvazioni va
    where va.tenant_id = v.tenant_id
      and va.variante_id = v.id
      and va.user_id = (select auth.uid())
  ) as approvata,
  (
    select min(va.created_at) from public.varianti_approvazioni va
    where va.tenant_id = v.tenant_id
      and va.variante_id = v.id
      and va.user_id = (select auth.uid())
  ) as approvata_at
from public.cantiere_clienti cc
join public.computi v
  on v.tenant_id = cc.tenant_id and v.cantiere_id = cc.cantiere_id
join public.computi b
  on b.tenant_id = v.tenant_id and b.id = v.parent_computo_id
left join public.computi_totali vt
  on vt.tenant_id = v.tenant_id and vt.computo_id = v.id
left join public.computi_totali bt
  on bt.tenant_id = b.tenant_id and bt.computo_id = b.id
where cc.user_id = (select auth.uid())
  and cc.attivo = true
  and v.tipo = 'variante'
  and v.stato = 'confermato';

create or replace view public.portale_variante_righe
with (security_barrier = true) as
select cv.*
from public.cantiere_clienti cc
join public.computi v
  on v.tenant_id = cc.tenant_id and v.cantiere_id = cc.cantiere_id
join public.computo_varianti_confronto cv
  on cv.tenant_id = v.tenant_id and cv.variante_id = v.id
where cc.user_id = (select auth.uid())
  and cc.attivo = true
  and v.tipo = 'variante'
  and v.stato = 'confermato';

revoke all privileges on table
  public.cantiere_clienti,
  public.cantiere_condivisioni,
  public.varianti_approvazioni
from public, anon, authenticated;
grant select, insert, update, delete on table
  public.cantiere_clienti,
  public.cantiere_condivisioni
to authenticated;
grant select, insert on table public.varianti_approvazioni to authenticated;
grant all on table
  public.cantiere_clienti,
  public.cantiere_condivisioni,
  public.varianti_approvazioni
to service_role;

revoke all privileges on table
  public.utente_tenant_correnti,
  public.portale_cantieri,
  public.portale_sal_approvati,
  public.portale_varianti,
  public.portale_variante_righe
from public, anon;
grant select on table
  public.utente_tenant_correnti,
  public.portale_cantieri,
  public.portale_sal_approvati,
  public.portale_varianti,
  public.portale_variante_righe
to authenticated, service_role;

drop policy if exists storage_client_shared_read on storage.objects;
create policy storage_client_shared_read on storage.objects
  for select to authenticated
  using (
    bucket_id in ('foto-cantiere', 'documenti')
    and exists (
      select 1
      from public.cantiere_condivisioni cs
      join public.cantiere_clienti cc
        on cc.tenant_id = cs.tenant_id
       and cc.cantiere_id = cs.cantiere_id
       and cc.user_id = (select auth.uid())
       and cc.attivo = true
      where cs.bucket = bucket_id
        and cs.storage_path = name
    )
  );

comment on table public.cantiere_clienti is
  'Ponte esplicito tra utenti client e singoli cantieri.';
comment on table public.cantiere_condivisioni is
  'Allowlist degli asset Storage visibili nel portale cliente.';
comment on table public.varianti_approvazioni is
  'Audit append-only delle approvazioni cliente, con timestamp, IP e user agent.';
