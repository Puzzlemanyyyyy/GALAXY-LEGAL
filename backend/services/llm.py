"""Unified LLM client.

Strategy:
- Embeddings (text-embedding-3-small, 1536 dim): always via the OpenAI SDK
  using ``OPENAI_API_KEY``. Emergent's universal key proxy does not expose
  the embeddings endpoint, so users must provide their own OpenAI key for
  vector indexing.

- Chat completions with strict JSON output: prefer ``emergentintegrations``
  (universal Emergent LLM Key) when ``OPENAI_API_KEY`` is empty; otherwise
  use the OpenAI SDK directly so the same code runs on Railway.

The functions are async and return tuples ``(payload, usage)`` where
``usage`` has ``input_tokens``, ``output_tokens``, ``cost_usd`` so callers
can persist cost on the run row.
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from dataclasses import dataclass
from typing import Any, Iterable

from config import settings


# ---------------------------------------------------------------------------
# Pricing (rough, used only for monthly budget guardrails)
# ---------------------------------------------------------------------------
PRICING_PER_1K = {
    "gpt-4o":                   {"in": 0.0025, "out": 0.010},
    "gpt-4o-mini":              {"in": 0.00015, "out": 0.0006},
    "text-embedding-3-small":   {"in": 0.00002, "out": 0.0},
}


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

    def add(self, other: "Usage") -> "Usage":
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cost_usd=round(self.cost_usd + other.cost_usd, 6),
        )


def _price(model: str, in_tok: int, out_tok: int) -> float:
    p = PRICING_PER_1K.get(model, PRICING_PER_1K["gpt-4o"])
    return round(in_tok / 1000 * p["in"] + out_tok / 1000 * p["out"], 6)


# ---------------------------------------------------------------------------
# Embeddings (OpenAI direct only)
# ---------------------------------------------------------------------------
async def embed_batch(texts: list[str], model: str | None = None) -> tuple[list[list[float]], Usage]:
    """Embed a batch of texts. Splits into chunks of <= 100."""
    model = model or settings.OPENAI_EMBEDDING_MODEL
    if not settings.OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY is required for embeddings. "
            "Add it to backend/.env (Emergent universal key does not expose embeddings)."
        )
    from openai import OpenAI  # local import keeps import-time cheap
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    vectors: list[list[float]] = []
    total_in = 0
    for i in range(0, len(texts), 100):
        batch = texts[i:i + 100]
        # SDK is sync; offload to thread to keep FastAPI async-friendly.
        resp = await asyncio.to_thread(client.embeddings.create, model=model, input=batch)
        vectors.extend([d.embedding for d in resp.data])
        total_in += getattr(resp, "usage", None).total_tokens if getattr(resp, "usage", None) else 0
    cost = _price(model, total_in, 0)
    return vectors, Usage(input_tokens=total_in, output_tokens=0, cost_usd=cost)


# ---------------------------------------------------------------------------
# Chat completion with strict JSON output
# ---------------------------------------------------------------------------
async def chat_json(
    *,
    system: str,
    user_text: str,
    json_schema: dict[str, Any],
    schema_name: str = "Output",
    model: str | None = None,
    max_retries: int = 2,
) -> tuple[dict[str, Any], Usage]:
    """Call an LLM and parse a JSON object that matches ``json_schema``.

    Tries the OpenAI SDK first when the user provided their own key, and
    otherwise routes through Emergent's universal key.
    """
    model = model or settings.OPENAI_MODEL
    last_err: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            if settings.OPENAI_API_KEY:
                payload, usage = await _chat_json_openai(system, user_text, json_schema, schema_name, model)
            else:
                payload, usage = await _chat_json_emergent(system, user_text, json_schema, model)
            return payload, usage
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            await asyncio.sleep(0.6 * (2 ** attempt))
    raise RuntimeError(f"chat_json failed after {max_retries + 1} attempts: {last_err}")


async def _chat_json_openai(system: str, user_text: str, schema: dict, schema_name: str, model: str) -> tuple[dict, Usage]:
    from openai import OpenAI
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    resp = await asyncio.to_thread(
        client.chat.completions.create,
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_text},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": schema_name, "schema": schema, "strict": True},
        },
        temperature=0.2,
    )
    content = resp.choices[0].message.content or "{}"
    payload = json.loads(content)
    u = resp.usage
    in_tok = getattr(u, "prompt_tokens", 0) if u else 0
    out_tok = getattr(u, "completion_tokens", 0) if u else 0
    return payload, Usage(input_tokens=in_tok, output_tokens=out_tok, cost_usd=_price(model, in_tok, out_tok))


async def _chat_json_emergent(system: str, user_text: str, schema: dict, model: str) -> tuple[dict, Usage]:
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise RuntimeError("Neither OPENAI_API_KEY nor EMERGENT_LLM_KEY is configured.")
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    chat = LlmChat(
        api_key=api_key,
        session_id=f"galaxy-legal-{uuid.uuid4()}",
        system_message=(
            system
            + "\n\nReturn ONLY a single JSON object that conforms to this JSON schema:\n"
            + json.dumps(schema, ensure_ascii=False)
            + "\nDo not include markdown fences, comments, or any prose."
        ),
    )
    chat.with_model("openai", model)
    raw = await chat.send_message(UserMessage(text=user_text))
    text = (raw or "").strip()
    if text.startswith("```"):
        # Strip optional ```json fences from older LiteLLM responses.
        text = text.split("```", 2)[-1]
        if text.startswith("json\n"):
            text = text[5:]
        text = text.strip("` \n")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Model did not return valid JSON: {text[:300]}") from exc
    # emergentintegrations doesn't surface token counts; estimate from text.
    in_tok = max(1, len((system + user_text).split()))
    out_tok = max(1, len(text.split()))
    return payload, Usage(input_tokens=in_tok, output_tokens=out_tok, cost_usd=_price(model, in_tok, out_tok))


# ---------------------------------------------------------------------------
# Helper: cheap budget check
# ---------------------------------------------------------------------------
def is_over_budget(spent_usd: float) -> bool:
    return spent_usd >= settings.OPENAI_MONTHLY_BUDGET_USD
