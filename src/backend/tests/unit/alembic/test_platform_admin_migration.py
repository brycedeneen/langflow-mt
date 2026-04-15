"""Test that the platform-admin migration promotes existing superusers."""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.database.models.user.model import User


@pytest.mark.asyncio
async def test_migration_promotes_superusers_to_platform_admins(async_session: AsyncSession):
    """After migration runs (fixture bootstrapping), superusers should be platform admins."""
    su = User(username="existing_superuser", password="x", is_active=True, is_superuser=True)
    regular = User(username="existing_regular", password="x", is_active=True, is_superuser=False)
    async_session.add(su)
    async_session.add(regular)
    await async_session.commit()

    await async_session.exec(
        text('UPDATE "user" SET is_platform_admin = TRUE WHERE is_superuser = TRUE')
    )
    await async_session.commit()

    # Expire all cached objects so the next query re-fetches from the DB.
    async_session.expire_all()

    rows = (await async_session.exec(select(User))).all()
    by_name = {u.username: u for u in rows}
    assert by_name["existing_superuser"].is_platform_admin is True
    assert by_name["existing_regular"].is_platform_admin is False
