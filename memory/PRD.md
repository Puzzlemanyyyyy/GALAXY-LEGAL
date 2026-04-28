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

## Core requirements (estáticos)
- **Anti-fantasma**: cada cita en un draft debe tener `evidence_id` que substring-match al texto original del documento.
- **RLS-first**: todas las queries de usuario usan cliente con JWT, no `service_role`.
- **Storage paths**: `<user_id>/<case_id>/<filename>` (bucket privado `legal-documents`, 25MB).
- **Drafts inmutables al aprobar**: trigger en DB bloquea modificaciones de drafts `approved`.
- **JSON schema en LLM**: todas las llamadas usan `response_format=json_schema`.
- **Idempotencia**: nunca sobrescribir runs/drafts existentes.

## What's been implemented

### 2026-04-28 — Fase 1: Infraestructura y Login
- Repo `galaxy-legal` desempaquetado en `/app` (preserva `.git` con remoto a `Puzzlemanyyyyy/GALAXY-LEGAL`).
- Backend FastAPI funcionando en supervisor (`server.py` re-exporta `app` desde `main.py`).
- Todas las rutas backend prefijadas con `/api` para enrutar correctamente por ingress de Emergent.
- Frontend Vite ejecutándose en puerto 3000 vía supervisor (`yarn start` → `vite --host 0.0.0.0 --port 3000`).
- `vite.config.js` configurado con `allowedHosts: true` para el cluster de Emergent.
- `.env` separados con `VITE_*` (Supabase publishable key) y `REACT_APP_BACKEND_URL` apuntando a la preview pública.
- Pantalla de login (magic link + Google OAuth) renderiza con diseño dark/sober + serif Cormorant + glow gold.
- `data-testid` añadidos en todos los elementos interactivos: `login-email-input`, `send-magic-link-btn`, `google-signin-btn`, `magic-link-sent-banner`, `login-error-banner`, `dashboard-page`, `signout-btn`, `new-case-btn`, etc.
- Magic link verificado end-to-end: la petición llega a `https://irzervhlczzzrydqfisn.supabase.co/auth/v1/otp` con `redirect_to=<preview>/auth/callback` correcto.
- Backend health check `/api/health` y router `/api/cases`, `/api/documents`, `/api/runs`, `/api/drafts`, `/api/drive` accesibles públicamente.
- Auth middleware (`get_current_user`) protege rutas con `Bearer <supabase_jwt>` — devuelve 401 sin token (verificado con curl).

## Backlog / Próximas fases (Emergent Prompt v1.0)

### P0 — Fase 2 (siguiente)
1. **Document ingestion pipeline**: `services/extractor.py` (PDF/DOCX/TXT), `services/chunker.py` (tiktoken cl100k_base, 400 tokens / 50 overlap), `services/embeddings.py` (text-embedding-3-small, batch 100). Endpoints: `POST /api/documents/upload`, `DELETE`, `POST /reindex`.
2. **Workflow engine**: base classes en `services/workflows/base.py`, primer workflow `initial_analysis.py` (gather → extract_facts → summarize → flag_risks).
3. **Citation validator**: `services/citation_validator.py` con substring-match case-insensitive whitespace-normalized.
4. **Frontend `CasePage.jsx`**: 3 columnas (docs / tabs / workflows). Conectar a backend.

### P1
- Workflows adicionales: `civil_demand.py`, `fiscal_consultation.py`, `jurisprudence_analysis.py`.
- `pages/DraftEditorPage.jsx` con marcadores `[E:xxx]` clicables y panel de evidencias.
- Drafts versioning con diff-match-patch, aprobación, export DOCX.
- Audit logging en todos los endpoints de cambio de estado.

### P2
- Google Drive Picker (`components/DrivePicker.jsx`) + `POST /api/drive/import`.
- Cost tracking + retry exponencial en llamadas OpenAI.
- Suite pytest (`backend/tests/test_chunker.py`, `test_citation_validator.py`, `test_workflows.py`).
- Deploy producción a Railway (2 servicios) + configuración Supabase URL Configuration con dominio público.

### Out of scope (v2+)
- Integración BOE / CENDOJ live API.
- Whisper transcripción de juicios.
- Multi-tenant org/team management UI.
- Billing / subscriptions.

## Hard rules (non-negotiable)
- No source, no claim — validador rechaza claims sin `evidence_ids`.
- Verbatim citation — `quote_excerpt` debe substring-match al `texto_extraido`.
- No silent overwrite — drafts approved son inmutables, nuevas revisiones crean versiones.
- Storage paths siempre `<user_id>/<case_id>/<filename>`.
- JSON schema en cada llamada OpenAI con `response_format`.
- Idempotencia: re-running workflow crea nuevo run, nunca sobrescribe.
