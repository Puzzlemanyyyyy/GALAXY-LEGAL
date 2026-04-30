"""Fiscal consultation workflow — produces a dictamen fiscal.

Sections: planteamiento de la consulta, cuestiones jurídicas, normativa
aplicable, análisis, implicaciones fiscales, riesgos, conclusión.
"""
from __future__ import annotations

import json

from .base import StepContext, Workflow, WorkflowStep
from .initial_analysis import _serialize_chunks


_QUESTIONS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "planteamiento": {"type": "string", "minLength": 40},
        "cuestiones": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "id": {"type": "string"},
                    "pregunta": {"type": "string"},
                    "evidence_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["id", "pregunta", "evidence_ids"],
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
    "required": ["planteamiento", "cuestiones", "evidences"],
}


_ANALYSIS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "normativa_aplicable": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "norma": {"type": "string"},
                    "articulo": {"type": "string"},
                    "sintesis": {"type": "string"},
                },
                "required": ["norma", "articulo", "sintesis"],
            },
        },
        "analisis": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "cuestion_id": {"type": "string"},
                    "razonamiento": {"type": "string", "minLength": 40},
                    "evidence_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["cuestion_id", "razonamiento", "evidence_ids"],
            },
        },
        "implicaciones_fiscales": {"type": "array", "items": {"type": "string"}},
        "riesgos": {"type": "array", "items": {"type": "string"}},
        "conclusion": {"type": "string", "minLength": 30},
    },
    "required": ["normativa_aplicable", "analisis", "implicaciones_fiscales", "riesgos", "conclusion"],
}


def _questions_prompt(ctx: StepContext) -> str:
    chunks_blob = _serialize_chunks(ctx.chunks)
    docs = "\n".join(f"- {d['id']}: {d.get('filename')}" for d in ctx.documents)
    return (
        "Eres asesor fiscal. A partir ÚNICAMENTE de los fragmentos aportados, "
        "identifica las cuestiones fiscales que plantea el expediente.\n\n"
        f"Documentos:\n{docs}\n\n"
        f"Caso: {ctx.case.get('title')}\n"
        "Reglas: cada cuestión debe tener al menos un evidence_id; "
        "cada evidence.quote_excerpt es literal de algún chunk; "
        "ids cortos cNNN para cuestiones, eNNN para evidences.\n\n"
        f"Fragmentos:\n{chunks_blob}"
    )


def _analysis_prompt(ctx: StepContext) -> str:
    q = ctx.previous_outputs.get("identify_questions", {})
    return (
        "Realiza el análisis fiscal: identifica normativa aplicable (LIRPF, LIS, "
        "LIVA, LGT, RGR, reglamentos) y razona cada cuestión previamente identificada.\n"
        "No inventes referencias normativas; si no estás seguro, omite.\n"
        "Reusa evidence_ids; no crees nuevos.\n\n"
        "Cuestiones (JSON):\n" + json.dumps(q, ensure_ascii=False)
    )


def _q_validator(payload: dict, ctx: StepContext) -> list[str]:
    errs: list[str] = []
    valid_doc_ids = {d["id"] for d in ctx.documents}
    ev_ids = {e.get("id") for e in payload.get("evidences", [])}
    for ev in payload.get("evidences", []):
        if ev.get("document_id") not in valid_doc_ids:
            errs.append(f"evidence {ev.get('id')} references unknown document_id")
    for q in payload.get("cuestiones", []):
        for eid in q.get("evidence_ids", []):
            if eid not in ev_ids:
                errs.append(f"cuestion {q.get('id')} references unknown evidence_id {eid}")
    return errs


class FiscalConsultationWorkflow(Workflow):
    workflow_type = "fiscal_consultation"
    title = "Consulta fiscal"
    draft_type = "fiscal_consultation"
    steps = [
        WorkflowStep(
            name="identify_questions",
            system_prompt=(
                "Eres asesor fiscal riguroso. Solo afirmas lo que se deriva "
                "literalmente de los documentos aportados."
            ),
            user_prompt_builder=_questions_prompt,
            output_schema=_QUESTIONS_SCHEMA,
            validator=_q_validator,
        ),
        WorkflowStep(
            name="build_analysis",
            system_prompt=(
                "Eres asesor fiscal. Citas solo normativa real (LIRPF, LIS, LIVA, "
                "LGT, reglamentos); nunca inventas artículos. Reusas evidence_ids."
            ),
            user_prompt_builder=_analysis_prompt,
            output_schema=_ANALYSIS_SCHEMA,
        ),
    ]

    async def assemble_draft(self, context: StepContext) -> dict:
        q = context.previous_outputs.get("identify_questions", {})
        a = context.previous_outputs.get("build_analysis", {})
        case_title = context.case.get("title") or "Consulta"
        parts: list[str] = []
        parts.append(f"# Consulta fiscal — {case_title}\n")
        parts.append("## Planteamiento\n")
        parts.append(q.get("planteamiento", "—") + "\n")
        parts.append("## Cuestiones planteadas\n")
        for it in q.get("cuestiones", []):
            refs = "".join(f"[E:{eid}]" for eid in it.get("evidence_ids", []))
            parts.append(f"- **{it.get('id')}**: {it.get('pregunta')} {refs}")
        parts.append("")
        parts.append("## Normativa aplicable\n")
        for n in a.get("normativa_aplicable", []):
            parts.append(f"- **{n.get('norma')}** — art. {n.get('articulo')}: {n.get('sintesis')}")
        parts.append("")
        parts.append("## Análisis\n")
        for an in a.get("analisis", []):
            refs = "".join(f"[E:{eid}]" for eid in an.get("evidence_ids", []))
            parts.append(f"- ({an.get('cuestion_id')}) {an.get('razonamiento')} {refs}")
        parts.append("")
        if a.get("implicaciones_fiscales"):
            parts.append("## Implicaciones fiscales\n")
            for imp in a["implicaciones_fiscales"]:
                parts.append(f"- {imp}")
            parts.append("")
        if a.get("riesgos"):
            parts.append("## Riesgos\n")
            for r in a["riesgos"]:
                parts.append(f"- {r}")
            parts.append("")
        parts.append("## Conclusión\n")
        parts.append(a.get("conclusion", "") + "\n")
        return {
            "title": f"Consulta fiscal — {case_title}",
            "content_md": "\n".join(parts).strip() + "\n",
            "evidences": q.get("evidences", []),
        }
