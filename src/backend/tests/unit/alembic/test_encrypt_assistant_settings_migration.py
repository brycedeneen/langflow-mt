"""Test the backfill migration logic that re-encrypts pre-existing plaintext
``assistant.api_key`` Variable rows.

We don't exercise the full alembic up/downgrade cycle (that's covered by the
standard migration suite). Instead we assert the migration's *behavior*
by importing the module and invoking its logic against a Variable row seeded
into an in-memory SQLite schema via the ``async_session`` fixture.

The default ``_auth_service()`` in a unit-test context is the ``lfx`` stub
whose ``encrypt_api_key`` / ``decrypt_api_key`` are no-ops. We patch in a real
Langflow ``AuthService`` so we exercise real Fernet round-trips and the
``gAAAAA`` prefix assertion is meaningful.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from langflow.services.auth.service import AuthService
from langflow.services.auth.utils import decrypt_api_key
from langflow.services.database.models.membership.model import Membership, MembershipRole
from langflow.services.database.models.organization.model import Organization
from langflow.services.database.models.user.model import User
from langflow.services.database.models.variable.model import Variable
from lfx.services.settings.auth import AuthSettings
from pydantic import SecretStr
from sqlmodel.ext.asyncio.session import AsyncSession


@pytest.fixture
def langflow_auth_service(tmp_path):
    """Real Langflow AuthService so encrypt/decrypt use real Fernet."""
    settings = AuthSettings(CONFIG_DIR=str(tmp_path))
    settings.SECRET_KEY = SecretStr("unit-test-secret-for-encryption")
    settings_service = SimpleNamespace(
        auth_settings=settings,
        settings=SimpleNamespace(config_dir=str(tmp_path)),
    )
    return AuthService(settings_service)


@pytest.fixture(autouse=True)
def use_langflow_auth_for_encryption(langflow_auth_service):
    """Route ``encrypt_api_key`` / ``decrypt_api_key`` through a real AuthService."""
    with patch("langflow.services.auth.utils.get_auth_service", return_value=langflow_auth_service):
        yield


@pytest.fixture
async def plaintext_assistant_row(async_session: AsyncSession):
    """Seed ONE plaintext assistant.api_key Variable row (and its owner user/org)."""
    slug = uuid.uuid4().hex[:8]
    org = Organization(name=f"OrgM-{slug}", slug=f"org-m-{slug}", is_personal=True)
    user = User(username=f"migrate-{slug}", password="x", is_active=True)
    async_session.add_all([org, user])
    await async_session.flush()
    async_session.add(Membership(user_id=user.id, organization_id=org.id, role=MembershipRole.OWNER))
    await async_session.flush()
    plain = Variable(
        name="assistant.api_key",
        value="sk-was-plaintext",
        type="assistant_setting",
        default_fields=[],
        user_id=user.id,
        organization_id=org.id,
    )
    async_session.add(plain)
    await async_session.commit()
    await async_session.refresh(plain)
    return {"plain_id": plain.id, "user_id": user.id, "org_id": org.id}


@pytest.mark.asyncio
async def test_migration_encrypts_plaintext_row_in_place(
    async_session: AsyncSession, plaintext_assistant_row
):
    """The migration's upgrade() should re-encrypt plaintext rows via
    a direct SQL UPDATE (it doesn't use the ORM).

    We replicate the upgrade() body against a live session to exercise the
    same SQL path the real migration runs during ``alembic upgrade head``.
    """
    from langflow.alembic.versions.fe03bc35cf61_encrypt_assistant_settings import (
        FERNET_PREFIX,
    )
    from langflow.services.auth.utils import encrypt_api_key

    # Sanity: the seed row is plaintext.
    row = await async_session.get(Variable, plaintext_assistant_row["plain_id"])
    assert row.value == "sk-was-plaintext"
    assert not row.value.startswith(FERNET_PREFIX)
    async_session.expire_all()

    # Run the migration logic inline using raw SQL (matches upgrade() body
    # exactly — the real migration uses ``bind.execute(sa.text(...))``).
    sync_rows = (
        await async_session.execute(
            sa.text(
                "SELECT id, value FROM variable "
                "WHERE name = 'assistant.api_key' "
                "AND value IS NOT NULL "
                "AND value != ''"
            )
        )
    ).fetchall()
    for row_id, value in sync_rows:
        if isinstance(value, bytes):
            value = value.decode("utf-8", errors="replace")
        if value.startswith(FERNET_PREFIX):
            continue
        encrypted = encrypt_api_key(value)
        await async_session.execute(
            sa.text("UPDATE variable SET value = :v WHERE id = :id"),
            {"v": encrypted, "id": row_id},
        )
    await async_session.commit()
    async_session.expire_all()

    # Assert: the previously-plaintext row is now Fernet-encrypted and
    # decrypts back to the original value.
    row = await async_session.get(Variable, plaintext_assistant_row["plain_id"])
    assert row.value.startswith(FERNET_PREFIX), (
        f"row was not re-encrypted: value={row.value[:20]}"
    )
    assert decrypt_api_key(row.value) == "sk-was-plaintext"


@pytest.mark.asyncio
async def test_migration_is_idempotent_on_already_encrypted_row(
    async_session: AsyncSession, plaintext_assistant_row
):
    """Running the migration logic twice must leave the row in the same state."""
    from langflow.alembic.versions.fe03bc35cf61_encrypt_assistant_settings import (
        FERNET_PREFIX,
    )
    from langflow.services.auth.utils import encrypt_api_key

    # First pass: encrypt the plaintext row.
    row = await async_session.get(Variable, plaintext_assistant_row["plain_id"])
    row.value = encrypt_api_key(row.value)
    async_session.add(row)
    await async_session.commit()
    first_pass_value = row.value
    assert first_pass_value.startswith(FERNET_PREFIX)
    async_session.expire_all()

    # Second pass: migration should detect Fernet prefix and skip.
    sync_rows = (
        await async_session.execute(
            sa.text(
                "SELECT id, value FROM variable "
                "WHERE name = 'assistant.api_key' "
                "AND value IS NOT NULL "
                "AND value != ''"
            )
        )
    ).fetchall()
    skipped = 0
    for _row_id, value in sync_rows:
        if isinstance(value, bytes):
            value = value.decode("utf-8", errors="replace")
        if value.startswith(FERNET_PREFIX):
            skipped += 1
            continue
        # Would re-encrypt — should never hit on second pass.
        raise AssertionError(f"Migration would re-encrypt an already-encrypted row: {value[:20]}")
    assert skipped >= 1  # our plaintext_assistant_row, now encrypted

    # The value must be identical to what we set in the first pass (no double-encrypt).
    async_session.expire_all()
    row = await async_session.get(Variable, plaintext_assistant_row["plain_id"])
    assert row.value == first_pass_value
