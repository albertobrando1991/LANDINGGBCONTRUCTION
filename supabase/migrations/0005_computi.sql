-- ============================================================
-- 0005 — Computi metrici e voci con snapshot prezzi
-- ============================================================

create table public.computi (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  lead_id uuid references public.leads(id) on delete set null,
  cantiere_id uuid references public.cantieri(id) on delete set null,
  parent_computo_id uuid references public.computi(id) on delete set null,
  prezzario_id uuid references public.prezzari(id) on delete set null,
  tipo text not null default 'estimativo'
    check (tipo in ('estimativo','esecutivo','variante')),
  stato text not null default 'bozza'
    check (stato in ('bozza','ai_da_revisionare','confermato','archiviato')),
  numero text,
  note text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index on public.computi (tenant_id, stato, created_at desc);

create table public.computo_voci (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  computo_id uuid not null references public.computi(id) on delete cascade,
  origine_voce_id uuid references public.prezzario_voci(id) on delete set null,
  ordine integer not null default 0,
  super_categoria text not null,
  categoria text not null,
  sub_categoria text,
  descrizione text not null,
  um text not null,
  tipo text not null default 'a_misura',
  qta numeric(12,3) not null default 0,
  prezzo_unitario numeric(12,2) not null default 0,
  totale numeric(14,2) generated always as (round(qta * prezzo_unitario, 2)) stored,
  generata_da_ai boolean not null default false,
  validata_umano boolean not null default false
);
create index on public.computo_voci (tenant_id, computo_id, ordine);

create or replace view public.computi_totali as
  select c.id as computo_id, c.tenant_id,
         coalesce(sum(v.totale), 0)::numeric(14,2) as totale,
         count(v.id) as n_voci,
         count(v.id) filter (where v.generata_da_ai and not v.validata_umano) as n_da_validare
  from public.computi c
  left join public.computo_voci v on v.computo_id = c.id
  group by c.id, c.tenant_id;

create or replace function public.blocca_computo_confermato()
returns trigger language plpgsql as $$
begin
  if exists (select 1 from public.computi c
             where c.id = coalesce(new.computo_id, old.computo_id)
               and c.stato in ('confermato','archiviato')) then
    raise exception 'Computo confermato: crea una variante per modificarlo';
  end if;
  return coalesce(new, old);
end; $$;

create trigger computo_voci_blocco
  before insert or update or delete on public.computo_voci
  for each row execute function public.blocca_computo_confermato();

do $$
declare t text;
begin
  foreach t in array array['computi','computo_voci'] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('alter table public.%I force row level security', t);
    execute format(
      'create policy tenant_read on public.%I for select using (public.is_member(tenant_id))', t);
    execute format(
      'create policy tenant_write on public.%I for all
         using (public.is_member(tenant_id)) with check (public.is_member(tenant_id))', t);
  end loop;
end $$;

create trigger computi_touch before update on public.computi
  for each row execute function public.touch_updated_at();
