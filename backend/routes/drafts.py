"""Drafts: list, get, revise, approve, reject."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from diff_match_patch import diff_match_patch
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from services import audit
from services.auth import get_current_user
from services.supabase_client import get_supabase_admin, get_user_client


router = APIRouter()


class RevisionPayload(BaseModel):
    content_md: str
    title: Optional[str] = None


@router.get("")
async def list_drafts(case_id: str, user: dict = Depends(get_current_user)):
    sb = get_user_client(user["token"])
    res = sb.table("drafts").select("*").eq("case_id", case_id).order("created_at", desc=True).execute()
    return res.data


@router.get("/{draft_id}")
async def get_draft(draft_id: str, user: dict = Depends(get_current_user)):
    sb = get_user_client(user["token"])
    res = sb.table("drafts").select("*").eq("id", draft_id).single().execute()
    if not res.data:
        raise HTTPException(404, "Draft not found")
    return res.data


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
            "owner_id": user["id"],
            "parent_draft_id": draft_id,
            "version": int(parent_row.get("version", 1)) + 1,
            "draft_type": "revision",
            "title": payload.title or parent_row["title"],
            "content_md": payload.content_md,
            "diff_patch": patch,
            "status": "draft",
            "citations_valid": False,  # human revisions need re-validation in v2
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
    return inserted


@router.post("/{draft_id}/approve")
async def approve_draft(draft_id: str, user: dict = Depends(get_current_user)):
    sb = get_user_client(user["token"])
    draft = sb.table("drafts").select("*").eq("id", draft_id).single().execute()
    if not draft.data:
        raise HTTPException(404, "Draft not found")
    if not draft.data.get("citations_valid"):
        raise HTTPException(400, "Cannot approve: citations are not verified")
    admin = get_supabase_admin()
    updated = (
        admin.table("drafts")
        .update({
            "status": "approved",
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "approved_by": user["id"],
        })
        .eq("id", draft_id)
        .execute()
        .data[0]
    )
    audit.log(actor_id=user["id"], action="draft.approve", case_id=draft.data["case_id"], resource_type="draft", resource_id=draft_id)
    return updated


@router.post("/{draft_id}/reject")
async def reject_draft(draft_id: str, user: dict = Depends(get_current_user)):
    sb = get_user_client(user["token"])
    draft = sb.table("drafts").select("*").eq("id", draft_id).single().execute()
    if not draft.data:
        raise HTTPException(404, "Draft not found")
    admin = get_supabase_admin()
    updated = admin.table("drafts").update({"status": "rejected"}).eq("id", draft_id).execute().data[0]
    audit.log(actor_id=user["id"], action="draft.reject", case_id=draft.data["case_id"], resource_type="draft", resource_id=draft_id)
    return updated
