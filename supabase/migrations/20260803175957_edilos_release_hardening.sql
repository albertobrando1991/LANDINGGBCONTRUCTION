-- ============================================================
-- EdilOS release hardening
-- - la vista aggregata deve rispettare le RLS delle tabelle base
-- - gli helper SECURITY DEFINER non sono API anonime
-- - Storage upsert richiede anche una policy UPDATE
-- ============================================================

create or replace view public.computi_totali
with (security_invoker = true) as
  select c.id as computo_id, c.tenant_id,
         coalesce(sum(v.totale), 0)::numeric(14,2) as totale,
         count(v.id) as n_voci,
         count(v.id) filter (
           where v.generata_da_ai and not v.validata_umano
         ) as n_da_validare
  from public.computi c
  left join public.computo_voci v on v.computo_id = c.id
  group by c.id, c.tenant_id;

comment on view public.computi_totali is
  'Aggregati computo tenant-scoped; security_invoker applica le RLS delle tabelle base.';

-- Il brand del tenant è pubblico, ma soltanto attraverso quattro colonne
-- esplicitamente autorizzate. Dati fiscali, piano e crediti restano esclusi.
drop policy if exists tenants_read on public.tenants;
create policy tenants_read on public.tenants
  for select to authenticated
  using (public.is_member(id));

drop policy if exists tenants_update on public.tenants;
create policy tenants_update on public.tenants
  for update to authenticated
  using (public.has_role(id, array['owner','admin']::public.tenant_role[]))
  with check (public.has_role(id, array['owner','admin']::public.tenant_role[]));

drop policy if exists members_read on public.tenant_members;
create policy members_read on public.tenant_members
  for select to authenticated
  using (public.is_member(tenant_id));

drop policy if exists members_write on public.tenant_members;
create policy members_write on public.tenant_members
  for all to authenticated
  using (public.has_role(tenant_id, array['owner','admin']::public.tenant_role[]))
  with check (public.has_role(tenant_id, array['owner','admin']::public.tenant_role[]));

drop policy if exists tenants_public_brand on public.tenants;
create policy tenants_public_brand on public.tenants
  for select to anon
  using (attivo = true);

-- I ruoli base del progetto locale possono ereditare grant di tabella creati
-- dalla piattaforma. Revocali prima del grant per-colonna: la sola RLS non
-- impedirebbe a `anon` di leggere piva/piano/crediti dei tenant attivi.
revoke all privileges on table public.tenants from anon, public;
grant select (slug, ragione_sociale, theme, contatti)
  on public.tenants to anon;

revoke execute on function public.is_member(uuid) from public, anon;
revoke execute on function public.has_role(uuid, public.tenant_role[]) from public, anon;

drop policy if exists storage_tenant_update on storage.objects;
create policy storage_tenant_update on storage.objects for update
  using (
    bucket_id in ('planimetrie','render','foto-cantiere','documenti')
    and public.is_member(((storage.foldername(name))[1])::uuid)
  )
  with check (
    bucket_id in ('planimetrie','render','foto-cantiere','documenti')
    and public.is_member(((storage.foldername(name))[1])::uuid)
  );

-- Durante la fondazione il prezzario Campania era rimasto default anche dopo
-- la duplicazione. Se esiste un listino tenant, rendi default il più vecchio:
-- è quello calibrato dall'impresa e deve alimentare il ponte AI.
do $$
declare candidate record;
begin
  for candidate in
    select distinct on (tenant_id) tenant_id, id
    from public.prezzari
    where is_sistema = false
    order by tenant_id, created_at, id
  loop
    update public.prezzari
       set is_default = false
     where tenant_id = candidate.tenant_id
       and is_default = true;

    update public.prezzari
       set is_default = true
     where id = candidate.id;
  end loop;
end $$;
