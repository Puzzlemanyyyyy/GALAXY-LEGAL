# Galaxy Legal — Test Credentials

## Supabase project (live)
- **URL**: `https://irzervhlczzzrydqfisn.supabase.co`
- **Anon (publishable) key** (frontend, ya en `.env`): `sb_publishable_ii9pbB_4IEbcCQduLxqlMg_-RitzSyv`
- **Service role key**: ⚠️ **PENDIENTE** — el usuario debe ir a https://supabase.com/dashboard/project/irzervhlczzzrydqfisn/settings/api y copiarla a `/app/backend/.env` en `SUPABASE_SERVICE_ROLE_KEY`. Necesario para Fase 2 (uploads, audit_log, embeddings).
- **Project ref**: `irzervhlczzzrydqfisn`
- **Region**: `eu-west-3`

## Auth setup en Supabase Dashboard
Para que el magic link funcione end-to-end con la preview de Emergent, el usuario debe:

1. Ir a https://supabase.com/dashboard/project/irzervhlczzzrydqfisn/auth/url-configuration
2. **Site URL**: `https://ba999ff0-b0a0-4c59-b346-fc3f4eaa7af6.preview.emergentagent.com`
3. **Redirect URLs** — añadir:
   - `https://ba999ff0-b0a0-4c59-b346-fc3f4eaa7af6.preview.emergentagent.com/auth/callback`
   - `http://localhost:5173/auth/callback` (para dev local)
   - `http://localhost:3000/auth/callback` (para dev local Emergent)
4. Save

## Test login (manual)
- URL: https://ba999ff0-b0a0-4c59-b346-fc3f4eaa7af6.preview.emergentagent.com/login
- Flujo magic link: introducir email real → click "Enviar enlace mágico" → Supabase envía correo → click en el enlace → redirige a `/auth/callback` → Supabase establece sesión → navega a `/dashboard`.
- Estado verificado: la petición llega correctamente a Supabase y la respuesta es procesada (400 con email inválido confirma la integración).

## Backend smoke test
```
curl https://ba999ff0-b0a0-4c59-b346-fc3f4eaa7af6.preview.emergentagent.com/api/health
# → {"status":"ok","service":"galaxy-legal-api"}

curl -i https://ba999ff0-b0a0-4c59-b346-fc3f4eaa7af6.preview.emergentagent.com/api/auth/me
# → 401 Unauthorized (esperado sin Bearer token)
```

## Pendiente para Fase 2
- `SUPABASE_SERVICE_ROLE_KEY` (del dashboard, indicado arriba).
- `OPENAI_API_KEY` o usar Emergent LLM Key (compatibilidad con `gpt-4o` / `text-embedding-3-small`).
- `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET` + `GOOGLE_PICKER_API_KEY` (opcional, para Drive).
