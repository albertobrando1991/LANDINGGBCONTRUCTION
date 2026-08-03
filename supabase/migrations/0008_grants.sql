-- ============================================================
-- 0008 — Privilegi schema public per ruoli Supabase
-- RLS filtra le righe; senza GRANT il ruolo authenticated
-- riceve "permission denied for table …" anche con policy OK.
-- ============================================================

grant usage on schema public to anon, authenticated, service_role;

-- Tabelle di dominio EdilOS (Fase 0–1)
grant select, insert, update, delete on
  public.tenants,
  public.tenant_members,
  public.clienti,
  public.leads,
  public.cantieri,
  public.prezzari,
  public.prezzario_voci,
  public.computi,
  public.computo_voci,
  public.mapping_regole,
  public.preventivi
to authenticated;

-- Viste aggregate (security invoker: le RLS delle tabelle sottostanti restano attive)
grant select on public.computi_totali to authenticated;

grant all on
  public.tenants,
  public.tenant_members,
  public.clienti,
  public.leads,
  public.cantieri,
  public.prezzari,
  public.prezzario_voci,
  public.computi,
  public.computo_voci,
  public.mapping_regole,
  public.preventivi
to service_role;

grant select on public.computi_totali to service_role;

-- Sequence (se presenti; gen_random_uuid non le usa, ma default future-safe)
grant usage, select on all sequences in schema public to authenticated;
grant all on all sequences in schema public to service_role;

-- Helper RLS usati dalle policy e dal backend
grant execute on function public.is_member(uuid) to authenticated, service_role;
grant execute on function public.has_role(uuid, public.tenant_role[]) to authenticated, service_role;

-- Default privileges: tabelle future nel public
alter default privileges in schema public
  grant select, insert, update, delete on tables to authenticated;
alter default privileges in schema public
  grant all on tables to service_role;
alter default privileges in schema public
  grant usage, select on sequences to authenticated;
alter default privileges in schema public
  grant all on sequences to service_role;
