from __future__ import annotations

from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.audit.service import AuditLogEntry, AuditService
from langflow.services.database.models.audit_log import AuditAction, AuditLog, AuditTargetType


@pytest.fixture
async def db_session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    sm = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    @asynccontextmanager
    async def factory():
        async with sm() as s:
            yield s

    yield factory
    await engine.dispose()


@pytest.mark.asyncio
async def test_audit_service_persists_rows(db_session_factory):
    service = AuditService(db_session_factory)

    entries = [
        AuditLogEntry(
            actor_user_id=uuid4(),
            actor_email="user@example.com",
            actor_is_super=False,
            org_id=uuid4(),
            target_type=AuditTargetType.FLOW,
            target_id=uuid4(),
            action=AuditAction.CREATE,
            diff={"after": {"name": "x"}},
            request_metadata={"ip": "1.2.3.4", "method": "POST", "path": "/api/v1/flows", "request_id": "r1"},
        )
    ]

    await service.record_batch(entries)

    async with db_session_factory() as session:
        rows = (await session.exec(select(AuditLog))).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.actor_email == "user@example.com"
    assert row.action == AuditAction.CREATE
    assert row.target_type == AuditTargetType.FLOW
    assert row.diff_hash != ""


@pytest.mark.asyncio
async def test_audit_service_swallows_db_errors(db_session_factory):
    service = AuditService(db_session_factory)

    class _BrokenFactory:
        def __call__(self):
            raise RuntimeError("db down")

    service._session_factory = _BrokenFactory()  # inject failure
    # Must not raise
    await service.record_batch(
        [
            AuditLogEntry(
                actor_user_id=uuid4(),
                actor_email="u",
                actor_is_super=False,
                org_id=None,
                target_type=AuditTargetType.FLOW,
                target_id=uuid4(),
                action=AuditAction.CREATE,
                diff={},
                request_metadata={},
            )
        ]
    )
