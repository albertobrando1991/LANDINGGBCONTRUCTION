-- ============================================================
-- 0001 — Tenancy: tenants, membri, helper RLS, JWT hook
-- ============================================================

create extension if not exists pgcrypto;

create table public.tenants (
  id uuid primary key default gen_random_uuid(),
  slug text unique not null
    check (
      slug ~ '^[a-z0-9][a-z0-9-]{1,30}[a-z0-9]$'
      and slug not in ('app','api','www','admin','docs','mail','staging','cdn','static','assets','auth')
    ),
  ragione_sociale text not null,
  piva text,
  custom_domain text unique,
  theme jsonb not null default '{}'::jsonb,
  contatti jsonb not null default '{}'::jsonb,
  piano text not null default 'starter' check (piano in ('starter','pro','enterprise')),
  ai_credits integer not null default 0 check (ai_credits >= 0),
  attivo boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on column public.tenants.slug is
  'Il subdominio è <slug>.alantis.it — derivato, non memorizzato separatamente.';

create type public.tenant_role as enum ('owner','admin','staff','operations','client');

create table public.tenant_members (
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  user_id   uuid not null references auth.users(id) on delete cascade,
  role      public.tenant_role not null default 'staff',
  nome      text,
  photo_url text,
  created_at timestamptz not null default now(),
  primary key (tenant_id, user_id)
);
create index on public.tenant_members (user_id);

-- ---------- Helper RLS ----------
create or replace function public.is_member(t uuid)
returns boolean
language sql stable security definer set search_path = public, pg_temp as $$
  select exists (
    select 1 from public.tenant_members
    where tenant_id = t and user_id = auth.uid()
  );
$$;

create or replace function public.has_role(t uuid, roles public.tenant_role[])
returns boolean
language sql stable security definer set search_path = public, pg_temp as $$
  select exists (
    select 1 from public.tenant_members
    where tenant_id = t and user_id = auth.uid() and role = any(roles)
  );
$$;

-- ---------- RLS su tenants / tenant_members ----------
alter table public.tenants enable row level security;
alter table public.tenants force row level security;

create policy tenants_read on public.tenants
  for select using (public.is_member(id));
create policy tenants_update on public.tenants
  for update using (public.has_role(id, array['owner','admin']::public.tenant_role[]))
  with check   (public.has_role(id, array['owner','admin']::public.tenant_role[]));

alter table public.tenant_members enable row level security;
alter table public.tenant_members force row level security;

create policy members_read on public.tenant_members
  for select using (public.is_member(tenant_id));
create policy members_write on public.tenant_members
  for all using (public.has_role(tenant_id, array['owner','admin']::public.tenant_role[]))
  with check   (public.has_role(tenant_id, array['owner','admin']::public.tenant_role[]));

-- ---------- Custom Access Token Hook ----------
create or replace function public.custom_access_token_hook(event jsonb)
returns jsonb
language plpgsql stable security definer set search_path = public, pg_temp as $$
declare claims jsonb; tenants jsonb;
begin
  select coalesce(jsonb_agg(jsonb_build_object('t', tenant_id, 'r', role)), '[]'::jsonb)
    into tenants
  from public.tenant_members
  where user_id = (event->>'user_id')::uuid;

  claims := coalesce(event->'claims', '{}'::jsonb);
  claims := jsonb_set(claims, '{app_tenants}', tenants);
  return jsonb_set(event, '{claims}', claims);
end; $$;

grant execute on function public.custom_access_token_hook(jsonb) to supabase_auth_admin;
revoke execute on function public.custom_access_token_hook(jsonb) from authenticated, anon, public;

-- ---------- trigger updated_at riusabile ----------
create or replace function public.touch_updated_at()
returns trigger language plpgsql as $$
begin new.updated_at := now(); return new; end; $$;

create trigger tenants_touch before update on public.tenants
  for each row execute function public.touch_updated_at();
