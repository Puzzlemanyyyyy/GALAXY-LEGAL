-- Galaxy Legal — Phase 2-b schema additions
-- Adds: shared_drafts table + increment_share_view RPC + insert_draft_atomic RPC
-- Safe to apply: only creates new objects, does not touch existing tables or enums.
-- Apply via Supabase Dashboard → SQL Editor → Run.

-- =============================================================
-- 1) shared_drafts — read-only public links
-- =============================================================
create table if not exists public.shared_drafts (
  token           uuid primary key default gen_random_uuid(),
  draft_id        uuid not null references public.drafts(id) on delete cascade,
  created_by      uuid not null references auth.users(id) on delete cascade,
  expires_at      timestamptz,                    -- null = never expires
  watermark       text,                           -- optional firm watermark shown on the public page
  view_count      integer not null default 0,
  last_viewed_at  timestamptz,
  created_at      timestamptz not null default now()
);

create index if not exists shared_drafts_draft_idx      on public.shared_drafts(draft_id);
create index if not exists shared_drafts_created_by_idx on public.shared_drafts(created_by);

alter table public.shared_drafts enable row level security;

-- Only the creator can list / update / delete their own share tokens via the authenticated client.
drop policy if exists "shared_drafts owner all" on public.shared_drafts;
create policy "shared_drafts owner all" on public.shared_drafts
  for all using (auth.uid() = created_by) with check (auth.uid() = created_by);
-- The anonymous public endpoint uses the service_role key AND explicitly checks
-- token+expiry before returning anything, so no permissive SELECT policy for anon.

-- =============================================================
-- 2) increment_share_view — atomic view counter usable from anon
-- =============================================================
create or replace function public.increment_share_view(p_token uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  update public.shared_drafts
     set view_count = view_count + 1,
         last_viewed_at = now()
   where token = p_token
     and (expires_at is null or expires_at > now());
end;
$$;

grant execute on function public.increment_share_view(uuid) to anon, authenticated;

-- =============================================================
-- 3) insert_draft_atomic — race-safe draft version bump
-- =============================================================
-- Uses a transaction-level advisory lock keyed on (case_id, tipo_documento)
-- so concurrent workflow runs can't collide on the
-- drafts_case_tipo_version_uidx unique constraint.
create or replace function public.insert_draft_atomic(
  p_case_id     uuid,
  p_run_id      uuid,
  p_parent_id   uuid,
  p_tipo        workflow_type,
  p_content_md  text,
  p_diff        text
)
returns public.drafts
language plpgsql
security definer
set search_path = public
as $$
declare
  v_lock_key bigint;
  v_next     integer;
  v_row      public.drafts;
begin
  v_lock_key := hashtextextended(p_case_id::text || ':' || p_tipo::text, 0);
  perform pg_advisory_xact_lock(v_lock_key);

  select coalesce(max(version), 0) + 1 into v_next
    from public.drafts
   where case_id = p_case_id and tipo_documento = p_tipo;

  insert into public.drafts (
    case_id, run_id, parent_draft_id, version, tipo_documento,
    content_md, diff_from_previous, status
  ) values (
    p_case_id, p_run_id, p_parent_id, v_next, p_tipo,
    p_content_md, p_diff, 'draft'::draft_status
  )
  returning * into v_row;

  return v_row;
end;
$$;

grant execute on function public.insert_draft_atomic(uuid, uuid, uuid, workflow_type, text, text) to service_role, authenticated;

-- =============================================================
-- Done. 1 table + 2 RPCs. No alterations to existing objects.
-- =============================================================
