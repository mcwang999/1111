create extension if not exists vector;
create extension if not exists pgcrypto;

create table if not exists documents (
  id uuid primary key default gen_random_uuid(),
  doc_type text not null,
  title text not null,
  content text not null,
  metadata jsonb not null default '{}'::jsonb,
  embedding vector(1536),
  source_url text,
  created_by_agent text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists documents_doc_type_idx
  on documents (doc_type);

create index if not exists documents_created_at_idx
  on documents (created_at desc);

create index if not exists documents_metadata_gin_idx
  on documents using gin (metadata);

create unique index if not exists documents_raw_source_url_unique
  on documents ((metadata->>'normalized_source_url'))
  where doc_type = 'raw_source'
    and metadata ? 'normalized_source_url';

create unique index if not exists documents_card_dedup_key_unique
  on documents ((metadata->>'dedup_key'))
  where doc_type in ('intel_card', 'social_signal_card')
    and metadata ? 'dedup_key';

create index if not exists documents_briefing_status_idx
  on documents ((metadata->>'briefing_status'))
  where doc_type in ('intel_card', 'social_signal_card');

create index if not exists documents_published_at_idx
  on documents ((metadata->>'published_at'))
  where doc_type in ('intel_card', 'social_signal_card', 'raw_source');

create index if not exists documents_last_seen_at_idx
  on documents ((metadata->>'last_seen_at'))
  where doc_type in ('intel_card', 'social_signal_card');

create index if not exists documents_embedding_idx
  on documents using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);

create table if not exists tasks (
  id uuid primary key default gen_random_uuid(),
  task_type text not null,
  status text not null default 'pending',
  requested_by_agent text,
  assigned_agent text,
  input_payload jsonb not null default '{}'::jsonb,
  result_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz
);

create index if not exists tasks_status_idx
  on tasks (status);

create index if not exists tasks_task_type_idx
  on tasks (task_type);

create table if not exists agent_runs (
  id uuid primary key default gen_random_uuid(),
  agent_name text not null,
  tool_name text not null,
  input_payload jsonb not null default '{}'::jsonb,
  output_payload jsonb not null default '{}'::jsonb,
  status text not null,
  error_message text,
  created_at timestamptz not null default now(),
  completed_at timestamptz
);

create index if not exists agent_runs_agent_name_idx
  on agent_runs (agent_name);

create table if not exists briefing_references (
  id uuid primary key default gen_random_uuid(),
  briefing_doc_id uuid not null references documents(id) on delete cascade,
  briefing_item_id text not null,
  referenced_doc_id uuid not null references documents(id) on delete cascade,
  reference_type text not null,
  created_at timestamptz not null default now()
);

create index if not exists briefing_references_briefing_doc_id_idx
  on briefing_references (briefing_doc_id);

create or replace function set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists documents_set_updated_at on documents;
create trigger documents_set_updated_at
before update on documents
for each row
execute function set_updated_at();

drop trigger if exists tasks_set_updated_at on tasks;
create trigger tasks_set_updated_at
before update on tasks
for each row
execute function set_updated_at();
