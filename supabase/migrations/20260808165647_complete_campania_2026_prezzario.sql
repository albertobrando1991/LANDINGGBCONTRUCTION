-- Il prezzario ufficiale contiene unita ulteriori rispetto al listino GB
-- (es. cad/30gg, ha, t, mq/cm). Le voci custom restano validate dall'API.
alter table public.prezzario_voci
  drop constraint if exists prezzario_voci_um_check;

create unique index if not exists prezzario_voci_prezzario_codice_uidx
  on public.prezzario_voci (tenant_id, prezzario_id, codice)
  where codice is not null;

create index if not exists prezzario_voci_search_idx
  on public.prezzario_voci (tenant_id, prezzario_id, lower(codice));
