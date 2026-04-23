"""Tests for setup_superuser fail-fast behavior."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from langflow.services.utils import setup_superuser
from pydantic import SecretStr


async def test_setup_superuser_fails_without_username():
    settings_service = MagicMock()
    settings_service.auth_settings.SUPERUSER = ""
    settings_service.auth_settings.SUPERUSER_PASSWORD = SecretStr("real-password")
    session = AsyncMock()

    with pytest.raises(ValueError, match="LANGFLOW_SUPERUSER"):
        await setup_superuser(settings_service, session)


async def test_setup_superuser_fails_without_password():
    settings_service = MagicMock()
    settings_service.auth_settings.SUPERUSER = "admin"
    settings_service.auth_settings.SUPERUSER_PASSWORD = SecretStr("")
    session = AsyncMock()

    with pytest.raises(ValueError, match="LANGFLOW_SUPERUSER_PASSWORD"):
        await setup_superuser(settings_service, session)


async def test_setup_superuser_creates_user_with_valid_env(monkeypatch):
    settings_service = MagicMock()
    settings_service.auth_settings.SUPERUSER = "admin"
    settings_service.auth_settings.SUPERUSER_PASSWORD = SecretStr("realpw")
    session = AsyncMock()

    created = {}

    async def fake_create(username, password, db):
        created["username"] = username
        created["password"] = password
        user = MagicMock()
        user.id = "user-id"
        return user

    from langflow.services.auth import utils as auth_utils

    monkeypatch.setattr(auth_utils, "create_super_user", fake_create, raising=False)

    await setup_superuser(settings_service, session)

    assert created["username"] == "admin"
    assert created["password"] == "realpw"
    settings_service.auth_settings.reset_credentials.assert_called_once()
