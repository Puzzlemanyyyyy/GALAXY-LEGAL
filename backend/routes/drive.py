"""Google Drive integration — picker config + Drive Picker import endpoint.

Auth flow is client-side (GIS `initTokenClient` + Picker). Token never stored.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from config import settings
from services import audit, drive
from services.auth import get_current_user


logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/picker-config")
async def picker_config(user: dict = Depends(get_current_user)):
    """Return frontend config to initialise GIS + Picker.

    If GOOGLE_CLIENT_ID is empty, returns ``configured: false`` so the
    frontend can hide the Drive button instead of crashing.
    """
    configured = bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_PICKER_API_KEY)
    return {
        "configured": configured,
        "apiKey": settings.GOOGLE_PICKER_API_KEY if configured else None,
        "clientId": settings.GOOGLE_CLIENT_ID if configured else None,
        "scope": "https://www.googleapis.com/auth/drive.file",
    }


class DriveFileRef(BaseModel):
    id: str
    name: Optional[str] = None
    mimeType: Optional[str] = None
    revisionId: Optional[str] = None


class DriveImportPayload(BaseModel):
    case_id: str
    drive_files: list[DriveFileRef] = Field(min_length=1, max_length=50)
    access_token: str


@router.post("/import", status_code=201)
async def import_from_drive(
    payload: DriveImportPayload,
    background: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    """Download files picked via the Drive Picker into the given case.

    Behavior:
      - 401 ``TOKEN_VALIDATION_FAILED`` if access_token's `aud` doesn't
        match GOOGLE_CLIENT_ID or scope is missing.
      - 503 ``DRIVE_NOT_CONFIGURED`` if the server has no GOOGLE_CLIENT_ID.
      - 403 ``DRIVE_TOKEN_EXPIRED`` if the token expires mid-import; the
        body includes ``imported`` (already done) and ``pending`` (left).
      - 201 with ``{imported, errors}`` when all files were processed.
    """
    # Late import to avoid a circular reference between routes/documents and
    # services/drive (which needs the same background indexer).
    from routes.documents import _index_in_background

    files = [f.model_dump() for f in payload.drive_files]
    try:
        result = await drive.import_drive_files(
            case_id=payload.case_id,
            drive_files=files,
            access_token=payload.access_token,
            user=user,
            background_indexer=lambda doc_id, raw, mime, name: background.add_task(
                _index_in_background, doc_id, raw, mime, name
            ),
        )
    except drive.DriveTokenError as exc:
        if exc.code == "DRIVE_TOKEN_EXPIRED":
            partial = exc.partial
            raise HTTPException(
                status_code=exc.status_code,
                detail={
                    "code": exc.code,
                    "message": str(exc),
                    "imported": partial.imported if partial else [],
                    "pending": partial.pending if partial else [],
                    "errors": partial.errors if partial else [],
                },
            ) from exc
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)}) from exc

    audit.log(
        actor_id=user["id"],
        action="drive.import",
        case_id=payload.case_id,
        resource_type="case",
        resource_id=payload.case_id,
        payload={
            "imported": len(result.imported),
            "deduped": sum(1 for x in result.imported if x.get("deduped")),
            "errors": len(result.errors),
            "drive_ids": [x["drive_id"] for x in result.imported],
        },
    )

    return {
        "imported": result.imported,
        "errors": result.errors,
        "pending": result.pending,
    }
