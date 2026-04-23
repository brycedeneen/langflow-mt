from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from langflow.services.assistant.guards import (
    CrossOrgAccessError,
    guard_assistant_org_scope,
)


def test_same_org_passes() -> None:
    org_id = uuid4()
    guard_assistant_org_scope(
        actor_org_id=org_id,
        target_org_id=org_id,
        target_label="flow",
    )


def test_different_org_raises_cross_org() -> None:
    actor = uuid4()
    other = uuid4()
    with pytest.raises(CrossOrgAccessError) as exc:
        guard_assistant_org_scope(
            actor_org_id=actor,
            target_org_id=other,
            target_label="flow",
        )
    assert "flow" in str(exc.value)


def test_target_without_org_short_circuits() -> None:
    guard_assistant_org_scope(
        actor_org_id=uuid4(),
        target_org_id=None,
        target_label="platform_template",
    )


def test_cross_org_error_is_permission_error_subclass() -> None:
    assert issubclass(CrossOrgAccessError, PermissionError)


def test_error_message_does_not_leak_target_id() -> None:
    actor = uuid4()
    other = UUID("12345678-1234-5678-1234-567812345678")
    with pytest.raises(CrossOrgAccessError) as exc:
        guard_assistant_org_scope(
            actor_org_id=actor,
            target_org_id=other,
            target_label="flow",
        )
    assert str(other) not in str(exc.value)
    assert str(actor) not in str(exc.value)
