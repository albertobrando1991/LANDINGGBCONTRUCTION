-- Pubblica automaticamente nel fascicolo cliente ogni preventivo effettivamente
-- inviato. Il PDF resta generato dallo snapshot del preventivo e non richiede una
-- copia duplicata nello storage.

alter table public.documenti_cliente
  drop constraint if exists documenti_cliente_tipo_check;
alter table public.documenti_cliente
  add constraint documenti_cliente_tipo_check check (tipo in (
    'preventivo', 'contratto', 'sal', 'fattura', 'contabile_pagamento',
    'ricevuta', 'extra', 'verbale', 'altro'
  ));

alter table public.documenti_cliente
  drop constraint if exists documenti_cliente_file_check;
alter table public.documenti_cliente
  add constraint documenti_cliente_file_check check (
    (
      storage_path is null
      and bucket is null
      and (
        (tipo = 'preventivo' and preventivo_id is not null)
        or (tipo = 'contratto' and contratto_id is not null)
      )
    )
    or (storage_path is not null and bucket = 'documenti' and nome_file is not null)
  );

create unique index if not exists documenti_cliente_preventivo_generato_uidx
  on public.documenti_cliente (tenant_id, preventivo_id)
  where tipo = 'preventivo' and provenienza = 'azienda' and storage_path is null;

create or replace function public.pubblica_preventivo_inviato_nel_portale()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
  if new.stato <> 'bozza' and old.stato = 'bozza' then
    insert into public.documenti_cliente (
      tenant_id, preventivo_id, tipo, provenienza, stato, titolo,
      versione, created_at, updated_at
    ) values (
      new.tenant_id, new.id, 'preventivo', 'azienda', 'pubblicato',
      'Preventivo ' || new.numero, 1,
      coalesce(new.inviato_at, now()), coalesce(new.inviato_at, now())
    )
    on conflict (tenant_id, preventivo_id)
      where tipo = 'preventivo'
        and provenienza = 'azienda'
        and storage_path is null
    do update set
      stato = 'pubblicato',
      titolo = excluded.titolo,
      updated_at = excluded.updated_at;
  end if;
  return new;
end;
$$;

revoke execute on function public.pubblica_preventivo_inviato_nel_portale()
from public, anon, authenticated;

drop trigger if exists preventivi_pubblica_documento_cliente on public.preventivi;
create trigger preventivi_pubblica_documento_cliente
  after update of stato on public.preventivi
  for each row execute function public.pubblica_preventivo_inviato_nel_portale();

insert into public.documenti_cliente (
  tenant_id, preventivo_id, tipo, provenienza, stato, titolo,
  versione, created_at, updated_at
)
select
  p.tenant_id, p.id, 'preventivo', 'azienda', 'pubblicato',
  'Preventivo ' || p.numero, 1,
  coalesce(p.inviato_at, p.updated_at, p.created_at),
  coalesce(p.inviato_at, p.updated_at, p.created_at)
from public.preventivi p
where p.stato <> 'bozza'
on conflict (tenant_id, preventivo_id)
  where tipo = 'preventivo'
    and provenienza = 'azienda'
    and storage_path is null
do update set
  stato = 'pubblicato',
  titolo = excluded.titolo;

-- View dedicata: evita di esporre le colonne operative del preventivo nella
-- dashboard e rende il payload completo soltanto al cliente assegnato.
create or replace view public.portale_preventivi_pdf
with (security_barrier = true) as
select
  pc.tenant_id,
  p.id as preventivo_id,
  p.numero,
  p.stato,
  p.created_at,
  p.validita_giorni,
  p.totale_imponibile,
  p.sconto_percentuale,
  p.iva_percentuale,
  p.totale_iva,
  p.totale_documento,
  p.snapshot_voci,
  p.superficie_mq,
  p.durate_fasi,
  p.note,
  coalesce(l.nome, cl.nome, pc.nome) as cliente_nome,
  coalesce(l.email, cl.email, pc.email) as cliente_email,
  coalesce(l.telefono, cl.telefono) as cliente_telefono,
  coalesce(l.indirizzo, cl.indirizzo) as cliente_indirizzo,
  coalesce(l.citta, cl.citta) as cliente_citta,
  ca.indirizzo as cantiere_indirizzo,
  t.piva as tenant_piva
from public.preventivo_clienti pc
join public.preventivi p
  on p.tenant_id = pc.tenant_id and p.id = pc.preventivo_id
join public.tenants t on t.id = p.tenant_id
left join public.leads l
  on l.tenant_id = p.tenant_id and l.id = p.lead_id
left join public.clienti cl
  on cl.tenant_id = p.tenant_id and cl.id = p.cliente_id
left join public.computi co
  on co.tenant_id = p.tenant_id and co.id = p.computo_id
left join public.cantieri ca
  on ca.tenant_id = p.tenant_id and ca.id = co.cantiere_id
where pc.user_id = (select auth.uid())
  and pc.attivo = true
  and p.stato <> 'bozza';

revoke all privileges on table public.portale_preventivi_pdf
from public, anon;
grant select on table public.portale_preventivi_pdf
to authenticated, service_role;

comment on view public.portale_preventivi_pdf is
  'Payload PDF del preventivo inviato, leggibile soltanto dal cliente assegnato.';
