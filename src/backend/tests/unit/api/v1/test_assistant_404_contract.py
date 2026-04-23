from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from langflow.services.assistant.guards import CrossOrgAccessError


def _make_app_with_router(router) -> FastAPI:
    app = FastAPI()

    @app.exception_handler(CrossOrgAccessError)
    async def _handler(_request, _exc):
        return JSONResponse(status_code=404, content={"detail": "not found"})

    app.include_router(router)
    return app


@pytest.mark.parametrize(
    "module_name",
    [
        "langflow.api.v1.assistant",
        "langflow.api.v1.component_assist",
    ],
)
def test_cross_org_error_returns_404(module_name: str) -> None:
    from importlib import import_module

    module = import_module(module_name)
    router = module.router
    original_routes = list(router.routes)

    try:
        # Inject a diagnostic route that always raises the guard error.
        @router.get("/__probe_cross_org_404__", include_in_schema=False)
        async def _probe() -> None:
            raise CrossOrgAccessError("probe")

        app = _make_app_with_router(router)
        client = TestClient(app)
        # The router has a prefix (e.g. /assistant or /assistant/components), so
        # the probe route lives under that prefix.
        probe_path = (router.prefix or "") + "/__probe_cross_org_404__"
        resp = client.get(probe_path)
        assert resp.status_code == 404, resp.text
        # Do not leak the raised message.
        assert "probe" not in resp.text
        assert resp.json() == {"detail": "not found"}
    finally:
        router.routes[:] = original_routes
