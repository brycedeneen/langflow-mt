from __future__ import annotations

import os

import typer
from arq.worker import run_worker

from lfx.log.logger import configure


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
    log_level: str = typer.Option(
        "info",
        "--log-level",
        envvar="LANGFLOW_LOG_LEVEL",
        help="Logging level (debug, info, warning, error, critical).",
    ),
):
    """Run a distributed flow-execution worker."""
    # Configure logging before importing worker internals so startup logs are visible.
    os.environ["LANGFLOW_LOG_LEVEL"] = log_level
    configure(log_level=log_level)

    from langflow.worker_app.settings import WorkerSettings

    settings_cls = WorkerSettings
    if queue:
        settings_cls.queue_name = queue[0]
    if concurrency is not None:
        settings_cls.max_jobs = concurrency
    run_worker(settings_cls)
