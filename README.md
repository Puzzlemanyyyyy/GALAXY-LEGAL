# Galaxy Legal

AI-powered legal workspace for law firms and in-house legal teams. Built on Supabase, FastAPI and React. Connects to Google Drive, runs deterministic legal workflows over your documents, generates citation-grounded drafts (demands, fiscal queries, jurisprudence analysis), and exports to DOCX/PDF.

**Anti-fantasma by design**: every claim in a generated draft must be backed by a verifiable evidence_id pointing to a document chunk. The backend rejects model output where citations don't substring-match the source.

## Stack

- **DB / Auth / Storage**: Supabase Pro (Postgres 17 + pgvector)
- **Backend**: FastAPI (Python 3.11)
- **Frontend**: React + Vite + Tailwind + shadcn/ui
- **LLM**: OpenAI gpt-4o + text-embedding-3-small
- **Drive**: google-api-python-client + Google Picker (scope `drive.file`)
- **Deploy**: Railway (backend + frontend) or Vercel (frontend) + Railway (backend)

## Project structure

```
galaxy-legal/
├── backend/         FastAPI + workflows + Drive + OpenAI
├── frontend/        React + Tailwind + shadcn/ui
├── supabase/        SQL migrations (already applied on cloud)
├── docs/            Emergent prompt package, architecture notes
└── .github/         CI workflows
```

## Quick start

1. Copy `.env.example` to `.env` in both `backend/` and `frontend/` and fill credentials
2. Backend: `cd backend && pip install -r requirements.txt && uvicorn main:app --reload`
3. Frontend: `cd frontend && npm install && npm run dev`
4. Open http://localhost:5173

## Deploy to Railway

Push this repo to GitHub. In Railway:
1. New Project → Deploy from GitHub → select repo
2. Add two services from same repo with root paths `backend` and `frontend`
3. Paste env vars from `.env.example` (filled with real values)
4. Done — Railway autodetects FastAPI and Vite

See `docs/DEPLOY.md` for details.

## License

Proprietary — Galaxy Pay / Pablo Puzzlegold
