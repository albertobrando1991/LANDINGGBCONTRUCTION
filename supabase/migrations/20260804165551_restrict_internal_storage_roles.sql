-- Storage EdilOS e interno all'impresa: il ruolo client non puo elencare,
-- leggere o caricare documenti del tenant. L'eventuale portale cliente avra
-- policy dedicate per singola risorsa, non accesso tenant-wide.

update storage.buckets
set file_size_limit = 26214400,
    allowed_mime_types = array[
      'application/pdf',
      'image/jpeg',
      'image/png',
      'image/webp'
    ]
where id = 'planimetrie';

update storage.buckets
set file_size_limit = 15728640,
    allowed_mime_types = array['image/jpeg', 'image/png', 'image/webp']
where id in ('render', 'foto-cantiere');

update storage.buckets
set file_size_limit = 26214400,
    allowed_mime_types = array[
      'application/pdf',
      'image/jpeg',
      'image/png',
      'image/webp',
      'application/msword',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'application/vnd.ms-excel',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    ]
where id = 'documenti';

drop policy if exists storage_tenant_read on storage.objects;
create policy storage_tenant_read on storage.objects
  for select to authenticated
  using (
    bucket_id in ('planimetrie','render','foto-cantiere','documenti')
    and public.has_role(
      ((storage.foldername(name))[1])::uuid,
      array['owner','admin','staff','operations']::public.tenant_role[]
    )
  );

drop policy if exists storage_tenant_write on storage.objects;
create policy storage_tenant_write on storage.objects
  for insert to authenticated
  with check (
    bucket_id in ('planimetrie','render','foto-cantiere','documenti')
    and public.has_role(
      ((storage.foldername(name))[1])::uuid,
      array['owner','admin','staff','operations']::public.tenant_role[]
    )
  );

drop policy if exists storage_tenant_update on storage.objects;
create policy storage_tenant_update on storage.objects
  for update to authenticated
  using (
    bucket_id in ('planimetrie','render','foto-cantiere','documenti')
    and public.has_role(
      ((storage.foldername(name))[1])::uuid,
      array['owner','admin','staff','operations']::public.tenant_role[]
    )
  )
  with check (
    bucket_id in ('planimetrie','render','foto-cantiere','documenti')
    and public.has_role(
      ((storage.foldername(name))[1])::uuid,
      array['owner','admin','staff','operations']::public.tenant_role[]
    )
  );

drop policy if exists storage_tenant_delete on storage.objects;
create policy storage_tenant_delete on storage.objects
  for delete to authenticated
  using (
    bucket_id in ('planimetrie','render','foto-cantiere','documenti')
    and public.has_role(
      ((storage.foldername(name))[1])::uuid,
      array['owner','admin']::public.tenant_role[]
    )
  );
