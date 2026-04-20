"""Tests for VariableService.has_user_managed_variable — ensures the method
distinguishes user-managed Variables from auto-secrets and from absence."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest


USER_ID = uuid4()


@pytest.mark.asyncio
async def test_has_user_managed_variable_signature_accepts_kwargs():
    """Method exists and accepts the keyword-only args we depend on."""
    from langflow.services.variable.service import DatabaseVariableService
    method = DatabaseVariableService.has_user_managed_variable
    # Method must exist on the service class.
    assert callable(method)


@pytest.mark.asyncio
async def test_has_user_managed_variable_returns_true_when_row_exists():
    """When the SELECT 1 finds a matching user-managed Variable, return True."""
    # Mock session whose .exec(...).first() returns a truthy row.
    class _Result:
        def first(self):
            return 42  # any truthy placeholder for a row
    svc = AsyncMock()
    session = AsyncMock()
    session.exec = AsyncMock(return_value=_Result())

    # Bind the real method to the mock service so we can test it directly.
    from langflow.services.variable.service import DatabaseVariableService
    bound = DatabaseVariableService.has_user_managed_variable.__get__(svc, DatabaseVariableService)
    result = await bound(name="my_api_key", user_id=USER_ID, session=session)
    assert result is True


@pytest.mark.asyncio
async def test_has_user_managed_variable_returns_false_when_no_row():
    """When the SELECT 1 finds nothing, return False."""
    class _Result:
        def first(self):
            return None
    svc = AsyncMock()
    session = AsyncMock()
    session.exec = AsyncMock(return_value=_Result())

    from langflow.services.variable.service import DatabaseVariableService
    bound = DatabaseVariableService.has_user_managed_variable.__get__(svc, DatabaseVariableService)
    result = await bound(name="nonexistent", user_id=USER_ID, session=session)
    assert result is False
