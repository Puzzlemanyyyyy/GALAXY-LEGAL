# Despliegue — Galaxy Legal

## A) GitHub

```bash
cd galaxy-legal
git remote add origin git@github.com:<TU_USUARIO>/galaxy-legal.git
git branch -M main
git push -u origin main
```

(Si prefieres HTTPS: `git remote add origin https://github.com/<TU_USUARIO>/galaxy-legal.git`)

## B) Railway — 2 servicios desde 1 repo

1. **railway.app → New Project → Deploy from GitHub repo → galaxy-legal**
2. Railway detecta el monorepo. Crea un primer servicio:
   - **Settings → Service → Root Directory: `backend`**
   - **Variables → pega todo lo que está en `.env.example` con valores reales**
   - **Deploy** — Railway autodetecta FastAPI (Nixpacks) y `railway.json`
3. **+ New → GitHub Repo → mismo repo** para el segundo servicio:
   - **Root Directory: `frontend`**
   - **Variables → pega solo las `VITE_*`**
   - **Settings → Networking → Generate Domain**
4. Copia el dominio público del backend y úsalo como `VITE_API_BASE_URL` en el frontend
5. Copia el dominio público del frontend y añádelo a:
   - `BACKEND_CORS_ORIGINS` en el backend
   - **Authorized JS origins** en Google Cloud Console
   - **Site URL** y **Redirect URLs** en Supabase Dashboard → Authentication → URL Configuration

## C) Supabase — configurar Auth

Dashboard del proyecto `galaxy-legal` (`irzervhlczzzrydqfisn`):

1. **Authentication → Providers → Email** → activa "Enable Email provider" + "Magic Link"
2. **Authentication → Providers → Google** → activa, pega `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET`
3. **Authentication → URL Configuration**:
   - Site URL: `https://<tu-frontend>.up.railway.app`
   - Redirect URLs: añade `http://localhost:5173/auth/callback` y `https://<tu-frontend>.up.railway.app/auth/callback`

## D) Google Cloud — OAuth Client

1. console.cloud.google.com → New Project `galaxy-legal-prod`
2. APIs & Services → Library → habilita **Google Drive API** y **Google Picker API**
3. APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID
   - Type: Web application
   - Authorized JS origins: `http://localhost:5173`, `http://localhost:8000`, dominios Railway
   - Authorized redirect URIs: añade tus 2 callback URLs
4. Create Credentials → API Key → restringe a "Picker API"
5. OAuth consent screen → External, scopes: `drive.file`, `userinfo.email`, `userinfo.profile`

## E) Local dev

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env  # rellena las variables
uvicorn main:app --reload

# Frontend (otra terminal)
cd frontend
npm install
cp ../.env.example .env  # rellena VITE_*
npm run dev
# abre http://localhost:5173
```

## Costes mensuales esperados

| Item | $ / mes |
|---|---|
| Supabase Pro org (compartido con Galaxy Pay) | ya pagado |
| Supabase proyecto `galaxy-legal` | $10 |
| Railway Hobby (2 servicios) | $5 (incluye $5 crédito) |
| OpenAI API (uso real) | $30–80 |
| Google Cloud | $0 |
| **Total** | **~$45–95** |
