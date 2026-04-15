from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import UUID

from langflow.services.database.models.flow_run_log.model import FlowRunLog, LogLevel


class RunLogSink:
    def __init__(
        self,
        *,
        session_factory: Callable,
        run_id: UUID,
        flush_interval: float = 0.5,
        max_buffer: int = 100,
        max_total_bytes: int = 10 * 1024 * 1024,
    ):
        self._session_factory = session_factory
        self._run_id = run_id
        self._flush_interval = flush_interval
        self._max_buffer = max_buffer
        self._max_total_bytes = max_total_bytes
        self._buffer: list[FlowRunLog] = []
        self._bytes_written = 0
        self._truncated = False
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        try:
            while not self._stop.is_set():
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=self._flush_interval)
                except asyncio.TimeoutError:
                    pass
                await self._flush()
        finally:
            await self._flush()

    def emit(self, *, level: str, message: str, node_id: str | None, extra: dict[str, Any] | None) -> None:
        if self._bytes_written >= self._max_total_bytes:
            if not self._truncated:
                self._truncated = True
                self._buffer.append(FlowRunLog(
                    run_id=self._run_id, ts=datetime.now(timezone.utc),
                    level=LogLevel.WARN, node_id=None,
                    message="log capture truncated: max size reached", extra=None,
                ))
            return
        size = len(message.encode("utf-8"))
        self._bytes_written += size
        self._buffer.append(FlowRunLog(
            run_id=self._run_id, ts=datetime.now(timezone.utc),
            level=LogLevel(level), node_id=node_id, message=message, extra=extra,
        ))

    async def _flush(self) -> None:
        async with self._lock:
            if not self._buffer:
                return
            batch, self._buffer = self._buffer, []
        async with self._session_factory() as session:
            session.add_all(batch)
            await session.commit()

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            await self._task
