"""Mappers between the Supabase schema columns and the API response shape.

The live Supabase schema uses domain-translated names (nombre, tipo_documento,
completed_at, error_message, diff_from_previous, page_count, reviewer_id)
and lacks a few columns that the application tracks logically (status,
source, index_error, external_id on evidences, title and citations_valid
on drafts, current_step on runs).

These helpers keep one canonical JSON shape for the frontend while the
backend continues to insert into the real columns. Logical fields that
don't have a dedicated column are stored inside JSONB bags (``metadata``
on ``case_documents``, ``output_jsonb`` on ``runs``) and reconstructed on
read.
"""
from __future__ import annotations

import re
from typing import Any


# ---------------------------------------------------------------------------
# case_documents
# ---------------------------------------------------------------------------
def doc_to_api(row: dict[str, Any]) -> dict[str, Any]:
    metadata = row.get("metadata") or {}
    index_error = metadata.get("index_error") if isinstance(metadata, dict) else None
    indexed_at = row.get("indexed_at")
    if index_error:
        status = "failed"
    elif indexed_at:
        status = "ready"
    else:
        status = "indexing"
    return {
        "id": row.get("id"),
        "case_id": row.get("case_id"),
        "filename": row.get("nombre"),
        "storage_path": row.get("storage_path"),
        "mime_type": row.get("mime_type"),
        "size_bytes": row.get("size_bytes"),
        "hash_sha256": row.get("hash_sha256"),
        "drive_file_id": row.get("drive_file_id"),
        "drive_revision_id": row.get("drive_revision_id"),
        "source": (metadata.get("source") if isinstance(metadata, dict) else None) or "upload",
        "pages_count": row.get("page_count"),
        "texto_extraido": row.get("texto_extraido"),
        "status": status,
        "index_error": index_error,
        "indexed_at": indexed_at,
        "created_at": row.get("created_at"),
    }


def new_doc_row(
    *,
    case_id: str,
    filename: str | None,
    storage_path: str,
    mime_type: str | None,
    size_bytes: int,
    hash_sha256: str,
    source: str = "upload",
    drive_file_id: str | None = None,
    drive_revision_id: str | None = None,
) -> dict:
    name = filename or "document"
    return {
        "case_id": case_id,
        "nombre": name,
        # ``tipo`` is a domain enum on the live schema (the valid value we
        # confirmed is "other"; legal categories like demanda/factura/etc
        # will be set by the user on edit). Store the raw file extension in
        # metadata so we still have it available downstream.
        "tipo": "other",
        "mime_type": mime_type,
        "size_bytes": size_bytes,
        "hash_sha256": hash_sha256,
        "storage_path": storage_path,
        "drive_file_id": drive_file_id,
        "drive_revision_id": drive_revision_id,
        "metadata": {
            "source": source,
            "ext": (name.rsplit(".", 1)[-1].lower() if "." in name else "") or None,
        },
    }


# ---------------------------------------------------------------------------
# runs
# ---------------------------------------------------------------------------
def run_to_api(row: dict[str, Any]) -> dict[str, Any]:
    output = row.get("output_jsonb") or {}
    return {
        "id": row.get("id"),
        "case_id": row.get("case_id"),
        "owner_id": row.get("owner_id"),
        "workflow_type": row.get("workflow_type"),
        "status": row.get("status"),
        "current_step": (output.get("_current_step") if isinstance(output, dict) else None),
        "output_jsonb": output,
        "tokens_input": row.get("tokens_input") or 0,
        "tokens_output": row.get("tokens_output") or 0,
        "cost_usd": float(row.get("cost_usd") or 0),
        "error": row.get("error_message"),
        "started_at": row.get("started_at"),
        "finished_at": row.get("completed_at"),
        "created_at": row.get("created_at"),
    }


# ---------------------------------------------------------------------------
# evidences
# ---------------------------------------------------------------------------
def evidence_to_api(row: dict[str, Any]) -> dict[str, Any]:
    # claim_id column is reused to store both the "e001" external id and
    # (via a JSON payload) the original claim it supports. For legacy
    # responses we expose it as ``external_id``.
    return {
        "id": row.get("id"),
        "run_id": row.get("run_id"),
        "document_id": row.get("document_id"),
        "external_id": row.get("claim_id") or row.get("id"),
        "claim_id": row.get("claim_id"),
        "chunk_id": row.get("chunk_id"),
        "page": row.get("page"),
        "paragraph": row.get("paragraph"),
        "quote_excerpt": row.get("quote_excerpt"),
        "verified": bool(row.get("verified")),
        "created_at": row.get("created_at"),
    }


# ---------------------------------------------------------------------------
# drafts
# ---------------------------------------------------------------------------
_H1 = re.compile(r"^\s*#\s+(.+?)\s*$", re.M)


def _derive_title(content_md: str, fallback: str) -> str:
    m = _H1.search(content_md or "")
    return (m.group(1).strip() if m else fallback) or fallback


def draft_to_api(row: dict[str, Any]) -> dict[str, Any]:
    tipo = row.get("tipo_documento") or "draft"
    title = _derive_title(row.get("content_md") or "", tipo.replace("_", " ").title())
    is_revision = bool(row.get("parent_draft_id"))
    # Our workflow pipeline only creates drafts after citation validation
    # succeeds; revisions (human edits) require re-validation in v2.
    citations_valid = (not is_revision) and (row.get("status") != "rejected")
    return {
        "id": row.get("id"),
        "case_id": row.get("case_id"),
        "run_id": row.get("run_id"),
        "parent_draft_id": row.get("parent_draft_id"),
        "version": row.get("version"),
        "draft_type": tipo,
        "tipo_documento": tipo,
        "title": title,
        "content_md": row.get("content_md"),
        "diff_patch": row.get("diff_from_previous"),
        "status": row.get("status"),
        "citations_valid": citations_valid,
        "approved_at": row.get("approved_at"),
        "approved_by": row.get("reviewer_id"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }
