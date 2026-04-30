"""Document ingestion: upload, list, get, delete, reindex."""
from __future__ import annotations

import asyncio
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile

from services import audit
from services.auth import get_current_user
from services.chunker import chunk_text
from services.embeddings_pipeline import index_document
from services.extractor import extract
from services.mappers import doc_to_api, new_doc_row
from services.supabase_client import get_supabase_admin, get_user_client


router = APIRouter()


@router.get("")
async def list_documents(case_id: str, user: dict = Depends(get_current_user)):
    sb = get_user_client(user["token"])
    res = (
        sb.table("case_documents")
        .select("*")
        .eq("case_id", case_id)
        .order("created_at", desc=True)
        .execute()
    )
    return [doc_to_api(r) for r in (res.data or [])]


@router.get("/{document_id}")
async def get_document(document_id: str, user: dict = Depends(get_current_user)):
    sb = get_user_client(user["token"])
    res = sb.table("case_documents").select("*").eq("id", document_id).single().execute()
    if not res.data:
        raise HTTPException(404, "Document not found")
    return doc_to_api(res.data)


@router.post("/upload", status_code=201)
async def upload_document(
    background: BackgroundTasks,
    case_id: str = Form(...),
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    """Upload a document, dedupe by SHA-256, store in Supabase Storage, queue indexing."""
    raw = await file.read()
    if not raw:
        raise HTTPException(400, "Empty file")
    digest = hashlib.sha256(raw).hexdigest()

    user_sb = get_user_client(user["token"])
    existing = (
        user_sb.table("case_documents")
        .select("*")
        .eq("case_id", case_id)
        .eq("hash_sha256", digest)
        .limit(1)
        .execute()
    )
    if existing.data:
        return doc_to_api(existing.data[0])

    case_row = user_sb.table("cases").select("id, owner_id").eq("id", case_id).single().execute()
    if not case_row.data:
        raise HTTPException(404, "Case not found or not owned")

    admin = get_supabase_admin()
    storage_name = f"{user['id']}/{case_id}/{uuid.uuid4()}-{file.filename or 'document'}"
    admin.storage.from_("legal-documents").upload(
        path=storage_name,
        file=raw,
        file_options={
            "content-type": file.content_type or "application/octet-stream",
            "upsert": "true",
        },
    )

    inserted = (
        admin.table("case_documents")
        .insert(new_doc_row(
            case_id=case_id,
            filename=file.filename,
            storage_path=storage_name,
            mime_type=file.content_type,
            size_bytes=len(raw),
            hash_sha256=digest,
            source="upload",
        ))
        .execute()
    )
    if not inserted.data:
        raise HTTPException(500, "Failed to register document")
    doc_row = inserted.data[0]

    audit.log(
        actor_id=user["id"],
        action="document.upload",
        case_id=case_id,
        resource_type="document",
        resource_id=doc_row["id"],
        payload={"filename": doc_row.get("nombre"), "size_bytes": doc_row.get("size_bytes")},
    )

    background.add_task(_index_in_background, doc_row["id"], raw, file.content_type, file.filename)
    return doc_to_api(doc_row)


def _index_in_background(document_id: str, file_bytes: bytes, mime: Optional[str], filename: Optional[str]):
    try:
        asyncio.run(_index_async(document_id, file_bytes, mime, filename))
    except Exception as exc:  # noqa: BLE001
        admin = get_supabase_admin()
        # Merge error into metadata so we don't clobber source/etc.
        current = admin.table("case_documents").select("metadata").eq("id", document_id).single().execute().data or {}
        meta = dict(current.get("metadata") or {})
        meta["index_error"] = str(exc)[:1000]
        admin.table("case_documents").update({"metadata": meta}).eq("id", document_id).execute()
        print(f"[ingest] document {document_id} failed: {exc}")


async def _index_async(document_id: str, file_bytes: bytes, mime: Optional[str], filename: Optional[str]):
    extracted = extract(file_bytes, mime, filename)
    chunks = chunk_text(extracted)
    await index_document(document_id=document_id, extracted=extracted, chunks=chunks)


@router.post("/{document_id}/reindex")
async def reindex_document(document_id: str, background: BackgroundTasks, user: dict = Depends(get_current_user)):
    user_sb = get_user_client(user["token"])
    doc = user_sb.table("case_documents").select("*").eq("id", document_id).single().execute()
    if not doc.data:
        raise HTTPException(404, "Document not found")
    admin = get_supabase_admin()
    file_bytes_resp = admin.storage.from_("legal-documents").download(doc.data["storage_path"])
    if not file_bytes_resp:
        raise HTTPException(500, "Failed to download stored file")
    admin.table("document_chunks").delete().eq("document_id", document_id).execute()

    # Reset indexed_at and clear previous error.
    meta = dict(doc.data.get("metadata") or {})
    meta.pop("index_error", None)
    admin.table("case_documents").update({"indexed_at": None, "metadata": meta}).eq("id", document_id).execute()

    background.add_task(
        _index_in_background, document_id, bytes(file_bytes_resp), doc.data.get("mime_type"), doc.data.get("nombre")
    )
    audit.log(actor_id=user["id"], action="document.reindex", case_id=doc.data.get("case_id"), resource_type="document", resource_id=document_id)
    return {"status": "indexing"}


@router.delete("/{document_id}", status_code=204)
async def delete_document(document_id: str, user: dict = Depends(get_current_user)):
    user_sb = get_user_client(user["token"])
    doc = user_sb.table("case_documents").select("*").eq("id", document_id).single().execute()
    if not doc.data:
        raise HTTPException(404, "Document not found")
    admin = get_supabase_admin()
    try:
        admin.storage.from_("legal-documents").remove([doc.data["storage_path"]])
    except Exception:
        pass
    admin.table("case_documents").delete().eq("id", document_id).execute()
    audit.log(actor_id=user["id"], action="document.delete", case_id=doc.data.get("case_id"), resource_type="document", resource_id=document_id)
    return None
