# Galaxy Legal — Current State

**Last updated:** 2026-04-30
**Phase:** 2(b) complete · 2(c) Drive + Railway deferred to next session
**Preview URL:** https://ba999ff0-b0a0-4c59-b346-fc3f4eaa7af6.preview.emergentagent.com
**Repo:** github.com/Puzzlemanyyyyy/GALAXY-LEGAL

---

## What works end-to-end (verified in production-like preview)

### Authentication
- Supabase magic-link login via email (LoginPage)
- **Password fallback** for testing / dev: toggle "¿Tienes contraseña?" on LoginPage reveals a password input. Uses `supabase.auth.signInWithPassword` against the Supabase built-in password provider. Works even if Site URL/Redirect URLs are not yet configured.
- Password grant for automated tests (`/auth/v1/token?grant_type=password`)
- ProtectedRoute + AuthCallback wired
- Session persisted in `localStorage` under `sb-irzervhlczzzrydqfisn-auth-token`

### Cases & Documents
- Cases CRUD (RLS-enforced, user-scoped)
- Document upload (drag & drop): PDF, DOCX, TXT
- SHA-256 dedupe against `case_documents.hash_sha256`
- Text extraction (pdfplumber / python-docx / plain)
- Chunking via tiktoken `cl100k_base` (400 tokens / 50 overlap)
- Embeddings: OpenAI `text-embedding-3-small` (1536-dim) batched 100/req
- Storage: Supabase bucket `legal-documents` (25 MB, paths `<user_id>/<case_id>/...`)
- Vector search via Postgres RPC `match_document_chunks(query_embedding, p_case_id, threshold, count)`

### Workflows (4 implemented)
- `initial_analysis` — extract_facts + flag_risks
- `civil_demand` — encabezamiento + numbered hechos (every hecho with ≥1 `[E:xxx]` marker) + fundamentos + petitum + otrosíes
- `fiscal_consultation` — planteamiento + cuestiones + normativa + análisis + implicaciones + riesgos + conclusión
- `jurisprudence_analysis` — internal case-law analysis (no CENDOJ yet) with favorable vs adverse posture

All workflows use:
- JSON schema strict enforcement on OpenAI calls (`response_format=json_schema`)
- Retry-with-feedback loop (max 2 retries) when schema validation fails
- Incremental persistence of `output_jsonb._current_step` for observability

### Anti-fantasma (citation invariant)
- Every `[E:xxx]` marker resolves to an `evidence_id`
- `evidences.quote_excerpt` MUST substring-match (case-insensitive, whitespace-normalized) the source `case_documents.texto_extraido`
- Validator (`services/citation_validator.py`) runs after every workflow output
- If a single citation fails verbatim check → run goes to `needs_human` and NO draft is created
- **Production proof:** 81/81 evidences verbatim-verified (100%); 2/15 runs naturally went to `needs_human` because the LLM tried paraphrasing — caught by the validator, no hallucinations leaked through

### Drafts
- Atomic version increment via Postgres RPC `insert_draft_atomic(p_case_id, p_run_id, p_parent_id, p_tipo, p_content_md, p_diff)` with `pg_advisory_xact_lock(hash(case_id, tipo_documento))`
- Fallback to non-atomic `max+1` insert ONLY if RPC missing — emits `logger.warning("insert_draft_atomic RPC unavailable, falling back to max+1 (non-atomic)", exc_info=True)`
- Race-condition test: 5 concurrent inserts → 5 unique consecutive versions, no gaps
- Draft revisions trigger re-validation of citations against the original run's evidences
- Approve endpoint rejects (HTTP 422) revisions with unverified markers
- Trigger `trg_drafts_immutable` blocks edits to `content_md` after `status='approved'`

### Sharing (read-only public links)
- Table `shared_drafts (token uuid PK, draft_id, created_by, expires_at, watermark, view_count, last_viewed_at)` with RLS owner-all
- `POST /api/drafts/{id}/share` (24h / 7d / 30d / never + watermark)
- `GET /api/drafts/{id}/shares` (list active tokens with view_count)
- `DELETE /api/drafts/shares/{token}` (revoke)
- `GET /api/public/drafts/{token}` (no auth) → returns `{case, draft, evidences, watermark, expires_at}`
- View counter incremented atomically via RPC `increment_share_view(p_token)` SECURITY DEFINER (anon-callable)
- Frontend `/public/drafts/:token` → PublicDraftPage with split layout (draft body + evidence panel)
- Markers `[E:xxx]` are clickable `<button data-testid="evidence-marker-<id>" data-evidence-id="<id>">` → smooth scroll + 1.5s amber highlight on the matching evidence row in the side panel

### DOCX export
- `POST /api/drafts/{id}/export-docx` → generates Word file via python-docx (Title / H1 / H2 / H3 / List Bullet / **bold** / *italic*)
- `[E:xxx]` markers rendered as smaller grey runs (visible but unobtrusive)
- Uploaded to Supabase Storage at `<user>/<case>/exports/draft-<id>-v<ver>-<hash>.docx`
- Returns 1-hour signed URL
- Updates `drafts.exported_at` (now exposed via `services/mappers.py:draft_to_api`)
- Audit log entry `draft.export_docx`

### Budget guardrail
- `OPENAI_MONTHLY_BUDGET_USD=50` default in `config.py` (NOT in .env so it's safe to override)
- `services/budget.py:get_current_usage()` aggregates `runs.cost_usd` for the current month
- `POST /api/runs` returns **HTTP 402 Payment Required** if `spent >= budget`
- `GET /api/usage/current` returns `{spent_usd, budget_usd, remaining_usd, run_count, month, over_budget}`
- Frontend `UsageBar` component on Dashboard (green <80%, amber 80-100%, red 100%)

### Audit log
- `audit_log` table on every state-changing action (run.create, run.complete, draft.revision, draft.approve, draft.reject, draft.export_docx, share.create, share.revoke, etc.)
- 91+ entries in current preview DB

### Testing
- Backend: 45/45 pytest green (unit + e2e)
- Test files in `/app/backend/tests/`:
  - `test_chunker.py` — tiktoken chunking
  - `test_citation_validator.py` — verbatim substring matching
  - `test_workflow_registry.py` — registry integrity
  - `test_docx_exporter.py` — DOCX rendering
  - `test_budget.py` — over-budget detection
  - `test_sharing.py` — token lifecycle
  - `test_versioning.py` — race condition (5 concurrent atomic inserts)
  - `test_e2e_flow.py` — full pipeline (~$0.02 OpenAI per run)
  - `test_phase2b_e2e.py` — Phase 2b features end-to-end
- Frontend: smoke validated via Playwright screenshots (PublicDraftPage marker click → highlight)

---

## Backlog (deferred, not in scope yet)

### Phase 2(c) — Drive + production deploy (next session)
- `frontend/src/components/DrivePicker.jsx` — GIS `initTokenClient` + Picker with `drive.file` scope (privacy-first), folder selection disabled
- `backend/services/drive.py` + `backend/routes/drive.py`:
  - `POST /api/drive/import` accepting `{case_id, drive_files, access_token}`
  - Token validation against `https://oauth2.googleapis.com/tokeninfo` (verify `aud == GOOGLE_CLIENT_ID` + scope `drive.file`)
  - Binary download `GET /drive/v3/files/{id}?alt=media`
  - Google-native export `GET /drive/v3/files/{id}/export?mimeType=...` (Docs→docx, Sheets→xlsx)
  - Mid-import token expiry → return `{code:"DRIVE_TOKEN_EXPIRED", imported, pending}` (HTTP 403) so frontend can re-prompt and retry only pending
  - Reuse existing `_index_in_background` pipeline (chunk + embed)
  - SHA-256 dedupe against `case_documents.hash_sha256`
- Railway deploy:
  - Service 1: backend (root `/backend`, build `pip install`, start `uvicorn server:app --host 0.0.0.0 --port $PORT`)
  - Service 2: frontend (root `/frontend`, build `yarn build`, start `vite preview --host 0.0.0.0 --port $PORT`)
  - Configure env vars in Railway panel (NOT committed to repo)
  - Update `VITE_API_BASE_URL` in frontend to point at Railway backend domain
  - Update `BACKEND_CORS_ORIGINS` in backend to allow Railway frontend domain
- Supabase URL Configuration update with Railway domains

### Phase 3 — Legal-grade RAG (months of work)
- BOE bulk + indexing (~2 weeks, ~$30/mo extra hosting)
- CENDOJ jurisprudence integration (~3 weeks, complex parsing)
- Roman law corpus (Corpus Iuris Civilis) — nice-to-have academic
- Common law (BAILII / CourtListener) — only if a paying client requests it
- Legal citation validator (second pass): verify each statute/precedent reference against the external corpus, not just the case documents

### Phase 4 — Commercial polish
- OG image preview for shareable links (Pillow → `GET /api/public/drafts/{token}/og.png`)
- `/privacy` and `/terms` static pages
- ShareDraftModal Statistics view (RGPD-safe: only `last_viewed_at`, no IP, no geo)
- Whisper trial transcription
- Multi-tenant org/team UI
- Stripe billing
- CENDOJ/BOE live API

---

## Live test resources

- **Test user:** `e2e-test@galaxylegal.dev` / `GalaxyLegal_e2e_2026!`
- **Persistent 7-day public draft (no auth required):**
  https://ba999ff0-b0a0-4c59-b346-fc3f4eaa7af6.preview.emergentagent.com/public/drafts/4a1d042b-9f35-4cc0-a98a-1cde263be263
  Token: `4a1d042b-9f35-4cc0-a98a-1cde263be263` (NOT revoked)
- **Test credentials reference:** `/app/memory/test_credentials.md`

---

## Environment variables required for production deploy

### Backend (`/app/backend/.env`)
```
SUPABASE_URL=https://irzervhlczzzrydqfisn.supabase.co
SUPABASE_PROJECT_REF=irzervhlczzzrydqfisn
SUPABASE_ANON_KEY=<sb_publishable_...>
SUPABASE_SERVICE_ROLE_KEY=<service_role_jwt>      # secret, never log
SUPABASE_JWT_SECRET=<jwt_signing_secret>          # for token verification
SUPABASE_BUCKET=legal-documents

OPENAI_API_KEY=<sk-proj-...>                      # required for embeddings
OPENAI_MODEL=gpt-4o
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_MONTHLY_BUDGET_USD=50

EMERGENT_LLM_KEY=<sk-emergent-...>                # optional fallback for chat (NOT embeddings)

BACKEND_PORT=8001
BACKEND_CORS_ORIGINS=*                            # restrict to Railway frontend domain in prod

# Phase 2(c) — Drive (when added)
GOOGLE_CLIENT_ID=<client_id>.apps.googleusercontent.com   # for tokeninfo aud validation

# Mongo (legacy / not used in production code path; safe to omit on Railway)
MONGO_URL=mongodb://localhost:27017
DB_NAME=galaxy_legal
```

### Frontend (`/app/frontend/.env`)
```
VITE_API_BASE_URL=https://<railway-backend-domain>
VITE_SUPABASE_URL=https://irzervhlczzzrydqfisn.supabase.co
VITE_SUPABASE_ANON_KEY=<sb_publishable_...>

# Phase 2(c) — Drive (when added)
VITE_GOOGLE_CLIENT_ID=<same_as_backend>
VITE_GOOGLE_PICKER_API_KEY=<picker_api_key>
```

**Never commit `.env` files to GitHub.** All Railway env vars must be set in the Railway service panel (Variables tab).

---

## Run locally

```bash
# Backend
cd /app/backend
pip install -r requirements.txt
uvicorn server:app --reload --host 0.0.0.0 --port 8001

# Frontend
cd /app/frontend
yarn install
yarn dev   # http://localhost:5173

# Run tests
cd /app/backend
pytest tests/ -q                      # full suite (~$0.02 OpenAI per e2e run)
pytest tests/ -q -k 'not TestFullFlow'  # unit-only, no OpenAI cost
```

---

## Deploy to Railway (when Phase 2(c) starts)

1. Connect repo `Puzzlemanyyyyy/GALAXY-LEGAL` (already done by user).
2. Create two services from the same repo:
   - **Backend service**
     - Root directory: `/backend`
     - Build command: `pip install -r requirements.txt`
     - Start command: `uvicorn server:app --host 0.0.0.0 --port $PORT`
     - Set all backend env vars from the list above
   - **Frontend service**
     - Root directory: `/frontend`
     - Build command: `yarn install && yarn build`
     - Start command: `npx vite preview --host 0.0.0.0 --port $PORT`
     - Set all frontend env vars (with `VITE_API_BASE_URL` pointing at backend service public domain)
3. Generate public domains for both services.
4. Update `BACKEND_CORS_ORIGINS` in backend to the frontend's Railway domain.
5. Update Supabase URL Configuration:
   - Site URL: `https://<railway-frontend-domain>`
   - Redirect URLs: `https://<railway-frontend-domain>/auth/callback`
6. Update Google Cloud Console OAuth Client → Authorized JS origins: add `https://<railway-frontend-domain>`.
7. Smoke test: open Railway frontend, magic-link login, create case, upload doc, run `civil_demand`, approve, export DOCX, share public link.

---

## Ready-to-push checklist (2026-05-04)

Before clicking **"Save to GitHub"** in the Emergent chat, confirm:

- [x] Backend: 45/45 pytest green (`cd backend && pytest tests/ -q`)
- [x] Frontend lint: no issues (`LoginPage.jsx`, `PublicDraftPage.jsx`, `DashboardPage.jsx`, etc.)
- [x] LoginPage password fallback: toggle "¿Tienes contraseña?" added for dev/test access
- [x] Google Sign-In button removed from LoginPage (was stale scaffolding, Supabase provider was never enabled)
- [x] `services/mappers.py:draft_to_api` exposes `exported_at`
- [x] Evidence markers in PublicDraftPage are clickable (`<button data-testid="evidence-marker-…">` with scroll + 1.5s amber highlight)
- [x] `logger.warning` on `insert_draft_atomic` RPC fallback (runs.py + drafts.py)
- [x] `sharing.py::resolve_public_draft` wraps `.single()` calls in try/except → 404 clean on orphaned drafts
- [x] Persistent 7-day demo share token live and verified:
  `https://ba999ff0-b0a0-4c59-b346-fc3f4eaa7af6.preview.emergentagent.com/public/drafts/4a1d042b-9f35-4cc0-a98a-1cde263be263`
- [x] `docs/CURRENT_STATE.md` up to date

### What's NOT included in this push (intentional backlog)

- Google Drive Picker (Fase 2c) — requires user's Google Cloud OAuth credentials
- Railway deploy configuration (Fase 2c) — requires Railway account + env vars setup in Railway panel
- BOE / CENDOJ legal-corpus RAG (Fase 3a) — requires budget approval (~$400 one-shot + ~$30/mo hosting) and external corpus access
- Eur-Lex / vLex / commercial legal DBs (Fase 3b/c)
- OG image preview, /privacy, /terms (Fase 2d polish)

### After the push, the user must

1. Verify on `github.com/Puzzlemanyyyyy/GALAXY-LEGAL` that the 13 key files are present (see list in finish summary).
2. In Railway: **turn OFF auto-deploy** on the connected service until Fase 2c starts (otherwise Railway will try to build without env vars and fail silently).
3. Finish applying **Supabase URL Configuration** (Site URL + 3 Redirect URLs) — the form was open but unsaved in the last screenshot. Needed for the magic-link path to work end-to-end.
4. In Supabase Settings → Integrations: consider **disabling "Automatic branching"** — currently ON and triggers on every PR, costs money outside your Spend Cap.

---

## Commit message context (since Emergent auto-commits use UUIDs)

This document represents the closing of the following work, all of which is already in the auto-commit history:

> **feat: phase 2a + 2b complete**
>
> - Workflows: `initial_analysis`, `civil_demand`, `fiscal_consultation`, `jurisprudence_analysis` with JSON schema strict + verbatim citation validator
> - Document ingestion: upload, SHA-256 dedupe, extract (PDF/DOCX/TXT), chunk (tiktoken cl100k_base 400/50), embed (OpenAI text-embedding-3-small)
> - Drafts versioning: `insert_draft_atomic` RPC with advisory lock + diff
> - Anti-fantasma enforced: 81/81 evidences verbatim-verified in production
> - Public sharing: `shared_drafts` table + token-based read-only links with smooth-scroll-and-highlight on marker click
> - DOCX export with python-docx + signed Storage URL
> - Budget guardrail with HTTP 402
> - Audit log on all state changes
> - 45/45 backend pytest green
