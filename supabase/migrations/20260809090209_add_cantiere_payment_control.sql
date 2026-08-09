-- Controllo economico contrattuale per cantiere.
-- Separa il valore tecnico dei SAL dalle date finanziarie concordate, ma
-- mantiene collegamenti espliciti e auditabili fra contratto, rate e incassi.

create table public.piani_pagamento (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  cantiere_id uuid not null,
  preventivo_id uuid not null,
  stato text not null default 'attivo'
    check (stato in ('bozza', 'attivo', 'sospeso', 'completato')),
  totale_contratto numeric(14,2) not null check (totale_contratto > 0),
  cliente_nome text not null check (length(btrim(cliente_nome)) between 2 and 200),
  cliente_email text,
  cliente_telefono text,
  email_automatica boolean not null default true,
  whatsapp_automatico boolean not null default false,
  whatsapp_consenso_at timestamptz,
  giorni_preavviso integer[] not null default array[7, 1, 0],
  contratto_confermato_at timestamptz not null default now(),
  created_by uuid default auth.uid() references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint piani_pagamento_tenant_id_id_key unique (tenant_id, id),
  constraint piani_pagamento_cantiere_tenant_fk
    foreign key (tenant_id, cantiere_id)
    references public.cantieri(tenant_id, id) on delete restrict,
  constraint piani_pagamento_preventivo_tenant_fk
    foreign key (tenant_id, preventivo_id)
    references public.preventivi(tenant_id, id) on delete restrict,
  constraint piani_pagamento_preventivo_unique unique (tenant_id, preventivo_id),
  constraint piani_pagamento_preavviso_check check (
    cardinality(giorni_preavviso) between 1 and 10
    and array_position(giorni_preavviso, null) is null
    and 0 <= all(giorni_preavviso)
  ),
  constraint piani_pagamento_whatsapp_consenso_check check (
    whatsapp_automatico = false or whatsapp_consenso_at is not null
  )
);

create unique index piani_pagamento_cantiere_attivo_uidx
  on public.piani_pagamento (tenant_id, cantiere_id)
  where stato in ('bozza', 'attivo', 'sospeso');
create index piani_pagamento_tenant_stato_idx
  on public.piani_pagamento (tenant_id, stato, cantiere_id);

alter table public.incassi
  drop constraint incassi_stato_check,
  add column piano_pagamento_id uuid,
  add column numero_rata integer,
  add column tipo_rata text,
  add column percentuale numeric(6,3),
  add column modalita_pagamento text,
  add constraint incassi_piano_pagamento_tenant_fk
    foreign key (tenant_id, piano_pagamento_id)
    references public.piani_pagamento(tenant_id, id) on delete restrict,
  add constraint incassi_numero_rata_check
    check (numero_rata is null or numero_rata > 0),
  add constraint incassi_tipo_rata_check
    check (tipo_rata is null or tipo_rata in ('acconto', 'sal', 'saldo', 'extra')),
  add constraint incassi_percentuale_check
    check (percentuale is null or percentuale between 0 and 100),
  add constraint incassi_stato_check
    check (stato in ('previsto', 'parziale', 'incassato', 'annullato'));

create unique index incassi_piano_numero_rata_uidx
  on public.incassi (tenant_id, piano_pagamento_id, numero_rata)
  where piano_pagamento_id is not null;

create table public.pagamenti_cliente (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  cantiere_id uuid not null,
  incasso_id uuid not null,
  importo numeric(14,2) not null check (importo > 0),
  data_pagamento date not null default current_date,
  metodo text,
  riferimento text,
  note text,
  registrato_da uuid default auth.uid() references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  constraint pagamenti_cliente_tenant_id_id_key unique (tenant_id, id),
  constraint pagamenti_cliente_cantiere_tenant_fk
    foreign key (tenant_id, cantiere_id)
    references public.cantieri(tenant_id, id) on delete restrict,
  constraint pagamenti_cliente_incasso_tenant_fk
    foreign key (tenant_id, incasso_id)
    references public.incassi(tenant_id, id) on delete restrict
);

create index pagamenti_cliente_incasso_idx
  on public.pagamenti_cliente (tenant_id, incasso_id, data_pagamento, created_at);
create index pagamenti_cliente_cantiere_idx
  on public.pagamenti_cliente (tenant_id, cantiere_id, data_pagamento desc);

create table public.extra_cantiere (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  cantiere_id uuid not null,
  sal_id uuid,
  incasso_id uuid,
  numero integer not null,
  titolo text not null check (length(btrim(titolo)) between 2 and 200),
  descrizione text not null check (length(btrim(descrizione)) between 2 and 2000),
  imponibile numeric(14,2) not null check (imponibile > 0),
  iva_percentuale numeric(5,2) not null default 10 check (iva_percentuale between 0 and 100),
  totale numeric(14,2) generated always as
    (round(imponibile + imponibile * iva_percentuale / 100, 2)) stored,
  data_scadenza date,
  stato text not null default 'bozza'
    check (stato in ('bozza', 'inviato', 'approvato', 'rifiutato', 'annullato')),
  created_by uuid default auth.uid() references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint extra_cantiere_tenant_id_id_key unique (tenant_id, id),
  constraint extra_cantiere_numero_unique unique (tenant_id, cantiere_id, numero),
  constraint extra_cantiere_cantiere_tenant_fk
    foreign key (tenant_id, cantiere_id)
    references public.cantieri(tenant_id, id) on delete restrict,
  constraint extra_cantiere_sal_tenant_fk
    foreign key (tenant_id, sal_id)
    references public.sal(tenant_id, id) on delete set null (sal_id),
  constraint extra_cantiere_incasso_tenant_fk
    foreign key (tenant_id, incasso_id)
    references public.incassi(tenant_id, id) on delete set null (incasso_id)
);

create index extra_cantiere_cantiere_stato_idx
  on public.extra_cantiere (tenant_id, cantiere_id, stato, numero desc);

create table public.documenti_economici (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  cantiere_id uuid not null,
  tipo text not null check (tipo in ('riepilogo_sal', 'autorizzazione_extra')),
  sal_id uuid,
  extra_id uuid,
  stato text not null default 'generato'
    check (stato in ('generato', 'inviato', 'sottoscritto', 'rifiutato')),
  snapshot jsonb not null default '{}'::jsonb,
  documento_hash text not null,
  firmato_da uuid references auth.users(id) on delete set null,
  firmatario_nome text,
  firma_ip inet,
  firma_user_agent text,
  firmato_at timestamptz,
  created_by uuid default auth.uid() references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint documenti_economici_tenant_id_id_key unique (tenant_id, id),
  constraint documenti_economici_cantiere_tenant_fk
    foreign key (tenant_id, cantiere_id)
    references public.cantieri(tenant_id, id) on delete restrict,
  constraint documenti_economici_sal_tenant_fk
    foreign key (tenant_id, sal_id)
    references public.sal(tenant_id, id) on delete restrict,
  constraint documenti_economici_extra_tenant_fk
    foreign key (tenant_id, extra_id)
    references public.extra_cantiere(tenant_id, id) on delete restrict,
  constraint documenti_economici_riferimento_check check (
    (tipo = 'riepilogo_sal' and sal_id is not null and extra_id is null)
    or
    (tipo = 'autorizzazione_extra' and extra_id is not null and sal_id is null)
  ),
  constraint documenti_economici_firma_check check (
    stato <> 'sottoscritto'
    or (firmato_at is not null and firmatario_nome is not null)
  )
);

create unique index documenti_economici_sal_uidx
  on public.documenti_economici (tenant_id, sal_id)
  where sal_id is not null;
create unique index documenti_economici_extra_uidx
  on public.documenti_economici (tenant_id, extra_id)
  where extra_id is not null;

create table public.documenti_economici_firme (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  cantiere_id uuid not null,
  documento_id uuid not null,
  user_id uuid not null default auth.uid() references auth.users(id) on delete restrict,
  decisione text not null check (decisione in ('sottoscritto', 'rifiutato')),
  firmatario_nome text not null check (length(btrim(firmatario_nome)) between 2 and 200),
  ip inet not null,
  user_agent text,
  created_at timestamptz not null default now(),
  constraint documenti_economici_firme_tenant_id_id_key unique (tenant_id, id),
  constraint documenti_economici_firme_cantiere_tenant_fk
    foreign key (tenant_id, cantiere_id)
    references public.cantieri(tenant_id, id) on delete restrict,
  constraint documenti_economici_firme_documento_tenant_fk
    foreign key (tenant_id, documento_id)
    references public.documenti_economici(tenant_id, id) on delete restrict,
  constraint documenti_economici_firme_unique unique (tenant_id, documento_id, user_id)
);

create index documenti_economici_firme_documento_idx
  on public.documenti_economici_firme (tenant_id, documento_id, created_at desc);

create table public.notifiche_pagamento (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  cantiere_id uuid not null,
  incasso_id uuid not null,
  canale text not null check (canale in ('email', 'whatsapp')),
  tipo text not null check (tipo in ('preavviso', 'scadenza', 'sollecito', 'manuale')),
  destinatario text not null,
  programmata_per date not null,
  stato text not null default 'programmata'
    check (stato in ('programmata', 'in_corso', 'inviata', 'fallita', 'saltata')),
  tentativi integer not null default 0 check (tentativi >= 0),
  provider_id text,
  errore text,
  payload jsonb not null default '{}'::jsonb,
  inviata_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint notifiche_pagamento_tenant_id_id_key unique (tenant_id, id),
  constraint notifiche_pagamento_cantiere_tenant_fk
    foreign key (tenant_id, cantiere_id)
    references public.cantieri(tenant_id, id) on delete restrict,
  constraint notifiche_pagamento_incasso_tenant_fk
    foreign key (tenant_id, incasso_id)
    references public.incassi(tenant_id, id) on delete restrict,
  constraint notifiche_pagamento_idempotenza_unique
    unique (tenant_id, incasso_id, canale, tipo, programmata_per)
);

create index notifiche_pagamento_da_inviare_idx
  on public.notifiche_pagamento (programmata_per, created_at)
  where stato in ('programmata', 'fallita');

do $$
declare table_name text;
begin
  foreach table_name in array array[
    'piani_pagamento', 'pagamenti_cliente', 'extra_cantiere',
    'documenti_economici', 'documenti_economici_firme', 'notifiche_pagamento'
  ] loop
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
  end loop;
end $$;

drop policy documenti_economici_firme_finance_read
  on public.documenti_economici_firme;
drop policy documenti_economici_firme_finance_insert
  on public.documenti_economici_firme;
drop policy documenti_economici_firme_finance_update
  on public.documenti_economici_firme;

create policy documenti_economici_firme_read
  on public.documenti_economici_firme for select to authenticated
  using (
    (select public.has_role(
      tenant_id, array['owner','admin']::public.tenant_role[]
    ))
    or (
      user_id = (select auth.uid())
      and (select public.is_cantiere_client(tenant_id, cantiere_id))
    )
  );
create policy documenti_economici_firme_client_insert
  on public.documenti_economici_firme for insert to authenticated
  with check (
    user_id = (select auth.uid())
    and (select public.is_cantiere_client(tenant_id, cantiere_id))
    and exists (
      select 1 from public.documenti_economici d
      where d.tenant_id = documenti_economici_firme.tenant_id
        and d.cantiere_id = documenti_economici_firme.cantiere_id
        and d.id = documenti_economici_firme.documento_id
        and d.stato in ('generato', 'inviato')
    )
  );

create or replace function public.applica_firma_documento_economico()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  doc public.documenti_economici%rowtype;
  extra_row public.extra_cantiere%rowtype;
  nuovo_incasso uuid;
  piano_attivo uuid;
begin
  select * into doc
  from public.documenti_economici
  where tenant_id = new.tenant_id and id = new.documento_id
  for update;

  update public.documenti_economici
  set stato = new.decisione,
      firmato_da = new.user_id,
      firmatario_nome = new.firmatario_nome,
      firma_ip = new.ip,
      firma_user_agent = new.user_agent,
      firmato_at = new.created_at
  where tenant_id = new.tenant_id and id = new.documento_id;

  if doc.tipo = 'autorizzazione_extra' then
    update public.extra_cantiere
    set stato = case
      when new.decisione = 'sottoscritto' then 'approvato'
      else 'rifiutato'
    end
    where tenant_id = new.tenant_id and id = doc.extra_id
    returning * into extra_row;

    if new.decisione = 'sottoscritto'
       and extra_row.data_scadenza is not null
       and extra_row.incasso_id is null then
      select id into piano_attivo
      from public.piani_pagamento
      where tenant_id = extra_row.tenant_id
        and cantiere_id = extra_row.cantiere_id
        and stato = 'attivo'
      order by created_at desc limit 1;

      insert into public.incassi (
        tenant_id, cantiere_id, sal_id, descrizione, importo,
        data_prevista, stato, tipo_rata, numero_rata, piano_pagamento_id
      ) values (
        extra_row.tenant_id, extra_row.cantiere_id, extra_row.sal_id,
        'Extra ' || lpad(extra_row.numero::text, 2, '0') || ' - ' || extra_row.titolo,
        extra_row.totale, extra_row.data_scadenza, 'previsto', 'extra',
        1000 + extra_row.numero, piano_attivo
      ) returning id into nuovo_incasso;

      update public.extra_cantiere set incasso_id = nuovo_incasso
      where tenant_id = extra_row.tenant_id and id = extra_row.id;

      insert into public.scadenze (
        tenant_id, cantiere_id, incasso_id, tipo, titolo, importo, data_scadenza
      ) values (
        extra_row.tenant_id, extra_row.cantiere_id, nuovo_incasso, 'incasso',
        'Pagamento extra ' || lpad(extra_row.numero::text, 2, '0'),
        extra_row.totale, extra_row.data_scadenza
      );
    end if;
  end if;
  return new;
end;
$$;

revoke execute on function public.applica_firma_documento_economico()
  from public, anon, authenticated;

create trigger documenti_economici_firme_apply
  after insert on public.documenti_economici_firme
  for each row execute function public.applica_firma_documento_economico();

create trigger piani_pagamento_touch before update on public.piani_pagamento
  for each row execute function public.touch_updated_at();
create trigger extra_cantiere_touch before update on public.extra_cantiere
  for each row execute function public.touch_updated_at();
create trigger documenti_economici_touch before update on public.documenti_economici
  for each row execute function public.touch_updated_at();
create trigger notifiche_pagamento_touch before update on public.notifiche_pagamento
  for each row execute function public.touch_updated_at();

revoke all privileges on table
  public.piani_pagamento,
  public.pagamenti_cliente,
  public.extra_cantiere,
  public.documenti_economici,
  public.documenti_economici_firme,
  public.notifiche_pagamento
from public, anon, authenticated;

grant select, insert, update on table
  public.piani_pagamento,
  public.pagamenti_cliente,
  public.extra_cantiere,
  public.documenti_economici,
  public.documenti_economici_firme,
  public.notifiche_pagamento
to authenticated;

grant all on table
  public.piani_pagamento,
  public.pagamenti_cliente,
  public.extra_cantiere,
  public.documenti_economici,
  public.documenti_economici_firme,
  public.notifiche_pagamento
to service_role;

comment on table public.piani_pagamento is
  'Snapshot del piano finanziario concordato dopo accettazione del contratto.';
comment on table public.pagamenti_cliente is
  'Movimenti reali ricevuti dal cliente e allocati a una rata prevista.';
comment on table public.extra_cantiere is
  'Lavorazioni extra con approvazione separata e valore economico immutabile alla firma.';
comment on table public.documenti_economici is
  'Snapshot firmabili di SAL ed extra con hash e audit della sottoscrizione.';
comment on table public.documenti_economici_firme is
  'Audit append-only della sottoscrizione o del rifiuto da parte del cliente.';
comment on table public.notifiche_pagamento is
  'Coda e registro idempotente dei promemoria email e WhatsApp.';

create or replace view public.portale_pagamenti_cliente
with (security_barrier = true) as
select
  i.tenant_id,
  i.cantiere_id,
  i.id as incasso_id,
  i.numero_rata,
  i.tipo_rata,
  i.descrizione,
  i.importo,
  i.data_prevista,
  i.stato,
  i.modalita_pagamento,
  i.sal_id,
  coalesce(sum(pc.importo), 0)::numeric(14,2) as pagato,
  (i.importo - coalesce(sum(pc.importo), 0))::numeric(14,2) as residuo
from public.cantiere_clienti cc
join public.incassi i
  on i.tenant_id = cc.tenant_id and i.cantiere_id = cc.cantiere_id
left join public.pagamenti_cliente pc
  on pc.tenant_id = i.tenant_id and pc.incasso_id = i.id
where cc.user_id = (select auth.uid())
  and cc.attivo = true
  and i.stato <> 'annullato'
group by i.id;

create or replace view public.portale_documenti_economici
with (security_barrier = true) as
select
  d.tenant_id,
  d.cantiere_id,
  d.id as documento_id,
  d.tipo,
  d.sal_id,
  d.extra_id,
  d.stato,
  d.snapshot,
  d.documento_hash,
  d.created_at,
  exists (
    select 1 from public.documenti_economici_firme f
    where f.tenant_id = d.tenant_id
      and f.documento_id = d.id
      and f.user_id = (select auth.uid())
  ) as gia_deciso
from public.cantiere_clienti cc
join public.documenti_economici d
  on d.tenant_id = cc.tenant_id and d.cantiere_id = cc.cantiere_id
where cc.user_id = (select auth.uid())
  and cc.attivo = true
  and d.stato in ('inviato', 'sottoscritto', 'rifiutato');

revoke all privileges on table
  public.portale_pagamenti_cliente,
  public.portale_documenti_economici
from public, anon;
grant select on table
  public.portale_pagamenti_cliente,
  public.portale_documenti_economici
to authenticated, service_role;
