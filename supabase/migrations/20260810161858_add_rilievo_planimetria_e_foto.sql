-- Tavola planimetrica e galleria generale del Primo rilievo.
-- Gli asset restano nei bucket privati tenant-scoped gia protetti da RLS.

alter table public.rilievi
  add column planimetria_path text,
  add column planimetria_preview_path text,
  add column planimetria_filename text,
  add column planimetria_mime_type text,
  add column planimetria_data jsonb not null
    default '{"version": 1, "elementi": []}'::jsonb,
  add column foto_paths text[] not null default '{}'::text[];

alter table public.rilievi
  add constraint rilievi_planimetria_path_check check (
    planimetria_path is null or char_length(planimetria_path) between 1 and 700
  ),
  add constraint rilievi_planimetria_preview_path_check check (
    planimetria_preview_path is null
    or char_length(planimetria_preview_path) between 1 and 700
  ),
  add constraint rilievi_planimetria_filename_check check (
    planimetria_filename is null
    or char_length(planimetria_filename) between 1 and 255
  ),
  add constraint rilievi_planimetria_mime_type_check check (
    planimetria_mime_type is null
    or planimetria_mime_type in (
      'application/pdf', 'image/jpeg', 'image/png', 'image/webp'
    )
  ),
  add constraint rilievi_planimetria_data_check check (
    jsonb_typeof(planimetria_data) = 'object'
    and jsonb_typeof(planimetria_data -> 'elementi') = 'array'
  ),
  add constraint rilievi_foto_paths_check check (
    array_position(foto_paths, null) is null
    and cardinality(foto_paths) <= 30
  );

comment on column public.rilievi.planimetria_path is
  'Originale PDF o immagine nel bucket privato planimetrie.';
comment on column public.rilievi.planimetria_preview_path is
  'Preview immagine usata come sfondo annotabile nel canvas.';
comment on column public.rilievi.planimetria_data is
  'Tavola normalizzata: calibrazione, muri, ambienti, quote e note.';
comment on column public.rilievi.foto_paths is
  'Galleria fotografica generale dell immobile, distinta dalle foto ambiente.';
