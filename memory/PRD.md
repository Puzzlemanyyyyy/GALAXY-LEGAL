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

### 2026-05-XX · Iteration 3 — Issue cleanup + Railway deploy ready
**SQL drift reconciled** via new idempotent `supabase/0003_align_to_live.sql` (~210 líneas). Aplica RENAME COLUMN + ENUMs (`workflow_type`, `draft_status`) + DROPs de columnas legacy. Fresh project: 0001+0002+0003 reproduce el estado vivo. Live DB: 0003 es no-op por los guards `do $$ ... $$`.

**`backend/config.py` saneado**: eliminado `JWT_SECRET="change-me"`, eliminado `GOOGLE_REDIRECT_URI`, `BACKEND_CORS_ORIGINS` reset a localhost-only por defecto (producción debe setear vía env), `SUPABASE_PROJECT_REF` ya no hardcoded.

**`.env.example` añadidos** para backend y frontend (no existían). Frontend ships solo `VITE_*` (no más `REACT_APP_*` legacy que confundía).

**DOCX export**: marcadores `[E:xxx]` ahora bracketed superscript (font.superscript=True, ≤8pt). Test nuevo `test_docx_evidence_marker_is_superscript_with_brackets`. Lint clean.

**`docs/DEPLOY.md` reescrito** con receta deploy Railway en dos pases (placeholder → real URLs), env vars listas para copy-paste, smoke checklist post-deploy, common issues, rollback plan, custom domain steps, costes esperados ($80-95/mes).

**Smoke test contra preview**: 9/9 verde — health, password login, drive picker-config (correctamente `configured=false`), usage shape, public draft sin auth, /privacy y /terms render (verificados con Playwright porque el HTML inicial Vite no tiene contenido pre-hidratación), list cases, exported_at expuesto.

**Pytest**: 29/29 deterministas verde post-changes. Los 2 e2e contra preview live (test_phase2b_e2e + test_e2e_flow) siguen flaky por network — no son regresiones nuevas.

**Sin tocar**: `citation_validator.py`, `workflows/*`, `0002_phase2b.sql` (instrucciones explícitas).

**Bloqueado en usuario**: ejecutar deploy Railway siguiendo DEPLOY.md (cuenta + UI propia, agente sin acceso). Smoke test contra Railway tras deploy.

---

### 2026-05-04 · Fase 2(c) avanzada + páginas legales + manual de usuario
**Drive Picker (frontend + backend listos, esperando credenciales del usuario)**:
- `frontend/src/components/DrivePicker.jsx` — carga GIS (`accounts.google.com/gsi/client`) y gapi (`apis.google.com/js/api.js`) idempotentemente. Usa `google.accounts.oauth2.initTokenClient` con scope `drive.file` (privacy-first). Picker configurado con `setSelectFolderEnabled(false) + setIncludeFolders(false) + ViewId.DOCS + DocsViewMode.LIST` para forzar selección individual de archivos. Handler de `DRIVE_TOKEN_EXPIRED` mid-import: reabre el picker con `prompt='consent'` y reintenta SOLO los pendientes (no double-import). Si el backend no tiene `GOOGLE_CLIENT_ID`, renderiza un aviso en gris en lugar del botón.
- `backend/services/drive.py` — `validate_access_token` llama `https://oauth2.googleapis.com/tokeninfo`, verifica `aud == GOOGLE_CLIENT_ID` (defense vs confused-deputy) + scope `drive.file`. `download_drive_file` distingue Google-native (`/export?mimeType=docx|xlsx|pptx`) vs binario (`?alt=media`). Mid-import 401 → `DriveTokenError(DRIVE_TOKEN_EXPIRED)` con `partial=DriveImportResult(imported, pending, errors)` adjunta para que la ruta lo devuelva.
- `backend/routes/drive.py::POST /api/drive/import` — devuelve 503 `DRIVE_NOT_CONFIGURED` si falta env var, 401 `TOKEN_VALIDATION_FAILED`, 403 `DRIVE_TOKEN_EXPIRED` con `{imported, pending}`, 201 con `{imported, errors, pending}` en caso normal. Audit log `drive.import` con resumen.
- 7/7 tests unitarios nuevos en `tests/test_drive_service.py` (mockean tokeninfo + Drive API): aud mismatch → 401, scope missing → 401, Google-native → /export, binario → ?alt=media, 401 mid-import → DRIVE_TOKEN_EXPIRED.

**Páginas legales (RGPD/comercial)**:
- `frontend/src/pages/PrivacyPage.jsx` — política de privacidad RGPD-compliant en español: responsable, datos tratados, finalidad y base legal, plazos de conservación, encargados (Supabase, OpenAI, Google, Railway), derechos ARSULIPO, no decisiones automatizadas. Plantilla con `[Nombre del titular]` para que el usuario rellene.
- `frontend/src/pages/TermsPage.jsx` — términos y condiciones: aceptación, descripción, **cláusula clave de "Galaxy Legal NO presta servicios jurídicos"** (responsabilidad deontológica del abogado), obligaciones del usuario, propiedad intelectual, ley aplicable.
- Rutas públicas `/privacy` y `/terms` en `main.jsx`. Verificadas en preview.

**Manual de usuario**:
- `docs/MANUAL_USUARIO.md` — 10 secciones, ~600 líneas, en español. Cubre desde "Acceder por primera vez" hasta el resumen de 1 minuto. Tabla de workflows con tiempo y coste. Estados de ejecución (especial atención a `needs_human` como feature, no bug). Garantías técnicas vendibles + lista honesta de lo que NO hace todavía.

**Stop confirmado en Fase 2(c) — esperando del usuario**:
- Pulsar "Save to GitHub".
- Crear OAuth Client + API Key en Google Cloud Console y meter `GOOGLE_CLIENT_ID` + `GOOGLE_PICKER_API_KEY` en `.env` (frontend y backend).
- Cuando esté: Drive Picker funciona inmediatamente sin tocar más código.
- Railway deploy queda pendiente (necesita repo actualizado en GitHub + cuenta Railway con env vars).
- Fase 3 (BOE/CENDOJ RAG) sigue requiriendo aprobación de gasto OpenAI (~$400 one-shot) antes de ejecutar.

**Tests post-cambios**: 28/28 verde en suite determinista. Los e2e que tocan el preview URL (test_phase2b_e2e + test_e2e_flow + test_versioning) son flaky por timeouts de red contra Emergent preview, no por bugs nuevos. Lint JS/Python limpio.

---

### 2026-05-04 · Fase 2(b) — Cierre final + LoginPage refinado
- `LoginPage.jsx` limpiado: eliminado botón "Continuar con Google" (era scaffolding, provider Supabase nunca habilitado). Añadido **fallback de login por contraseña** vía toggle "¿Tienes contraseña?" — usa `supabase.auth.signInWithPassword`. Permite entrar con las credenciales de `test_credentials.md` sin depender de que la URL Configuration de Supabase esté aplicada.
- Smoke E2E verificado: login con contraseña → redirect a `/dashboard` → token en localStorage → app renderiza.
- `docs/CURRENT_STATE.md` actualizado con ready-to-push checklist, acciones del usuario post-push (auto-deploy OFF en Railway + Supabase URL Configuration save + Automatic branching OFF).
- 45/45 pytest backend verde, lint JS/Python limpio.

**Stop confirmado en Fase 2(b)**. El usuario eligió opción A: cerrar 2(b) → pulsar Save to GitHub → siguiente sesión = Fase 2(c) Drive + Railway. Fase 3 (RAG legal BOE/CENDOJ) queda después de Fase 2(c), con budget aprobado explícitamente.

---

### 2026-04-30 · Fase 2(b) — E2E verificado + refinado (iteration_2.json + refix)
Testing agent validó el suite de 6 puntos pedido por el usuario:
- `civil_demand` E2E → demanda con 5 hechos numerados + [E:xxx] en cada uno + petitum + otrosíes, 5 evidencias `verified=true`, coste $0.0212.
- DOCX export 39 044 B (Title×1, H1×1, H2×5, Bullets×9, Normal×27).
- Budget guardrail (unit-level, `settings.OPENAI_MONTHLY_BUDGET_USD=0` → 402 + `over_budget=true` + restore a 50).
- Race condition vía RPC `insert_draft_atomic` + `pg_advisory_xact_lock` → 5 versions únicas consecutivas sin huecos.
- Sharing backend completo (create 201 → list → public GET ×3 → `view_count=3` en DB → revoke 204 → 404).
- PublicDraftPage sin login: watermark, banner, panel 5 evidencias, NO dashboard chrome.

**Refix (4 items P0/P1) aplicado tras el iteration_2**:
- `services/mappers.py:draft_to_api` ahora expone `exported_at`. Verificado end-to-end: POST `/export-docx` → GET draft → campo no-null.
- `routes/runs.py` + `routes/drafts.py::create_revision`: el catch del RPC `insert_draft_atomic` ahora emite `logger.warning(...)` con `exc_info=True` cuando cae al fallback max+1. Antes era silencioso.
- `services/sharing.py::resolve_public_draft`: ambos `.single()` (draft y case) envueltos en try/except → 404 limpio si el draft está huérfano o RLS-hidden.
- `PublicDraftPage.jsx`: markers `[E:xxx]` ahora son `<button data-testid="evidence-marker-exxx" data-evidence-id="exxx">` con onClick → `scrollIntoView({behavior:'smooth'})` + `ring-amber-300 bg-amber-50 border-amber-400` por 1.5s sobre la fila correspondiente del panel lateral. Verificado con screenshot (el panel `e001` sale outlineado en ámbar tras click).
- Pytest backend 45/45 green tras los fixes. Lint JS limpio.

**Link persistente 7d (NO revocar)** para review manual del usuario:
`https://ba999ff0-b0a0-4c59-b346-fc3f4eaa7af6.preview.emergentagent.com/public/drafts/4a1d042b-9f35-4cc0-a98a-1cde263be263`

## Pendiente

### P0 — Usuario debe aplicar SQL
Aplicar `/app/supabase/0002_phase2b.sql` vía MCP o SQL Editor:
- `shared_drafts` tabla + RLS policy.
- `increment_share_view(uuid)` RPC.
- `insert_draft_atomic(...)` RPC con advisory lock.

Ninguna alteración sobre objetos existentes — solo add-only.

**UPDATE 2026-04-30**: el usuario ya aplicó este SQL y confirmó que las 3 estructuras existen en su instancia. RPC `insert_draft_atomic` invocada correctamente en el test de race condition (5 inserts concurrentes). Status: **DONE**.

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
