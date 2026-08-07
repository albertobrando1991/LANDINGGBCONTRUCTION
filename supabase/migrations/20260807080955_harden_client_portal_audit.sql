-- Il portale usa il backend per registrare l'approvazione: il browser non
-- deve poter forgiare IP, user-agent o timestamp tramite la Data API.

create schema if not exists private;
revoke all on schema private from public, anon;
grant usage on schema private to authenticated, service_role;

drop policy if exists cantiere_clienti_internal_insert
  on public.cantiere_clienti;
drop policy if exists cantiere_clienti_internal_update
  on public.cantiere_clienti;
drop policy if exists cantiere_clienti_internal_delete
  on public.cantiere_clienti;

create policy cantiere_clienti_admin_insert on public.cantiere_clienti
  for insert to authenticated
  with check (
    (select public.has_role(
      tenant_id, array['owner','admin']::public.tenant_role[]
    ))
  );
create policy cantiere_clienti_admin_update on public.cantiere_clienti
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
create policy cantiere_clienti_admin_delete on public.cantiere_clienti
  for delete to authenticated
  using (
    (select public.has_role(
      tenant_id, array['owner','admin']::public.tenant_role[]
    ))
  );

revoke insert on table public.varianti_approvazioni from authenticated;

create or replace function private.approva_variante_cliente(
  p_tenant_id uuid,
  p_cantiere_id uuid,
  p_variante_id uuid,
  p_ip inet,
  p_user_agent text default null
)
returns table (
  id uuid,
  tenant_id uuid,
  cantiere_id uuid,
  variante_id uuid,
  user_id uuid,
  decisione text,
  ip inet,
  user_agent text,
  created_at timestamptz,
  created boolean
)
language sql
volatile
security definer
set search_path = ''
as $$
  with authorized as (
    select auth.uid() as user_id
    where auth.uid() is not null
      and public.is_approvable_client_variant(
        p_tenant_id, p_cantiere_id, p_variante_id
      )
  ),
  inserted as (
    insert into public.varianti_approvazioni (
      tenant_id, cantiere_id, variante_id, user_id, ip, user_agent
    )
    select
      p_tenant_id,
      p_cantiere_id,
      p_variante_id,
      authorized.user_id,
      p_ip,
      nullif(left(coalesce(p_user_agent, ''), 500), '')
    from authorized
    on conflict (tenant_id, variante_id, user_id) do nothing
    returning
      varianti_approvazioni.id,
      varianti_approvazioni.tenant_id,
      varianti_approvazioni.cantiere_id,
      varianti_approvazioni.variante_id,
      varianti_approvazioni.user_id,
      varianti_approvazioni.decisione,
      varianti_approvazioni.ip,
      varianti_approvazioni.user_agent,
      varianti_approvazioni.created_at
  )
  select inserted.*, true as created
  from inserted
  union all
  select
    existing.id,
    existing.tenant_id,
    existing.cantiere_id,
    existing.variante_id,
    existing.user_id,
    existing.decisione,
    existing.ip,
    existing.user_agent,
    existing.created_at,
    false as created
  from public.varianti_approvazioni existing
  join authorized
    on authorized.user_id = existing.user_id
  where existing.tenant_id = p_tenant_id
    and existing.cantiere_id = p_cantiere_id
    and existing.variante_id = p_variante_id
    and not exists (select 1 from inserted)
  limit 1;
$$;

revoke all on function private.approva_variante_cliente(
  uuid, uuid, uuid, inet, text
) from public, anon;
grant execute on function private.approva_variante_cliente(
  uuid, uuid, uuid, inet, text
) to authenticated, service_role;

comment on function private.approva_variante_cliente(
  uuid, uuid, uuid, inet, text
) is 'Backend-only entry point for immutable client variant approval audit.';
