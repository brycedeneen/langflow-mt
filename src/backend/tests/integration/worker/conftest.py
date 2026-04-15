"""Conftest for worker integration tests.

These tests don't use the full Langflow app — they test worker functions
in isolation with a lightweight DB + live Redis. Override the autouse
_start_app fixture from the parent integration conftest so no HTTP client
is started.
"""
import pytest


@pytest.fixture(autouse=True)
def _start_app():
    """Override the parent integration conftest's autouse fixture.

    Worker tests don't need the full ASGI app running.
    """
    pass
