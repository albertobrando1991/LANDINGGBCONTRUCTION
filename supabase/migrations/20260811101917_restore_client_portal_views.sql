-- Ripristina le due viste cliente risultate assenti sul progetto remoto,
-- nonostante la migration economica 20260809090209 fosse in history.
-- Le viste espongono soltanto righe collegate all'utente autenticato.

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

comment on view public.portale_pagamenti_cliente is
  'Pagamenti visibili soltanto al cliente associato al cantiere.';

comment on view public.portale_documenti_economici is
  'Documenti economici visibili soltanto al cliente associato al cantiere.';
