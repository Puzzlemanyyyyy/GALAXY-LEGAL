# Galaxy Legal — Test Credentials

## Supabase project (live)
- **URL**: `https://irzervhlczzzrydqfisn.supabase.co`
- **Anon (publishable) key** (frontend, ya en `/app/frontend/.env`):
  `sb_publishable_ii9pbB_4IEbcCQduLxqlMg_-RitzSyv`
- **Service role key**: ⚠️ **PENDIENTE** — el usuario debe ir a https://supabase.com/dashboard/project/irzervhlczzzrydqfisn/settings/api y copiarla a `/app/backend/.env` en `SUPABASE_SERVICE_ROLE_KEY`. Necesario para uploads, embeddings, audit_log, ejecución de workflows.
- **Project ref**: `irzervhlczzzrydqfisn`
- **Region**: `eu-west-3`

## SQL migration to apply
Pegar el contenido de `/app/supabase/0001_init_schema.sql` en Supabase Dashboard → SQL Editor → Run.
Resultado: 8 tablas, RLS, bucket `legal-documents` (privado, 25MB), RPC `match_document_chunks`, trigger anti-overwrite de drafts approved, auto-create profile on signup.

## Auth setup en Supabase Dashboard
1. https://supabase.com/dashboard/project/irzervhlczzzrydqfisn/auth/url-configuration
2. **Site URL**: `https://ba999ff0-b0a0-4c59-b346-fc3f4eaa7af6.preview.emergentagent.com`
3. **Redirect URLs**: añadir
   - `https://ba999ff0-b0a0-4c59-b346-fc3f4eaa7af6.preview.emergentagent.com/auth/callback`
   - `http://localhost:5173/auth/callback`
   - `http://localhost:3000/auth/callback`
4. Save

## LLM keys
- **Emergent LLM Key** (en `/app/backend/.env` como `EMERGENT_LLM_KEY=sk-emergent-aD24d948a5c4f04793`): activo pero con balance agotado (~$0.001 budget). Para que los workflows con `gpt-4o` funcionen hay que TOP-UP en Profile → Universal Key → Add Balance.
- **OpenAI API key del usuario** (alternativa, $50 budget mencionado): pegar en `/app/backend/.env` como `OPENAI_API_KEY=sk-...`. Si está presente, el código usa OpenAI directo y prescinde de la Emergent LLM Key.
- **Embeddings**: SIEMPRE requieren `OPENAI_API_KEY` (la Emergent LLM Key no expone el endpoint de embeddings). Sin esto, indexación de documentos fallará con `RuntimeError: OPENAI_API_KEY is required for embeddings`.

## Test login (manual)
URL: https://ba999ff0-b0a0-4c59-b346-fc3f4eaa7af6.preview.emergentagent.com/login
- Magic link: introducir email real → "Enviar enlace mágico" → recibir correo → click → `/auth/callback` → redirect a `/dashboard`.
- Verificación e2e: la petición POST a `https://irzervhlczzzrydqfisn.supabase.co/auth/v1/otp` se dispara con `redirect_to` correcto.

## Backend smoke test
```
API=https://ba999ff0-b0a0-4c59-b346-fc3f4eaa7af6.preview.emergentagent.com
curl $API/api/health                       # → {"status":"ok",...}
curl $API/api/                             # → {"name":"Galaxy Legal API",...}
curl -i $API/api/auth/me                   # → 401 (sin Bearer)
curl -i $API/api/cases                     # → 401
curl -i $API/api/runs/types                # → 401
```

## Pytest (sin claves, deterministas)
```
cd /app/backend && /root/.venv/bin/python -m pytest tests/ -q
# 9 tests pasan (chunker + citation_validator)
```
