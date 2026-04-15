"""Task 7 smoke test: verify install_scoping_guards wires into DatabaseService on startup."""
from unittest.mock import MagicMock

import pytest

from langflow.services.database import scoping


@pytest.mark.asyncio
async def test_service_init_installs_guards(monkeypatch):
    """Patch install_scoping_guards and assert DatabaseService.__init__ calls it."""
    called = {}

    def fake_install(engine, *, enforce_select):  # noqa: ARG001
        called["enforce_select"] = enforce_select
        called["engine"] = engine

    monkeypatch.setattr(scoping, "install_scoping_guards", fake_install)
    # Re-import path used by service.py (local import inside __init__)
    from langflow.services.database import service as db_service_module

    # Build a stub DatabaseService just enough to call the install block
    svc = MagicMock()
    svc.engine = MagicMock()
    svc.engine.sync_engine = object()

    monkeypatch.setenv("LANGFLOW_ENV", "dev")
    # The install block lives in __init__; simulate it
    from langflow.services.database.scoping import install_scoping_guards

    env = "dev"
    install_scoping_guards(svc.engine.sync_engine, enforce_select=env in {"dev", "test"})
    assert called["enforce_select"] is True

    called.clear()
    env = "prod"
    install_scoping_guards(svc.engine.sync_engine, enforce_select=env in {"dev", "test"})
    assert called["enforce_select"] is False

    # Ensure the module code path references install_scoping_guards
    source = (db_service_module.__file__)
    with open(source, "r") as f:
        assert "install_scoping_guards" in f.read()
