from __future__ import annotations

import os

import typer

from lfx.log.logger import configure


def worker_cmd(
    queue: list[str] = typer.Option(
        None,
        "--queue",
        "-q",
        help=(
            "Queue to consume (one of: runs:high, runs:default, runs:low, webhooks). "
            "Taskiq workers consume one queue per process; pass -q at most once. "
            "Run multiple worker processes (one per queue) to drain several queues. "
            "Defaults to runs:default."
        ),
    ),
    concurrency: int | None = typer.Option(
        None,
        "--concurrency",
        help="Max in-flight jobs per worker process (maps to taskiq --workers).",
    ),
    log_level: str = typer.Option(
        "info",
        "--log-level",
        envvar="LANGFLOW_LOG_LEVEL",
        help="Logging level (debug, info, warning, error, critical).",
    ),
):
    """Run a distributed flow-execution worker (Taskiq-backed)."""
    # Configure logging before importing worker internals so startup logs are visible.
    os.environ["LANGFLOW_LOG_LEVEL"] = log_level
    configure(log_level=log_level)

    # Import worker task modules so their @broker.task decorators register
    # tasks against the brokers before the receiver starts consuming.
    from langflow.worker_app import settings as _wire  # noqa: F401  (lifecycle hooks)
    from langflow.worker_app import execute as _e  # noqa: F401
    from langflow.worker_app import webhook as _w  # noqa: F401
    from langflow.worker_app import reaper as _r  # noqa: F401
    from langflow.worker_app import retention as _ret  # noqa: F401
    from langflow.worker_app import audit_cleanup as _a  # noqa: F401
    from langflow.worker_app import pricing_refresh as _p  # noqa: F401

    queues = queue or ["runs:default"]
    if len(queues) > 1:
        raise typer.BadParameter(
            "Taskiq consumes one queue per worker process. "
            "Pass -q at most once and run additional worker processes for other queues.",
        )

    name_to_broker_spec = {
        "runs:high": "langflow.worker_app.brokers:broker_high",
        "runs:default": "langflow.worker_app.brokers:broker_default",
        "runs:low": "langflow.worker_app.brokers:broker_low",
        "webhooks": "langflow.worker_app.brokers:broker_webhooks",
    }

    selected = queues[0]
    if selected not in name_to_broker_spec:
        raise typer.BadParameter(f"unknown queue: {selected}")
    broker_spec = name_to_broker_spec[selected]

    # Build Taskiq worker args. Taskiq's CLI signature is:
    #   taskiq worker <broker_module:variable> [modules...] [flags...]
    # The parent-process imports above only register tasks in *this* process;
    # taskiq's `--workers N` spawns child processes that re-import the broker
    # spec but nothing else, so the @broker.task decorators never fire there
    # and the receiver logs `task "..." is not found`. Pass every task module
    # as a positional arg so each child re-imports them at startup.
    task_modules = [
        "langflow.worker_app.settings",
        "langflow.worker_app.execute",
        "langflow.worker_app.webhook",
        "langflow.worker_app.reaper",
        "langflow.worker_app.retention",
        "langflow.worker_app.audit_cleanup",
        "langflow.worker_app.pricing_refresh",
    ]
    cli_args: list[str] = [broker_spec, *task_modules]
    if concurrency is not None:
        cli_args += ["--workers", str(concurrency)]
    cli_args += ["--log-level", log_level.upper()]

    # taskiq 0.12.x exposes the worker subcommand as `WorkerCMD`. The class
    # extends `TaskiqCMD` whose contract is `exec(args)` — there is no `run()`.
    from taskiq.cli.worker.cmd import WorkerCMD

    raise typer.Exit(code=WorkerCMD().exec(cli_args) or 0)
