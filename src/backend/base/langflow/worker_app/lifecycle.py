"""Worker process startup/shutdown hooks for every broker."""
from __future__ import annotations

import os
import socket

from redis.asyncio import Redis
from taskiq import TaskiqEvents

from lfx.log.logger import logger

from langflow.worker_app import deps as worker_deps
from langflow.worker_app.brokers import ALL_BROKERS


WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"


async def _on_startup(state: object) -> None:
    from langflow.services.deps import get_db_service, get_settings_service, get_storage_service
    from langflow.services.utils import initialize_services

    await initialize_services()

    settings_service = get_settings_service()
    db_service = get_db_service()
    settings = settings_service.settings

    worker_deps._set("settings", settings)
    worker_deps._set("sessionmaker", db_service.async_session_maker)
    worker_deps._set("storage", get_storage_service())
    worker_deps._set("redis", Redis.from_url(settings.redis_url))

    logger.info(f"Langflow worker started: worker_id={WORKER_ID}")


async def _on_shutdown(state: object) -> None:
    redis = worker_deps._state.get("redis")
    if redis is not None:
        await redis.aclose()
    worker_deps._clear()
    logger.info(f"Langflow worker shutting down: worker_id={WORKER_ID}")


def register_lifecycle() -> None:
    """Wire startup/shutdown to every broker so the active worker fires them."""
    for broker in ALL_BROKERS:
        broker.add_event_handler(TaskiqEvents.WORKER_STARTUP, _on_startup)
        broker.add_event_handler(TaskiqEvents.WORKER_SHUTDOWN, _on_shutdown)


register_lifecycle()
