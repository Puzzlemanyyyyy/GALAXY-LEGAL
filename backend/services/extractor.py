"""Document text extraction by mime type."""
from __future__ import annotations

import io
import re
from typing import TypedDict


class Page(TypedDict):
    page: int
    text: str


class Extracted(TypedDict):
    full_text: str
    pages: list[Page]
    pages_count: int


def _normalize(text: str) -> str:
    text = text.replace("\u00ad", "")  # soft hyphen
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_text_from_pdf(file_bytes: bytes) -> Extracted:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(file_bytes))
    pages: list[Page] = []
    parts: list[str] = []
    for idx, page in enumerate(reader.pages, start=1):
        try:
            txt = page.extract_text() or ""
        except Exception:
            txt = ""
        txt = _normalize(txt)
        pages.append({"page": idx, "text": txt})
        parts.append(txt)
    full = "\n\n".join(parts)
    return {"full_text": full, "pages": pages, "pages_count": len(pages)}


def extract_text_from_docx(file_bytes: bytes) -> Extracted:
    from docx import Document
    doc = Document(io.BytesIO(file_bytes))
    paragraphs: list[str] = []
    for p in doc.paragraphs:
        t = (p.text or "").strip()
        if t:
            paragraphs.append(t)
    # python-docx loses page breaks; treat the whole doc as page 1.
    full = _normalize("\n\n".join(paragraphs))
    return {"full_text": full, "pages": [{"page": 1, "text": full}], "pages_count": 1}


def extract_text_from_txt(file_bytes: bytes) -> Extracted:
    raw = file_bytes.decode("utf-8", errors="replace")
    full = _normalize(raw)
    return {"full_text": full, "pages": [{"page": 1, "text": full}], "pages_count": 1}


def extract(file_bytes: bytes, mime_type: str | None, filename: str | None = None) -> Extracted:
    """Dispatch to the right extractor based on mime type or filename."""
    name = (filename or "").lower()
    mime = (mime_type or "").lower()
    if "pdf" in mime or name.endswith(".pdf"):
        return extract_text_from_pdf(file_bytes)
    if (
        "officedocument.wordprocessingml" in mime
        or "msword" in mime
        or name.endswith(".docx")
    ):
        return extract_text_from_docx(file_bytes)
    if mime.startswith("text/") or name.endswith((".txt", ".md")):
        return extract_text_from_txt(file_bytes)
    # Fallback: try PDF, then text.
    try:
        return extract_text_from_pdf(file_bytes)
    except Exception:
        return extract_text_from_txt(file_bytes)
