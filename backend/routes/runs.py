"""Workflow runs: queue, status, evidences, draft."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from services import audit, llm
from services.auth import get_current_user
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
    return res.data


@router.get("/{run_id}")
async def get_run(run_id: str, user: dict = Depends(get_current_user)):
    sb = get_user_client(user["token"])
    res = sb.table("runs").select("*").eq("id", run_id).single().execute()
    if not res.data:
        raise HTTPException(404, "Run not found")
    return res.data


@router.get("/{run_id}/evidences")
async def list_run_evidences(run_id: str, user: dict = Depends(get_current_user)):
    sb = get_user_client(user["token"])
    res = sb.table("evidences").select("*").eq("run_id", run_id).order("external_id").execute()
    return res.data


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
    return res.data[0]


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
            "status": "queued",
        })
        .execute()
    )
    run = inserted.data[0]

    audit.log(actor_id=user["id"], action="run.create", case_id=payload.case_id, resource_type="run", resource_id=run["id"], payload={"workflow_type": payload.workflow_type})

    background.add_task(_run_workflow_bg, run["id"], payload.case_id, payload.workflow_type, user["id"])
    return run


# ---------------------------------------------------------------------------
def _run_workflow_bg(run_id: str, case_id: str, workflow_type: str, owner_id: str) -> None:
    try:
        asyncio.run(_run_workflow_async(run_id, case_id, workflow_type, owner_id))
    except Exception as exc:  # noqa: BLE001
        admin = get_supabase_admin()
        admin.table("runs").update({
            "status": "failed",
            "error": str(exc)[:2000],
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", run_id).execute()
        print(f"[runs] run {run_id} failed: {exc}")


async def _run_workflow_async(run_id: str, case_id: str, workflow_type: str, owner_id: str) -> None:
    admin = get_supabase_admin()

    admin.table("runs").update({
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", run_id).execute()

    case = admin.table("cases").select("*").eq("id", case_id).single().execute().data
    documents = (
        admin.table("case_documents")
        .select("id, filename, mime_type, pages_count, texto_extraido, status")
        .eq("case_id", case_id)
        .eq("status", "ready")
        .execute()
        .data or []
    )
    if not documents:
        admin.table("runs").update({
            "status": "failed",
            "error": "No indexed documents in this case yet. Upload at least one document and wait for indexing.",
            "finished_at": datetime.now(timezone.utc).isoformat(),
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
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "output_jsonb": result.output,
    }
    if result.error:
        final_patch["error"] = result.error[:2000]

    if result.status == "succeeded" and result.draft is not None:
        draft_row = (
            admin.table("drafts")
            .insert({
                "case_id": case_id,
                "run_id": run_id,
                "owner_id": owner_id,
                "version": 1,
                "draft_type": result.draft["draft_type"],
                "title": result.draft["title"],
                "content_md": result.draft["content_md"],
                "citations_valid": result.draft["citations_valid"],
                "status": "draft",
            })
            .execute()
            .data[0]
        )
        if result.evidences:
            ev_rows = []
            for ev in result.evidences:
                ev_rows.append({
                    "run_id": run_id,
                    "case_id": case_id,
                    "owner_id": owner_id,
                    "document_id": ev["document_id"],
                    "external_id": ev["external_id"],
                    "claim_id": ev.get("claim_id"),
                    "page": ev.get("page"),
                    "paragraph": ev.get("paragraph"),
                    "quote_excerpt": ev["quote_excerpt"],
                    "verified": True,
                })
            admin.table("evidences").insert(ev_rows).execute()
        audit.log(
            actor_id=owner_id,
            action="run.succeeded",
            case_id=case_id,
            resource_type="run",
            resource_id=run_id,
            payload={"draft_id": draft_row["id"], "cost_usd": float(result.usage.cost_usd)},
        )

    admin.table("runs").update(final_patch).eq("id", run_id).execute()
