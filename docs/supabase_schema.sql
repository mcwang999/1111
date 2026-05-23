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
