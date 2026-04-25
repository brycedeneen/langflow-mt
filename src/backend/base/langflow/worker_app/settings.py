"""DEPRECATED — module retained as an import shim for the lifecycle wire-up.

The arq-era `WorkerSettings` class is replaced by:
- `langflow.worker_app.brokers` (broker registry)
- `langflow.worker_app.deps` (TaskiqDepends providers)
- `langflow.worker_app.lifecycle` (broker startup/shutdown)

Importing this module ensures lifecycle handlers are registered.
"""
from langflow.worker_app import lifecycle  # noqa: F401  (registration side-effect)
