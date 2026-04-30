# Galaxy Legal — PRD

## Original problem statement
AI-powered legal workspace para despachos y equipos in-house. Stack:
- **DB / Auth / Storage**: Supabase Pro (Postgres 17 + pgvector), proyecto `galaxy-legal` (`irzervhlczzzrydqfisn`), región `eu-west-3`
- **Backend**: FastAPI 0.115 (Python 3.11)
- **Frontend**: React 18 + Vite + Tailwind
- **LLM**: GPT‑4o + `text-embedding-3-small` (1536 dim) — OpenAI directa (SDK) + Emergent LLM Key como fallback
- **Drive**: Google Drive API + Picker (pendiente Fase 2-c)
- **Deploy producción**: Railway (backend + frontend) — pendiente

## Core requirements
- **Anti-fantasma**: cada cita en un draft tiene `evidence_id` que substring-match verbatim al `texto_extraido` del documento fuente.
- **RLS-first**: queries de usuario vía JWT; service-role solo para storage + audit_log + workflow background.
- **Storage paths**: `<user_id>/<case_id>/<filename>` (bucket privado `legal-documents`, 25 MB).
- **Drafts inmutables tras aprobación**: trigger `trg_drafts_immutable` bloquea modificaciones de `content_md` en drafts `approved`.
- **JSON schema strict** en cada llamada OpenAI (`response_format={"type":"json_schema","strict":true}`).
- **Idempotencia**: runs nunca sobrescriben; drafts auto-incrementan version por `(case_id, tipo_documento)`.

## What's been implemented

### 2026-04-28 · Fase 1 — Login + infra (verificado e2e)
- Repo `galaxy-legal` integrado en `/app` preservando `.git` con remoto a `Puzzlemanyyyyy/GALAXY-LEGAL`.
- Backend FastAPI en supervisor :8001 (`server.py` re-exporta `app`); rutas bajo `/api`.
- Frontend Vite en supervisor :3000 (`yarn start` → `vite --host 0.0.0.0 --port 3000`).
- Pantalla de login (magic link + Google OAuth) con diseño dark/sober + Cormorant + glow gold.
- Magic link e2e: petición a `/auth/v1/otp` con `redirect_to=<preview>/auth/callback` correcto.

### 2026-04-30 · Fase 2(a) — Núcleo crítico (e2e verificado por testing agent, 24/24 tests)
**Backend**
- **Services** (`/app/backend/services/`): `llm.py` (dual-path OpenAI/Emergent + cost tracking + retry 3x), `extractor.py` (PDF/DOCX/TXT), `chunker.py` (tiktoken cl100k_base, 400/50 overlap, page tracking), `embeddings_pipeline.py` (batch 100), `citation_validator.py` (substring-match verbatim, normaliza whitespace), `audit.py` (write-only), `workflows/base.py` (engine con JSON schema enforcement + retry con feedback + persistencia incremental), `workflows/initial_analysis.py` (pasos: `extract_facts` + `flag_risks`), `workflows/registry.py`, `mappers.py` (traduce DB schema ↔ API response para absorber quirks).
- **Routes** (`/api/...`): `documents` (upload + dedupe SHA-256 + bg indexing, list, get, reindex, delete), `runs` (types, list, get, draft, evidences, POST con bg task), `drafts` (list, get, revision con `diff_match_patch`, approve bloqueado si `parent_draft_id` ≠ null, reject).
- **Adaptación al schema real**: mapper traduce `nombre↔filename`, `page_count↔pages_count`, `tipo_documento↔draft_type`, `completed_at↔finished_at`, `error_message↔error`, `diff_from_previous↔diff_patch`, `reviewer_id↔approved_by`; enum `runs.status` usa `completed` (no `succeeded`); `case_documents.tipo` cae a `'other'` y la extensión real se guarda en `metadata.ext`; estado derivado (`indexing/ready/failed`) desde `indexed_at` + `metadata.index_error`; `citations_valid` computado por mapper (true si el draft no tiene `parent_draft_id`).

**Frontend** (`/app/frontend/src/`)
- `lib/api.js` — wrapper fetch con Bearer token automático de sesión Supabase.
- `pages/LoginPage.jsx` — magic link + Google con `data-testid` completos.
- `pages/DashboardPage.jsx` — lista real de cases con cards clicables, modal de creación (`NewCaseModal`), status pills.
- `pages/CasePage.jsx` — layout 3 columnas: izquierda (DocumentUpload drag&drop + lista docs con DocStatus badges), centro (tabs Resumen/Borradores/Evidencias/Auditoría), derecha (WorkflowCard con `workflow-card-<type>` testid + lista de runs con polling).
- `pages/DraftEditorPage.jsx` — editor markdown + vista previa con marcadores `[E:xxx]` resaltados (verde verificado / rojo no), panel de evidencias con quote_excerpt, banner si hay citas sin verificar, Aprobar deshabilitado si `citations_valid=false`.
- `components/{NewCaseModal, DocumentUpload, WorkflowCard}.jsx` — componentes con `data-testid` consistentes.
- Routing: `/` → `/dashboard` → `/cases/:caseId` → `/cases/:caseId/drafts/:draftId`.

**Testing (iteración 1)** — `/app/test_reports/iteration_1.json`
- 24/24 tests verdes (9 unit + 15 e2e backend): upload → indexación → workflow → citas verbatim-verificadas → aprobación → inmutabilidad.
- Anti-fantasma verificado: cada `evidence.quote_excerpt` substring-match al `texto_extraido` del doc. Todas `verified=true`.
- Smoke e2e manual del main agent: run `initial_analysis` produjo draft con 5 citas verificadas (`e001..e005`), coste $0.015, aprobado OK.
- Frontend verificado: auth via password grant → localStorage inyectado → `/dashboard` → 4 cases cards → click → `/cases/:id` → workflow-card-initial_analysis visible.

### Correcciones aplicadas post-testing
- Fix template literal roto en `CasePage.jsx:160` que renderizaba `${0.0169}` literal (ahora `$0.0169`).
- `data-testid="workflows-list"` añadido para facilitar selectores de test.
- Limpieza de ramas legacy `'succeeded'` (ahora solo `'completed'`).
- Confirmado `data-testid="workflow-card-initial_analysis"` presente en `WorkflowCard.jsx`.

## Hard rules enforced (verificadas)
1. ✅ **No source, no claim** — validador rechaza claims sin `evidence_ids`.
2. ✅ **Verbatim citation** — `quote_excerpt` substring-match case-insensitive whitespace-normalized al `texto_extraido`.
3. ✅ **No silent overwrite** — trigger DB bloquea overwrite de approved; revisions crean nueva versión con `parent_draft_id`.
4. ✅ **RLS-first** — queries usuario via `get_user_client(token)`; service-role solo en rutas admin (storage, audit, workflow bg).
5. ✅ **Storage paths** siempre `<user_id>/<case_id>/<uuid>-<filename>`.
6. ✅ **JSON schema strict** en cada llamada OpenAI.
7. ✅ **Idempotencia** runs + auto-increment version en drafts.

## Pendiente

### P1 — Workflows adicionales (Fase 2-b)
- `workflows/civil_demand.py` — demanda civil (encabezamiento, hechos, fundamentos, petitum, otrosíes).
- `workflows/fiscal_consultation.py` — consulta fiscal con citas a normativa BOE.
- `workflows/jurisprudence_analysis.py` — análisis jurisprudencia interna.
- Export DOCX (`GET /api/drafts/{id}/export-docx` con `python-docx`).
- Cost tracking global + budget guardrail mensual (`OPENAI_MONTHLY_BUDGET_USD`).
- Re-validación de citas en revisiones humanas.
- Version auto-increment transaccional (Postgres function + upsert) para evitar carreras.

### P2 — Drive + producción (Fase 2-c)
- `components/DrivePicker.jsx` + `POST /api/drive/import`.
- Google OAuth + Picker API en Google Cloud Console.
- Suite pytest workflows (mocked OpenAI).
- Deploy producción Railway + Supabase URL Configuration con dominio público.
- Configurar Supabase URL Configuration con preview URL (Site URL + Redirect URLs) para magic link e2e real.

### Out of scope (v2+)
- BOE / CENDOJ live API.
- Whisper transcripción juicios.
- Multi-tenant org/team UI.
- Billing / subscriptions.
- Modo Demo sin login (idea comercial, usuario la descartó para v1 porque "un demo con workflows flojos vende peor que ninguno").
