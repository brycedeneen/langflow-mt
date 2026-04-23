from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from langflow.services.audit.context import audit_ctx
from langflow.services.audit.middleware import AuditContextMiddleware


@pytest.mark.asyncio
async def test_middleware_sets_and_clears_context():
    app = FastAPI()
    app.add_middleware(AuditContextMiddleware)

    captured: list = []

    @app.get("/probe")
    async def probe() -> dict:
        ctx = audit_ctx.get()
        captured.append(ctx)
        return {"ok": True}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/probe",
            headers={"User-Agent": "pytest/1", "X-Request-ID": "rid-123"},
        )
    assert resp.status_code == 200

    # Context was set inside the handler
    assert len(captured) == 1
    ctx = captured[0]
    assert ctx is not None
    assert ctx.method == "GET"
    assert ctx.path == "/probe"
    assert ctx.user_agent == "pytest/1"
    assert ctx.request_id == "rid-123"

    # And is cleared afterwards
    assert audit_ctx.get() is None
