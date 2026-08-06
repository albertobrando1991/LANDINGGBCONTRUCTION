-- ============================================================
-- Fase 5 - Economics cantiere
-- Controllo gestionale interno, senza fatturazione elettronica.
-- I dati finanziari sono limitati ai ruoli owner/admin.
-- ============================================================

create table public.fornitori (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  ragione_sociale text not null check (length(btrim(ragione_sociale)) between 2 and 200),
  piva text,
  codice_fiscale text,
  email text,
  telefono text,
  indirizzo text,
  note text,
  attivo boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint fornitori_tenant_id_id_key unique (tenant_id, id),
  constraint fornitori_piva_non_vuota check (piva is null or length(btrim(piva)) > 0),
  constraint fornitori_email_non_vuota check (email is null or length(btrim(email)) > 0)
);

create unique index fornitori_tenant_piva_uidx
  on public.fornitori (tenant_id, lower(piva))
  where piva is not null;
create index fornitori_tenant_attivo_nome_idx
  on public.fornitori (tenant_id, attivo, ragione_sociale);

create table public.spese (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  cantiere_id uuid not null,
  fornitore_id uuid,
  categoria text not null default 'altro'
    check (categoria in (
      'materiali', 'manodopera', 'subappalto', 'noleggio',
      'trasporto', 'utenze', 'professionisti', 'altro'
    )),
  descrizione text not null check (length(btrim(descrizione)) between 2 and 500),
  numero_documento text,
  data_documento date not null default current_date,
  imponibile numeric(14,2) not null check (imponibile >= 0),
  iva_percentuale numeric(5,2) not null default 22
    check (iva_percentuale between 0 and 100),
  iva_importo numeric(14,2)
    generated always as (round(imponibile * iva_percentuale / 100, 2)) stored,
  totale numeric(14,2)
    generated always as (
      round(imponibile + (imponibile * iva_percentuale / 100), 2)
    ) stored,
  stato text not null default 'registrata'
    check (stato in ('registrata', 'pagata', 'annullata')),
  data_pagamento date,
  allegato_path text,
  note text,
  created_by uuid default auth.uid() references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint spese_tenant_id_id_key unique (tenant_id, id),
  constraint spese_cantiere_tenant_fk
    foreign key (tenant_id, cantiere_id)
    references public.cantieri(tenant_id, id) on delete restrict,
  constraint spese_fornitore_tenant_fk
    foreign key (tenant_id, fornitore_id)
    references public.fornitori(tenant_id, id)
    on delete set null (fornitore_id),
  constraint spese_pagata_data_check
    check (stato <> 'pagata' or data_pagamento is not null),
  constraint spese_allegato_tenant_check
    check (
      allegato_path is null
      or split_part(allegato_path, '/', 1) = tenant_id::text
    )
);

create index spese_tenant_cantiere_data_idx
  on public.spese (tenant_id, cantiere_id, data_documento desc, created_at desc);
create index spese_tenant_fornitore_idx
  on public.spese (tenant_id, fornitore_id)
  where fornitore_id is not null;
create index spese_created_by_idx on public.spese (created_by)
  where created_by is not null;

create table public.incassi (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  cantiere_id uuid not null,
  sal_id uuid,
  descrizione text not null check (length(btrim(descrizione)) between 2 and 500),
  importo numeric(14,2) not null check (importo > 0),
  data_prevista date not null,
  data_incasso date,
  stato text not null default 'previsto'
    check (stato in ('previsto', 'incassato', 'annullato')),
  metodo text,
  note text,
  created_by uuid default auth.uid() references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint incassi_tenant_id_id_key unique (tenant_id, id),
  constraint incassi_cantiere_tenant_fk
    foreign key (tenant_id, cantiere_id)
    references public.cantieri(tenant_id, id) on delete restrict,
  constraint incassi_sal_tenant_fk
    foreign key (tenant_id, sal_id)
    references public.sal(tenant_id, id)
    on delete set null (sal_id),
  constraint incassi_incassato_data_check
    check (stato <> 'incassato' or data_incasso is not null)
);

create index incassi_tenant_cantiere_data_idx
  on public.incassi (tenant_id, cantiere_id, data_prevista desc, created_at desc);
create index incassi_tenant_sal_idx
  on public.incassi (tenant_id, sal_id) where sal_id is not null;
create index incassi_created_by_idx on public.incassi (created_by)
  where created_by is not null;
create index incassi_aperti_scadenza_idx
  on public.incassi (tenant_id, data_prevista)
  where stato = 'previsto';

create table public.scadenze (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  cantiere_id uuid not null,
  spesa_id uuid,
  incasso_id uuid,
  tipo text not null check (tipo in ('incasso', 'pagamento', 'adempimento')),
  titolo text not null check (length(btrim(titolo)) between 2 and 300),
  importo numeric(14,2) check (importo is null or importo >= 0),
  data_scadenza date not null,
  stato text not null default 'aperta'
    check (stato in ('aperta', 'completata', 'annullata')),
  completata_at timestamptz,
  note text,
  created_by uuid default auth.uid() references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint scadenze_tenant_id_id_key unique (tenant_id, id),
  constraint scadenze_cantiere_tenant_fk
    foreign key (tenant_id, cantiere_id)
    references public.cantieri(tenant_id, id) on delete restrict,
  constraint scadenze_spesa_tenant_fk
    foreign key (tenant_id, spesa_id)
    references public.spese(tenant_id, id)
    on delete set null (spesa_id),
  constraint scadenze_incasso_tenant_fk
    foreign key (tenant_id, incasso_id)
    references public.incassi(tenant_id, id)
    on delete set null (incasso_id),
  constraint scadenze_riferimento_unico_check
    check (num_nonnulls(spesa_id, incasso_id) <= 1),
  constraint scadenze_completata_data_check
    check (stato <> 'completata' or completata_at is not null)
);

create index scadenze_tenant_cantiere_data_idx
  on public.scadenze (tenant_id, cantiere_id, data_scadenza, created_at);
create index scadenze_aperte_data_idx
  on public.scadenze (tenant_id, data_scadenza)
  where stato = 'aperta';
create index scadenze_tenant_spesa_idx
  on public.scadenze (tenant_id, spesa_id) where spesa_id is not null;
create index scadenze_tenant_incasso_idx
  on public.scadenze (tenant_id, incasso_id) where incasso_id is not null;
create index scadenze_created_by_idx on public.scadenze (created_by)
  where created_by is not null;

do $$
declare table_name text;
begin
  foreach table_name in array array['fornitori', 'spese', 'incassi', 'scadenze']
  loop
    execute format('alter table public.%I enable row level security', table_name);
    execute format('alter table public.%I force row level security', table_name);
    execute format(
      'create policy %I on public.%I for select to authenticated using '
      '((select public.has_role(tenant_id, array[''owner'',''admin'']::public.tenant_role[])))',
      table_name || '_finance_read', table_name
    );
    execute format(
      'create policy %I on public.%I for insert to authenticated with check '
      '((select public.has_role(tenant_id, array[''owner'',''admin'']::public.tenant_role[])))',
      table_name || '_finance_insert', table_name
    );
    execute format(
      'create policy %I on public.%I for update to authenticated using '
      '((select public.has_role(tenant_id, array[''owner'',''admin'']::public.tenant_role[]))) '
      'with check ((select public.has_role(tenant_id, array[''owner'',''admin'']::public.tenant_role[])))',
      table_name || '_finance_update', table_name
    );
    execute format(
      'create policy %I on public.%I for delete to authenticated using '
      '((select public.has_role(tenant_id, array[''owner'',''admin'']::public.tenant_role[])))',
      table_name || '_finance_delete', table_name
    );
  end loop;
end $$;

create trigger fornitori_touch before update on public.fornitori
  for each row execute function public.touch_updated_at();
create trigger spese_touch before update on public.spese
  for each row execute function public.touch_updated_at();
create trigger incassi_touch before update on public.incassi
  for each row execute function public.touch_updated_at();
create trigger scadenze_touch before update on public.scadenze
  for each row execute function public.touch_updated_at();

create or replace view public.marginalita_cantiere
with (security_invoker = true) as
with ricavi as (
  select s.tenant_id, s.cantiere_id,
         coalesce(sum(r.importo_periodo), 0)::numeric(14,2) as ricavi_maturati
  from public.sal s
  join public.sal_righe r
    on r.tenant_id = s.tenant_id and r.sal_id = s.id
  where s.stato in ('emesso', 'approvato')
  group by s.tenant_id, s.cantiere_id
), costi as (
  select tenant_id, cantiere_id,
         coalesce(sum(totale), 0)::numeric(14,2) as costi_registrati,
         coalesce(sum(totale) filter (where stato = 'pagata'), 0)::numeric(14,2)
           as costi_pagati
  from public.spese
  where stato <> 'annullata'
  group by tenant_id, cantiere_id
), movimenti as (
  select tenant_id, cantiere_id,
         coalesce(sum(importo) filter (where stato = 'incassato'), 0)::numeric(14,2)
           as incassato,
         coalesce(sum(importo) filter (where stato = 'previsto'), 0)::numeric(14,2)
           as da_incassare
  from public.incassi
  where stato <> 'annullato'
  group by tenant_id, cantiere_id
), agenda as (
  select tenant_id, cantiere_id,
         count(*) filter (where stato = 'aperta') as scadenze_aperte,
         count(*) filter (
           where stato = 'aperta' and data_scadenza < current_date
         ) as scadenze_scadute
  from public.scadenze
  group by tenant_id, cantiere_id
)
select
  c.tenant_id,
  c.id as cantiere_id,
  c.cliente,
  c.stato as stato_cantiere,
  c.importo as budget_contrattuale,
  coalesce(r.ricavi_maturati, 0)::numeric(14,2) as ricavi_maturati,
  coalesce(k.costi_registrati, 0)::numeric(14,2) as costi_registrati,
  coalesce(k.costi_pagati, 0)::numeric(14,2) as costi_pagati,
  coalesce(m.incassato, 0)::numeric(14,2) as incassato,
  coalesce(m.da_incassare, 0)::numeric(14,2) as da_incassare,
  (coalesce(r.ricavi_maturati, 0) - coalesce(k.costi_registrati, 0))
    ::numeric(14,2) as margine,
  case
    when coalesce(r.ricavi_maturati, 0) = 0 then null
    else round(
      ((coalesce(r.ricavi_maturati, 0) - coalesce(k.costi_registrati, 0))
        / r.ricavi_maturati) * 100,
      2
    )
  end as margine_percentuale,
  coalesce(a.scadenze_aperte, 0) as scadenze_aperte,
  coalesce(a.scadenze_scadute, 0) as scadenze_scadute
from public.cantieri c
left join ricavi r on r.tenant_id = c.tenant_id and r.cantiere_id = c.id
left join costi k on k.tenant_id = c.tenant_id and k.cantiere_id = c.id
left join movimenti m on m.tenant_id = c.tenant_id and m.cantiere_id = c.id
left join agenda a on a.tenant_id = c.tenant_id and a.cantiere_id = c.id
where public.has_role(
  c.tenant_id,
  array['owner','admin']::public.tenant_role[]
);

comment on view public.marginalita_cantiere is
  'Ricavi maturati da SAL emessi/approvati meno spese registrate per cantiere.';

revoke all privileges on table
  public.fornitori, public.spese, public.incassi, public.scadenze,
  public.marginalita_cantiere
from public, anon, authenticated;

grant select, insert, update, delete on table
  public.fornitori, public.spese, public.incassi, public.scadenze
to authenticated;
grant select on table public.marginalita_cantiere to authenticated;

grant all on table
  public.fornitori, public.spese, public.incassi, public.scadenze
to service_role;
grant select on table public.marginalita_cantiere to service_role;

comment on table public.fornitori is 'Anagrafica fornitori interna del tenant.';
comment on table public.spese is 'Costi di cantiere con snapshot IVA e allegato privato opzionale.';
comment on table public.incassi is 'Incassi previsti o ricevuti, associabili a un SAL.';
comment on table public.scadenze is 'Agenda economica e amministrativa del cantiere.';
