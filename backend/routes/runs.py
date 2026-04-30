"""Workflow runs: queue, status, evidences, draft."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from services import audit
from services.auth import get_current_user
from services.mappers import draft_to_api, evidence_to_api, run_to_api
from services.supabase_client import get_supabase_admin, get_user_client
from services.workflows import REGISTRY, get_workflow


router = APIRouter()


class RunCreate(BaseModel):
    case_id: str
    workflow_type: str


@router.get("/types")
async def list_workflow_types(_user: dict = Depends(get_current_user)):
    return [
        {"workflow_type": cls.workflow_type, "title": cls.title, "draft_type": cls.draft_type}
        for cls in REGISTRY.values()
    ]


@router.get("")
async def list_runs(case_id: str, user: dict = Depends(get_current_user)):
    sb = get_user_client(user["token"])
    res = sb.table("runs").select("*").eq("case_id", case_id).order("created_at", desc=True).execute()
    return [run_to_api(r) for r in (res.data or [])]


@router.get("/{run_id}")
async def get_run(run_id: str, user: dict = Depends(get_current_user)):
    sb = get_user_client(user["token"])
    res = sb.table("runs").select("*").eq("id", run_id).single().execute()
    if not res.data:
        raise HTTPException(404, "Run not found")
    return run_to_api(res.data)


@router.get("/{run_id}/evidences")
async def list_run_evidences(run_id: str, user: dict = Depends(get_current_user)):
    sb = get_user_client(user["token"])
    res = sb.table("evidences").select("*").eq("run_id", run_id).order("created_at").execute()
    return [evidence_to_api(r) for r in (res.data or [])]


@router.get("/{run_id}/draft")
async def get_run_draft(run_id: str, user: dict = Depends(get_current_user)):
    sb = get_user_client(user["token"])
    res = (
        sb.table("drafts")
        .select("*")
        .eq("run_id", run_id)
        .order("version", desc=True)
        .limit(1)
        .execute()
    )
    if not res.data:
        raise HTTPException(404, "No draft for run yet")
    return draft_to_api(res.data[0])


@router.post("", status_code=202)
async def create_run(payload: RunCreate, background: BackgroundTasks, user: dict = Depends(get_current_user)):
    if payload.workflow_type not in REGISTRY:
        raise HTTPException(400, f"Unknown workflow_type. Available: {list(REGISTRY)}")

    user_sb = get_user_client(user["token"])
    case = user_sb.table("cases").select("*").eq("id", payload.case_id).single().execute()
    if not case.data:
        raise HTTPException(404, "Case not found")

    admin = get_supabase_admin()
    inserted = (
        admin.table("runs")
        .insert({
            "case_id": payload.case_id,
            "owner_id": user["id"],
            "workflow_type": payload.workflow_type,
            "model": "gpt-4o",
            "prompt_version": "v1",
            "status": "queued",
            "input_jsonb": {},
            "output_jsonb": {},
        })
        .execute()
    )
    run = inserted.data[0]

    audit.log(
        actor_id=user["id"],
        action="run.create",
        case_id=payload.case_id,
        resource_type="run",
        resource_id=run["id"],
        payload={"workflow_type": payload.workflow_type},
    )

    background.add_task(_run_workflow_bg, run["id"], payload.case_id, payload.workflow_type, user["id"])
    return run_to_api(run)


# ---------------------------------------------------------------------------
def _run_workflow_bg(run_id: str, case_id: str, workflow_type: str, owner_id: str) -> None:
    try:
        asyncio.run(_run_workflow_async(run_id, case_id, workflow_type, owner_id))
    except Exception as exc:  # noqa: BLE001
        admin = get_supabase_admin()
        admin.table("runs").update({
            "status": "failed",
            "error_message": str(exc)[:2000],
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", run_id).execute()
        print(f"[runs] run {run_id} failed: {exc}")


async def _run_workflow_async(run_id: str, case_id: str, workflow_type: str, owner_id: str) -> None:
    admin = get_supabase_admin()

    admin.table("runs").update({
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", run_id).execute()

    case = admin.table("cases").select("*").eq("id", case_id).single().execute().data
    # Only include documents whose extraction is done (indexed_at not null,
    # no index_error). The schema has no status column, so we derive it.
    docs_raw = (
        admin.table("case_documents")
        .select("id, nombre, mime_type, page_count, texto_extraido, indexed_at, metadata")
        .eq("case_id", case_id)
        .execute()
        .data or []
    )
    documents = []
    for d in docs_raw:
        meta = d.get("metadata") or {}
        has_err = isinstance(meta, dict) and meta.get("index_error")
        if d.get("indexed_at") and not has_err:
            documents.append({
                "id": d["id"],
                "filename": d.get("nombre"),
                "mime_type": d.get("mime_type"),
                "pages_count": d.get("page_count"),
                "texto_extraido": d.get("texto_extraido") or "",
            })
    if not documents:
        admin.table("runs").update({
            "status": "failed",
            "error_message": "No indexed documents in this case yet. Upload at least one document and wait for indexing.",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", run_id).execute()
        return

    chunks = (
        admin.table("document_chunks")
        .select("id, document_id, chunk_index, page, paragraph, chunk_text, token_count")
        .eq("case_id", case_id)
        .order("document_id")
        .order("chunk_index")
        .limit(200)
        .execute()
        .data or []
    )

    workflow = get_workflow(workflow_type)
    result = await workflow.run(
        run_id=run_id,
        case=case,
        documents=documents,
        chunks=chunks,
        admin=admin,
        owner_id=owner_id,
    )

    final_patch: dict = {
        "status": result.status,
        "tokens_input": result.usage.input_tokens,
        "tokens_output": result.usage.output_tokens,
        "cost_usd": result.usage.cost_usd,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "output_jsonb": result.output,
    }
    if result.error:
        final_patch["error_message"] = result.error[:2000]

    if result.status == "completed" and result.draft is not None:
        tipo = result.draft["draft_type"]
        # Compute next version for (case, tipo_documento) — the live schema has
        # a unique constraint on (case_id, tipo_documento, version).
        existing = (
            admin.table("drafts")
            .select("version")
            .eq("case_id", case_id)
            .eq("tipo_documento", tipo)
            .order("version", desc=True)
            .limit(1)
            .execute()
            .data or []
        )
        next_version = (existing[0]["version"] if existing else 0) + 1
        draft_row = (
            admin.table("drafts")
            .insert({
                "case_id": case_id,
                "run_id": run_id,
                "version": next_version,
                "tipo_documento": tipo,
                "content_md": result.draft["content_md"],
                "status": "draft",
            })
            .execute()
            .data[0]
        )
        if result.evidences:
            # Map chunk coordinates (document_id, page, paragraph) to chunk_id
            # so evidences link back to the concrete chunk row.
            chunk_lookup: dict[tuple, str] = {}
            for c in chunks:
                chunk_lookup.setdefault((c["document_id"], c.get("page"), c.get("paragraph")), c["id"])
            ev_rows = []
            for ev in result.evidences:
                chunk_id = chunk_lookup.get((ev["document_id"], ev.get("page"), ev.get("paragraph")))
                ev_rows.append({
                    "run_id": run_id,
                    "document_id": ev["document_id"],
                    "chunk_id": chunk_id,
                    "claim_id": ev["external_id"],  # real column — we store the "e001" id here
                    "page": ev.get("page"),
                    "paragraph": ev.get("paragraph"),
                    "quote_excerpt": ev["quote_excerpt"],
                    "verified": True,
                })
            admin.table("evidences").insert(ev_rows).execute()
        audit.log(
            actor_id=owner_id,
            action="run.completed",
            case_id=case_id,
            resource_type="run",
            resource_id=run_id,
            payload={"draft_id": draft_row["id"], "cost_usd": float(result.usage.cost_usd)},
        )

    admin.table("runs").update(final_patch).eq("id", run_id).execute()
