"""Initial analysis workflow.

Goal: after the first document is indexed in a case, produce an executive
summary, a facts matrix, and a list of risks/red flags. The output is a
draft of type ``initial_analysis`` that the lawyer can review or feed into
later workflows (civil_demand, fiscal_consultation, etc.).
"""
from __future__ import annotations

import json

from .base import StepContext, Workflow, WorkflowStep


_FACTS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "case_summary": {"type": "string", "minLength": 30},
        "parties": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "role": {"type": "string"},
                    "name": {"type": "string"},
                },
                "required": ["role", "name"],
            },
        },
        "facts": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "fact_id": {"type": "string"},
                    "text": {"type": "string"},
                    "evidence_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["fact_id", "text", "evidence_ids"],
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
    "required": ["case_summary", "parties", "facts", "evidences"],
}


_RISKS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "risks": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "id": {"type": "string"},
                    "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                    "title": {"type": "string"},
                    "explanation": {"type": "string"},
                    "evidence_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["id", "severity", "title", "explanation", "evidence_ids"],
            },
        },
        "next_steps": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["risks", "next_steps"],
}


def _serialize_chunks(chunks: list[dict]) -> str:
    """Format chunks for the model, including their stable identifiers."""
    parts = []
    for c in chunks[:80]:  # cap context size
        parts.append(
            f"[doc={c['document_id']} page={c.get('page','?')} para={c.get('paragraph','?')}]\n"
            f"{c['chunk_text']}"
        )
    return "\n\n---\n\n".join(parts)


def _facts_user_prompt(ctx: StepContext) -> str:
    chunks_blob = _serialize_chunks(ctx.chunks)
    docs = "\n".join(f"- {d['id']}: {d.get('filename')}" for d in ctx.documents)
    return (
        "Eres un analista jurídico. Lee ÚNICAMENTE los siguientes fragmentos "
        "(no inventes nada que no esté literalmente en ellos) y produce un análisis inicial.\n\n"
        f"Documentos del expediente:\n{docs}\n\n"
        f"Caso: {ctx.case.get('title')}\n"
        f"Jurisdicción: {ctx.case.get('jurisdiccion') or '—'}\n"
        f"Materia: {ctx.case.get('materia') or '—'}\n\n"
        "Reglas estrictas:\n"
        "- Cada `fact` requiere al menos un `evidence_ids`.\n"
        "- Cada `evidences[i].quote_excerpt` debe ser un fragmento VERBATIM (palabra por palabra) "
        "presente en alguno de los chunks proporcionados.\n"
        "- `evidences[i].document_id` debe ser uno de los document_ids listados arriba.\n"
        "- Usa identificadores cortos: facts c001..cNNN, evidences e001..eNNN.\n\n"
        f"Fragmentos disponibles:\n{chunks_blob}"
    )


def _risks_user_prompt(ctx: StepContext) -> str:
    facts = ctx.previous_outputs.get("extract_facts", {})
    return (
        "A partir del análisis fáctico previo, identifica los riesgos legales y "
        "próximos pasos recomendados. Usa los `evidence_ids` ya creados (no inventes "
        "nuevas evidencias).\n\n"
        "Análisis fáctico (JSON):\n"
        + json.dumps(facts, ensure_ascii=False)
    )


def _facts_validator(payload: dict, ctx: StepContext) -> list[str]:
    errs: list[str] = []
    valid_doc_ids = {d["id"] for d in ctx.documents}
    evidence_ids = {e.get("id") for e in payload.get("evidences", [])}
    for ev in payload.get("evidences", []):
        if ev.get("document_id") not in valid_doc_ids:
            errs.append(f"evidence {ev.get('id')} references unknown document_id {ev.get('document_id')}")
    for fact in payload.get("facts", []):
        if not fact.get("evidence_ids"):
            errs.append(f"fact {fact.get('fact_id')} has no evidence_ids")
        for eid in fact.get("evidence_ids", []):
            if eid not in evidence_ids:
                errs.append(f"fact {fact.get('fact_id')} references unknown evidence_id {eid}")
    return errs


class InitialAnalysisWorkflow(Workflow):
    workflow_type = "initial_analysis"
    title = "Análisis inicial"
    draft_type = "initial_analysis"
    steps = [
        WorkflowStep(
            name="extract_facts",
            system_prompt=(
                "Eres un asistente jurídico riguroso. Solo afirmas lo que está literalmente "
                "en los documentos provistos. Si algo no aparece, lo omites."
            ),
            user_prompt_builder=_facts_user_prompt,
            output_schema=_FACTS_SCHEMA,
            validator=_facts_validator,
        ),
        WorkflowStep(
            name="flag_risks",
            system_prompt=(
                "Eres un analista de riesgos legales. Reutiliza los evidence_ids ya "
                "creados; no introduzcas nuevas evidencias."
            ),
            user_prompt_builder=_risks_user_prompt,
            output_schema=_RISKS_SCHEMA,
        ),
    ]

    async def assemble_draft(self, context: StepContext) -> dict:
        facts_out = context.previous_outputs.get("extract_facts", {})
        risks_out = context.previous_outputs.get("flag_risks", {})

        case_title = context.case.get("title") or "Expediente"
        summary = facts_out.get("case_summary", "")
        parties = facts_out.get("parties", [])
        facts = facts_out.get("facts", [])
        evidences = facts_out.get("evidences", [])
        risks = risks_out.get("risks", [])
        next_steps = risks_out.get("next_steps", [])

        lines: list[str] = []
        lines.append(f"# Análisis inicial — {case_title}\n")
        if summary:
            lines.append("## Resumen ejecutivo\n")
            lines.append(summary + "\n")
        if parties:
            lines.append("## Partes\n")
            for p in parties:
                lines.append(f"- **{p.get('role','')}**: {p.get('name','')}")
            lines.append("")
        if facts:
            lines.append("## Hechos\n")
            for f in facts:
                refs = "".join(f"[E:{eid}]" for eid in f.get("evidence_ids", []))
                lines.append(f"- ({f.get('fact_id')}) {f.get('text')} {refs}")
            lines.append("")
        if risks:
            lines.append("## Riesgos identificados\n")
            for r in risks:
                refs = "".join(f"[E:{eid}]" for eid in r.get("evidence_ids", []))
                lines.append(f"- **{r.get('severity','').upper()}** — {r.get('title')}: {r.get('explanation')} {refs}")
            lines.append("")
        if next_steps:
            lines.append("## Próximos pasos\n")
            for ns in next_steps:
                lines.append(f"- {ns}")
            lines.append("")

        return {
            "title": f"Análisis inicial — {case_title}",
            "content_md": "\n".join(lines).strip() + "\n",
            "evidences": evidences,
        }
