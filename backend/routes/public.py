"""Public (unauthenticated) endpoints.

The only entrypoint is ``GET /api/public/drafts/{token}`` which resolves a
shared-draft token to a read-only payload. No owner/run ids are exposed.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from services import sharing


router = APIRouter()


@router.get("/drafts/{token}")
async def get_public_draft(token: str):
    payload = sharing.resolve_public_draft(token)
    if not payload:
        raise HTTPException(404, "Shared draft not found")
    if payload.get("_expired"):
        raise HTTPException(410, "Share link expired")
    return payload
