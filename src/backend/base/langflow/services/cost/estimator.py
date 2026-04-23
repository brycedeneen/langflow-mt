from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from langflow.services.pricing.service import PricingService


Confidence = Literal["rough", "low", "none"]


@dataclass(frozen=True)
class EstimatorConfig:
    llm_input: int
    llm_output: int
    embed_input: int
    agent_multiplier: int


@dataclass(frozen=True)
class EstimateResult:
    expected_cost_cents: int
    low_cost_cents: int
    high_cost_cents: int
    confidence: Confidence
    per_component: list[dict[str, Any]]


def _classify(node: dict) -> Literal["llm", "embedding", "agent", "other"]:
    data = node.get("data") or {}
    node_type = str(data.get("type") or "")
    if "Agent" in node_type:
        return "agent"
    if "Embedding" in node_type or node_type.endswith("Embeddings"):
        return "embedding"
    # Prefer the structured `trace_type` on the inner node template when present.
    inner = (data.get("node") or {}).get("trace_type") if isinstance(data.get("node"), dict) else None
    if inner == "llm":
        return "llm"
    if inner == "embedding":
        return "embedding"
    if node_type in {"LanguageModel", "LLM"}:
        return "llm"
    return "other"


def _get_model_name(node: dict) -> str:
    template = ((node.get("data") or {}).get("node") or {}).get("template") or {}
    for k in ("model_name", "model"):
        if k in template:
            v = template[k]
            if isinstance(v, dict):
                val = v.get("value")
                if isinstance(val, list) and val and isinstance(val[0], dict):
                    return str(val[0].get("provider") or val[0].get("model") or "")
                return str(val or "")
            return str(v or "")
    return ""


def estimate_flow_cost(
    flow_data: dict,
    *,
    pricing: PricingService,
    config: EstimatorConfig,
) -> EstimateResult:
    nodes = (flow_data or {}).get("nodes") or []
    per_component: list[dict[str, Any]] = []
    expected = 0
    any_unknown = False

    for node in nodes:
        kind = _classify(node)
        if kind == "other":
            continue

        model = _get_model_name(node)
        in_tokens = config.llm_input if kind in {"llm", "agent"} else config.embed_input
        out_tokens = config.llm_output if kind in {"llm", "agent"} else 0
        calls = config.agent_multiplier if kind == "agent" else 1

        price = pricing.get_price(model) if model else None
        unknown = price is None
        if unknown:
            any_unknown = True
            cents = 0
        else:
            per_call = pricing.compute_cost_cents(model, input_tokens=in_tokens, output_tokens=out_tokens)
            cents = per_call * calls

        expected += cents
        per_component.append({
            "node_id": node.get("id"),
            "kind": kind,
            "model": model,
            "estimated_input_tokens": in_tokens * calls,
            "estimated_output_tokens": out_tokens * calls,
            "cost_cents": cents,
            "unknown": unknown,
        })

    # Confidence: none if any unknown; rough for fully-known defaults.
    confidence: Confidence = "none" if any_unknown else "rough"
    # Low/high: +/-50% of expected
    low = int(round(expected * 0.5))
    high = int(round(expected * 1.75))
    return EstimateResult(
        expected_cost_cents=expected,
        low_cost_cents=low,
        high_cost_cents=high,
        confidence=confidence,
        per_component=per_component,
    )
