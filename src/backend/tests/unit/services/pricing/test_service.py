from __future__ import annotations

import pytest

from langflow.services.pricing.service import ModelPrice, PricingService


def test_override_beats_litellm():
    service = PricingService(
        overrides={"custom-model": ModelPrice(input_cents_per_1k=5.0, output_cents_per_1k=15.0)}
    )
    # Without loading litellm, overrides are still resolvable
    cents = service.compute_cost_cents("custom-model", input_tokens=1000, output_tokens=1000)
    assert cents == 20  # 5 input + 15 output


def test_unknown_model_returns_zero():
    service = PricingService(overrides={})
    cents = service.compute_cost_cents("totally-made-up/model", input_tokens=1000, output_tokens=1000)
    assert cents == 0


def test_litellm_map_is_consulted_when_no_override(monkeypatch):
    import litellm

    # Shim litellm.model_cost for deterministic test.
    monkeypatch.setattr(
        litellm,
        "model_cost",
        {"claude-opus-4-7": {"input_cost_per_token": 0.000015, "output_cost_per_token": 0.000075}},
        raising=False,
    )
    service = PricingService(overrides={})
    service.reload_from_litellm()
    # 1000 input tokens -> 0.015 USD -> 1.5 cents; rounded
    cents = service.compute_cost_cents("claude-opus-4-7", input_tokens=1000, output_tokens=1000)
    # 1.5 + 7.5 = 9 cents
    assert cents == 9


def test_compute_cost_micros_unknown_model_returns_none():
    service = PricingService(overrides={})
    assert service.compute_cost_micros("totally-made-up/model", input_tokens=1000, output_tokens=1000) is None


def test_compute_cost_micros_zero_tokens_returns_zero():
    service = PricingService(
        overrides={"m": ModelPrice(input_cents_per_1k=5.0, output_cents_per_1k=15.0)}
    )
    assert service.compute_cost_micros("m", input_tokens=0, output_tokens=0) == 0


def test_compute_cost_micros_known_model_full_cents():
    # 5 cents input + 15 cents output = 20 cents = 200_000 micros
    service = PricingService(
        overrides={"m": ModelPrice(input_cents_per_1k=5.0, output_cents_per_1k=15.0)}
    )
    assert service.compute_cost_micros("m", input_tokens=1000, output_tokens=1000) == 200_000


def test_compute_cost_micros_sub_cent_positive():
    # 100 input tokens at 1 cent/1k = 0.1 cents = 1000 micros
    service = PricingService(
        overrides={"m": ModelPrice(input_cents_per_1k=1.0, output_cents_per_1k=0.0)}
    )
    micros = service.compute_cost_micros("m", input_tokens=100, output_tokens=0)
    assert 0 < micros < 10_000
    assert micros == 1000


def test_compute_cost_micros_does_not_affect_compute_cost_cents():
    # Sanity: existing behavior unchanged.
    service = PricingService(overrides={})
    assert service.compute_cost_cents("totally-made-up/model", input_tokens=1, output_tokens=1) == 0
