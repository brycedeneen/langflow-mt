from __future__ import annotations

import asyncio

import typer
from arq.worker import Worker

from langflow.worker_app.settings import WorkerSettings


def worker_cmd(
    queue: list[str] = typer.Option(
        None,
        "--queue",
        "-q",
        help=(
            "Queue to poll (repeat -q to specify multiple — arq processes one per worker; "
            "run multiple processes for multiple queues)."
        ),
    ),
    concurrency: int | None = typer.Option(
        None,
        "--concurrency",
        help="Max in-flight jobs per worker process.",
    ),
):
    """Run a distributed flow-execution worker."""
    settings_cls = WorkerSettings
    if queue:
        settings_cls.queue_name = queue[0]
    if concurrency is not None:
        settings_cls.max_jobs = concurrency
    asyncio.run(Worker(settings_cls=settings_cls).async_run())
