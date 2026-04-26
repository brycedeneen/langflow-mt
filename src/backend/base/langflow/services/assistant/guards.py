"""Cross-org access guards for assistant-callable tools.

This module is defense-in-depth. The primary enforcement for cross-org access
is an explicit ``organization_id`` filter on the DB query inside every tool.
``guard_assistant_org_scope`` is the belt-and-suspenders check: call it at the
tool entry with the resolved target's ``organization_id`` before returning
data to the caller. It catches regressions where a future query forgets the
filter.

Callers MUST translate :class:`CrossOrgAccessError` into HTTP 404 at the
router boundary (never 403) to avoid leaking existence of the target.
"""

from __future__ import annotations

from uuid import UUID


class CrossOrgAccessError(PermissionError):
    """An assistant tool tried to read data outside the actor's active org."""


def guard_assistant_org_scope(
    *,
    actor_org_id: UUID,
    target_org_id: UUID | None,
    target_label: str,
) -> None:
    """Raise if ``target_org_id`` belongs to a different org than ``actor_org_id``.

    A ``target_org_id`` of ``None`` short-circuits — platform-global resources
    (e.g. shared templates) are always allowed. This is the intentional
    escape hatch; keep its use limited to explicitly platform-scoped data.

    The error message intentionally omits both UUIDs so audit logs / error
    responses cannot be mined for target existence.
    """
    if target_org_id is None:
        return
    if target_org_id != actor_org_id:
        msg = f"cross-org access to {target_label} is not permitted"
        raise CrossOrgAccessError(msg)
