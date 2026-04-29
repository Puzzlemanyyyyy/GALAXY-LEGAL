"""Token-aware chunking with page tracking."""
from __future__ import annotations

import re
from dataclasses import dataclass

import tiktoken

from .extractor import Extracted

_ENC = tiktoken.get_encoding("cl100k_base")


@dataclass
class Chunk:
    chunk_index: int
    chunk_text: str
    page: int
    paragraph: int
    token_count: int


def _split_paragraphs(text: str) -> list[str]:
    # Split on blank lines or hard returns; keep non-empty paragraphs.
    parts = re.split(r"\n\s*\n+|\r\n\s*\r\n+", text)
    return [p.strip() for p in parts if p.strip()]


def chunk_text(extracted: Extracted, target_tokens: int = 400, overlap_tokens: int = 50) -> list[Chunk]:
    """Greedy paragraph-aware chunker with token overlap for context preservation."""
    chunks: list[Chunk] = []
    chunk_idx = 0

    for page_obj in extracted["pages"]:
        page_no = page_obj["page"]
        paragraphs = _split_paragraphs(page_obj["text"])
        if not paragraphs:
            continue

        buf: list[str] = []
        buf_tokens = 0
        first_para_no = 1

        for p_idx, para in enumerate(paragraphs, start=1):
            tok = len(_ENC.encode(para))
            if buf and buf_tokens + tok > target_tokens:
                # Flush current buffer
                text = "\n\n".join(buf)
                chunks.append(Chunk(
                    chunk_index=chunk_idx,
                    chunk_text=text,
                    page=page_no,
                    paragraph=first_para_no,
                    token_count=buf_tokens,
                ))
                chunk_idx += 1
                # Carry overlap (last paragraphs) into the new buffer.
                overlap_buf: list[str] = []
                overlap_count = 0
                for prev in reversed(buf):
                    pt = len(_ENC.encode(prev))
                    if overlap_count + pt > overlap_tokens:
                        break
                    overlap_buf.insert(0, prev)
                    overlap_count += pt
                buf = overlap_buf
                buf_tokens = overlap_count
                first_para_no = max(1, p_idx - len(overlap_buf))

            buf.append(para)
            buf_tokens += tok

        if buf:
            text = "\n\n".join(buf)
            chunks.append(Chunk(
                chunk_index=chunk_idx,
                chunk_text=text,
                page=page_no,
                paragraph=first_para_no,
                token_count=buf_tokens,
            ))
            chunk_idx += 1

    return chunks
