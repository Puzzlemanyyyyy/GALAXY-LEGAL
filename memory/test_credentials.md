# Galaxy Legal — Test Credentials

## Test user (creado por main agent, verificado funcional)
- **Email**: `e2e-test@galaxylegal.dev`
- **Password**: `GalaxyLegal_e2e_2026!`
- **User ID**: `08cdcd1a-4ae1-4fa3-8b38-3b4afa01de46`
- **Método**: Supabase password grant (`POST /auth/v1/token?grant_type=password` con header `apikey=<anon_key>`)
- **Uso en tests**: el token de acceso devuelto sirve como `Authorization: Bearer <token>` para todos los endpoints `/api/*`.
- **Inyección en frontend**: guardar el payload (`access_token, refresh_token, expires_at, token_type, user`) en `localStorage` bajo la clave `sb-irzervhlczzzrydqfisn-auth-token` y navegar a `/dashboard` para saltar la pantalla de magic link.

## Supabase project (live)
- **URL**: `https://irzervhlczzzrydqfisn.supabase.co`
- **Anon/publishable key** (frontend y seguridad): `sb_publishable_ii9pbB_4IEbcCQduLxqlMg_-RitzSyv` — guardada en `/app/frontend/.env` como `VITE_SUPABASE_URL` + `VITE_SUPABASE_ANON_KEY`.
- **Service role key**: en `/app/backend/.env` (`SUPABASE_SERVICE_ROLE_KEY`). NO la imprimas en logs ni la subas al repo público.
- **Region**: `eu-west-3`
- **Project ref**: `irzervhlczzzrydqfisn`

## Schema (aplicado por el usuario previamente)
- 8 tablas con RLS: `profiles`, `cases`, `case_documents`, `document_chunks`, `runs`, `evidences`, `drafts`, `audit_log`.
- Extensiones: `vector`, `pg_trgm`, `pgcrypto`.
- Bucket privado: `legal-documents` (25 MB, paths `<user_id>/<case_id>/...`).
- RPC: `match_document_chunks(query_embedding vector(1536), p_case_id uuid, match_threshold float, match_count int)`.
- Trigger: `trg_drafts_immutable` bloquea cambios de `content_md` en drafts con `status='approved'`.
- **NO ejecutar `/app/supabase/0001_init_schema.sql`** — ese archivo es solo documentación de referencia. El schema real es el que ya hay en producción (tiene más columnas y enums más estrictos).

## Enum values live (para tests)
- `cases.status`: `open, in_progress, review, closed, archived`
- `case_documents.tipo`: `contract, demand, ruling, correspondence, evidence, transcript, other`
- `case_documents.confidentiality`: `public, internal, confidential, restricted`
- `runs.workflow_type`: `initial_analysis, civil_demand, fiscal_consultation, jurisprudence_analysis, appeal, criminal_complaint, trial_review`
- `runs.status`: `queued, running, completed, failed, needs_human` (⚠️ `completed`, no `succeeded`)
- `drafts.tipo_documento`: mismo set que workflow_type
- `drafts.status`: `draft, in_review, approved, exported, rejected`

## Supabase Auth URL Configuration (pendiente usuario)
Para que el magic link funcione e2e desde la preview:
1. https://supabase.com/dashboard/project/irzervhlczzzrydqfisn/auth/url-configuration
2. **Site URL**: `https://ba999ff0-b0a0-4c59-b346-fc3f4eaa7af6.preview.emergentagent.com`
3. **Redirect URLs** añadir: `https://ba999ff0-b0a0-4c59-b346-fc3f4eaa7af6.preview.emergentagent.com/auth/callback`

Si no se configura, el magic link recibido por correo fallará al redirigir. No afecta a los tests automatizados (usan password grant).

## LLM keys en /app/backend/.env
- `OPENAI_API_KEY`: configurada, usada directamente para embeddings (obligatorio) y chat.
- `EMERGENT_LLM_KEY=sk-emergent-aD24d948a5c4f04793`: universal key, usada como fallback si `OPENAI_API_KEY` estuviera vacía. Balance ≈ $0 al inicio; el usuario puede topear en Profile → Universal Key → Add Balance si quiere usarla exclusivamente.
- **Embeddings**: SIEMPRE requieren `OPENAI_API_KEY` (la Emergent LLM Key no expone el endpoint de embeddings).

## Smoke commands
```bash
# Health + auth + routes
API=https://ba999ff0-b0a0-4c59-b346-fc3f4eaa7af6.preview.emergentagent.com
curl $API/api/health                       # {"status":"ok",...}
curl -i $API/api/cases                     # 401 sin Bearer
curl -i $API/api/runs/types                # 401 sin Bearer

# Pytest — 9 unit + 15 e2e, 24/24 green
cd /app/backend && /root/.venv/bin/python -m pytest tests/ -q
```

## Observaciones
- Casos e2e existentes en la DB del test user: ~4 (creados durante el smoke + el testing agent). Limpieza no requerida para v1.
- Cada run del workflow `initial_analysis` cuesta ~$0.015 de OpenAI. Usar con moderación en CI.
