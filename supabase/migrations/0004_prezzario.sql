-- ============================================================
-- 0004 — Prezzari e voci (Campania + custom per tenant)
-- ============================================================

create table public.prezzari (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  nome text not null,
  fonte text not null default 'campania' check (fonte in ('campania','custom','importato')),
  anno integer,
  is_default boolean not null default false,
  is_sistema boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create unique index prezzari_un_default_per_tenant
  on public.prezzari (tenant_id) where is_default;

create table public.prezzario_voci (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  prezzario_id uuid not null references public.prezzari(id) on delete cascade,
  codice text,
  super_categoria text not null,
  categoria text not null,
  sub_categoria text,
  descrizione text not null,
  um text not null check (um in ('mq','ml','mc','cad','corpo','kg','h','n')),
  prezzo_unitario numeric(12,2) not null check (prezzo_unitario >= 0),
  prezzo_riferimento numeric(12,2),
  tipo text not null default 'a_misura' check (tipo in ('a_misura','a_corpo')),
  chiave_wizard boolean not null default false,
  attiva boolean not null default true,
  created_at timestamptz not null default now()
);
create index on public.prezzario_voci (tenant_id, prezzario_id, categoria);
create index on public.prezzario_voci (tenant_id, prezzario_id) where chiave_wizard;
create index on public.prezzario_voci (tenant_id, codice);

-- il prezzario di sistema non si modifica: si duplica
create or replace function public.blocca_prezzario_sistema()
returns trigger language plpgsql as $$
begin
  if exists (select 1 from public.prezzari p
             where p.id = coalesce(new.prezzario_id, old.prezzario_id) and p.is_sistema) then
    raise exception 'Il prezzario Campania è di sola lettura: duplicalo per modificarlo';
  end if;
  return coalesce(new, old);
end; $$;

create trigger prezzario_voci_no_sistema
  before insert or update or delete on public.prezzario_voci
  for each row execute function public.blocca_prezzario_sistema();

do $$
declare t text;
begin
  foreach t in array array['prezzari','prezzario_voci'] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('alter table public.%I force row level security', t);
    execute format(
      'create policy tenant_read on public.%I for select using (public.is_member(tenant_id))', t);
    execute format(
      'create policy tenant_write on public.%I for all
         using (public.is_member(tenant_id)) with check (public.is_member(tenant_id))', t);
  end loop;
end $$;

create trigger prezzari_touch before update on public.prezzari
  for each row execute function public.touch_updated_at();
