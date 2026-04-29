-- Galaxy Legal — Supabase schema (Postgres 17 + pgvector)
-- Anti-fantasma legal workspace: cases, documents (chunked + embedded), runs, evidences, drafts, audit.
-- Region: eu-west-3. Project ref: irzervhlczzzrydqfisn.
-- Apply via Supabase Dashboard → SQL Editor → Run, or `supabase db push` if linked locally.

-- =============================================================
-- 0) Extensions
-- =============================================================
create extension if not exists "pgcrypto";
create extension if not exists "vector";

-- =============================================================
-- 1) Profiles (1-to-1 with auth.users)
-- =============================================================
create table if not exists public.profiles (
  id            uuid primary key references auth.users(id) on delete cascade,
  email         text unique not null,
  full_name     text,
  org_id        uuid,
  created_at    timestamptz not null default now()
);

alter table public.profiles enable row level security;

drop policy if exists "profiles self read"   on public.profiles;
drop policy if exists "profiles self update" on public.profiles;
create policy "profiles self read"   on public.profiles for select using (auth.uid() = id);
create policy "profiles self update" on public.profiles for update using (auth.uid() = id);

-- Auto-create profile row on signup
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, email)
  values (new.id, new.email)
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- =============================================================
-- 2) Cases (expedientes)
-- =============================================================
create table if not exists public.cases (
  id            uuid primary key default gen_random_uuid(),
  owner_id      uuid not null references auth.users(id) on delete cascade,
  title         text not null,
  reference     text,
  jurisdiccion  text,
  materia       text,
  description   text,
  status        text not null default 'open',
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

create index if not exists cases_owner_idx on public.cases(owner_id);

alter table public.cases enable row level security;
drop policy if exists "cases owner all" on public.cases;
create policy "cases owner all" on public.cases
  for all using (auth.uid() = owner_id) with check (auth.uid() = owner_id);

-- =============================================================
-- 3) Case documents (uploaded files metadata)
-- =============================================================
create table if not exists public.case_documents (
  id                  uuid primary key default gen_random_uuid(),
  case_id             uuid not null references public.cases(id) on delete cascade,
  owner_id            uuid not null references auth.users(id) on delete cascade,
  filename            text not null,
  storage_path        text not null,
  mime_type           text,
  size_bytes          bigint,
  hash_sha256         text not null,
  source              text not null default 'upload',  -- upload | drive
  drive_file_id       text,
  drive_revision_id   text,
  texto_extraido      text,
  pages_count         integer,
  status              text not null default 'pending', -- pending | indexing | ready | failed
  index_error         text,
  indexed_at          timestamptz,
  created_at          timestamptz not null default now()
);

create unique index if not exists case_documents_case_hash_uidx
  on public.case_documents(case_id, hash_sha256);
create index if not exists case_documents_case_idx on public.case_documents(case_id);

alter table public.case_documents enable row level security;
drop policy if exists "case_documents owner all" on public.case_documents;
create policy "case_documents owner all" on public.case_documents
  for all using (auth.uid() = owner_id) with check (auth.uid() = owner_id);

-- =============================================================
-- 4) Document chunks (vector store)
-- =============================================================
create table if not exists public.document_chunks (
  id            uuid primary key default gen_random_uuid(),
  document_id   uuid not null references public.case_documents(id) on delete cascade,
  case_id       uuid not null references public.cases(id) on delete cascade,
  owner_id      uuid not null references auth.users(id) on delete cascade,
  chunk_index   integer not null,
  page          integer,
  paragraph     integer,
  chunk_text    text not null,
  token_count   integer,
  embedding     vector(1536),
  created_at    timestamptz not null default now(),
  unique (document_id, chunk_index)
);

create index if not exists document_chunks_doc_idx  on public.document_chunks(document_id);
create index if not exists document_chunks_case_idx on public.document_chunks(case_id);
create index if not exists document_chunks_embed_idx
  on public.document_chunks using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);

alter table public.document_chunks enable row level security;
drop policy if exists "document_chunks owner all" on public.document_chunks;
create policy "document_chunks owner all" on public.document_chunks
  for all using (auth.uid() = owner_id) with check (auth.uid() = owner_id);

-- RPC: similarity search scoped by case
create or replace function public.match_document_chunks(
  query_embedding   vector(1536),
  p_case_id         uuid,
  match_threshold   float default 0.70,
  match_count       int   default 8
)
returns table (
  id            uuid,
  document_id   uuid,
  chunk_index   integer,
  page          integer,
  paragraph     integer,
  chunk_text    text,
  similarity    float
)
language sql stable security invoker as $$
  select c.id, c.document_id, c.chunk_index, c.page, c.paragraph, c.chunk_text,
         1 - (c.embedding <=> query_embedding) as similarity
  from public.document_chunks c
  where c.case_id = p_case_id
    and 1 - (c.embedding <=> query_embedding) > match_threshold
  order by c.embedding <=> query_embedding asc
  limit match_count;
$$;

-- =============================================================
-- 5) Runs (workflow executions)
-- =============================================================
create table if not exists public.runs (
  id              uuid primary key default gen_random_uuid(),
  case_id         uuid not null references public.cases(id) on delete cascade,
  owner_id        uuid not null references auth.users(id) on delete cascade,
  workflow_type   text not null,
  status          text not null default 'queued', -- queued | running | succeeded | failed | needs_human
  current_step    text,
  output_jsonb    jsonb not null default '{}'::jsonb,
  tokens_input    integer not null default 0,
  tokens_output   integer not null default 0,
  cost_usd        numeric(10,4) not null default 0,
  error           text,
  started_at      timestamptz,
  finished_at     timestamptz,
  created_at      timestamptz not null default now()
);

create index if not exists runs_case_idx on public.runs(case_id);

alter table public.runs enable row level security;
drop policy if exists "runs owner all" on public.runs;
create policy "runs owner all" on public.runs
  for all using (auth.uid() = owner_id) with check (auth.uid() = owner_id);

-- =============================================================
-- 6) Evidences (claim ↔ verbatim chunk excerpt)
-- =============================================================
create table if not exists public.evidences (
  id              uuid primary key default gen_random_uuid(),
  run_id          uuid not null references public.runs(id) on delete cascade,
  case_id         uuid not null references public.cases(id) on delete cascade,
  owner_id        uuid not null references auth.users(id) on delete cascade,
  document_id     uuid not null references public.case_documents(id) on delete cascade,
  chunk_id        uuid references public.document_chunks(id) on delete set null,
  external_id     text not null,           -- e001 / e002 ... as referenced in draft markdown
  claim_id        text,                    -- c001
  page            integer,
  paragraph       integer,
  quote_excerpt   text not null,           -- verbatim string substring-match'd at validation time
  verified        boolean not null default false,
  created_at      timestamptz not null default now()
);

create index if not exists evidences_run_idx on public.evidences(run_id);
create unique index if not exists evidences_run_extid_uidx on public.evidences(run_id, external_id);

alter table public.evidences enable row level security;
drop policy if exists "evidences owner all" on public.evidences;
create policy "evidences owner all" on public.evidences
  for all using (auth.uid() = owner_id) with check (auth.uid() = owner_id);

-- =============================================================
-- 7) Drafts (generated docs with versioning + immutability)
-- =============================================================
create table if not exists public.drafts (
  id                uuid primary key default gen_random_uuid(),
  case_id           uuid not null references public.cases(id) on delete cascade,
  run_id            uuid references public.runs(id) on delete set null,
  owner_id          uuid not null references auth.users(id) on delete cascade,
  parent_draft_id   uuid references public.drafts(id) on delete set null,
  version           integer not null default 1,
  draft_type        text not null,         -- initial_analysis | civil_demand | fiscal_consultation | jurisprudence_analysis | revision
  title             text not null,
  content_md        text not null,
  diff_patch        text,                  -- diff-match-patch from parent version
  status            text not null default 'draft', -- draft | approved | rejected
  citations_valid   boolean not null default false,
  approved_at       timestamptz,
  approved_by       uuid references auth.users(id),
  exported_docx_path text,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);

create index if not exists drafts_case_idx on public.drafts(case_id);
create index if not exists drafts_run_idx  on public.drafts(run_id);

alter table public.drafts enable row level security;
drop policy if exists "drafts owner all" on public.drafts;
create policy "drafts owner all" on public.drafts
  for all using (auth.uid() = owner_id) with check (auth.uid() = owner_id);

-- Trigger: block content_md modifications on approved drafts
create or replace function public.prevent_approved_draft_changes()
returns trigger
language plpgsql as $$
begin
  if old.status = 'approved' and new.content_md is distinct from old.content_md then
    raise exception 'Cannot modify content_md of an approved draft (id=%). Create a new revision instead.', old.id
      using errcode = 'check_violation';
  end if;
  return new;
end;
$$;

drop trigger if exists drafts_no_overwrite_approved on public.drafts;
create trigger drafts_no_overwrite_approved
  before update on public.drafts
  for each row execute procedure public.prevent_approved_draft_changes();

-- =============================================================
-- 8) Audit log
-- =============================================================
create table if not exists public.audit_log (
  id              uuid primary key default gen_random_uuid(),
  actor_id        uuid references auth.users(id),
  case_id         uuid references public.cases(id) on delete set null,
  action          text not null,         -- e.g. 'document.upload', 'draft.approve'
  resource_type   text,
  resource_id     uuid,
  payload         jsonb not null default '{}'::jsonb,
  created_at      timestamptz not null default now()
);

create index if not exists audit_log_actor_idx  on public.audit_log(actor_id);
create index if not exists audit_log_case_idx   on public.audit_log(case_id);

alter table public.audit_log enable row level security;
drop policy if exists "audit_log self read" on public.audit_log;
create policy "audit_log self read" on public.audit_log
  for select using (auth.uid() = actor_id);
-- writes: backend uses service_role key (bypasses RLS)

-- =============================================================
-- 9) Storage bucket: legal-documents (private, 25 MB)
-- =============================================================
insert into storage.buckets (id, name, public, file_size_limit)
values ('legal-documents', 'legal-documents', false, 26214400)
on conflict (id) do update set file_size_limit = excluded.file_size_limit, public = false;

-- Storage policies: paths must start with <user_id>/<case_id>/
drop policy if exists "legal-documents owner read"   on storage.objects;
drop policy if exists "legal-documents owner write"  on storage.objects;
drop policy if exists "legal-documents owner delete" on storage.objects;

create policy "legal-documents owner read"
  on storage.objects for select
  using (
    bucket_id = 'legal-documents'
    and split_part(name, '/', 1) = auth.uid()::text
  );

create policy "legal-documents owner write"
  on storage.objects for insert
  with check (
    bucket_id = 'legal-documents'
    and split_part(name, '/', 1) = auth.uid()::text
  );

create policy "legal-documents owner delete"
  on storage.objects for delete
  using (
    bucket_id = 'legal-documents'
    and split_part(name, '/', 1) = auth.uid()::text
  );

-- =============================================================
-- Done. 8 tables + RLS + bucket + RPC + triggers.
-- =============================================================
