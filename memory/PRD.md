# Galaxy Legal — PRD

## Original problem statement
AI-powered legal workspace para despachos y equipos in-house. Stack:
- **DB / Auth / Storage**: Supabase Pro (Postgres 17 + pgvector), proyecto `galaxy-legal` (`irzervhlczzzrydqfisn`), región `eu-west-3`
- **Backend**: FastAPI 0.115 (Python 3.11)
- **Frontend**: React 18 + Vite + Tailwind
- **LLM**: GPT‑4o + `text-embedding-3-small` (1536 dim)
- **Drive**: Google Drive API + Google Picker (`drive.file` scope)
- **Deploy producción**: Railway (backend + frontend)

## User personas
- Abogado/a de despacho que sube documentos (PDF, DOCX) a expedientes y necesita generar borradores legales con citas verificables.
- Asesor fiscal que sube normativa y consulta IA para producir una respuesta razonada con referencias al BOE.
- Compliance / responsable jurídico de empresa que audita drafts y gestiona aprobaciones.

## Core requirements
- **Anti-fantasma**: cada cita en un draft debe tener `evidence_id` que substring-match al texto original del documento.
- **RLS-first**: todas las queries de usuario usan cliente con JWT, no `service_role`.
- **Storage paths**: `<user_id>/<case_id>/<filename>` (bucket privado `legal-documents`, 25MB).
- **Drafts inmutables al aprobar**: trigger en DB bloquea modificaciones de drafts `approved`.
- **JSON schema en LLM**: todas las llamadas usan `response_format=json_schema`.
- **Idempotencia**: nunca sobrescribir runs/drafts existentes.

## What's been implemented

### 2026-04-28 — Fase 1: Infraestructura y Login
- Repo `galaxy-legal` desempaquetado en `/app` (preserva `.git` con remoto a `Puzzlemanyyyyy/GALAXY-LEGAL`).
- Backend FastAPI: `server.py` re-exporta `app` desde `main.py`. Todas las rutas con prefijo `/api`.
- Frontend Vite en supervisor :3000 (`yarn start` → `vite --host 0.0.0.0 --port 3000`).
- `.env` separados con `VITE_*` (Supabase publishable key) y `REACT_APP_BACKEND_URL`.
- Pantalla de login (magic link + Google OAuth) renderiza con diseño dark/sober + Cormorant + glow gold.
- `data-testid` en todos los CTAs.
- Magic link verificado e2e: petición POST a `/auth/v1/otp` con `redirect_to` correcto.

### 2026-04-29 — Fase 2 (a): Núcleo crítico (ingestion + initial_analysis + UI)
**SQL migration** (`/app/supabase/0001_init_schema.sql`) — 8 tablas (`profiles`, `cases`, `case_documents`, `document_chunks`, `runs`, `evidences`, `drafts`, `audit_log`) + RLS + bucket privado `legal-documents` + RPC `match_document_chunks` + trigger anti-overwrite + auto-create profile on signup.

**Backend services**:
- `services/llm.py` — cliente flexible: chat por `emergentintegrations` (Emergent LLM Key) o OpenAI SDK directo si `OPENAI_API_KEY` está set; embeddings siempre vía OpenAI SDK; cost tracking (gpt-4o, text-embedding-3-small) + retry exponencial 3x.
- `services/extractor.py` — PDF (pypdf), DOCX (python-docx), TXT con fallback. Devuelve `{full_text, pages, pages_count}`.
- `services/chunker.py` — paragraph-aware con `tiktoken cl100k_base`, target 400 tokens / overlap 50, page tracking.
- `services/embeddings_pipeline.py` — extract → chunk → embed (batch 100) → insert en `document_chunks` con vector(1536) + actualiza `case_documents.status='ready'`.
- `services/citation_validator.py` — substring-match case-insensitive whitespace-normalized; rechaza paráfrasis, evidencias <10 chars, document_ids inexistentes.
- `services/audit.py` — write-only audit_log helper.
- `services/workflows/base.py` — `Workflow` + `WorkflowStep` con JSON schema enforcement, validador custom, retry-on-fail con feedback al modelo, persistencia incremental de outputs.
- `services/workflows/initial_analysis.py` — workflow `initial_analysis` (pasos: `extract_facts` + `flag_risks`) que produce draft con resumen, partes, hechos referenciando `[E:xxx]`, riesgos, próximos pasos.
- `services/workflows/registry.py` — registry de workflows.

**Backend routes** (`/api` prefix):
- `documents.py` — `GET`, `GET /{id}`, `POST /upload` (multipart, dedupe SHA-256, storage upload, queue indexing en background), `POST /{id}/reindex`, `DELETE /{id}`.
- `runs.py` — `GET /types`, `GET`, `GET /{id}`, `GET /{id}/evidences`, `GET /{id}/draft`, `POST` (queue + bg task que ejecuta workflow → valida citas → persist draft + evidences).
- `drafts.py` — `GET`, `GET /{id}`, `POST /{id}/revision` (diff-match-patch + version increment), `POST /{id}/approve` (requires citations_valid), `POST /{id}/reject`.

**Frontend**:
- `lib/api.js` — wrapper fetch con Bearer token automático.
- `pages/DashboardPage.jsx` — lista real de cases con cards clicables, modal de creación, status pills, empty state.
- `pages/CasePage.jsx` — layout 3 columnas: izquierda (upload + lista de docs con badges de indexación), centro (tabs: Resumen / Borradores / Evidencias / Auditoría), derecha (workflow cards + lista de runs con polling).
- `pages/DraftEditorPage.jsx` — editor markdown + vista previa con marcadores `[E:xxx]` resaltados (verde verificado, rojo no verificado), panel lateral de evidencias con quote_excerpt, banner si hay citas sin verificar, "Aprobar" deshabilitado si no es válido.
- `components/NewCaseModal.jsx` — formulario con título, referencia, jurisdicción, materia, descripción.
- `components/DocumentUpload.jsx` — drag&drop multi-file con barra de progreso por fichero.
- `components/WorkflowCard.jsx` — card con título, subtítulo, botón Ejecutar.
- Routing actualizado: `/dashboard` → `/cases/:caseId` → `/cases/:caseId/drafts/:draftId`.

**Tests** (`backend/tests/`): 9 tests unitarios pasan (`test_chunker.py`, `test_citation_validator.py`).

### Hard rules enforced en código
1. ✅ No source, no claim — validador rechaza claims sin `evidence_ids`.
2. ✅ Verbatim citation — `quote_excerpt` debe substring-match al `texto_extraido`.
3. ✅ No silent overwrite — drafts approved son inmutables (DB trigger).
4. ✅ RLS-first — `get_user_client(token)` para queries de usuario; `get_supabase_admin()` solo para storage uploads, audit_log writes y workflow background tasks.
5. ✅ Storage paths siempre `<user_id>/<case_id>/<filename>`.
6. ✅ JSON schema en cada llamada OpenAI (`response_format={"type":"json_schema","strict":true}`).
7. ✅ Idempotencia: re-running workflow crea nuevo run row.

## Pendiente

### P0 — Próxima sesión
- ⚠️ **Usuario debe aplicar la migración** `/app/supabase/0001_init_schema.sql` en Supabase Dashboard → SQL Editor (las tablas no están todavía).
- ⚠️ **Usuario debe añadir `SUPABASE_SERVICE_ROLE_KEY`** al `/app/backend/.env` (sección Settings → API en Supabase Dashboard).
- ⚠️ **Para LLM funcional**: o (a) topear Emergent LLM Key balance, o (b) añadir `OPENAI_API_KEY` al `.env`. Embeddings requieren obligatoriamente OpenAI key (Emergent LLM Key no expone embeddings).
- ⚠️ Configurar Supabase URL Configuration con la preview URL para que el magic link redirija OK.
- Una vez los 4 anteriores listos, llamar `testing_agent_v3` para test e2e completo.

### P1 — Workflows adicionales (Fase 2-b)
- `services/workflows/civil_demand.py` — demanda civil (encabezamiento, hechos, fundamentos, petitum).
- `services/workflows/fiscal_consultation.py` — consulta fiscal con citas a normativa.
- `services/workflows/jurisprudence_analysis.py` — análisis jurisprudencia interna del caso.
- Export DOCX (`GET /api/drafts/{id}/export-docx`).
- Cost tracking + budget guardrail mensual.
- Re-validar citas en revisiones humanas.

### P2 — Drive + producción (Fase 2-c)
- `components/DrivePicker.jsx` + `POST /api/drive/import` (descarga vía Drive API, hash, store, ingest).
- Configurar Google OAuth + Picker API en Google Cloud Console.
- Suite pytest workflows (mocked OpenAI).
- Deploy producción Railway (2 servicios) + Supabase URL Configuration con dominio público.

### Out of scope (v2+)
- Integración BOE / CENDOJ live API.
- Whisper transcripción de juicios.
- Multi-tenant org/team UI.
- Billing / subscriptions.
