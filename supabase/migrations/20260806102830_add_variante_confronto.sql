-- ============================================================
-- Fase 4 - Varianti e quadro di confronto
-- Ogni voce copiata conserva il riferimento alla voce contrattuale.
-- La vista applica le RLS delle tabelle base tramite security_invoker.
-- ============================================================

alter table public.computo_voci
  add column if not exists parent_voce_id uuid;

-- Le vecchie copie ordinarie non sono varianti contrattuali.
update public.computi
   set parent_computo_id = null
 where tipo <> 'variante'
   and parent_computo_id is not null;

-- Backfill deterministico per eventuali varianti create prima della Fase 4.
update public.computo_voci variante_voce
   set parent_voce_id = base_voce.id
  from public.computi variante,
       public.computo_voci base_voce
 where variante.id = variante_voce.computo_id
   and variante.tipo = 'variante'
   and variante.parent_computo_id is not null
   and base_voce.computo_id = variante.parent_computo_id
   and base_voce.tenant_id = variante_voce.tenant_id
   and base_voce.ordine = variante_voce.ordine
   and base_voce.descrizione = variante_voce.descrizione
   and base_voce.um = variante_voce.um
   and base_voce.origine_voce_id is not distinct from variante_voce.origine_voce_id
   and variante_voce.parent_voce_id is null;

create unique index if not exists computi_tenant_id_id_uidx
  on public.computi (tenant_id, id);

create unique index if not exists computo_voci_tenant_id_id_uidx
  on public.computo_voci (tenant_id, id);

create index if not exists computi_tenant_parent_idx
  on public.computi (tenant_id, parent_computo_id)
  where parent_computo_id is not null;

create unique index if not exists computo_voci_variante_parent_uidx
  on public.computo_voci (tenant_id, computo_id, parent_voce_id)
  where parent_voce_id is not null;

alter table public.computi
  add constraint computi_parent_tenant_fk
  foreign key (tenant_id, parent_computo_id)
  references public.computi (tenant_id, id)
  on delete set null (parent_computo_id)
  not valid;

alter table public.computi
  add constraint computi_variante_parent_check
  check (
    (tipo = 'variante' and parent_computo_id is not null)
    or (tipo <> 'variante' and parent_computo_id is null)
  ) not valid;

alter table public.computo_voci
  add constraint computo_voci_parent_tenant_fk
  foreign key (tenant_id, parent_voce_id)
  references public.computo_voci (tenant_id, id)
  on delete set null (parent_voce_id)
  not valid;

alter table public.computi validate constraint computi_parent_tenant_fk;
alter table public.computi validate constraint computi_variante_parent_check;
alter table public.computo_voci validate constraint computo_voci_parent_tenant_fk;

create or replace view public.computo_varianti_confronto
with (security_invoker = true) as
with righe as (
  select
    variante.tenant_id,
    variante.id as variante_id,
    base.id as computo_base_id,
    base_voce.id as voce_base_id,
    variante_voce.id as voce_variante_id,
    coalesce(variante_voce.ordine, base_voce.ordine) as ordine,
    base_voce.descrizione as descrizione_base,
    variante_voce.descrizione as descrizione_variante,
    base_voce.um as um_base,
    variante_voce.um as um_variante,
    base_voce.qta as qta_base,
    variante_voce.qta as qta_variante,
    base_voce.prezzo_unitario as prezzo_base,
    variante_voce.prezzo_unitario as prezzo_variante,
    base_voce.totale as importo_base,
    variante_voce.totale as importo_variante,
    case
      when variante_voce.id is null then 'soppressa'
      when base_voce.descrizione is distinct from variante_voce.descrizione
        or base_voce.um is distinct from variante_voce.um
        or base_voce.qta is distinct from variante_voce.qta
        or base_voce.prezzo_unitario is distinct from variante_voce.prezzo_unitario
        then 'modificata'
      else 'invariata'
    end as classificazione
  from public.computi variante
  join public.computi base
    on base.id = variante.parent_computo_id
   and base.tenant_id = variante.tenant_id
  join public.computo_voci base_voce
    on base_voce.computo_id = base.id
   and base_voce.tenant_id = base.tenant_id
  left join public.computo_voci variante_voce
    on variante_voce.computo_id = variante.id
   and variante_voce.tenant_id = variante.tenant_id
   and variante_voce.parent_voce_id = base_voce.id
  where variante.tipo = 'variante'

  union all

  select
    variante.tenant_id,
    variante.id as variante_id,
    base.id as computo_base_id,
    null::uuid as voce_base_id,
    variante_voce.id as voce_variante_id,
    variante_voce.ordine,
    null::text as descrizione_base,
    variante_voce.descrizione as descrizione_variante,
    null::text as um_base,
    variante_voce.um as um_variante,
    null::numeric as qta_base,
    variante_voce.qta as qta_variante,
    null::numeric as prezzo_base,
    variante_voce.prezzo_unitario as prezzo_variante,
    null::numeric as importo_base,
    variante_voce.totale as importo_variante,
    'nuova'::text as classificazione
  from public.computi variante
  join public.computi base
    on base.id = variante.parent_computo_id
   and base.tenant_id = variante.tenant_id
  join public.computo_voci variante_voce
    on variante_voce.computo_id = variante.id
   and variante_voce.tenant_id = variante.tenant_id
  where variante.tipo = 'variante'
    and variante_voce.parent_voce_id is null
), base_totali as (
  select
    variante.tenant_id,
    variante.id as variante_id,
    coalesce(sum(base_voce.totale), 0)::numeric(14,2) as totale_base
  from public.computi variante
  join public.computi base
    on base.id = variante.parent_computo_id
   and base.tenant_id = variante.tenant_id
  left join public.computo_voci base_voce
    on base_voce.computo_id = base.id
   and base_voce.tenant_id = base.tenant_id
  where variante.tipo = 'variante'
  group by variante.tenant_id, variante.id
)
select
  r.*,
  (coalesce(r.qta_variante, 0) - coalesce(r.qta_base, 0))::numeric(12,3)
    as delta_qta,
  (coalesce(r.prezzo_variante, 0) - coalesce(r.prezzo_base, 0))::numeric(12,2)
    as delta_prezzo,
  (coalesce(r.importo_variante, 0) - coalesce(r.importo_base, 0))::numeric(14,2)
    as delta_importo,
  case
    when bt.totale_base = 0 then null
    else round(
      ((coalesce(r.importo_variante, 0) - coalesce(r.importo_base, 0))
        / bt.totale_base) * 100,
      2
    )
  end as delta_percentuale_contratto
from righe r
join base_totali bt
  on bt.tenant_id = r.tenant_id
 and bt.variante_id = r.variante_id;

comment on view public.computo_varianti_confronto is
  'Quadro tenant-scoped delle varianti: invariata, modificata, nuova o soppressa.';

revoke all privileges on table public.computo_varianti_confronto
  from public, anon;
grant select on public.computo_varianti_confronto
  to authenticated, service_role;
