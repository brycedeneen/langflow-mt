"""Local conftest for alembic integration tests.

The parent ``tests/integration/conftest.py`` defines an autouse ``_start_app``
fixture that spins up the full Langflow client. Migration round-trip tests
operate on a temporary SQLite file with no app context, so we override that
fixture here to be a no-op.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _start_app():  # type: ignore[override]
    """No-op replacement so migration tests don't require the Langflow app."""
    yield
