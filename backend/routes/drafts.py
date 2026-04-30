"""Drafts: list, get, revise, approve, reject."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from diff_match_patch import diff_match_patch
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from services import audit
from services.auth import get_current_user
from services.mappers import draft_to_api
from services.supabase_client import get_supabase_admin, get_user_client


router = APIRouter()


class RevisionPayload(BaseModel):
    content_md: str
    title: Optional[str] = None  # accepted for UX but stored as H1 inside content_md


@router.get("")
async def list_drafts(case_id: str, user: dict = Depends(get_current_user)):
    sb = get_user_client(user["token"])
    res = sb.table("drafts").select("*").eq("case_id", case_id).order("created_at", desc=True).execute()
    return [draft_to_api(r) for r in (res.data or [])]


@router.get("/{draft_id}")
async def get_draft(draft_id: str, user: dict = Depends(get_current_user)):
    sb = get_user_client(user["token"])
    res = sb.table("drafts").select("*").eq("id", draft_id).single().execute()
    if not res.data:
        raise HTTPException(404, "Draft not found")
    return draft_to_api(res.data)


@router.post("/{draft_id}/revision", status_code=201)
async def create_revision(draft_id: str, payload: RevisionPayload, user: dict = Depends(get_current_user)):
    sb = get_user_client(user["token"])
    parent = sb.table("drafts").select("*").eq("id", draft_id).single().execute()
    if not parent.data:
        raise HTTPException(404, "Draft not found")
    parent_row = parent.data

    dmp = diff_match_patch()
    diff = dmp.diff_main(parent_row["content_md"], payload.content_md)
    dmp.diff_cleanupSemantic(diff)
    patch = dmp.patch_toText(dmp.patch_make(parent_row["content_md"], diff))

    admin = get_supabase_admin()
    inserted = (
        admin.table("drafts")
        .insert({
            "case_id": parent_row["case_id"],
            "run_id": parent_row.get("run_id"),
            "parent_draft_id": draft_id,
            "version": int(parent_row.get("version", 1)) + 1,
            "tipo_documento": parent_row.get("tipo_documento") or "draft",
            "content_md": payload.content_md,
            "diff_from_previous": patch,
            "status": "draft",
        })
        .execute()
        .data[0]
    )
    audit.log(
        actor_id=user["id"],
        action="draft.revision",
        case_id=parent_row["case_id"],
        resource_type="draft",
        resource_id=inserted["id"],
        payload={"parent_draft_id": draft_id, "version": inserted["version"]},
    )
    return draft_to_api(inserted)


@router.post("/{draft_id}/approve")
async def approve_draft(draft_id: str, user: dict = Depends(get_current_user)):
    sb = get_user_client(user["token"])
    draft = sb.table("drafts").select("*").eq("id", draft_id).single().execute()
    if not draft.data:
        raise HTTPException(404, "Draft not found")
    # Approval requires that citations have been validated — which in our
    # pipeline is true for drafts created directly by a successful workflow run
    # (no parent) and false for human revisions until we re-run the validator.
    if draft.data.get("parent_draft_id"):
        raise HTTPException(400, "Cannot approve a human revision without re-validating citations")

    admin = get_supabase_admin()
    updated = (
        admin.table("drafts")
        .update({
            "status": "approved",
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "reviewer_id": user["id"],
        })
        .eq("id", draft_id)
        .execute()
        .data[0]
    )
    audit.log(actor_id=user["id"], action="draft.approve", case_id=draft.data["case_id"], resource_type="draft", resource_id=draft_id)
    return draft_to_api(updated)


@router.post("/{draft_id}/reject")
async def reject_draft(draft_id: str, user: dict = Depends(get_current_user)):
    sb = get_user_client(user["token"])
    draft = sb.table("drafts").select("*").eq("id", draft_id).single().execute()
    if not draft.data:
        raise HTTPException(404, "Draft not found")
    admin = get_supabase_admin()
    updated = admin.table("drafts").update({"status": "rejected"}).eq("id", draft_id).execute().data[0]
    audit.log(actor_id=user["id"], action="draft.reject", case_id=draft.data["case_id"], resource_type="draft", resource_id=draft_id)
    return draft_to_api(updated)
