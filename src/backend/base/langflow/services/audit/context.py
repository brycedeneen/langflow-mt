from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class AuditContext:
    user_id: UUID | None
    user_email: str
    is_platform_admin: bool
    is_super: bool
    org_id: UUID | None
    request_id: str
    ip: str | None
    user_agent: str | None
    path: str
    method: str
    # Optional per-request hint when the inferred action isn't obvious.
    # Keyed by (target_type, target_id); value is the override action string.
    action_hints: dict[tuple[str, UUID], str] = field(default_factory=dict)


audit_ctx: ContextVar[AuditContext | None] = ContextVar("audit_ctx", default=None)


def set_action_hint(target_type: str, target_id: UUID, action: str) -> None:
    """Endpoint handlers call this when the action isn't inferable from dirty fields.

    No-op if audit context isn't set (e.g., during a worker/system write).
    """
    ctx = audit_ctx.get()
    if ctx is None:
        return
    ctx.action_hints[(target_type, target_id)] = action
