"""Google Drive integration — client-side OAuth (GIS) flow.

The frontend obtains a short-lived access_token (~1h) via the Google
Identity Services (GIS) `initTokenClient` with scope `drive.file` and
sends it in the body of POST /api/drive/import. We never store the
token. We never store a refresh token. Privacy-first.

Security guarantees on each /import call:
  1. Validate `aud` of the token equals our GOOGLE_CLIENT_ID via the
     public tokeninfo endpoint (defense vs confused-deputy attack).
  2. Verify scope contains `drive.file` (read-only would also be OK
     but we're strict to match what the frontend requested).
  3. Honour mid-import token expiry: return a structured 403 with
     `code=DRIVE_TOKEN_EXPIRED` plus the lists of imported / pending
     so the frontend can re-prompt the Picker and resume only the
     pending files (no double imports).
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Optional

import httpx

from config import settings


logger = logging.getLogger(__name__)


GOOGLE_TOKENINFO = "https://oauth2.googleapis.com/tokeninfo"
DRIVE_FILES = "https://www.googleapis.com/drive/v3/files"

REQUIRED_SCOPE = "https://www.googleapis.com/auth/drive.file"

# Google-native MIME types -> export target (and the extension we'll save).
GOOGLE_NATIVE_EXPORT = {
    "application/vnd.google-apps.document": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".docx",
    ),
    "application/vnd.google-apps.spreadsheet": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xlsx",
    ),
    "application/vnd.google-apps.presentation": (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".pptx",
    ),
}


class DriveTokenError(Exception):
    """Raised when the access_token fails validation or has expired."""

    def __init__(self, code: str, message: str, status_code: int = 401, partial: Optional["DriveImportResult"] = None) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.partial = partial


@dataclass
class DriveImportResult:
    imported: list[dict] = field(default_factory=list)   # [{drive_id, document_id, filename, dedupe?}]
    pending: list[dict] = field(default_factory=list)    # [{drive_id, name, reason}]
    errors: list[dict] = field(default_factory=list)     # [{drive_id, name, error}]


# ---------------------------------------------------------------------------
# Token validation
# ---------------------------------------------------------------------------
async def validate_access_token(token: str) -> dict:
    """Call Google tokeninfo and verify aud + scope. Raises DriveTokenError."""
    if not token or len(token) < 20:
        raise DriveTokenError("TOKEN_VALIDATION_FAILED", "Missing or malformed token")
    if not settings.GOOGLE_CLIENT_ID:
        raise DriveTokenError(
            "DRIVE_NOT_CONFIGURED",
            "Drive integration not configured on server (GOOGLE_CLIENT_ID empty)",
            status_code=503,
        )

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(GOOGLE_TOKENINFO, params={"access_token": token})
    if r.status_code != 200:
        raise DriveTokenError("TOKEN_VALIDATION_FAILED", f"tokeninfo returned {r.status_code}")
    info = r.json()

    # aud check — defense vs confused deputy: someone could try to forward us
    # a Drive token issued for a totally different OAuth client.
    aud = info.get("aud") or info.get("azp")
    if aud != settings.GOOGLE_CLIENT_ID:
        raise DriveTokenError(
            "TOKEN_VALIDATION_FAILED",
            f"Token audience mismatch (got '{aud}', expected our client id)",
        )

    scopes = (info.get("scope") or "").split()
    if REQUIRED_SCOPE not in scopes:
        raise DriveTokenError(
            "TOKEN_VALIDATION_FAILED",
            f"Token missing required scope {REQUIRED_SCOPE}",
        )
    return info


# ---------------------------------------------------------------------------
# Download / export
# ---------------------------------------------------------------------------
async def download_drive_file(token: str, file_id: str, mime_type: str) -> tuple[bytes, str, str]:
    """Return (file_bytes, effective_mime, suggested_extension)."""
    headers = {"Authorization": f"Bearer {token}"}
    if mime_type in GOOGLE_NATIVE_EXPORT:
        export_mime, ext = GOOGLE_NATIVE_EXPORT[mime_type]
        url = f"{DRIVE_FILES}/{file_id}/export"
        params = {"mimeType": export_mime}
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.get(url, headers=headers, params=params)
        _raise_for_drive_status(r)
        return r.content, export_mime, ext

    # Binary file — alt=media.
    url = f"{DRIVE_FILES}/{file_id}"
    params = {"alt": "media"}
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.get(url, headers=headers, params=params)
    _raise_for_drive_status(r)
    # Try to derive a reasonable extension from the original mime.
    ext = ""
    if mime_type == "application/pdf":
        ext = ".pdf"
    elif mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        ext = ".docx"
    elif mime_type == "text/plain":
        ext = ".txt"
    return r.content, mime_type, ext


def _raise_for_drive_status(response: httpx.Response) -> None:
    if response.status_code == 401:
        raise DriveTokenError("DRIVE_TOKEN_EXPIRED", "Drive token expired or revoked", status_code=403)
    if response.status_code == 403:
        # Drive distinguishes 403 by reason; for our purposes most 403 here
        # mean scope insufficient or rate-limited.
        raise DriveTokenError("DRIVE_FORBIDDEN", "Drive denied the request (scope or quota)", status_code=403)
    if response.status_code >= 400:
        raise DriveTokenError(
            "DRIVE_DOWNLOAD_FAILED",
            f"Drive returned {response.status_code}: {response.text[:200]}",
            status_code=502,
        )


# ---------------------------------------------------------------------------
# Import orchestration
# ---------------------------------------------------------------------------
async def import_drive_files(
    *,
    case_id: str,
    drive_files: list[dict],
    access_token: str,
    user: dict,
    background_indexer,
) -> DriveImportResult:
    """Download each picked file, dedupe by SHA-256, store in Supabase Storage,
    insert case_documents row, queue indexing.

    `background_indexer` is `routes.documents._index_in_background` injected
    to avoid a circular import.
    """
    import uuid
    from services.supabase_client import get_supabase_admin, get_user_client
    from services.mappers import new_doc_row

    # Validate first — fast fail if creds bad.
    await validate_access_token(access_token)

    user_sb = get_user_client(user["token"])
    admin = get_supabase_admin()

    # Verify case ownership before anything else.
    case_row = user_sb.table("cases").select("id, owner_id").eq("id", case_id).single().execute()
    if not case_row.data:
        raise DriveTokenError("CASE_NOT_FOUND", "Case not found or not owned", status_code=404)

    result = DriveImportResult()

    for idx, f in enumerate(drive_files):
        drive_id = f.get("id")
        name = f.get("name") or f"drive-{drive_id}"
        mime = f.get("mimeType") or "application/octet-stream"
        try:
            raw, eff_mime, ext = await download_drive_file(access_token, drive_id, mime)
        except DriveTokenError as exc:
            if exc.code == "DRIVE_TOKEN_EXPIRED":
                # Stop the loop. Frontend will re-pick the picker and retry pending.
                pending_tail = drive_files[idx:]
                result.pending = [{"drive_id": p.get("id"), "name": p.get("name"), "mimeType": p.get("mimeType")} for p in pending_tail]
                logger.warning(
                    "Drive token expired mid-import (case=%s, processed=%d/%d)",
                    case_id, idx, len(drive_files),
                )
                # Re-raise carrying partial progress so the route can return it.
                raise DriveTokenError(
                    "DRIVE_TOKEN_EXPIRED",
                    "Drive token expired mid-import",
                    status_code=403,
                    partial=result,
                ) from exc
            result.errors.append({"drive_id": drive_id, "name": name, "error": exc.code})
            continue
        except Exception as exc:  # noqa: BLE001
            logger.exception("drive download failed for %s", drive_id)
            result.errors.append({"drive_id": drive_id, "name": name, "error": f"download_failed:{exc!s}"[:200]})
            continue

        digest = hashlib.sha256(raw).hexdigest()

        # Dedupe by hash within the case.
        existing = (
            user_sb.table("case_documents")
            .select("*")
            .eq("case_id", case_id)
            .eq("hash_sha256", digest)
            .limit(1)
            .execute()
        )
        if existing.data:
            doc = existing.data[0]
            result.imported.append({
                "drive_id": drive_id,
                "document_id": doc["id"],
                "filename": doc.get("nombre"),
                "deduped": True,
            })
            continue

        # Storage upload.
        clean_name = (name if name.lower().endswith(ext.lower()) else f"{name}{ext}") if ext else name
        storage_path = f"{user['id']}/{case_id}/{uuid.uuid4()}-{clean_name}"
        admin.storage.from_("legal-documents").upload(
            path=storage_path,
            file=raw,
            file_options={"content-type": eff_mime, "upsert": "true"},
        )

        inserted = (
            admin.table("case_documents")
            .insert(new_doc_row(
                case_id=case_id,
                filename=clean_name,
                storage_path=storage_path,
                mime_type=eff_mime,
                size_bytes=len(raw),
                hash_sha256=digest,
                source="drive",
                drive_file_id=drive_id,
                drive_revision_id=f.get("revisionId"),
            ))
            .execute()
        )
        if not inserted.data:
            result.errors.append({"drive_id": drive_id, "name": name, "error": "insert_failed"})
            continue
        doc_row = inserted.data[0]

        # Queue indexing in background (same path as upload).
        background_indexer(doc_row["id"], raw, eff_mime, clean_name)

        result.imported.append({
            "drive_id": drive_id,
            "document_id": doc_row["id"],
            "filename": doc_row.get("nombre"),
            "deduped": False,
        })

    return result
