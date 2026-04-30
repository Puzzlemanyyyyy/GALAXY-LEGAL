"""Base classes for the workflow engine.

A ``Workflow`` is a fixed sequence of ``WorkflowStep`` objects. Each step
asks the LLM for a strict-JSON output, validates it against a JSON schema,
optionally runs a custom validator, persists the partial output to
``runs.output_jsonb``, and feeds the next step.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from supabase import Client

from services import llm
from services.citation_validator import (
    EvidenceInput,
    parse_evidence_markers,
    validate_citations,
)


# ---------------------------------------------------------------------------
@dataclass
class StepContext:
    """Inputs available to each step's prompt builder."""
    case: dict
    documents: list[dict]      # case_documents rows
    chunks: list[dict]         # selected document_chunks rows
    previous_outputs: dict     # outputs of prior steps keyed by step name


@dataclass
class WorkflowStep:
    name: str
    system_prompt: str
    user_prompt_builder: Callable[[StepContext], str]
    output_schema: dict
    validator: Callable[[dict, StepContext], list[str]] | None = None


@dataclass
class WorkflowResult:
    status: str                      # 'completed' | 'failed' | 'needs_human' (matches DB enum run_status)
    output: dict
    evidences: list[dict]            # ready to insert into evidences table
    draft: dict | None               # ready to insert into drafts table (None if needs_human)
    usage: llm.Usage = field(default_factory=llm.Usage)
    error: str | None = None


# ---------------------------------------------------------------------------
class Workflow:
    workflow_type: str = "base"
    title: str = "Workflow"
    draft_type: str = "initial_analysis"
    steps: list[WorkflowStep] = []

    # Subclasses implement this.
    async def assemble_draft(self, context: StepContext) -> dict:
        """Build final draft markdown + evidences list from accumulated step outputs.

        Returns dict ``{title, content_md, evidences: [EvidenceInput-shaped dicts]}``.
        """
        raise NotImplementedError

    async def run(
        self,
        *,
        run_id: str,
        case: dict,
        documents: list[dict],
        chunks: list[dict],
        admin: Client,
        owner_id: str,
    ) -> WorkflowResult:
        outputs: dict[str, Any] = {}
        total_usage = llm.Usage()
        for step in self.steps:
            ctx = StepContext(case=case, documents=documents, chunks=chunks, previous_outputs=outputs)
            user_text = step.user_prompt_builder(ctx)
            payload, usage = await llm.chat_json(
                system=step.system_prompt,
                user_text=user_text,
                json_schema=step.output_schema,
                schema_name=f"{self.workflow_type}_{step.name}",
            )
            total_usage = total_usage.add(usage)

            if step.validator:
                errors = step.validator(payload, ctx)
                if errors:
                    # One retry with the errors fed back as user message.
                    retry_prompt = (
                        user_text
                        + "\n\nThe previous answer failed validation. Fix these issues and retry:\n- "
                        + "\n- ".join(errors)
                    )
                    payload, usage = await llm.chat_json(
                        system=step.system_prompt,
                        user_text=retry_prompt,
                        json_schema=step.output_schema,
                        schema_name=f"{self.workflow_type}_{step.name}_retry",
                    )
                    total_usage = total_usage.add(usage)
                    errors = step.validator(payload, ctx)
                    if errors:
                        return WorkflowResult(
                            status="needs_human",
                            output={**outputs, step.name: payload, "_validation_errors": errors},
                            evidences=[],
                            draft=None,
                            usage=total_usage,
                            error=f"Step '{step.name}' validation failed: {errors}",
                        )
            outputs[step.name] = payload

            # Persist incremental progress. The live schema lacks a
            # ``current_step`` column, so we tuck it inside output_jsonb.
            admin.table("runs").update({
                "output_jsonb": {**outputs, "_current_step": step.name},
                "tokens_input": total_usage.input_tokens,
                "tokens_output": total_usage.output_tokens,
                "cost_usd": total_usage.cost_usd,
            }).eq("id", run_id).execute()

        # Last step done — assemble draft + verify citations.
        ctx_final = StepContext(case=case, documents=documents, chunks=chunks, previous_outputs=outputs)
        draft = await self.assemble_draft(ctx_final)

        # Validate citations against the documents' extracted text.
        documents_text = {d["id"]: (d.get("texto_extraido") or "") for d in documents}
        # Normalise evidence dict keys: the LLM schemas expose ``id`` for the
        # external evidence identifier (e001, e002...) while our DB/validator
        # expect ``external_id``. Accept both for backwards compatibility.
        def _ext_id(e: dict) -> str:
            return e.get("external_id") or e.get("id") or ""

        evidence_inputs = [
            EvidenceInput(
                external_id=_ext_id(e),
                document_id=e["document_id"],
                quote_excerpt=e["quote_excerpt"],
                page=e.get("page"),
                paragraph=e.get("paragraph"),
            )
            for e in draft.get("evidences", [])
        ]
        validation = validate_citations(evidence_inputs, documents_text)

        # Drop dangling [E:xxx] markers that point to evidence we can't verify.
        ref_ids = parse_evidence_markers(draft.get("content_md", ""))
        known_ids = {e.external_id for e in evidence_inputs}
        unknown_markers = [r for r in ref_ids if r not in known_ids]

        if not validation.valid or unknown_markers:
            err = []
            if validation.errors:
                err.extend([f"{e.external_id}: {e.reason}" for e in validation.errors])
            if unknown_markers:
                err.append(f"Draft references unknown evidence ids: {unknown_markers}")
            return WorkflowResult(
                status="needs_human",
                output={**outputs, "_assembled_draft": draft, "_validation_errors": err},
                evidences=[],
                draft=None,
                usage=total_usage,
                error="Citation validation failed: " + "; ".join(err),
            )

        evidences_payload = [
            {
                "external_id": _ext_id(e),
                "claim_id": e.get("claim_id"),
                "document_id": e["document_id"],
                "page": e.get("page"),
                "paragraph": e.get("paragraph"),
                "quote_excerpt": e["quote_excerpt"],
                "verified": True,
            }
            for e in draft.get("evidences", [])
        ]

        return WorkflowResult(
            status="completed",
            output=outputs,
            evidences=evidences_payload,
            draft={
                "title": draft["title"],
                "content_md": draft["content_md"],
                "draft_type": self.draft_type,
                "citations_valid": True,
            },
            usage=total_usage,
        )
