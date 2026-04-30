"""Jurisprudence analysis workflow — analysis restricted to the case corpus.

Sections: issues, internal findings per issue, evidence-backed memo. Does
not reach out to CENDOJ yet (planned for v2-c); all findings must be
grounded on verbatim excerpts from uploaded documents in this case.
"""
from __future__ import annotations

import json

from .base import StepContext, Workflow, WorkflowStep
from .initial_analysis import _serialize_chunks


_ISSUES_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "id": {"type": "string"},
                    "titulo": {"type": "string"},
                    "descripcion": {"type": "string"},
                    "evidence_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["id", "titulo", "descripcion", "evidence_ids"],
            },
        },
        "evidences": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "id": {"type": "string"},
                    "document_id": {"type": "string"},
                    "page": {"type": ["integer", "null"]},
                    "paragraph": {"type": ["integer", "null"]},
                    "quote_excerpt": {"type": "string", "minLength": 10},
                    "claim_id": {"type": ["string", "null"]},
                },
                "required": ["id", "document_id", "page", "paragraph", "quote_excerpt", "claim_id"],
            },
        },
    },
    "required": ["issues", "evidences"],
}


_MEMO_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "issue_id": {"type": "string"},
                    "finding": {"type": "string", "minLength": 30},
                    "postura_favorable": {"type": "string"},
                    "postura_contraria": {"type": "string"},
                    "evidence_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["issue_id", "finding", "postura_favorable", "postura_contraria", "evidence_ids"],
            },
        },
        "recomendaciones": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["findings", "recomendaciones"],
}


def _issues_prompt(ctx: StepContext) -> str:
    chunks_blob = _serialize_chunks(ctx.chunks)
    docs = "\n".join(f"- {d['id']}: {d.get('filename')}" for d in ctx.documents)
    return (
        "Eres abogado con experiencia en análisis de jurisprudencia. "
        "A partir EXCLUSIVAMENTE de los fragmentos aportados, identifica las "
        "cuestiones jurídicas relevantes (no inventes jurisprudencia externa).\n\n"
        f"Documentos:\n{docs}\n\n"
        f"Caso: {ctx.case.get('title')}\n"
        "Cada issue con al menos un evidence_id; evidences con quote_excerpt "
        "literal de los chunks.\n\n"
        f"Fragmentos:\n{chunks_blob}"
    )


def _memo_prompt(ctx: StepContext) -> str:
    issues = ctx.previous_outputs.get("extract_issues", {})
    return (
        "Para cada issue identificada, redacta un finding balanceado que refleje "
        "la postura más favorable y la más contraria. Reusa evidence_ids existentes.\n\n"
        "Issues (JSON):\n" + json.dumps(issues, ensure_ascii=False)
    )


def _issues_validator(payload: dict, ctx: StepContext) -> list[str]:
    errs: list[str] = []
    valid_doc_ids = {d["id"] for d in ctx.documents}
    for ev in payload.get("evidences", []):
        if ev.get("document_id") not in valid_doc_ids:
            errs.append(f"evidence {ev.get('id')} references unknown document_id")
    for it in payload.get("issues", []):
        if not it.get("evidence_ids"):
            errs.append(f"issue {it.get('id')} has no evidence_ids")
    return errs


class JurisprudenceAnalysisWorkflow(Workflow):
    workflow_type = "jurisprudence_analysis"
    title = "Análisis de jurisprudencia"
    draft_type = "jurisprudence_analysis"
    steps = [
        WorkflowStep(
            name="extract_issues",
            system_prompt=(
                "Eres abogado riguroso. Solo analizas lo que aparece en los documentos "
                "aportados, sin introducir jurisprudencia externa."
            ),
            user_prompt_builder=_issues_prompt,
            output_schema=_ISSUES_SCHEMA,
            validator=_issues_validator,
        ),
        WorkflowStep(
            name="build_memo",
            system_prompt=(
                "Eres abogado que redacta memos jurídicos balanceados. Reusas "
                "evidence_ids; no inventas jurisprudencia externa."
            ),
            user_prompt_builder=_memo_prompt,
            output_schema=_MEMO_SCHEMA,
        ),
    ]

    async def assemble_draft(self, context: StepContext) -> dict:
        issues = context.previous_outputs.get("extract_issues", {})
        memo = context.previous_outputs.get("build_memo", {})
        case_title = context.case.get("title") or "Expediente"
        parts: list[str] = []
        parts.append(f"# Análisis de jurisprudencia — {case_title}\n")
        parts.append("## Cuestiones identificadas\n")
        for it in issues.get("issues", []):
            refs = "".join(f"[E:{eid}]" for eid in it.get("evidence_ids", []))
            parts.append(f"- **{it.get('id')} — {it.get('titulo')}**: {it.get('descripcion')} {refs}")
        parts.append("")
        parts.append("## Análisis\n")
        for f in memo.get("findings", []):
            refs = "".join(f"[E:{eid}]" for eid in f.get("evidence_ids", []))
            parts.append(f"### {f.get('issue_id')}\n")
            parts.append(f.get("finding", "") + f" {refs}")
            parts.append("")
            parts.append(f"_Postura favorable_: {f.get('postura_favorable','—')}")
            parts.append(f"_Postura contraria_: {f.get('postura_contraria','—')}")
            parts.append("")
        if memo.get("recomendaciones"):
            parts.append("## Recomendaciones\n")
            for r in memo["recomendaciones"]:
                parts.append(f"- {r}")
            parts.append("")
        return {
            "title": f"Análisis de jurisprudencia — {case_title}",
            "content_md": "\n".join(parts).strip() + "\n",
            "evidences": issues.get("evidences", []),
        }
