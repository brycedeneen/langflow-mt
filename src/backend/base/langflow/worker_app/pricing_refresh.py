from __future__ import annotations

from lfx.log.logger import logger

from langflow.worker_app.brokers import broker_default


@broker_default.task(
    task_name="refresh_pricing_cache",
    schedule=[{"cron": "0 0 * * *"}],  # daily at 00:00 UTC
)
async def refresh_pricing_cache() -> None:
    """Daily: reload litellm's model_cost map into PricingService."""
    try:
        from langflow.services.deps import get_pricing_service
        service = get_pricing_service()
        service.reload_from_litellm()
    except Exception as exc:  # noqa: BLE001
        logger.exception("refresh_pricing_cache failed: %s", exc)
