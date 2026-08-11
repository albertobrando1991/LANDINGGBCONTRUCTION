-- Consente ai ruoli operativi interni di aggiungere esclusivamente clienti.
-- La promozione o modifica di membership esistenti resta owner/admin-only.

drop policy if exists members_insert on public.tenant_members;
create policy members_insert on public.tenant_members
  for insert to authenticated
  with check (
    (select public.has_role(
      tenant_id, array['owner','admin']::public.tenant_role[]
    ))
    or (
      role = 'client'::public.tenant_role
      and (select public.is_internal_member(tenant_id))
    )
  );

comment on policy members_insert on public.tenant_members is
  'Owner/admin possono invitare membri; i ruoli interni possono inserire solo client.';
