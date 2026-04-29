"""Citation validation — verbatim substring match between draft claims and chunks.

Hard rule (anti-fantasma): every evidence's ``quote_excerpt`` must appear,
case-insensitive and whitespace-normalized, inside the source document's
extracted text. The validator returns the list of unverified evidences;
callers MUST refuse to mark drafts approvable when the list is non-empty.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


_WS = re.compile(r"\s+")


def _norm(s: str) -> str:
    return _WS.sub(" ", (s or "").strip().lower())


@dataclass
class EvidenceInput:
    external_id: str
    document_id: str
    quote_excerpt: str
    page: int | None = None
    paragraph: int | None = None


@dataclass
class ValidationError:
    external_id: str
    reason: str


@dataclass
class ValidationResult:
    valid: bool
    errors: list[ValidationError]
    verified_ids: list[str]


def validate_citations(
    evidences: list[EvidenceInput],
    documents_text: dict[str, str],
) -> ValidationResult:
    """Validate every evidence against the corresponding document's full text.

    ``documents_text`` maps ``document_id`` to the full extracted text.
    """
    errors: list[ValidationError] = []
    verified: list[str] = []
    for ev in evidences:
        excerpt = _norm(ev.quote_excerpt)
        if len(excerpt) < 10:
            errors.append(ValidationError(ev.external_id, "quote_excerpt is too short (<10 chars after normalization)"))
            continue
        doc_text = documents_text.get(ev.document_id)
        if not doc_text:
            errors.append(ValidationError(ev.external_id, f"document_id {ev.document_id} not found in case scope"))
            continue
        if excerpt not in _norm(doc_text):
            errors.append(ValidationError(ev.external_id, "quote_excerpt does not substring-match the source document (verbatim required)"))
            continue
        verified.append(ev.external_id)
    return ValidationResult(valid=not errors, errors=errors, verified_ids=verified)


def parse_evidence_markers(content_md: str) -> list[str]:
    """Return the list of external_ids referenced as ``[E:xxx]`` in the markdown."""
    return list(dict.fromkeys(re.findall(r"\[E:([A-Za-z0-9_-]+)\]", content_md or "")))
