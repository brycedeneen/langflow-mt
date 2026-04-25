"""TaskiqDepends providers for worker tasks.

These are resolved by the Taskiq DI system at task-call time, replacing
the arq `ctx` dict.
"""
from __future__ import annotations

from typing import Any

from redis.asyncio import Redis


# Module-level state populated at worker startup. The Taskiq broker
# `on_event(WORKER_STARTUP)` hook (in lifecycle.py) initialises Langflow
# services and stores references here.
_state: dict[str, Any] = {}


def _set(key: str, value: Any) -> None:
    _state[key] = value


def _clear() -> None:
    _state.clear()


def get_db_sessionmaker():
    return _state["sessionmaker"]


def get_storage():
    return _state["storage"]


def get_settings():
    return _state["settings"]


def get_redis() -> Redis:
    return _state["redis"]


def get_graph_runner():
    """Injection hook for tests; default None means use the in-process runner."""
    return _state.get("graph_runner")
