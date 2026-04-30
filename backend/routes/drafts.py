"""Drafts: list, get, revise, approve, reject, export DOCX, share."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from diff_match_patch import diff_match_patch
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from services import audit, sharing
from services.auth import get_current_user
from services.citation_validator import (
    EvidenceInput,
    parse_evidence_markers,
    validate_citations,
)
from services.docx_exporter import export_draft_to_storage
from services.mappers import draft_to_api
from services.supabase_client import get_supabase_admin, get_user_client


logger = logging.getLogger(__name__)
router = APIRouter()


class RevisionPayload(BaseModel):
    content_md: str
    title: Optional[str] = None


class SharePayload(BaseModel):
    expires_in: str = Field(default="7d", description="24h | 7d | 30d | never")
    watermark: Optional[str] = None


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
    """Create a new draft version from a human-edited body.

    Runs citation validation on the new content: every [E:xxx] marker must
    resolve to an existing verified evidence whose quote_excerpt is a verbatim
    substring of its source document. The returned draft carries a
    ``citations_valid`` boolean and the list of unverified markers/errors so
    the UI can block approval until they're resolved.
    """
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

    # ---- Re-validate citations against the originating run's evidences.
    markers = parse_evidence_markers(payload.content_md)
    unverified_markers: list[str] = []
    validation_errors: list[dict] = []

    run_id = parent_row.get("run_id")
    if run_id and markers:
        ev_rows = admin.table("evidences").select("*").eq("run_id", run_id).execute().data or []
        ev_by_ext = {(r.get("claim_id") or r.get("id")): r for r in ev_rows}

        # Check every marker is known.
        for m in markers:
            if m not in ev_by_ext:
                unverified_markers.append(m)

        # Re-check quote_excerpt substring match against source documents.
        doc_ids = {r["document_id"] for r in ev_rows if r.get("document_id")}
        docs_map: dict[str, str] = {}
        if doc_ids:
            docs_q = admin.table("case_documents").select("id, texto_extraido").in_("id", list(doc_ids)).execute()
            for d in (docs_q.data or []):
                docs_map[d["id"]] = d.get("texto_extraido") or ""

        ev_inputs = [
            EvidenceInput(
                external_id=(r.get("claim_id") or r["id"]),
                document_id=r["document_id"],
                quote_excerpt=r["quote_excerpt"],
                page=r.get("page"),
                paragraph=r.get("paragraph"),
            )
            for r in ev_rows
        ]
        result = validate_citations(ev_inputs, docs_map)
        if result.errors:
            validation_errors = [{"external_id": e.external_id, "reason": e.reason} for e in result.errors]

    # ---- Insert new revision row.
    # Use the atomic RPC when available so concurrent revisions can't collide
    # on the unique constraint. Fall back to a plain insert with next-version
    # computation if the RPC is not present yet (e.g. before 0002 applied).
    inserted = None
    try:
        rpc = admin.rpc("insert_draft_atomic", {
            "p_case_id":     parent_row["case_id"],
            "p_run_id":      parent_row.get("run_id"),
            "p_parent_id":   draft_id,
            "p_tipo":        parent_row.get("tipo_documento") or "initial_analysis",
            "p_content_md":  payload.content_md,
            "p_diff":        patch,
        }).execute()
        data = rpc.data
        inserted = (data if isinstance(data, dict) else (data[0] if data else None))
    except Exception:
        logger.warning(
            "insert_draft_atomic RPC unavailable, falling back to max+1 "
            "(non-atomic) for draft revision parent_draft_id=%s",
            draft_id,
            exc_info=True,
        )
        inserted = None
    if inserted is None:
        existing = (
            admin.table("drafts")
            .select("version")
            .eq("case_id", parent_row["case_id"])
            .eq("tipo_documento", parent_row.get("tipo_documento") or "initial_analysis")
            .order("version", desc=True)
            .limit(1)
            .execute()
            .data or []
        )
        next_version = (existing[0]["version"] if existing else 0) + 1
        inserted = (
            admin.table("drafts")
            .insert({
                "case_id": parent_row["case_id"],
                "run_id": parent_row.get("run_id"),
                "parent_draft_id": draft_id,
                "version": next_version,
                "tipo_documento": parent_row.get("tipo_documento") or "initial_analysis",
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
        payload={"parent_draft_id": draft_id, "version": inserted["version"], "unverified_markers": unverified_markers},
    )

    api_shape = draft_to_api(inserted)
    api_shape["unverified_markers"] = unverified_markers
    api_shape["validation_errors"] = validation_errors
    api_shape["citations_valid"] = not unverified_markers and not validation_errors
    return api_shape


@router.post("/{draft_id}/approve")
async def approve_draft(draft_id: str, user: dict = Depends(get_current_user)):
    sb = get_user_client(user["token"])
    draft = sb.table("drafts").select("*").eq("id", draft_id).single().execute()
    if not draft.data:
        raise HTTPException(404, "Draft not found")

    # Revisions carry human edits and need re-validation before approval.
    if draft.data.get("parent_draft_id"):
        admin = get_supabase_admin()
        run_id = draft.data.get("run_id")
        content_md = draft.data.get("content_md") or ""
        markers = parse_evidence_markers(content_md)
        if run_id and markers:
            ev_rows = admin.table("evidences").select("*").eq("run_id", run_id).execute().data or []
            ev_by_ext = {(r.get("claim_id") or r.get("id")): r for r in ev_rows}
            unverified = [m for m in markers if m not in ev_by_ext]
            if unverified:
                raise HTTPException(422, f"Cannot approve revision: unverified citations {unverified}")
            doc_ids = list({r["document_id"] for r in ev_rows if r.get("document_id")})
            docs_map: dict[str, str] = {}
            if doc_ids:
                docs_q = admin.table("case_documents").select("id, texto_extraido").in_("id", doc_ids).execute()
                for d in (docs_q.data or []):
                    docs_map[d["id"]] = d.get("texto_extraido") or ""
            ev_inputs = [
                EvidenceInput(
                    external_id=(r.get("claim_id") or r["id"]),
                    document_id=r["document_id"],
                    quote_excerpt=r["quote_excerpt"],
                    page=r.get("page"),
                    paragraph=r.get("paragraph"),
                )
                for r in ev_rows
            ]
            result = validate_citations(ev_inputs, docs_map)
            if not result.valid:
                raise HTTPException(422, f"Cannot approve revision: validation failed — {[f'{e.external_id}:{e.reason}' for e in result.errors]}")

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


# -------------------------------------------------------------------
# DOCX export
# -------------------------------------------------------------------
@router.post("/{draft_id}/export-docx")
async def export_docx(draft_id: str, user: dict = Depends(get_current_user)):
    sb = get_user_client(user["token"])
    res = sb.table("drafts").select("*").eq("id", draft_id).single().execute()
    if not res.data:
        raise HTTPException(404, "Draft not found")
    draft = draft_to_api(res.data)
    path, signed_url = export_draft_to_storage(draft={**res.data, **draft}, owner_id=user["id"])
    admin = get_supabase_admin()
    admin.table("drafts").update({"exported_at": datetime.now(timezone.utc).isoformat()}).eq("id", draft_id).execute()
    audit.log(
        actor_id=user["id"],
        action="draft.export_docx",
        case_id=res.data["case_id"],
        resource_type="draft",
        resource_id=draft_id,
        payload={"storage_path": path},
    )
    return {"draft_id": draft_id, "storage_path": path, "signed_url": signed_url, "expires_in_seconds": 3600}


# -------------------------------------------------------------------
# Share
# -------------------------------------------------------------------
@router.post("/{draft_id}/share", status_code=201)
async def share_draft(draft_id: str, payload: SharePayload, user: dict = Depends(get_current_user)):
    sb = get_user_client(user["token"])
    draft = sb.table("drafts").select("id, case_id, status, reviewer_id").eq("id", draft_id).single().execute()
    if not draft.data:
        raise HTTPException(404, "Draft not found")
    try:
        row = sharing.create_share_token(
            draft_id=draft_id,
            created_by=user["id"],
            expires_in=payload.expires_in,
            watermark=payload.watermark,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    audit.log(
        actor_id=user["id"],
        action="draft.share",
        case_id=draft.data.get("case_id"),
        resource_type="draft",
        resource_id=draft_id,
        payload={"token": row["token"], "expires_in": payload.expires_in},
    )
    return row


@router.get("/{draft_id}/shares")
async def list_shares(draft_id: str, user: dict = Depends(get_current_user)):
    sb = get_user_client(user["token"])
    return sharing.list_share_tokens(draft_id=draft_id, user_sb=sb)


@router.delete("/shares/{token}", status_code=204)
async def revoke_share(token: str, user: dict = Depends(get_current_user)):
    sb = get_user_client(user["token"])
    sharing.revoke_share_token(token=token, user_sb=sb)
    audit.log(actor_id=user["id"], action="draft.share.revoke", resource_type="share", resource_id=token)
    return None
