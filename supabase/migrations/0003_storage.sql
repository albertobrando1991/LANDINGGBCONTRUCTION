-- ============================================================
-- 0003 — Storage buckets privati multi-tenant
-- Path obbligatorio: <tenant_id>/<risorsa>/<file>
-- ============================================================

insert into storage.buckets (id, name, public)
values ('planimetrie','planimetrie',false),
       ('render','render',false),
       ('foto-cantiere','foto-cantiere',false),
       ('documenti','documenti',false)
on conflict (id) do nothing;

create policy storage_tenant_read on storage.objects for select
  using (
    bucket_id in ('planimetrie','render','foto-cantiere','documenti')
    and public.is_member(((storage.foldername(name))[1])::uuid)
  );

create policy storage_tenant_write on storage.objects for insert
  with check (
    bucket_id in ('planimetrie','render','foto-cantiere','documenti')
    and public.is_member(((storage.foldername(name))[1])::uuid)
  );

create policy storage_tenant_delete on storage.objects for delete
  using (
    bucket_id in ('planimetrie','render','foto-cantiere','documenti')
    and public.has_role(((storage.foldername(name))[1])::uuid,
                        array['owner','admin']::public.tenant_role[])
  );
