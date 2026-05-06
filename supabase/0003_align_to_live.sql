-- Galaxy Legal — Phase 2-c · 0003_align_to_live.sql
-- Reconciles 0001_init_schema.sql with the column/enum names actually used
-- by the live backend code in production (irzervhlczzzrydqfisn).
--
-- HISTORY: 0001 was authored from a domain English schema (filename, status,
-- draft_type, finished_at, ...). The live database — manually evolved by the
-- product owner during Phase 2-a/b — uses Spanish-flavoured names plus a
-- pair of postgres ENUMs (workflow_type, draft_status) referenced by
-- insert_draft_atomic in 0002_phase2b.sql.
--
-- This script is IDEMPOTENT: it can be run repeatedly. It uses:
--   * `do $$ ... $$` blocks with `if exists` / `if not exists` guards
--   * `alter table ... rename column ... to ...` only when the source column
--     is present
--   * `create type ... if not exists` (emulated via pg_type lookup)
-- so applying it on top of 0001+0002 brings any clean Supabase project to
-- the same shape as production. Applying it on top of the live database is
-- a no-op.
--
-- Cross-checked column-by-column against /app/backend/services/mappers.py
-- and the route handlers as of 2026-05-XX.
--
-- ============================================================================
-- 0) ENUM types referenced by 0002_phase2b.sql::insert_draft_atomic
-- ============================================================================
do $$ begin
  if not exists (select 1 from pg_type where typname = 'workflow_type') then
    create type workflow_type as enum (
      'initial_analysis',
      'civil_demand',
      'fiscal_consultation',
      'jurisprudence_analysis'
    );
  end if;
end $$;

do $$ begin
  if not exists (select 1 from pg_type where typname = 'draft_status') then
    create type draft_status as enum ('draft', 'in_review', 'approved', 'exported', 'rejected');
  end if;
end $$;


-- ============================================================================
-- 1) case_documents — column renames + missing JSONB
-- ============================================================================

-- 1.a) filename -> nombre
do $$ begin
  if exists (select 1 from information_schema.columns
              where table_schema='public' and table_name='case_documents' and column_name='filename')
     and not exists (select 1 from information_schema.columns
              where table_schema='public' and table_name='case_documents' and column_name='nombre')
  then
    alter table public.case_documents rename column filename to nombre;
  end if;
end $$;

-- 1.b) pages_count -> page_count
do $$ begin
  if exists (select 1 from information_schema.columns
              where table_schema='public' and table_name='case_documents' and column_name='pages_count')
     and not exists (select 1 from information_schema.columns
              where table_schema='public' and table_name='case_documents' and column_name='page_count')
  then
    alter table public.case_documents rename column pages_count to page_count;
  end if;
end $$;

-- 1.c) Add `tipo` (legal-domain category, distinct from mime_type).
--      The mapper inserts the literal "other"; the user can edit later.
alter table public.case_documents add column if not exists tipo text not null default 'other';

-- 1.d) Add `metadata jsonb` — used to carry source ('upload'|'drive'),
--      file extension, index_error, etc.
alter table public.case_documents add column if not exists metadata jsonb not null default '{}'::jsonb;

-- 1.e) Drop deprecated standalone columns IF they exist (their data has been
--      migrated into metadata or is derived in mappers.py).
--      Status -> derived from indexed_at + metadata.index_error.
--      Source -> moved to metadata.source.
--      index_error -> moved to metadata.index_error.
--      Texto extraido is kept (live schema has it) — no drop.
do $$ begin
  if exists (select 1 from information_schema.columns
              where table_schema='public' and table_name='case_documents' and column_name='status') then
    alter table public.case_documents drop column status;
  end if;
  if exists (select 1 from information_schema.columns
              where table_schema='public' and table_name='case_documents' and column_name='source') then
    alter table public.case_documents drop column source;
  end if;
  if exists (select 1 from information_schema.columns
              where table_schema='public' and table_name='case_documents' and column_name='index_error') then
    alter table public.case_documents drop column index_error;
  end if;
end $$;


-- ============================================================================
-- 2) runs — error -> error_message, finished_at -> completed_at
-- ============================================================================

-- 2.a) error -> error_message
do $$ begin
  if exists (select 1 from information_schema.columns
              where table_schema='public' and table_name='runs' and column_name='error')
     and not exists (select 1 from information_schema.columns
              where table_schema='public' and table_name='runs' and column_name='error_message')
  then
    alter table public.runs rename column error to error_message;
  end if;
end $$;

-- 2.b) finished_at -> completed_at
do $$ begin
  if exists (select 1 from information_schema.columns
              where table_schema='public' and table_name='runs' and column_name='finished_at')
     and not exists (select 1 from information_schema.columns
              where table_schema='public' and table_name='runs' and column_name='completed_at')
  then
    alter table public.runs rename column finished_at to completed_at;
  end if;
end $$;

-- 2.c) `current_step` is a derived field exposed by mappers from
--      output_jsonb._current_step. No physical column needed; drop it if
--      0001 created one and no live code reads it directly.
do $$ begin
  if exists (select 1 from information_schema.columns
              where table_schema='public' and table_name='runs' and column_name='current_step') then
    alter table public.runs drop column current_step;
  end if;
end $$;


-- ============================================================================
-- 3) drafts — major realignment
-- ============================================================================

-- 3.a) draft_type -> tipo_documento (and switch to workflow_type enum)
do $$ begin
  if exists (select 1 from information_schema.columns
              where table_schema='public' and table_name='drafts' and column_name='draft_type')
     and not exists (select 1 from information_schema.columns
              where table_schema='public' and table_name='drafts' and column_name='tipo_documento')
  then
    alter table public.drafts rename column draft_type to tipo_documento;
  end if;
end $$;

-- Convert tipo_documento to enum if currently text. Skip silently if already
-- the enum type or if the rename above didn't run.
do $$ declare
  current_type text;
begin
  select data_type into current_type
    from information_schema.columns
   where table_schema='public' and table_name='drafts' and column_name='tipo_documento';
  if current_type = 'text' then
    alter table public.drafts
      alter column tipo_documento type workflow_type using tipo_documento::workflow_type;
  end if;
end $$;

-- 3.b) status -> draft_status enum (was free text in 0001)
do $$ declare
  current_type text;
begin
  select data_type into current_type
    from information_schema.columns
   where table_schema='public' and table_name='drafts' and column_name='status';
  if current_type = 'text' then
    alter table public.drafts
      alter column status drop default,
      alter column status type draft_status using status::draft_status,
      alter column status set default 'draft'::draft_status;
  end if;
end $$;

-- 3.c) diff_patch -> diff_from_previous
do $$ begin
  if exists (select 1 from information_schema.columns
              where table_schema='public' and table_name='drafts' and column_name='diff_patch')
     and not exists (select 1 from information_schema.columns
              where table_schema='public' and table_name='drafts' and column_name='diff_from_previous')
  then
    alter table public.drafts rename column diff_patch to diff_from_previous;
  end if;
end $$;

-- 3.d) approved_by -> reviewer_id
do $$ begin
  if exists (select 1 from information_schema.columns
              where table_schema='public' and table_name='drafts' and column_name='approved_by')
     and not exists (select 1 from information_schema.columns
              where table_schema='public' and table_name='drafts' and column_name='reviewer_id')
  then
    alter table public.drafts rename column approved_by to reviewer_id;
  end if;
end $$;

-- 3.e) Add exported_at (was `exported_docx_path text` — only the timestamp
--      is read by mappers.draft_to_api; the storage path is regenerated per
--      export and not persisted).
alter table public.drafts add column if not exists exported_at timestamptz;

-- 3.f) Drop legacy columns no longer read by the backend.
--      title -> derived in mappers from the H1 of content_md.
--      citations_valid -> derived from status + presence of parent.
--      exported_docx_path -> we only persist exported_at; signed URLs are
--                            regenerated on demand.
do $$ begin
  if exists (select 1 from information_schema.columns
              where table_schema='public' and table_name='drafts' and column_name='title') then
    alter table public.drafts drop column title;
  end if;
  if exists (select 1 from information_schema.columns
              where table_schema='public' and table_name='drafts' and column_name='citations_valid') then
    alter table public.drafts drop column citations_valid;
  end if;
  if exists (select 1 from information_schema.columns
              where table_schema='public' and table_name='drafts' and column_name='exported_docx_path') then
    alter table public.drafts drop column exported_docx_path;
  end if;
end $$;

-- 3.g) Unique index required by insert_draft_atomic (case_id, tipo_documento, version)
create unique index if not exists drafts_case_tipo_version_uidx
  on public.drafts(case_id, tipo_documento, version);


-- ============================================================================
-- 4) evidences — external_id semantics
-- ============================================================================
--
-- 0001 introduced a dedicated `external_id` column ("e001", ...). The live
-- code reuses `claim_id` for that purpose (mappers.evidence_to_api falls
-- back to id when claim_id is null). To keep both shapes valid we leave
-- `external_id` if it exists and additionally backfill claim_id when claim_id
-- is null. New rows go straight into claim_id.
do $$ begin
  if exists (select 1 from information_schema.columns
              where table_schema='public' and table_name='evidences' and column_name='external_id')
  then
    update public.evidences
       set claim_id = external_id
     where claim_id is null and external_id is not null;
  end if;
end $$;

-- Unique index on (run_id, claim_id) mirrors the original (run_id, external_id)
-- so no two evidences in the same run can collide on their public marker.
create unique index if not exists evidences_run_claim_uidx
  on public.evidences(run_id, claim_id) where claim_id is not null;


-- ============================================================================
-- Done. Re-run is safe: every block is idempotent.
-- ============================================================================
