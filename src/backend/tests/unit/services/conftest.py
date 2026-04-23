"""Shared fixtures for unit/services tests that need a lightweight async DB session factory."""
from __future__ import annotations

from contextlib import asynccontextmanager

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.pool import StaticPool


@pytest.fixture
async def session_factory():
    """Yield an async session factory backed by an in-memory SQLite database.

    The factory is an async context manager, matching the production
    ``db_service.async_session_maker`` pattern used by services:

        async with session_factory() as session:
            ...
    """
    # Import all models so SQLModel.metadata is fully populated.
    import langflow.services.database.models  # noqa: F401

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    @asynccontextmanager
    async def _factory():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session

    yield _factory

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()
