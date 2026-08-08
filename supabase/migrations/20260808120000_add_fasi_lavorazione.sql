-- ============================================================
-- Fasi di lavorazione e aree sulle voci di computo
-- La classificazione e deterministica e vive in backend/fasi_lavorazione.py:
-- qui non viene duplicata per non far divergere le due implementazioni.
-- I computi esistenti restano con fase null finche non si chiama
-- POST /computi/{id}/riclassifica: il PDF li tratta come "Da classificare".
-- ============================================================

alter table public.computo_voci
  add column if not exists fase text,
  add column if not exists fase_ordine smallint,
  add column if not exists area text;

alter table public.computo_voci
  add constraint computo_voci_fase_ordine_check
  check (fase_ordine is null or fase_ordine between 0 and 99) not valid;

alter table public.computo_voci validate constraint computo_voci_fase_ordine_check;

alter table public.computo_voci
  add constraint computo_voci_fase_coerente_check
  check ((fase is null) = (fase_ordine is null)) not valid;

alter table public.computo_voci validate constraint computo_voci_fase_coerente_check;

create index if not exists computo_voci_fase_idx
  on public.computo_voci (tenant_id, computo_id, fase_ordine, ordine);

create index if not exists computo_voci_area_idx
  on public.computo_voci (tenant_id, computo_id, area)
  where area is not null;
