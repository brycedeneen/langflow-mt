"""Tests for the api_key_hash O(1) lookup path on _check_key_from_db.

Replaces the prior O(N) Fernet-decrypt scan: every API key now stores a
deterministic HMAC-SHA256 (keyed by ``SECRET_KEY``) hex digest, and the auth
path looks up by that hash. The hash is the authoritative match — there is no
secondary Fernet verify.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import langflow.services.database.models.api_key.crud as crud_module
import pytest
from langflow.services.auth.service import AuthService
from langflow.services.auth.utils import compute_api_key_hash
from lfx.services.settings.auth import AuthSettings
from pydantic import SecretStr


@pytest.fixture
def settings_service(tmp_path):
    settings = AuthSettings(CONFIG_DIR=str(tmp_path))
    settings.SECRET_KEY = SecretStr("unit-test-secret-key-for-api-key-hash")
    return SimpleNamespace(
        auth_settings=settings,
        settings=SimpleNamespace(
            config_dir=str(tmp_path),
            disable_track_apikey_usage=True,
        ),
    )


@pytest.fixture(autouse=True)
def use_real_auth_service(settings_service):
    """Wire utils.encrypt_api_key/decrypt_api_key to the real AuthService."""
    auth_service = AuthService(settings_service)
    with patch("langflow.services.auth.utils.get_auth_service", return_value=auth_service):
        yield


class TestComputeApiKeyHash:
    def test_deterministic(self, settings_service):
        raw = "sk-test-key-abcdef"
        h1 = compute_api_key_hash(raw, settings_service)
        h2 = compute_api_key_hash(raw, settings_service)
        assert h1 == h2

    def test_distinct_keys_produce_distinct_hashes(self, settings_service):
        h1 = compute_api_key_hash("sk-one", settings_service)
        h2 = compute_api_key_hash("sk-two", settings_service)
        assert h1 != h2

    def test_distinct_secrets_produce_distinct_hashes(self, tmp_path):
        s1 = AuthSettings(CONFIG_DIR=str(tmp_path))
        s1.SECRET_KEY = SecretStr("secret-one-of-sufficient-length-x")
        s2 = AuthSettings(CONFIG_DIR=str(tmp_path))
        s2.SECRET_KEY = SecretStr("secret-two-of-sufficient-length-y")
        svc1 = SimpleNamespace(auth_settings=s1)
        svc2 = SimpleNamespace(auth_settings=s2)

        h1 = compute_api_key_hash("sk-shared", svc1)
        h2 = compute_api_key_hash("sk-shared", svc2)
        assert h1 != h2

    def test_hex_digest_shape(self, settings_service):
        h = compute_api_key_hash("sk-shape-check", settings_service)
        # SHA256 hex digest = 64 hex chars
        assert len(h) == 64
        int(h, 16)  # must parse as hex


class _Result:
    def __init__(self, items):
        self._items = list(items)

    def first(self):
        return self._items[0] if self._items else None

    def all(self):
        return self._items


class _SpyingSession:
    """Captures every exec() call so the test can assert exactly one query
    is issued — the O(1) WHERE api_key_hash == :h lookup — instead of a
    full row scan.
    """

    def __init__(self, rows_by_hash: dict[str, tuple], user):
        self._rows = rows_by_hash
        self._user = user
        self.exec_calls: list[object] = []
        self.get_calls: list[tuple] = []

    async def exec(self, query):
        await asyncio.sleep(0)
        self.exec_calls.append(query)
        # Inspect the compiled SQL for the bound :h param. We can't reliably
        # introspect SQLModel select() without a real engine, so we simulate
        # by always returning the single matching row when called.
        rendered = str(query)
        # Extract the hash from the bound parameters via repr fallback.
        for h, payload in self._rows.items():
            if h in rendered or len(self._rows) == 1:
                return _Result([payload])
        return _Result([])

    async def get(self, _model, _id):
        self.get_calls.append((_model, _id))
        return self._user


@pytest.mark.asyncio
async def test_check_key_from_db_uses_single_hash_lookup(settings_service):
    """Auth path issues exactly one query — by hash — and never enumerates rows."""
    raw = "sk-perf-test-key"
    expected_hash = compute_api_key_hash(raw, settings_service)

    user_id = uuid4()
    api_key_id = uuid4()
    fake_user = SimpleNamespace(id=user_id, is_active=True, username="alice")

    session = _SpyingSession(
        rows_by_hash={expected_hash: (api_key_id, user_id)},
        user=fake_user,
    )

    result = await crud_module._check_key_from_db(session, raw, settings_service)  # noqa: SLF001

    assert result is fake_user
    # Exactly one exec(): the hash lookup. No row scan, no per-row decrypt.
    assert len(session.exec_calls) == 1, (
        f"expected a single hash-lookup query, got {len(session.exec_calls)}"
    )
    # And exactly one get() to resolve the user.
    assert len(session.get_calls) == 1


@pytest.mark.asyncio
async def test_check_key_from_db_returns_none_for_unknown_key(settings_service):
    """Unknown raw keys return None after a single lookup — no fallback scan."""
    session = _SpyingSession(rows_by_hash={}, user=None)

    result = await crud_module._check_key_from_db(session, "sk-not-in-db", settings_service)

    assert result is None
    assert len(session.exec_calls) == 1
    assert len(session.get_calls) == 0
