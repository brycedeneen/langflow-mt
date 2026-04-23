from __future__ import annotations

import pytest

from langflow.services.cost.estimator import EstimatorConfig, estimate_flow_cost
from langflow.services.pricing.service import ModelPrice, PricingService


def _pricing_for(model: str, in_cents: float, out_cents: float) -> PricingService:
    return PricingService(
        overrides={model: ModelPrice(input_cents_per_1k=in_cents, output_cents_per_1k=out_cents)}
    )


def _llm_node(model: str) -> dict:
    return {
        "id": "n1",
        "data": {
            "type": "LanguageModel",
            "node": {"template": {"model_name": {"value": model}}},
        },
    }


def test_pure_llm_flow_rough_confidence():
    flow_data = {"nodes": [_llm_node("gpt-4o")]}
    pricing = _pricing_for("gpt-4o", in_cents=0.5, out_cents=1.5)
    config = EstimatorConfig(llm_input=800, llm_output=400, embed_input=512, agent_multiplier=4)

    result = estimate_flow_cost(flow_data, pricing=pricing, config=config)

    assert result.confidence == "rough"
    # 800/1000 * 0.5 + 400/1000 * 1.5 = 0.4 + 0.6 = 1 cent
    assert result.expected_cost_cents == 1
    assert result.per_component[0]["unknown"] is False


def test_unknown_model_forces_none_confidence():
    flow_data = {"nodes": [_llm_node("unknown-model")]}
    pricing = PricingService(overrides={})
    config = EstimatorConfig(llm_input=800, llm_output=400, embed_input=512, agent_multiplier=4)

    result = estimate_flow_cost(flow_data, pricing=pricing, config=config)
    assert result.confidence == "none"
    assert any(c["unknown"] for c in result.per_component)


def test_agent_node_multiplies_cost():
    flow_data = {
        "nodes": [
            {"id": "a", "data": {"type": "Agent", "node": {"template": {"model_name": {"value": "gpt-4o"}}}}}
        ]
    }
    pricing = _pricing_for("gpt-4o", in_cents=0.5, out_cents=1.5)
    config = EstimatorConfig(llm_input=800, llm_output=400, embed_input=512, agent_multiplier=4)

    result = estimate_flow_cost(flow_data, pricing=pricing, config=config)
    # Single call cost was 1 cent; agent multiplier 4 → 4 cents
    assert result.expected_cost_cents == 4
