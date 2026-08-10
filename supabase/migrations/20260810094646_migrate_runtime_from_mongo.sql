-- Cutover del runtime storico Mongo verso Supabase/Postgres.
-- I payload a struttura variabile (AI, ledger, webhook) restano JSONB, ma sono
-- tenant-scoped, indicizzati e non esposti dalla Data API.

create schema if not exists private;
revoke all on schema private from public, anon, authenticated;

create table private.runtime_documents (
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  collection text not null
    check (collection ~ '^[a-z][a-z0-9_]{1,62}$'),
  id text not null
    check (char_length(id) between 1 and 200),
  data jsonb not null default '{}'::jsonb
    check (jsonb_typeof(data) = 'object'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (tenant_id, collection, id)
);

create table private.runtime_migration_audits (
  manifest_sha256 text primary key
    check (manifest_sha256 ~ '^[0-9a-f]{64}$'),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  source_database text not null,
  source_exported_at timestamptz not null,
  collections jsonb not null
    check (jsonb_typeof(collections) = 'object'),
  source_count integer not null check (source_count >= 0),
  imported_count integer not null check (imported_count = source_count),
  verified_at timestamptz not null default now()
);

create index runtime_documents_collection_idx
  on private.runtime_documents (tenant_id, collection, updated_at desc);
create index runtime_documents_data_gin_idx
  on private.runtime_documents using gin (data jsonb_path_ops);
create index runtime_documents_status_idx
  on private.runtime_documents (
    tenant_id,
    collection,
    (data ->> 'status'),
    (data ->> 'created_at') desc
  );
create index runtime_documents_job_idx
  on private.runtime_documents (
    tenant_id,
    collection,
    (data ->> 'job_id'),
    (data ->> 'created_at')
  )
  where data ? 'job_id';
create index runtime_documents_account_idx
  on private.runtime_documents (
    tenant_id,
    collection,
    (data ->> 'account_id'),
    (data ->> 'created_at') desc
  )
  where data ? 'account_id';

create unique index runtime_documents_users_email_uidx
  on private.runtime_documents (
    tenant_id,
    lower(data ->> 'email')
  )
  where collection = 'users' and data ? 'email';
create unique index runtime_documents_credit_bucket_key_uidx
  on private.runtime_documents (
    tenant_id,
    (data ->> 'key')
  )
  where collection = 'ai_credit_buckets' and data ? 'key';
create unique index runtime_documents_credit_ledger_idem_uidx
  on private.runtime_documents (
    tenant_id,
    (data ->> 'idempotency_key')
  )
  where collection = 'ai_credit_ledger' and data ? 'idempotency_key';
create unique index runtime_documents_architect_cache_uidx
  on private.runtime_documents (
    tenant_id,
    (data ->> 'cache_type'),
    (data ->> 'file_hash'),
    (data ->> 'schema_version'),
    (data ->> 'provider'),
    (data ->> 'model')
  )
  where collection = 'ai_architect_cache'
    and data ?& array['cache_type', 'file_hash', 'schema_version', 'provider', 'model'];
create unique index runtime_documents_meta_event_uidx
  on private.runtime_documents (
    tenant_id,
    (data ->> 'leadgen_id')
  )
  where collection = 'meta_webhook_events' and data ? 'leadgen_id';
create unique index runtime_documents_meta_lead_uidx
  on private.runtime_documents (
    tenant_id,
    (data #>> '{external_ids,meta_leadgen_id}')
  )
  where collection = 'leads'
    and jsonb_typeof(data #> '{external_ids,meta_leadgen_id}') = 'string';

alter table private.runtime_documents enable row level security;
alter table private.runtime_documents force row level security;
alter table private.runtime_migration_audits enable row level security;
alter table private.runtime_migration_audits force row level security;

revoke all privileges on table private.runtime_documents
  from public, anon, authenticated;
revoke all privileges on table private.runtime_migration_audits
  from public, anon, authenticated;
grant all privileges on table private.runtime_documents to service_role;
grant all privileges on table private.runtime_migration_audits to service_role;

create trigger runtime_documents_touch
  before update on private.runtime_documents
  for each row execute function public.touch_updated_at();

create or replace function private.purge_expired_runtime_documents()
returns bigint
language plpgsql
security invoker
set search_path = ''
as $$
declare
  removed bigint;
begin
  delete from private.runtime_documents
  where (
    collection = 'api_rate_limits'
    and data ? 'expires_at'
    and (data ->> 'expires_at')::timestamptz < now()
  ) or (
    collection = 'ai_architect_upload_log'
    and data ? 'created_at'
    and (data ->> 'created_at')::timestamptz < now() - interval '1 day'
  );
  get diagnostics removed = row_count;
  return removed;
end;
$$;

revoke all on function private.purge_expired_runtime_documents() from public, anon, authenticated;
grant execute on function private.purge_expired_runtime_documents() to service_role;

comment on table private.runtime_documents is
  'Canonical Supabase store for variable-shape runtime records migrated from MongoDB. Not exposed through Data API.';
comment on table private.runtime_migration_audits is
  'Immutable evidence for verified source snapshots imported during the Supabase cutover.';
