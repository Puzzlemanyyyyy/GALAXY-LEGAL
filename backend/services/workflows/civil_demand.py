"""Civil demand workflow — produces a Spanish civil demand (``demanda civil``).

Sections: encabezamiento, hechos numerados (cada hecho con ≥1 evidence_id),
fundamentos de derecho, petitum, otrosíes. Every factual statement must be
anchored to an evidence_id pointing at a verbatim chunk excerpt.
"""
from __future__ import annotations

import json

from .base import StepContext, Workflow, WorkflowStep
from .initial_analysis import _serialize_chunks  # reuse


_FACTS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "encabezamiento": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "juzgado": {"type": "string"},
                "parte_actora": {"type": "string"},
                "parte_demandada": {"type": "string"},
                "tipo_procedimiento": {"type": "string"},
                "cuantia_eur": {"type": ["number", "null"]},
            },
            "required": ["juzgado", "parte_actora", "parte_demandada", "tipo_procedimiento", "cuantia_eur"],
        },
        "hechos": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "numero": {"type": "integer"},
                    "text": {"type": "string", "minLength": 20},
                    "evidence_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                },
                "required": ["numero", "text", "evidence_ids"],
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
    "required": ["encabezamiento", "hechos", "evidences"],
}


_LEGAL_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "fundamentos": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "numero": {"type": "integer"},
                    "titulo": {"type": "string"},
                    "desarrollo": {"type": "string", "minLength": 30},
                    "normas_citadas": {"type": "array", "items": {"type": "string"}},
                    "evidence_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["numero", "titulo", "desarrollo", "normas_citadas", "evidence_ids"],
            },
        },
        "petitum": {"type": "array", "items": {"type": "string"}, "minItems": 1},
        "otrosies": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["fundamentos", "petitum", "otrosies"],
}


def _facts_prompt(ctx: StepContext) -> str:
    chunks_blob = _serialize_chunks(ctx.chunks)
    docs = "\n".join(f"- {d['id']}: {d.get('filename')}" for d in ctx.documents)
    return (
        "Eres abogado procesalista. Redacta el apartado de HECHOS de una "
        "demanda civil española a partir ÚNICAMENTE de los fragmentos aportados.\n\n"
        f"Documentos del expediente:\n{docs}\n\n"
        f"Caso: {ctx.case.get('title')}\n"
        f"Jurisdicción: {ctx.case.get('jurisdiccion') or '—'}\n"
        f"Materia: {ctx.case.get('materia') or '—'}\n\n"
        "Reglas:\n"
        "- Cada hecho DEBE tener al menos un evidence_id; los evidences referencian "
        "fragmentos literales de los documentos.\n"
        "- `evidences[i].quote_excerpt` es un extracto VERBATIM (palabra por palabra) "
        "presente en alguno de los chunks.\n"
        "- Identificadores cortos: evidences e001..eNNN.\n"
        "- Si no hay datos para `cuantia_eur`, devuelve null.\n\n"
        f"Fragmentos disponibles:\n{chunks_blob}"
    )


def _legal_prompt(ctx: StepContext) -> str:
    facts = ctx.previous_outputs.get("extract_facts", {})
    return (
        "A partir del apartado de HECHOS ya redactado, construye los FUNDAMENTOS "
        "DE DERECHO, el PETITUM y los OTROSÍES. Cita normativa aplicable (Código "
        "Civil, LEC, legislación sectorial) sin inventar referencias.\n\n"
        "Reusa los evidence_ids ya existentes; no crees evidences nuevas.\n\n"
        "Hechos (JSON):\n"
        + json.dumps(facts, ensure_ascii=False)
    )


def _facts_validator(payload: dict, ctx: StepContext) -> list[str]:
    errs: list[str] = []
    valid_doc_ids = {d["id"] for d in ctx.documents}
    ev_ids = {e.get("id") for e in payload.get("evidences", [])}
    for ev in payload.get("evidences", []):
        if ev.get("document_id") not in valid_doc_ids:
            errs.append(f"evidence {ev.get('id')} references unknown document_id")
    for h in payload.get("hechos", []):
        if not h.get("evidence_ids"):
            errs.append(f"hecho {h.get('numero')} has no evidence_ids")
        for eid in h.get("evidence_ids", []):
            if eid not in ev_ids:
                errs.append(f"hecho {h.get('numero')} references unknown evidence_id {eid}")
    return errs


class CivilDemandWorkflow(Workflow):
    workflow_type = "civil_demand"
    title = "Demanda civil"
    draft_type = "civil_demand"
    steps = [
        WorkflowStep(
            name="extract_facts",
            system_prompt=(
                "Eres abogado procesalista español. Solo afirmas hechos que constan "
                "literalmente en los documentos aportados."
            ),
            user_prompt_builder=_facts_prompt,
            output_schema=_FACTS_SCHEMA,
            validator=_facts_validator,
        ),
        WorkflowStep(
            name="build_legal",
            system_prompt=(
                "Eres abogado procesalista. Citas solo normativa existente; reutilizas "
                "los evidence_ids ya creados."
            ),
            user_prompt_builder=_legal_prompt,
            output_schema=_LEGAL_SCHEMA,
        ),
    ]

    async def assemble_draft(self, context: StepContext) -> dict:
        facts = context.previous_outputs.get("extract_facts", {})
        legal = context.previous_outputs.get("build_legal", {})

        enc = facts.get("encabezamiento", {})
        case_title = context.case.get("title") or "Expediente"
        parts: list[str] = []
        parts.append(f"# Demanda civil — {case_title}\n")
        parts.append("## Encabezamiento\n")
        parts.append(f"- **Juzgado**: {enc.get('juzgado','—')}")
        parts.append(f"- **Parte actora**: {enc.get('parte_actora','—')}")
        parts.append(f"- **Parte demandada**: {enc.get('parte_demandada','—')}")
        parts.append(f"- **Procedimiento**: {enc.get('tipo_procedimiento','—')}")
        cuantia = enc.get("cuantia_eur")
        if cuantia is not None:
            parts.append(f"- **Cuantía**: {cuantia:.2f} EUR")
        parts.append("")
        parts.append("## Hechos\n")
        for h in facts.get("hechos", []):
            refs = "".join(f"[E:{eid}]" for eid in h.get("evidence_ids", []))
            parts.append(f"**{h.get('numero')}.** {h.get('text')} {refs}")
            parts.append("")
        parts.append("## Fundamentos de derecho\n")
        for f in legal.get("fundamentos", []):
            refs = "".join(f"[E:{eid}]" for eid in f.get("evidence_ids", []))
            normas = ", ".join(f.get("normas_citadas", []))
            parts.append(f"**{f.get('numero')}. {f.get('titulo')}** — {f.get('desarrollo')} {refs}")
            if normas:
                parts.append(f"_Normas: {normas}_")
            parts.append("")
        parts.append("## Petitum\n")
        for p in legal.get("petitum", []):
            parts.append(f"- {p}")
        parts.append("")
        otrosies = legal.get("otrosies", [])
        if otrosies:
            parts.append("## Otrosíes\n")
            for o in otrosies:
                parts.append(f"- {o}")
            parts.append("")

        return {
            "title": f"Demanda civil — {case_title}",
            "content_md": "\n".join(parts).strip() + "\n",
            "evidences": facts.get("evidences", []),
        }
