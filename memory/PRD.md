# Galaxy Legal — PRD

## Original problem statement
AI-powered legal workspace para despachos y equipos in-house. Stack:
- **DB / Auth / Storage**: Supabase Pro (Postgres 17 + pgvector), proyecto `galaxy-legal` (`irzervhlczzzrydqfisn`), región `eu-west-3`
- **Backend**: FastAPI 0.115 (Python 3.11)
- **Frontend**: React 18 + Vite + Tailwind
- **LLM**: GPT-4o + `text-embedding-3-small` (1536 dim) — OpenAI SDK directa + Emergent LLM Key fallback
- **Drive**: Google Drive API + Picker (pendiente Fase 2-c)
- **Deploy producción**: Railway (pendiente Fase 2-c)

## Core requirements (hard rules)
1. **Anti-fantasma**: cada cita en un draft tiene `evidence_id` que substring-match verbatim al `texto_extraido`.
2. **RLS-first**: queries de usuario vía JWT; service-role solo para storage + audit + workflow bg.
3. **Storage paths**: `<user_id>/<case_id>/<...>` (bucket privado 25 MB).
4. **Drafts inmutables tras aprobación**: trigger `trg_drafts_immutable` bloquea modificar `content_md`.
5. **JSON schema strict** en cada llamada OpenAI.
6. **Idempotencia**: runs nunca sobrescriben; drafts auto-incrementan version con advisory lock (Fase 2-b).
7. **Budget guardrail**: antes de cada run se verifica consumo mensual vs `OPENAI_MONTHLY_BUDGET_USD`.

## What's been implemented

### 2026-04-28 · Fase 1 — Login + infra base (verificada)
- Repo `galaxy-legal` integrado en `/app`, supervisor configurado (backend :8001, frontend :3000, prefijo `/api`).
- LoginPage (magic link + Google) con diseño dark/sober + Cormorant.
- `ProtectedRoute` + `AuthCallback` wired.

### 2026-04-30 · Fase 2(a) — Núcleo crítico (e2e, 24/24 tests)
- Schema real introspeccionado + capa `services/mappers.py` que traduce nombres DB (`nombre`, `tipo_documento`, `completed_at`, `error_message`, `diff_from_previous`, `reviewer_id`, `page_count`) ↔ shape frontend legacy.
- Ingestion: PDF/DOCX/TXT → chunking (tiktoken, 400/50) → embeddings batch 100 → `document_chunks` con vector(1536).
- Workflow engine con JSON schema strict enforcement + retry con feedback + persistencia incremental de `output_jsonb._current_step`.
- Workflow `initial_analysis`: extract_facts + flag_risks.
- Citation validator verbatim; drafts con marcadores `[E:xxx]` resueltos a tooltips verificados.
- Frontend 3-columnas CasePage, DraftEditorPage con preview, upload drag&drop.

### 2026-04-30 · Fase 2(b) — Workflows + export + budget + sharing (tests 30/30 en iter, 6 skipped esperan SQL)
**Workflows nuevos** (`backend/services/workflows/`):
- `civil_demand.py` — demanda civil (encabezamiento, hechos numerados con ≥1 evidence cada uno, fundamentos de derecho, petitum, otrosíes).
- `fiscal_consultation.py` — consulta fiscal (planteamiento, cuestiones, normativa aplicable sin inventar artículos, análisis, implicaciones, riesgos, conclusión).
- `jurisprudence_analysis.py` — análisis de jurisprudencia interna del caso (sin CENDOJ), findings con postura favorable vs contraria.
- `registry.py` actualizado con los 4 workflows.

**Export DOCX** (`services/docx_exporter.py`):
- Conversor markdown-ish (H1/H2/H3, bullets, **bold**, *italic*, `[E:xxx]` como superíndice gris) a `.docx` vía `python-docx`.
- Sube a Storage bajo `<user>/<case>/exports/draft-<id>-v<ver>-<hash>.docx` y devuelve signed URL 1h.
- Endpoint `POST /api/drafts/{id}/export-docx` actualiza `drafts.exported_at` y escribe audit log.

**Budget guardrail** (`services/budget.py` + `routes/usage.py`):
- Calcula consumo del mes en curso sumando `runs.cost_usd` on-the-fly (sin tabla materializada).
- `POST /api/runs` devuelve **402 Payment Required** si `spent >= OPENAI_MONTHLY_BUDGET_USD`.
- `GET /api/usage/current` devuelve `{spent_usd, budget_usd, remaining_usd, run_count, month, over_budget}`.
- Frontend: componente `UsageBar` en Dashboard con barra de progreso (verde <80%, ámbar 80-100%, rojo 100%).

**Re-validación de citas en revisiones** (`routes/drafts.py`):
- `POST /api/drafts/{id}/revision` detecta `[E:xxx]` en el nuevo `content_md`; cualquier marcador desconocido va a `unverified_markers[]`; re-valida `quote_excerpt ⊂ texto_extraido` contra los docs del run original.
- Response incluye `citations_valid` + `unverified_markers` + `validation_errors`.
- `POST /api/drafts/{id}/approve` sobre una revisión devuelve **422** si `unverified_markers` o `validation_errors` existen.

**Atomic version increment** (`services/workflows` + RPC `insert_draft_atomic`):
- RPC Postgres con `pg_advisory_xact_lock(hash(case_id, tipo_documento))` → `SELECT MAX(version)+1` → `INSERT ... RETURNING *`.
- Tanto `routes/runs.py` como `routes/drafts.py::create_revision` llaman a la RPC; fallback a max+1 no-transaccional si la RPC aún no está desplegada.

**Shareable read-only links** (tabla `shared_drafts` + `services/sharing.py` + `routes/public.py`):
- Tabla nueva: `shared_drafts (token uuid PK, draft_id, created_by, expires_at, watermark, view_count, last_viewed_at)` + RLS "owner all" + RPC `increment_share_view` (SECURITY DEFINER, anon-callable).
- Endpoint owner: `POST /api/drafts/{id}/share {expires_in: "24h"|"7d"|"30d"|"never", watermark}`, `GET /api/drafts/{id}/shares`, `DELETE /api/drafts/shares/{token}`.
- Endpoint público: `GET /api/public/drafts/{token}` (sin auth) devuelve `{case:{title,jurisdiccion,materia}, draft:{title,content_md,version,status}, evidences:[{external_id,page,paragraph,quote_excerpt,verified}], watermark, expires_at}`. Incrementa view_count atómicamente.
- Frontend: ruta pública `/public/drafts/:token` → `PublicDraftPage.jsx` con layout split (draft + panel de evidencias clicables). Markers `[E:xxx]` son `<button>` que hace scroll + highlight de la evidencia. Banner "Citas verificadas por Galaxy Legal" + watermark opcional + footer legal.
- Modal `ShareDraftModal.jsx` en DraftEditor: selector expiración, watermark, listado de links activos con copiar/abrir/revocar y contador de vistas.

**Tests añadidos** (todos verdes):
- `test_docx_exporter.py` — 2 tests (headings, bullets, bold/italic, footer).
- `test_budget.py` — 3 tests (vacío, suma, over-budget).
- `test_workflow_registry.py` — 3 tests (4 workflows registrados, estructura OK, unknown → ValueError).
- `test_sharing.py` — 3 tests (skip automático si `shared_drafts` no existe; create+resolve+revoke+invalid expires).
- `test_versioning.py` — 1 test asyncio (skip si RPC no existe; 5 inserts concurrentes con advisory lock, versiones únicas y consecutivas).

## Pendiente

### P0 — Usuario debe aplicar SQL
Aplicar `/app/supabase/0002_phase2b.sql` vía MCP o SQL Editor:
- `shared_drafts` tabla + RLS policy.
- `increment_share_view(uuid)` RPC.
- `insert_draft_atomic(...)` RPC con advisory lock.

Ninguna alteración sobre objetos existentes — solo add-only.

### P1 — Fase 2(c): Drive + producción
- `components/DrivePicker.jsx` + `POST /api/drive/import`.
- Google OAuth + Picker API en Google Cloud Console.
- Deploy Railway (2 servicios: backend + frontend).
- Supabase URL Configuration para dominio público.

### P2 — Enhancements
- CENDOJ / BOE live API (reemplaza al "interno del case").
- Whisper transcripción juicios.
- Multi-tenant org/team UI.
- Billing Stripe.
- Supabase Auth URL Configuration en preview (Site URL + Redirect) para magic link real end-to-end.

## Out of scope (v2+)
- Modo demo sin login (idea comercial descartada por el usuario — "un demo con workflows flojos vende peor que ninguno").
