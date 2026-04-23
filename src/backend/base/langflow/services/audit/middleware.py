from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from langflow.services.audit.context import AuditContext, audit_ctx

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send


class AuditContextMiddleware:
    """Populates `audit_ctx` for every HTTP request.

    User/org fields may be populated at request start only from headers/scope. The
    authenticated user is filled in later by a downstream dependency that calls
    `audit_ctx.get()` and replaces fields using `dataclasses.replace()` — but v1
    captures what we can before auth runs; the `after_commit` listener prefers a
    populated user when available.
    """

    def __init__(self, app: "ASGIApp") -> None:
        self.app = app

    async def __call__(self, scope: "Scope", receive: "Receive", send: "Send") -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {k.decode("latin-1"): v.decode("latin-1") for k, v in scope.get("headers", [])}
        request_id = headers.get("x-request-id") or str(uuid.uuid4())
        client = scope.get("client")
        ip = client[0] if client else None

        ctx = AuditContext(
            user_id=None,
            user_email="",
            is_platform_admin=False,
            is_super=False,
            org_id=None,
            request_id=request_id,
            ip=ip,
            user_agent=headers.get("user-agent"),
            path=scope.get("path", ""),
            method=scope.get("method", ""),
        )

        # Echo the request id as a response header for debug correlation.
        async def _send_with_header(message):
            if message["type"] == "http.response.start":
                hdrs = list(message.get("headers", []))
                hdrs.append((b"x-request-id", request_id.encode("latin-1")))
                message = {**message, "headers": hdrs}
            await send(message)

        token = audit_ctx.set(ctx)
        try:
            await self.app(scope, receive, _send_with_header)
        finally:
            audit_ctx.reset(token)
