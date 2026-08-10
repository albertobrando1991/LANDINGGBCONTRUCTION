-- Superficie di progetto e durate manuali sono dati del computo. Il preventivo
-- ne conserva una copia per rendere riproducibile il PDF gia emesso.
alter table public.computi
  add column if not exists superficie_mq numeric(10,2),
  add column if not exists durate_fasi jsonb not null default '{}'::jsonb;

alter table public.computi
  add constraint computi_superficie_mq_check
  check (superficie_mq is null or superficie_mq between 5 and 10000) not valid,
  add constraint computi_durate_fasi_object_check
  check (jsonb_typeof(durate_fasi) = 'object') not valid;

alter table public.computi validate constraint computi_superficie_mq_check;
alter table public.computi validate constraint computi_durate_fasi_object_check;

alter table public.preventivi
  add column if not exists superficie_mq numeric(10,2),
  add column if not exists durate_fasi jsonb not null default '{}'::jsonb;

alter table public.preventivi
  add constraint preventivi_superficie_mq_check
  check (superficie_mq is null or superficie_mq between 5 and 10000) not valid,
  add constraint preventivi_durate_fasi_object_check
  check (jsonb_typeof(durate_fasi) = 'object') not valid;

alter table public.preventivi validate constraint preventivi_superficie_mq_check;
alter table public.preventivi validate constraint preventivi_durate_fasi_object_check;
