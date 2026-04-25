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
    # Single call cost was 1 cent; agent multiplier 4 -> 4 cents
    assert result.expected_cost_cents == 4


def test_model_input_list_of_dicts_resolves_to_name_not_provider():
    """Regression: ModelInput stores [{"name": <id>, "provider": <label>, ...}].

    The estimator must resolve the ``name`` (litellm pricing key), not the
    ``provider`` label -- otherwise pricing lookup silently fails and the
    pre-run flow-cost widget renders ``?``.
    """
    flow_data = {
        "nodes": [
            {
                "id": "n1",
                "data": {
                    "type": "Agent",
                    "node": {
                        "template": {
                            "model": {
                                "value": [
                                    {
                                        "name": "claude-haiku-4-5-20251001",
                                        "icon": "Anthropic",
                                        "provider": "Anthropic",
                                        "metadata": {"context_length": 128000},
                                    }
                                ]
                            }
                        }
                    },
                },
            }
        ]
    }
    pricing = _pricing_for("claude-haiku-4-5-20251001", in_cents=0.5, out_cents=1.5)
    config = EstimatorConfig(llm_input=800, llm_output=400, embed_input=512, agent_multiplier=4)

    result = estimate_flow_cost(flow_data, pricing=pricing, config=config)
    # The model id was resolved -> pricing lookup succeeded -> known cost.
    assert result.confidence == "rough"
    assert result.per_component[0]["unknown"] is False
    assert result.per_component[0]["model"] == "claude-haiku-4-5-20251001"


def test_model_input_with_only_provider_returns_no_pricing():
    """Provider label alone is NOT a litellm key; estimator must not pretend
    it knows the model when only ``provider`` is present.
    """
    flow_data = {
        "nodes": [
            {
                "id": "n1",
                "data": {
                    "type": "LanguageModel",
                    "node": {"template": {"model": {"value": [{"provider": "Anthropic"}]}}},
                },
            }
        ]
    }
    pricing = PricingService(overrides={})
    config = EstimatorConfig(llm_input=800, llm_output=400, embed_input=512, agent_multiplier=4)

    result = estimate_flow_cost(flow_data, pricing=pricing, config=config)
    assert result.confidence == "none"
    assert result.per_component[0]["unknown"] is True
    # Crucially, the provider label did NOT leak through as the model id.
    assert result.per_component[0]["model"] != "Anthropic"
