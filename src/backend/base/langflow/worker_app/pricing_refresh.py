from __future__ import annotations

from lfx.log.logger import logger


async def refresh_pricing_cache(ctx) -> None:
    """Daily: reload litellm's model_cost map into PricingService."""
    try:
        from langflow.services.deps import get_pricing_service
        service = get_pricing_service()
        service.reload_from_litellm()
    except Exception as exc:  # noqa: BLE001
        logger.exception("refresh_pricing_cache failed: %s", exc)
