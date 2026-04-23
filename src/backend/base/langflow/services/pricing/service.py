from __future__ import annotations

import json
import os
from dataclasses import dataclass

from lfx.log.logger import logger

from langflow.services.base import Service


@dataclass(frozen=True)
class ModelPrice:
    input_cents_per_1k: float
    output_cents_per_1k: float


class PricingService(Service):
    name = "pricing_service"

    def __init__(self, overrides: dict[str, ModelPrice] | None = None) -> None:
        self._overrides: dict[str, ModelPrice] = dict(overrides or {})
        self._litellm_prices: dict[str, ModelPrice] = {}
        self._unknown_logged: set[str] = set()

    @classmethod
    def from_settings(cls, settings) -> "PricingService":
        raw = getattr(settings, "pricing_overrides_json", None) or os.environ.get(
            "PRICING_OVERRIDES_JSON", ""
        )
        overrides: dict[str, ModelPrice] = {}
        if raw:
            try:
                data = json.loads(raw)
                for model, v in data.items():
                    overrides[model] = ModelPrice(
                        input_cents_per_1k=float(v["input_cents_per_1k"]),
                        output_cents_per_1k=float(v["output_cents_per_1k"]),
                    )
            except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
                logger.warning("pricing_overrides_json parse failed: %s", exc)
        service = cls(overrides=overrides)
        service.reload_from_litellm()
        return service

    def reload_from_litellm(self) -> None:
        """Pull the current litellm model-cost map into memory."""
        try:
            import litellm
        except ImportError:
            logger.warning("litellm not installed; pricing will only use overrides")
            return

        prices: dict[str, ModelPrice] = {}
        for model, cfg in getattr(litellm, "model_cost", {}).items():
            try:
                in_per_tok = float(cfg.get("input_cost_per_token", 0.0) or 0.0)
                out_per_tok = float(cfg.get("output_cost_per_token", 0.0) or 0.0)
            except (TypeError, ValueError):
                continue
            # $/token -> cents/1k tokens
            prices[model] = ModelPrice(
                input_cents_per_1k=in_per_tok * 1000.0 * 100.0,
                output_cents_per_1k=out_per_tok * 1000.0 * 100.0,
            )
        self._litellm_prices = prices
        logger.info("PricingService refreshed: %d litellm models", len(prices))

    def get_price(self, model: str) -> ModelPrice | None:
        if not model:
            return None
        if model in self._overrides:
            return self._overrides[model]
        if model in self._litellm_prices:
            return self._litellm_prices[model]
        # Try litellm's provider-prefixed matches (e.g., "anthropic/claude-opus-4-7").
        for m, price in self._litellm_prices.items():
            if m == model or m.endswith(f"/{model}") or model.endswith(f"/{m}"):
                return price
        return None

    def compute_cost_cents(self, model: str, *, input_tokens: int, output_tokens: int) -> int:
        price = self.get_price(model)
        if price is None:
            if model not in self._unknown_logged:
                logger.warning("unknown model for pricing: %s", model)
                self._unknown_logged.add(model)
            return 0
        cents = (
            (input_tokens / 1000.0) * price.input_cents_per_1k
            + (output_tokens / 1000.0) * price.output_cents_per_1k
        )
        return int(round(cents))
