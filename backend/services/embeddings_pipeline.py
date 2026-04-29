"""Background indexing pipeline — chunks + embeddings + DB writes."""
from __future__ import annotations

from datetime import datetime, timezone

from services import llm
from services.chunker import Chunk
from services.extractor import Extracted
from services.supabase_client import get_supabase_admin


async def index_document(*, document_id: str, extracted: Extracted, chunks: list[Chunk]) -> None:
    admin = get_supabase_admin()
    if not chunks:
        admin.table("case_documents").update({
            "status": "ready",
            "texto_extraido": extracted["full_text"],
            "pages_count": extracted["pages_count"],
            "indexed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", document_id).execute()
        return

    # Pull case_id and owner_id once.
    doc = admin.table("case_documents").select("id, case_id, owner_id").eq("id", document_id).single().execute()
    if not doc.data:
        raise RuntimeError(f"document {document_id} disappeared during indexing")
    case_id = doc.data["case_id"]
    owner_id = doc.data["owner_id"]

    vectors, _usage = await llm.embed_batch([c.chunk_text for c in chunks])

    rows = []
    for chunk, vec in zip(chunks, vectors):
        rows.append({
            "document_id": document_id,
            "case_id": case_id,
            "owner_id": owner_id,
            "chunk_index": chunk.chunk_index,
            "page": chunk.page,
            "paragraph": chunk.paragraph,
            "chunk_text": chunk.chunk_text,
            "token_count": chunk.token_count,
            "embedding": vec,
        })

    # Insert in batches of 200 to stay below request size limits.
    for i in range(0, len(rows), 200):
        admin.table("document_chunks").insert(rows[i:i + 200]).execute()

    admin.table("case_documents").update({
        "status": "ready",
        "texto_extraido": extracted["full_text"],
        "pages_count": extracted["pages_count"],
        "indexed_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", document_id).execute()
