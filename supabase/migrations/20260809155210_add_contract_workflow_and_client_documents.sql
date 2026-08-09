-- Workflow contrattuale e fascicolo documentale cliente.
-- La scelta economica precede la validazione del contratto; ogni validazione
-- crea uno snapshot immutabile e pubblica il documento nel portale.

create table public.preventivo_clienti (
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  preventivo_id uuid not null,
  user_id uuid not null references auth.users(id) on delete cascade,
  email text not null,
  nome text check (nome is null or char_length(nome) <= 200),
  attivo boolean not null default true,
  invitato_da uuid default auth.uid() references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (tenant_id, preventivo_id, user_id),
  constraint preventivo_clienti_preventivo_tenant_fk
    foreign key (tenant_id, preventivo_id)
    references public.preventivi(tenant_id, id) on delete cascade
);

create index preventivo_clienti_user_active_idx
  on public.preventivo_clienti (user_id, tenant_id, preventivo_id)
  where attivo = true;

create or replace function public.is_preventivo_client(t uuid, p uuid)
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select exists (
    select 1
    from public.preventivo_clienti pc
    join public.tenant_members tm
      on tm.tenant_id = pc.tenant_id
     and tm.user_id = pc.user_id
     and tm.role = 'client'
    where pc.tenant_id = t
      and pc.preventivo_id = p
      and pc.user_id = (select auth.uid())
      and pc.attivo = true
  );
$$;

revoke execute on function public.is_preventivo_client(uuid, uuid)
  from public, anon;
grant execute on function public.is_preventivo_client(uuid, uuid)
  to authenticated, service_role;

create table public.scelte_pagamento_cliente (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  preventivo_id uuid not null,
  user_id uuid not null default auth.uid() references auth.users(id) on delete restrict,
  tipo text not null check (tipo in ('sal', 'scaglionato_fisso', 'due_tranche')),
  stato text not null default 'confermata' check (stato in ('confermata', 'revocata')),
  condizioni jsonb not null default '{}'::jsonb,
  confermata_at timestamptz not null default now(),
  ip inet,
  user_agent text check (user_agent is null or char_length(user_agent) <= 500),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint scelte_pagamento_tenant_id_id_key unique (tenant_id, id),
  constraint scelte_pagamento_preventivo_tenant_fk
    foreign key (tenant_id, preventivo_id)
    references public.preventivi(tenant_id, id) on delete restrict,
  constraint scelte_pagamento_cliente_fk
    foreign key (tenant_id, preventivo_id, user_id)
    references public.preventivo_clienti(tenant_id, preventivo_id, user_id)
    on delete restrict,
  constraint scelte_pagamento_cliente_unique unique (tenant_id, preventivo_id, user_id)
);

create table public.contratti (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  preventivo_id uuid not null,
  cantiere_id uuid,
  numero text not null,
  stato text not null default 'bozza'
    check (stato in ('bozza', 'validato', 'pubblicato', 'firmato', 'annullato')),
  versione_corrente integer not null default 0 check (versione_corrente >= 0),
  scelta_pagamento_id uuid,
  validato_da uuid references auth.users(id) on delete set null,
  validato_at timestamptz,
  pubblicato_at timestamptz,
  firmato_at timestamptz,
  created_by uuid default auth.uid() references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint contratti_tenant_id_id_key unique (tenant_id, id),
  constraint contratti_preventivo_tenant_fk
    foreign key (tenant_id, preventivo_id)
    references public.preventivi(tenant_id, id) on delete restrict,
  constraint contratti_cantiere_tenant_fk
    foreign key (tenant_id, cantiere_id)
    references public.cantieri(tenant_id, id) on delete restrict,
  constraint contratti_scelta_pagamento_tenant_fk
    foreign key (tenant_id, scelta_pagamento_id)
    references public.scelte_pagamento_cliente(tenant_id, id) on delete restrict,
  constraint contratti_preventivo_unique unique (tenant_id, preventivo_id),
  constraint contratti_validation_check check (
    stato = 'bozza'
    or (versione_corrente > 0 and scelta_pagamento_id is not null and validato_at is not null)
  )
);

create table public.contratto_versioni (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  contratto_id uuid not null,
  versione integer not null check (versione > 0),
  stato text not null check (stato in ('bozza', 'validata')),
  sezioni jsonb not null,
  pagamento_snapshot jsonb not null,
  contenuto_hash text not null,
  created_by uuid default auth.uid() references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  constraint contratto_versioni_contratto_tenant_fk
    foreign key (tenant_id, contratto_id)
    references public.contratti(tenant_id, id) on delete cascade,
  constraint contratto_versioni_unique unique (tenant_id, contratto_id, versione),
  constraint contratto_versioni_sezioni_check check (
    jsonb_typeof(sezioni) = 'array' and jsonb_array_length(sezioni) between 1 and 80
  )
);

create table public.documenti_cliente (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  preventivo_id uuid,
  cantiere_id uuid,
  contratto_id uuid,
  sal_id uuid,
  documento_originale_id uuid,
  tipo text not null check (tipo in (
    'contratto', 'sal', 'fattura', 'contabile_pagamento', 'ricevuta',
    'extra', 'verbale', 'altro'
  )),
  provenienza text not null check (provenienza in ('azienda', 'cliente')),
  stato text not null default 'pubblicato' check (stato in (
    'pubblicato', 'da_firmare', 'caricato_firmato', 'verificato', 'rifiutato', 'archiviato'
  )),
  titolo text not null check (char_length(btrim(titolo)) between 1 and 200),
  descrizione text check (descrizione is null or char_length(descrizione) <= 1000),
  bucket text check (bucket is null or bucket = 'documenti'),
  storage_path text,
  nome_file text,
  mime_type text,
  dimensione bigint check (dimensione is null or dimensione between 1 and 26214400),
  versione integer not null default 1 check (versione > 0),
  caricato_da uuid default auth.uid() references auth.users(id) on delete set null,
  verificato_da uuid references auth.users(id) on delete set null,
  verificato_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint documenti_cliente_tenant_id_id_key unique (tenant_id, id),
  constraint documenti_cliente_preventivo_tenant_fk
    foreign key (tenant_id, preventivo_id)
    references public.preventivi(tenant_id, id) on delete restrict,
  constraint documenti_cliente_cantiere_tenant_fk
    foreign key (tenant_id, cantiere_id)
    references public.cantieri(tenant_id, id) on delete restrict,
  constraint documenti_cliente_contratto_tenant_fk
    foreign key (tenant_id, contratto_id)
    references public.contratti(tenant_id, id) on delete restrict,
  constraint documenti_cliente_sal_tenant_fk
    foreign key (tenant_id, sal_id)
    references public.sal(tenant_id, id) on delete restrict,
  constraint documenti_cliente_originale_tenant_fk
    foreign key (tenant_id, documento_originale_id)
    references public.documenti_cliente(tenant_id, id) on delete restrict,
  constraint documenti_cliente_riferimento_check check (
    preventivo_id is not null or cantiere_id is not null
  ),
  constraint documenti_cliente_file_check check (
    (storage_path is null and bucket is null and tipo = 'contratto' and contratto_id is not null)
    or (storage_path is not null and bucket = 'documenti' and nome_file is not null)
  ),
  constraint documenti_cliente_path_check check (
    storage_path is null or storage_path like tenant_id::text || '/%'
  )
);

create unique index documenti_cliente_contratto_generato_uidx
  on public.documenti_cliente (tenant_id, contratto_id, versione)
  where tipo = 'contratto' and provenienza = 'azienda' and storage_path is null;
create index documenti_cliente_preventivo_idx
  on public.documenti_cliente (tenant_id, preventivo_id, created_at desc);
create index documenti_cliente_cantiere_idx
  on public.documenti_cliente (tenant_id, cantiere_id, created_at desc);

alter table public.preventivo_clienti enable row level security;
alter table public.preventivo_clienti force row level security;
alter table public.scelte_pagamento_cliente enable row level security;
alter table public.scelte_pagamento_cliente force row level security;
alter table public.contratti enable row level security;
alter table public.contratti force row level security;
alter table public.contratto_versioni enable row level security;
alter table public.contratto_versioni force row level security;
alter table public.documenti_cliente enable row level security;
alter table public.documenti_cliente force row level security;

create policy preventivo_clienti_read on public.preventivo_clienti
  for select to authenticated using (
    (select public.is_internal_member(tenant_id))
    or (user_id = (select auth.uid()) and attivo = true)
  );
create policy preventivo_clienti_internal_write on public.preventivo_clienti
  for all to authenticated
  using ((select public.is_internal_member(tenant_id)))
  with check ((select public.is_internal_member(tenant_id)));

create policy scelte_pagamento_read on public.scelte_pagamento_cliente
  for select to authenticated using (
    (select public.is_internal_member(tenant_id))
    or (user_id = (select auth.uid()) and (select public.is_preventivo_client(tenant_id, preventivo_id)))
  );
create policy scelte_pagamento_client_insert on public.scelte_pagamento_cliente
  for insert to authenticated with check (
    user_id = (select auth.uid())
    and (select public.is_preventivo_client(tenant_id, preventivo_id))
  );
create policy scelte_pagamento_client_update on public.scelte_pagamento_cliente
  for update to authenticated
  using (
    user_id = (select auth.uid())
    and (select public.is_preventivo_client(tenant_id, preventivo_id))
    and not exists (
      select 1 from public.contratti c
      where c.tenant_id = scelte_pagamento_cliente.tenant_id
        and c.preventivo_id = scelte_pagamento_cliente.preventivo_id
        and c.stato <> 'bozza'
    )
  )
  with check (
    user_id = (select auth.uid())
    and (select public.is_preventivo_client(tenant_id, preventivo_id))
  );
create policy scelte_pagamento_internal_write on public.scelte_pagamento_cliente
  for all to authenticated
  using ((select public.is_internal_member(tenant_id)))
  with check ((select public.is_internal_member(tenant_id)));

create policy contratti_read on public.contratti
  for select to authenticated using (
    (select public.is_internal_member(tenant_id))
    or (
      stato in ('validato', 'pubblicato', 'firmato')
      and (select public.is_preventivo_client(tenant_id, preventivo_id))
    )
  );
create policy contratti_internal_write on public.contratti
  for all to authenticated
  using ((select public.is_internal_member(tenant_id)))
  with check ((select public.is_internal_member(tenant_id)));

create policy contratto_versioni_read on public.contratto_versioni
  for select to authenticated using (
    (select public.is_internal_member(tenant_id))
    or (
      stato = 'validata' and exists (
        select 1 from public.contratti c
        where c.tenant_id = contratto_versioni.tenant_id
          and c.id = contratto_versioni.contratto_id
          and (select public.is_preventivo_client(c.tenant_id, c.preventivo_id))
      )
    )
  );
create policy contratto_versioni_internal_write on public.contratto_versioni
  for all to authenticated
  using ((select public.is_internal_member(tenant_id)))
  with check ((select public.is_internal_member(tenant_id)));

create policy documenti_cliente_read on public.documenti_cliente
  for select to authenticated using (
    (select public.is_internal_member(tenant_id))
    or (preventivo_id is not null and (select public.is_preventivo_client(tenant_id, preventivo_id)))
    or (cantiere_id is not null and (select public.is_cantiere_client(tenant_id, cantiere_id)))
  );
create policy documenti_cliente_internal_write on public.documenti_cliente
  for all to authenticated
  using ((select public.is_internal_member(tenant_id)))
  with check ((select public.is_internal_member(tenant_id)));
create policy documenti_cliente_client_insert on public.documenti_cliente
  for insert to authenticated with check (
    provenienza = 'cliente'
    and caricato_da = (select auth.uid())
    and storage_path is not null
    and (
      (preventivo_id is not null and (select public.is_preventivo_client(tenant_id, preventivo_id)))
      or (cantiere_id is not null and (select public.is_cantiere_client(tenant_id, cantiere_id)))
    )
  );

create or replace function public.collega_copia_firmata_cliente()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  righe_aggiornate integer;
begin
  if new.provenienza = 'cliente' and new.documento_originale_id is not null then
    update public.documenti_cliente
       set stato = 'caricato_firmato'
     where tenant_id = new.tenant_id
       and id = new.documento_originale_id
       and stato = 'da_firmare'
       and (
         (new.preventivo_id is not null and preventivo_id = new.preventivo_id)
         or (new.cantiere_id is not null and cantiere_id = new.cantiere_id)
       );
    get diagnostics righe_aggiornate = row_count;
    if righe_aggiornate <> 1 then
      raise exception 'Documento originale non coerente o non firmabile';
    end if;
  end if;
  return new;
end;
$$;

revoke execute on function public.collega_copia_firmata_cliente()
from public, anon, authenticated;

create trigger documenti_cliente_collega_firmato
  after insert on public.documenti_cliente
  for each row execute function public.collega_copia_firmata_cliente();

create trigger preventivo_clienti_touch before update on public.preventivo_clienti
  for each row execute function public.touch_updated_at();
create trigger scelte_pagamento_cliente_touch before update on public.scelte_pagamento_cliente
  for each row execute function public.touch_updated_at();
create trigger contratti_touch before update on public.contratti
  for each row execute function public.touch_updated_at();
create trigger documenti_cliente_touch before update on public.documenti_cliente
  for each row execute function public.touch_updated_at();

revoke all privileges on table
  public.preventivo_clienti, public.scelte_pagamento_cliente,
  public.contratti, public.contratto_versioni, public.documenti_cliente
from public, anon, authenticated;

grant select, insert, update, delete on table
  public.preventivo_clienti, public.scelte_pagamento_cliente,
  public.contratti, public.contratto_versioni, public.documenti_cliente
to authenticated;
grant all on table
  public.preventivo_clienti, public.scelte_pagamento_cliente,
  public.contratti, public.contratto_versioni, public.documenti_cliente
to service_role;

comment on table public.preventivo_clienti is
  'Accesso esplicito del cliente al preventivo prima dell apertura del cantiere.';
comment on table public.scelte_pagamento_cliente is
  'Scelta confermata dal cliente prima della validazione del contratto.';
comment on table public.contratti is
  'Testata del contratto con stato, versione e scelta pagamento congelata.';
comment on table public.contratto_versioni is
  'Snapshot append-only delle sezioni contrattuali editate e validate.';
comment on table public.documenti_cliente is
  'Fascicolo unico consultabile e scaricabile con originali e copie firmate.';

-- View definer intenzionale: espone solo i dati minimi del preventivo e filtra
-- auth.uid() prima di restituire righe. Evita di concedere ai client l intera
-- riga operativa di public.preventivi.
create or replace view public.portale_preventivi_contratti
with (security_barrier = true) as
select
  pc.tenant_id,
  pc.preventivo_id,
  p.numero as numero_preventivo,
  p.totale_documento,
  pc.user_id,
  coalesce(l.nome, cl.nome, pc.nome) as cliente_nome,
  sp.id as scelta_pagamento_id,
  sp.tipo as scelta_pagamento_tipo,
  sp.confermata_at as scelta_pagamento_confermata_at,
  c.id as contratto_id,
  c.numero as numero_contratto,
  c.stato as contratto_stato,
  c.versione_corrente,
  c.validato_at,
  c.pubblicato_at
from public.preventivo_clienti pc
join public.preventivi p
  on p.tenant_id = pc.tenant_id and p.id = pc.preventivo_id
left join public.leads l
  on l.tenant_id = p.tenant_id and l.id = p.lead_id
left join public.clienti cl
  on cl.tenant_id = p.tenant_id and cl.id = p.cliente_id
left join public.scelte_pagamento_cliente sp
  on sp.tenant_id = pc.tenant_id
 and sp.preventivo_id = pc.preventivo_id
 and sp.user_id = pc.user_id
 and sp.stato = 'confermata'
left join public.contratti c
  on c.tenant_id = p.tenant_id and c.preventivo_id = p.id
where pc.user_id = (select auth.uid()) and pc.attivo = true;

revoke all privileges on table public.portale_preventivi_contratti
from public, anon;
grant select on table public.portale_preventivi_contratti
to authenticated, service_role;
