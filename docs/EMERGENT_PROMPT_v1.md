# Galaxy Legal — Emergent Prompt v1.0

You are extending an existing scaffolded codebase, NOT building from scratch. The repo `galaxy-legal` already has Supabase fully provisioned, the FastAPI skeleton, and the React frontend with auth wired. Your job is to **expand the workflows, document ingestion, and AI generation** with strict citation grounding.

## What already exists (do NOT recreate)

### Supabase (live, ref `irzervhlczzzrydqfisn`, region eu-west-3)
- Tables: `profiles`, `cases`, `case_documents`, `document_chunks`, `runs`, `evidences`, `drafts`, `audit_log` — all with RLS
- Bucket: `legal-documents` (private, 25MB, paths must be `<user_id>/<case_id>/<filename>`)
- RPC: `match_document_chunks(query_embedding, p_case_id, match_threshold, match_count)`
- Trigger: blocks `update` on `drafts` where `status='approved'` and `content_md` changes
- Auto-create profile on signup

### Backend (`/backend`, FastAPI 0.115)
- `main.py` with CORS + 6 routers wired
- `config.py` loads env via pydantic-settings
- `services/supabase_client.py` — anon, admin, user-scoped clients
- `services/auth.py` — `get_current_user` dependency (Supabase JWT)
- `routes/cases.py` — CRUD complete
- `routes/health.py`, `routes/auth.py` — done
- `routes/documents.py`, `routes/runs.py`, `routes/drafts.py`, `routes/drive.py` — STUBS (you expand)

### Frontend (`/frontend`, React 18 + Vite + Tailwind)
- `src/lib/supabase.js` — Supabase client
- `src/pages/LoginPage.jsx` — magic link + Google OAuth (DONE)
- `src/pages/AuthCallback.jsx` — DONE
- `src/pages/DashboardPage.jsx` — placeholder list
- `src/components/ProtectedRoute.jsx` — DONE
- Routing in `src/main.jsx`

## Design system (use exactly these tokens)

```js
colors: {
  ink:    { 50:'#f6f7f9', 100:'#eceff4', 200:'#d8dee9', 600:'#4c566a', 900:'#1a1f2b' },
  brand:  { 50:'#eef2ff', 100:'#e0e7ff', 500:'#6366f1', 600:'#4f46e5', 700:'#4338ca', 900:'#1e1b4b' },
  gold:   { 400:'#d4a157', 500:'#b8893f', 600:'#9b6f2c' },
}
fonts: serif='"Cormorant Garamond"', sans='Inter'
```

UI feel: sober, lawyerly, soft glassmorphism, generous whitespace, serif headlines (Cormorant), sans body (Inter), gold accents only for premium markers, never for noise.

---

# WHAT YOU MUST BUILD (in order)

## 1. Document ingestion pipeline (`backend/routes/documents.py` + `backend/services/`)

Build:

### `services/extractor.py`
- `extract_text_from_pdf(file_bytes) -> dict` returns `{full_text, pages: [{page, text}]}` using `pypdf`
- `extract_text_from_docx(file_bytes) -> dict` using `python-docx` + `mammoth` for HTML fallback
- `extract_text_from_txt(file_bytes) -> dict`
- Dispatch by mime type

### `services/chunker.py`
- `chunk_text(extracted: dict, target_tokens=400, overlap_tokens=50) -> list[Chunk]`
- Each chunk knows: `chunk_text`, `page`, `paragraph`, `chunk_index`, `token_count`
- Use `tiktoken` with `cl100k_base` encoding to count tokens

### `services/embeddings.py`
- `embed_chunks(chunks: list[str]) -> list[list[float]]` — batch (max 100 per call) to `text-embedding-3-small`, dimension 1536
- Track total tokens, return cost estimate

### `routes/documents.py` — endpoints
- `POST /documents/upload` — multipart upload, requires `case_id`. Steps:
  1. Compute SHA-256 of file bytes
  2. Check duplicate by `(case_id, hash_sha256)` — if exists, return existing
  3. Store in Supabase Storage at `<user_id>/<case_id>/<uuid>-<filename>`
  4. Insert `case_documents` row (status: pending indexing)
  5. Background task: extract → chunk → embed → insert `document_chunks`
  6. Update `indexed_at` when done
  7. Return document row with index status
- `GET /documents?case_id=...` — already stub, leave as-is
- `GET /documents/{id}` — single doc
- `DELETE /documents/{id}` — cascades chunks
- `POST /documents/{id}/reindex` — re-runs chunk+embed

## 2. Drive integration (`backend/routes/drive.py`)

- `GET /drive/picker-config` — already stub, leave as-is
- `POST /drive/import` — body `{case_id, drive_files: [{id, name, mimeType}], access_token}`. Steps:
  1. Use the user-provided OAuth access token (frontend gets it from Google Picker)
  2. For each file: download via Drive API (`files.get` with `alt=media` for binary, or `files.export` for Google Docs → docx)
  3. Run through same upload pipeline as `/documents/upload`
  4. Store `drive_file_id` and `drive_revision_id` on the row
  5. Return list of created documents

Frontend pairing:
- Add `frontend/src/components/DrivePicker.jsx` that loads `https://apis.google.com/js/api.js` and `https://accounts.google.com/gsi/client`, requests `drive.file` scope, shows Google Picker, returns selected files to parent

## 3. Workflow engine (`backend/services/workflows/`)

Each workflow is a class with a fixed sequence of steps. Each step has its own prompt + JSON schema validator.

### Base classes (`services/workflows/base.py`)
```python
class WorkflowStep:
    name: str
    prompt_template: str
    output_schema: dict  # JSON schema
    validator: Callable[[dict], list[str]]  # returns list of errors, empty if valid

class Workflow:
    workflow_type: str
    steps: list[WorkflowStep]

    def run(self, run_id, case_id, user_id, supabase_client, openai_client) -> dict:
        # 1. For each step: gather context, call LLM with response_format={'type': 'json_schema', ...}
        # 2. Validate output against schema + custom validator
        # 3. If validation fails, retry once; if still fails, mark run as 'needs_human'
        # 4. Persist step output to runs.output_jsonb (merging)
        # 5. After last step: produce final draft, write to drafts, write evidences
```

### Workflows to implement (one file each in `services/workflows/`)

**`initial_analysis.py`** — runs automatically after first document is indexed
- Steps: `gather_documents` → `extract_facts` → `summarize` → `flag_risks`
- Output: executive summary + facts matrix + risk list (saved as a draft of type `initial_analysis`)

**`civil_demand.py`** (demanda civil España)
- Steps: `gather_evidence` → `propose_strategy` → `draft_facts_section` → `draft_legal_grounds` → `draft_petitum` → `assemble_draft` → `verify_citations`
- Final: full demand structure (encabezamiento, hechos, fundamentos de derecho, petitum, otrosíes)
- Each `hecho` requires at least one `evidence_id`

**`fiscal_consultation.py`**
- Steps: `gather_context` → `identify_fiscal_issues` → `apply_norms` (BOE references) → `compute_implications` → `draft_response`
- Output: structured consultation with norm citations + risk assessment

**`jurisprudence_analysis.py`**
- Steps: `extract_legal_questions` → `search_internal_corpus` → `summarize_findings` → `draft_memo`
- For v1: `search_internal_corpus` only searches uploaded jurisprudence docs in the case. CENDOJ API integration is v2.

### `routes/runs.py` — POST /runs
- Body: `{case_id, workflow_type}`
- Insert `runs` row (status: queued)
- Trigger workflow as background task
- Return run id immediately
- `GET /runs/{id}` — poll status
- `GET /runs/{id}/evidences` — list evidences
- `GET /runs/{id}/draft` — get produced draft

## 4. Citation validation (CRITICAL — anti-fantasma)

Before any draft is persisted, validate every claim:

### `services/citation_validator.py`
```python
def validate_citations(draft_content_md: str, evidences: list[Evidence], case_documents: list[Document]) -> ValidationResult:
    """
    Parses draft markdown for citation markers like [E:evidence_id].
    For each marker:
      1. Evidence row must exist in evidences[]
      2. Evidence's quote_excerpt must be a substring (case-insensitive, whitespace-normalized)
         of the source document's texto_extraido
      3. Page number, if specified, must match
    Returns: { valid: bool, errors: [...], unverified_claims: [...] }
    """
```

If validation fails, the run goes to `needs_human` state and the draft is NOT persisted as approvable.

LLM output schema MUST require citations in claims:
```json
{
  "claims": [{
    "claim_id": "c001",
    "text": "El demandado incumplió el contrato el 15 de marzo de 2024.",
    "evidence_ids": ["e001", "e003"]
  }],
  "evidences": [{
    "id": "e001",
    "document_id": "<uuid>",
    "page": 3,
    "paragraph": 7,
    "quote_excerpt": "...verbatim string from doc...",
    "claim_id": "c001"
  }]
}
```

The LLM is told: **"You may only cite quotes that exist verbatim in the provided document chunks. If a chunk doesn't contain what you need, return an empty claim."**

## 5. Drafts versioning (`backend/routes/drafts.py`)

- `POST /drafts/{id}/revision` — body `{content_md}`. Steps:
  1. Load current draft
  2. Compute diff with `diff-match-patch`
  3. Insert new draft row with `parent_draft_id`, incremented version, diff stored
  4. Return new draft
- `POST /drafts/{id}/approve` — sets status `approved`, sets `approved_at`. Trigger blocks future modification.
- `POST /drafts/{id}/reject` — sets status `rejected`
- `GET /drafts/{id}/export-docx` — uses `python-docx` to render markdown to .docx with proper headings, returns binary download. Also uploads to Supabase Storage.

## 6. Frontend pages (use design tokens above)

### `pages/CasePage.jsx` (`/cases/:id`)
Layout: 3-column split
- Left rail: documents list with index status badges, "Importar de Drive" button (opens DrivePicker), upload local
- Center: tabbed view — "Resumen" | "Hechos" | "Borradores" | "Evidencias" | "Auditoría"
- Right rail: workflows panel (cards: "Análisis inicial", "Demanda civil", "Consulta fiscal", "Análisis jurisprudencial") with "Ejecutar" button each
- Top: case header (title, jurisdicción, materia, status badge)

### `pages/DraftEditorPage.jsx` (`/cases/:case_id/drafts/:draft_id`)
- Center: markdown editor (use `@uiw/react-md-editor` or basic textarea + preview)
- Right rail: evidence panel — for each citation `[E:xxx]` highlighted in text, show source document, page, exact quote, "Ver en documento" button
- Top: version selector + "Guardar revisión" + "Aprobar" (locked unless all citations verified)
- Banner if any citation unverified: red, with list

### `pages/DashboardPage.jsx` — expand existing
- Replace placeholder with real grid:
  - "Nuevo expediente" CTA opens modal
  - Each case card: title, materia, jurisdicción, status, last_run, draft count

### `components/DocumentUpload.jsx`
- Drag & drop zone, multiple files, progress per file, calls `/documents/upload`

### `components/WorkflowCard.jsx`
- Title, description, "Ejecutar" button → POST `/runs`, polls status, navigates to draft when ready

### `components/EvidenceMarker.jsx`
- Inline component for `[E:xxx]` rendering in draft preview, click → opens panel with source

## 7. Audit logging

Add to ALL state-changing endpoints:
```python
supabase.table("audit_log").insert({
  "actor_id": user["id"],
  "case_id": case_id,
  "action": "draft.approve",  # dotted action
  "resource_type": "draft",
  "resource_id": draft_id,
  "payload": {...},
}).execute()
```

## 8. Error handling + observability

- Wrap every OpenAI call with retry (max 3, exponential backoff) and cost tracking
- Every run records `tokens_input`, `tokens_output`, `cost_usd`
- If monthly budget exceeded (`OPENAI_MONTHLY_BUDGET_USD`), reject new runs with clear error
- Log workflow step transitions to stdout with structured format

## 9. Tests (`backend/tests/`)

Pytest with at least:
- `test_chunker.py` — chunk count, token counts, page tracking
- `test_citation_validator.py` — verbatim match passes, paraphrase fails, missing evidence fails
- `test_workflows.py` — mock OpenAI, run civil_demand happy path

## 10. README updates

Update root `README.md` and `docs/DEPLOY.md` with:
- New env vars (none should be added beyond `.env.example`)
- Endpoints list
- How workflows are invoked
- Testing instructions

---

# Hard rules

1. **No source, no claim.** Any LLM output that produces text claims without evidence_ids is rejected by validator.
2. **Verbatim citation.** `quote_excerpt` must substring-match the document's `texto_extraido`. Case-insensitive, whitespace-normalized.
3. **No silent overwrite.** Drafts in `approved` state are immutable (DB trigger enforces). New revisions create new versions.
4. **RLS-first.** Every backend query uses `get_user_client(token)`, never `get_supabase_admin()` for user data. Admin client only for: cost tracking, audit log writes, system tasks.
5. **Storage paths.** Always `<user_id>/<case_id>/<filename>`. RLS policy on storage.objects relies on this prefix.
6. **JSON schema everywhere.** Every OpenAI structured output uses `response_format={'type': 'json_schema', 'json_schema': {...}}`. No prose-then-parse.
7. **Idempotency.** Re-running a workflow on the same case produces a new run, never overwrites previous runs.

# Out of scope for v1.0 (do NOT build)

- BOE / CENDOJ live API integration (placeholder for v2)
- Trial video transcription (Whisper integration in v2)
- Multi-tenant org/team management (schema supports it, UI doesn't expose)
- Billing / subscriptions
- Notifications / email
- Custom GPT Action layer (after web UI is solid)

# Definition of done

- I can sign in with magic link, land on dashboard, create a case
- I can drag-drop a PDF, see it indexed, see chunks in DB
- I can connect Google Drive, pick a file, see it imported
- I can click "Análisis inicial" → run completes → draft appears with verified citations
- I can click "Demanda civil" → draft generated, every "hecho" has at least one evidence link
- I can edit draft, save revision (diff stored), approve (locked), export .docx
- If I tamper with the LLM to invent a citation, validator rejects it and run goes to `needs_human`
- All RLS policies prevent user A from seeing user B's data
