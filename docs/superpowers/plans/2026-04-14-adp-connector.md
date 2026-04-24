# ADP Connector Bundle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship three Langflow components (ADP Auth, ADP API Request, ADP MCP) that let a flow authenticate to ADP over OAuth client_credentials + mTLS and talk to ADP's REST APIs and MCP server.

**Architecture:** Auth component returns a structured `ADPConnection` carrying access token, cert/key material, and base URLs. Downstream components (API Request, MCP) consume the connection via `HandleInput(input_types=["ADPConnection"])` and build their own mTLS `httpx.AsyncClient` per request. An in-process module-level cache keyed by `client_id` holds access tokens for 55 minutes and is force-refreshed on 401.

**Tech Stack:** Python 3.12, `httpx` (async, with `cert=` tuple for mTLS), `lfx.custom.custom_component.component.Component`, `lfx.io` inputs, `lfx.base.mcp.util.MCPStreamableHttpClient`, `pytest` + `pytest-asyncio`, `pytest-httpx` (already used by repo).

**Spec:** `docs/superpowers/specs/2026-04-14-adp-connector-design.md`

**Branch:** `feat/adp-connector` (already created off `main`)

---

## Background notes for the implementer

- The mTLS + form-urlencoded work in `api_request.py` lives on branch `feat/api-request-mtls-and-form-urlencoded` and is **not** merged to `main` yet. This plan does not depend on that branch; `_shared.py` implements its own mTLS client builder. Reference-only pattern from that branch: `httpx.AsyncClient(cert=(cert_path, key_path))` or `cert=(cert_path, key_path, password)`.
- `httpx` only accepts cert/key as **file paths**, not raw PEM strings. When the user supplies pasted PEM content, we write it to a `tempfile.NamedTemporaryFile(delete=False)` with mode `0o600`, use the path, and clean up afterward.
- Existing bundle conventions: `src/lfx/src/lfx/components/<bundle>/__init__.py` re-exports component classes. Example: `src/lfx/src/lfx/components/notion/__init__.py`.
- `HandleInput(name="connection", input_types=["ADPConnection"])` is the pattern for typed wires between components. The `input_types` list contains the **string name** of the type used for UI wire validation.
- `Output(display_name="...", name="...", method="method_name")` — the method returns the value emitted on that output.
- Unit tests live under `src/lfx/tests/unit/components/<bundle>/`. Example: `src/lfx/tests/unit/components/ibm/test_watsonx.py`.
- Run tests with `uv run --directory src/lfx pytest tests/unit/components/adp -v` (project uses `uv`).

---

## File Structure

**Create:**
- `src/lfx/src/lfx/components/adp/__init__.py` — bundle re-exports
- `src/lfx/src/lfx/components/adp/_shared.py` — `ADPConnection`, token cache, mTLS helpers
- `src/lfx/src/lfx/components/adp/adp_auth.py` — `ADPAuthComponent`
- `src/lfx/src/lfx/components/adp/adp_api_request.py` — `ADPAPIRequestComponent`
- `src/lfx/src/lfx/components/adp/adp_mcp.py` — `ADPMCPComponent`
- `src/lfx/tests/unit/components/adp/__init__.py`
- `src/lfx/tests/unit/components/adp/conftest.py` — shared fixtures
- `src/lfx/tests/unit/components/adp/test_shared.py`
- `src/lfx/tests/unit/components/adp/test_adp_auth.py`
- `src/lfx/tests/unit/components/adp/test_adp_api_request.py`
- `src/lfx/tests/unit/components/adp/test_adp_mcp.py`

**Responsibility per file:**
- `_shared.py` — single source of truth for connection shape, token fetch, mTLS client construction. No Langflow component base; pure functions + dataclass so it is trivially unit-testable.
- `adp_auth.py` — thin Langflow wrapper that reads inputs, calls `_shared.fetch_token`, returns `ADPConnection`.
- `adp_api_request.py` — path resolution, pagination loop, 401 retry — none of which belongs in `_shared.py`.
- `adp_mcp.py` — MCP transport wiring; leans on `lfx.base.mcp.util` where possible.

---

## Task 1: Scaffold bundle directory and empty `ADPConnection`

**Files:**
- Create: `src/lfx/src/lfx/components/adp/__init__.py`
- Create: `src/lfx/src/lfx/components/adp/_shared.py`
- Create: `src/lfx/tests/unit/components/adp/__init__.py`
- Create: `src/lfx/tests/unit/components/adp/test_shared.py`

- [x] **Step 1: Write failing test for `ADPConnection` dataclass shape**

Create `src/lfx/tests/unit/components/adp/__init__.py` as an empty file.

Create `src/lfx/tests/unit/components/adp/test_shared.py`:

```python
from datetime import datetime, timezone

from lfx.components.adp._shared import ADPConnection


def test_adp_connection_defaults():
    conn = ADPConnection(
        client_id="test-client",
        client_secret="test-secret",
        cert_source="path",
        cert_path="/tmp/cert.pem",
        key_path="/tmp/key.pem",
    )
    assert conn.client_id == "test-client"
    assert conn.api_base_url == "https://api.adp.com"
    assert conn.mcp_base_url.startswith("https://mcp.adp.com")
    assert conn.access_token is None
    assert conn.token_expires_at is None
    assert conn.cert_pem is None
    assert conn.key_pem is None


def test_adp_connection_with_pem():
    conn = ADPConnection(
        client_id="c",
        client_secret="s",
        cert_source="pem",
        cert_pem="-----BEGIN CERT-----\nabc\n-----END CERT-----\n",
        key_pem="-----BEGIN KEY-----\nxyz\n-----END KEY-----\n",
    )
    assert conn.cert_source == "pem"
    assert conn.cert_path is None
    assert conn.key_path is None
    assert "BEGIN CERT" in conn.cert_pem


def test_adp_connection_token_fields_mutable():
    conn = ADPConnection(
        client_id="c",
        client_secret="s",
        cert_source="path",
        cert_path="/tmp/c.pem",
        key_path="/tmp/k.pem",
    )
    now = datetime.now(tz=timezone.utc)
    conn.access_token = "abc"
    conn.token_expires_at = now
    assert conn.access_token == "abc"
    assert conn.token_expires_at == now
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run --directory src/lfx pytest tests/unit/components/adp/test_shared.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lfx.components.adp'`

- [x] **Step 3: Create bundle `__init__.py` and `_shared.py` with `ADPConnection`**

Create `src/lfx/src/lfx/components/adp/__init__.py`:

```python
"""ADP connector bundle: Auth, API Request, MCP."""
```

(Leave component re-exports for Task 8 — they don't exist yet.)

Create `src/lfx/src/lfx/components/adp/_shared.py`:

```python
"""Shared helpers for ADP components: connection object, token fetch, mTLS client."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

DEFAULT_API_BASE_URL = "https://api.adp.com"
DEFAULT_MCP_BASE_URL = "https://mcp.adp.com/mcp"  # placeholder until real URL known
DEFAULT_TOKEN_URL = "https://accounts.adp.com/auth/oauth/v2/token"
TOKEN_TTL_SECONDS = 55 * 60  # 55 minutes


@dataclass
class ADPConnection:
    """Shared connection state produced by ADPAuthComponent, consumed by API/MCP components.

    Not frozen: token and expiry are mutated by the token-fetch helper.
    """

    client_id: str
    client_secret: str
    cert_source: Literal["path", "pem"]
    cert_path: str | None = None
    key_path: str | None = None
    cert_pem: str | None = None
    key_pem: str | None = None
    api_base_url: str = DEFAULT_API_BASE_URL
    mcp_base_url: str = DEFAULT_MCP_BASE_URL
    token_url: str = DEFAULT_TOKEN_URL
    access_token: str | None = None
    token_expires_at: datetime | None = None
```

- [x] **Step 4: Run tests to verify they pass**

Run: `uv run --directory src/lfx pytest tests/unit/components/adp/test_shared.py -v`
Expected: 3 passed

- [x] **Step 5: Commit**

```bash
git add src/lfx/src/lfx/components/adp/__init__.py \
        src/lfx/src/lfx/components/adp/_shared.py \
        src/lfx/tests/unit/components/adp/__init__.py \
        src/lfx/tests/unit/components/adp/test_shared.py
git commit -m "feat(adp): scaffold bundle with ADPConnection dataclass"
```

---

## Task 2: mTLS httpx client builder (file-path source)

**Files:**
- Modify: `src/lfx/src/lfx/components/adp/_shared.py`
- Modify: `src/lfx/tests/unit/components/adp/test_shared.py`

- [x] **Step 1: Write failing test for `build_mtls_httpx_client` with file-path certs**

Append to `src/lfx/tests/unit/components/adp/test_shared.py`:

```python
import httpx
import pytest

from lfx.components.adp._shared import build_mtls_httpx_client


def test_build_mtls_client_with_paths(tmp_path):
    cert_file = tmp_path / "cert.pem"
    key_file = tmp_path / "key.pem"
    cert_file.write_text("-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----\n")
    key_file.write_text("-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----\n")

    conn = ADPConnection(
        client_id="c",
        client_secret="s",
        cert_source="path",
        cert_path=str(cert_file),
        key_path=str(key_file),
    )
    client = build_mtls_httpx_client(conn)
    try:
        assert isinstance(client, httpx.AsyncClient)
    finally:
        pytest.importorskip("anyio")
        import anyio
        anyio.run(client.aclose)


def test_build_mtls_client_requires_both_paths():
    conn = ADPConnection(
        client_id="c",
        client_secret="s",
        cert_source="path",
        cert_path="/tmp/cert.pem",
        key_path=None,
    )
    with pytest.raises(ValueError, match="cert_path and key_path"):
        build_mtls_httpx_client(conn)
```

- [x] **Step 2: Run tests to verify failure**

Run: `uv run --directory src/lfx pytest tests/unit/components/adp/test_shared.py -v`
Expected: 2 FAIL with `ImportError` for `build_mtls_httpx_client`

- [x] **Step 3: Implement `build_mtls_httpx_client`**

Append to `src/lfx/src/lfx/components/adp/_shared.py`:

```python
import os
import tempfile
from pathlib import Path

import httpx


def build_mtls_httpx_client(conn: "ADPConnection", *, timeout: float = 30.0) -> httpx.AsyncClient:
    """Build an httpx.AsyncClient configured with mTLS from an ADPConnection.

    For ``cert_source="path"`` the cert/key paths are used directly.
    For ``cert_source="pem"`` the PEM contents are written to temp files (0600)
    and those paths are handed to httpx. Temp files are cleaned up when the
    returned client is closed.
    """
    if conn.cert_source == "path":
        if not conn.cert_path or not conn.key_path:
            msg = "cert_path and key_path are required when cert_source='path'"
            raise ValueError(msg)
        cert_tuple = (conn.cert_path, conn.key_path)
        temp_paths: list[Path] = []
    elif conn.cert_source == "pem":
        if not conn.cert_pem or not conn.key_pem:
            msg = "cert_pem and key_pem are required when cert_source='pem'"
            raise ValueError(msg)
        cert_tuple, temp_paths = _write_pem_temp_files(conn.cert_pem, conn.key_pem)
    else:
        msg = f"Unknown cert_source: {conn.cert_source!r}"
        raise ValueError(msg)

    client = httpx.AsyncClient(cert=cert_tuple, timeout=timeout)
    # Attach temp paths for cleanup on close
    client._adp_temp_cert_paths = temp_paths  # noqa: SLF001 - internal marker

    original_aclose = client.aclose

    async def aclose_with_cleanup() -> None:
        try:
            await original_aclose()
        finally:
            for p in temp_paths:
                try:
                    p.unlink(missing_ok=True)
                except OSError:
                    pass

    client.aclose = aclose_with_cleanup  # type: ignore[method-assign]
    return client


def _write_pem_temp_files(cert_pem: str, key_pem: str) -> tuple[tuple[str, str], list[Path]]:
    """Write cert/key PEM strings to 0600 temp files; return (cert,key) paths + cleanup list."""
    cert_path = _write_secure_tempfile(cert_pem, suffix=".pem")
    key_path = _write_secure_tempfile(key_pem, suffix=".pem")
    return (str(cert_path), str(key_path)), [cert_path, key_path]


def _write_secure_tempfile(content: str, *, suffix: str) -> Path:
    fd, name = tempfile.mkstemp(suffix=suffix, prefix="adp-")
    try:
        os.write(fd, content.encode("utf-8"))
    finally:
        os.close(fd)
    path = Path(name)
    path.chmod(0o600)
    return path
```

- [x] **Step 4: Run tests to verify they pass**

Run: `uv run --directory src/lfx pytest tests/unit/components/adp/test_shared.py -v`
Expected: 5 passed

- [x] **Step 5: Commit**

```bash
git add src/lfx/src/lfx/components/adp/_shared.py src/lfx/tests/unit/components/adp/test_shared.py
git commit -m "feat(adp): add mTLS httpx client builder (file-path source)"
```

---

## Task 3: mTLS client builder — PEM-paste source + temp-file cleanup

**Files:**
- Modify: `src/lfx/tests/unit/components/adp/test_shared.py`
- (`_shared.py` already supports PEM from Task 2; this task locks in the behavior with tests.)

- [x] **Step 1: Write failing tests for PEM source and cleanup behavior**

Append to `src/lfx/tests/unit/components/adp/test_shared.py`:

```python
import asyncio


def test_build_mtls_client_with_pem_writes_temp_files():
    conn = ADPConnection(
        client_id="c",
        client_secret="s",
        cert_source="pem",
        cert_pem="-----BEGIN CERTIFICATE-----\nabc\n-----END CERTIFICATE-----\n",
        key_pem="-----BEGIN PRIVATE KEY-----\nxyz\n-----END PRIVATE KEY-----\n",
    )
    client = build_mtls_httpx_client(conn)
    temp_paths = client._adp_temp_cert_paths  # noqa: SLF001
    assert len(temp_paths) == 2
    for p in temp_paths:
        assert p.exists()
        # Permissions on POSIX only
        mode = p.stat().st_mode & 0o777
        assert mode == 0o600

    asyncio.run(client.aclose())
    for p in temp_paths:
        assert not p.exists(), f"{p} should have been cleaned up on aclose"


def test_build_mtls_client_pem_requires_both():
    conn = ADPConnection(
        client_id="c",
        client_secret="s",
        cert_source="pem",
        cert_pem="-----BEGIN CERTIFICATE-----\n...\n",
        key_pem=None,
    )
    with pytest.raises(ValueError, match="cert_pem and key_pem"):
        build_mtls_httpx_client(conn)


def test_build_mtls_client_unknown_source():
    conn = ADPConnection(
        client_id="c",
        client_secret="s",
        cert_source="path",
    )
    # Missing paths AND invalid combination
    conn.cert_source = "bogus"  # type: ignore[assignment]
    with pytest.raises(ValueError, match="Unknown cert_source"):
        build_mtls_httpx_client(conn)
```

- [x] **Step 2: Run tests to verify they pass (implementation already exists from Task 2)**

Run: `uv run --directory src/lfx pytest tests/unit/components/adp/test_shared.py -v`
Expected: 8 passed

- [x] **Step 3: Commit**

```bash
git add src/lfx/tests/unit/components/adp/test_shared.py
git commit -m "test(adp): cover PEM-paste mTLS source and temp-file cleanup"
```

---

## Task 4: Token fetch with 55-min cache and force refresh

**Files:**
- Modify: `src/lfx/src/lfx/components/adp/_shared.py`
- Modify: `src/lfx/tests/unit/components/adp/test_shared.py`

- [x] **Step 1: Write failing tests for `fetch_token`**

Append to `src/lfx/tests/unit/components/adp/test_shared.py`:

```python
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from lfx.components.adp._shared import TOKEN_TTL_SECONDS, fetch_token


def _make_conn(tmp_path) -> ADPConnection:
    cert = tmp_path / "c.pem"
    key = tmp_path / "k.pem"
    cert.write_text("c")
    key.write_text("k")
    return ADPConnection(
        client_id="my-id",
        client_secret="my-secret",
        cert_source="path",
        cert_path=str(cert),
        key_path=str(key),
    )


@pytest.mark.asyncio
async def test_fetch_token_populates_access_token_and_expiry(tmp_path):
    conn = _make_conn(tmp_path)

    fake_response = httpx.Response(
        200,
        json={"access_token": "tok-123", "token_type": "Bearer", "expires_in": 3600},
    )

    with patch("lfx.components.adp._shared._post_token_request", new=AsyncMock(return_value=fake_response)):
        await fetch_token(conn)

    assert conn.access_token == "tok-123"
    assert conn.token_expires_at is not None
    delta = conn.token_expires_at - datetime.now(tz=timezone.utc)
    # Should be ~55 min; allow 5s slack
    assert abs(delta.total_seconds() - TOKEN_TTL_SECONDS) < 5


@pytest.mark.asyncio
async def test_fetch_token_uses_cache_when_not_expired(tmp_path):
    conn = _make_conn(tmp_path)
    conn.access_token = "cached-tok"
    conn.token_expires_at = datetime.now(tz=timezone.utc) + timedelta(minutes=30)

    mock_post = AsyncMock()
    with patch("lfx.components.adp._shared._post_token_request", new=mock_post):
        await fetch_token(conn)

    mock_post.assert_not_called()
    assert conn.access_token == "cached-tok"


@pytest.mark.asyncio
async def test_fetch_token_force_bypasses_cache(tmp_path):
    conn = _make_conn(tmp_path)
    conn.access_token = "old-tok"
    conn.token_expires_at = datetime.now(tz=timezone.utc) + timedelta(minutes=30)

    fake_response = httpx.Response(200, json={"access_token": "new-tok", "expires_in": 3600})
    with patch("lfx.components.adp._shared._post_token_request", new=AsyncMock(return_value=fake_response)):
        await fetch_token(conn, force=True)

    assert conn.access_token == "new-tok"


@pytest.mark.asyncio
async def test_fetch_token_expired_triggers_refresh(tmp_path):
    conn = _make_conn(tmp_path)
    conn.access_token = "old-tok"
    conn.token_expires_at = datetime.now(tz=timezone.utc) - timedelta(seconds=1)

    fake_response = httpx.Response(200, json={"access_token": "fresh-tok", "expires_in": 3600})
    with patch("lfx.components.adp._shared._post_token_request", new=AsyncMock(return_value=fake_response)):
        await fetch_token(conn)

    assert conn.access_token == "fresh-tok"


@pytest.mark.asyncio
async def test_fetch_token_surfaces_adp_error_body(tmp_path):
    conn = _make_conn(tmp_path)
    fake_response = httpx.Response(
        401,
        json={"error": "invalid_client", "error_description": "bad creds"},
    )
    with patch("lfx.components.adp._shared._post_token_request", new=AsyncMock(return_value=fake_response)):
        with pytest.raises(RuntimeError, match="invalid_client"):
            await fetch_token(conn)
```

- [x] **Step 2: Run tests to verify they fail**

Run: `uv run --directory src/lfx pytest tests/unit/components/adp/test_shared.py -v`
Expected: 5 new FAILs (ImportError for `fetch_token`)

- [x] **Step 3: Implement `fetch_token` + `_post_token_request`**

Append to `src/lfx/src/lfx/components/adp/_shared.py`:

```python
from datetime import datetime, timedelta, timezone


async def fetch_token(conn: ADPConnection, *, force: bool = False) -> None:
    """Ensure ``conn.access_token`` is populated and non-expired.

    Uses the in-memory cache on ``conn``. Sets ``token_expires_at`` to now + 55 min
    on success (ignoring ADP's ``expires_in`` — 55 min is our explicit contract).
    On non-2xx responses, raises RuntimeError with the response body attached so
    callers can surface ADP's OAuth error payload to users.
    """
    if not force and _token_is_fresh(conn):
        return

    async with build_mtls_httpx_client(conn) as client:
        response = await _post_token_request(client, conn)

    if response.status_code >= 400:
        try:
            detail = response.json()
        except ValueError:
            detail = response.text
        msg = f"ADP token endpoint returned {response.status_code}: {detail}"
        raise RuntimeError(msg)

    payload = response.json()
    access_token = payload.get("access_token")
    if not access_token:
        msg = f"ADP token response missing access_token: {payload}"
        raise RuntimeError(msg)

    conn.access_token = access_token
    conn.token_expires_at = datetime.now(tz=timezone.utc) + timedelta(seconds=TOKEN_TTL_SECONDS)


def _token_is_fresh(conn: ADPConnection) -> bool:
    if not conn.access_token or not conn.token_expires_at:
        return False
    return datetime.now(tz=timezone.utc) < conn.token_expires_at


async def _post_token_request(client: httpx.AsyncClient, conn: ADPConnection) -> httpx.Response:
    """Isolated for easy mocking in tests."""
    return await client.post(
        conn.token_url,
        data={
            "grant_type": "client_credentials",
            "client_id": conn.client_id,
            "client_secret": conn.client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
```

Also ensure `datetime, timezone` are imported at top of `_shared.py` (should already be used in tests; add to module imports).

- [x] **Step 4: Run tests to verify they pass**

Run: `uv run --directory src/lfx pytest tests/unit/components/adp/test_shared.py -v`
Expected: 13 passed

- [x] **Step 5: Commit**

```bash
git add src/lfx/src/lfx/components/adp/_shared.py src/lfx/tests/unit/components/adp/test_shared.py
git commit -m "feat(adp): add token fetch with 55-min cache and force refresh"
```

---

## Task 5: `ADPAuthComponent`

**Files:**
- Create: `src/lfx/src/lfx/components/adp/adp_auth.py`
- Create: `src/lfx/tests/unit/components/adp/test_adp_auth.py`

- [x] **Step 1: Write failing tests for `ADPAuthComponent`**

Create `src/lfx/tests/unit/components/adp/test_adp_auth.py`:

```python
from unittest.mock import AsyncMock, patch

import pytest

from lfx.components.adp._shared import ADPConnection
from lfx.components.adp.adp_auth import ADPAuthComponent


@pytest.mark.asyncio
async def test_auth_component_returns_connection_with_token(tmp_path):
    cert = tmp_path / "c.pem"
    key = tmp_path / "k.pem"
    cert.write_text("c")
    key.write_text("k")

    component = ADPAuthComponent(
        client_id="cid",
        client_secret="secret",
        cert_source="File Path",
        cert_path=str(cert),
        key_path=str(key),
        cert_pem="",
        key_pem="",
        token_url="https://accounts.adp.com/auth/oauth/v2/token",
    )

    async def fake_fetch(conn, *, force=False):
        conn.access_token = "abc"

    with patch("lfx.components.adp.adp_auth.fetch_token", new=AsyncMock(side_effect=fake_fetch)):
        result = await component.build_connection()

    assert isinstance(result, ADPConnection)
    assert result.client_id == "cid"
    assert result.cert_source == "path"
    assert result.cert_path == str(cert)
    assert result.access_token == "abc"


@pytest.mark.asyncio
async def test_auth_component_pem_mode():
    component = ADPAuthComponent(
        client_id="cid",
        client_secret="secret",
        cert_source="PEM",
        cert_path="",
        key_path="",
        cert_pem="-----BEGIN CERTIFICATE-----\nabc\n",
        key_pem="-----BEGIN PRIVATE KEY-----\nxyz\n",
        token_url="https://accounts.adp.com/auth/oauth/v2/token",
    )
    with patch("lfx.components.adp.adp_auth.fetch_token", new=AsyncMock()):
        result = await component.build_connection()
    assert result.cert_source == "pem"
    assert "BEGIN CERTIFICATE" in result.cert_pem


@pytest.mark.asyncio
async def test_auth_component_missing_client_id_raises():
    component = ADPAuthComponent(
        client_id="",
        client_secret="secret",
        cert_source="File Path",
        cert_path="/tmp/c.pem",
        key_path="/tmp/k.pem",
        cert_pem="",
        key_pem="",
        token_url="https://accounts.adp.com/auth/oauth/v2/token",
    )
    with pytest.raises(ValueError, match="client_id"):
        await component.build_connection()


@pytest.mark.asyncio
async def test_auth_component_path_mode_missing_cert_raises():
    component = ADPAuthComponent(
        client_id="cid",
        client_secret="secret",
        cert_source="File Path",
        cert_path="",
        key_path="/tmp/k.pem",
        cert_pem="",
        key_pem="",
        token_url="https://accounts.adp.com/auth/oauth/v2/token",
    )
    with pytest.raises(ValueError, match="cert_path"):
        await component.build_connection()
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run --directory src/lfx pytest tests/unit/components/adp/test_adp_auth.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lfx.components.adp.adp_auth'`

- [x] **Step 3: Implement `ADPAuthComponent`**

Create `src/lfx/src/lfx/components/adp/adp_auth.py`:

```python
"""ADPAuthComponent — produces an ADPConnection via OAuth client_credentials + mTLS."""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, Output, SecretStrInput, TabInput
from lfx.schema.dotdict import dotdict
from lfx.utils.component_utils import set_field_display

from ._shared import DEFAULT_TOKEN_URL, ADPConnection, fetch_token


class ADPAuthComponent(Component):
    display_name = "ADP Auth"
    description = "Authenticate to ADP via OAuth 2.0 client_credentials over mTLS."
    icon = "Key"
    name = "ADPAuth"

    inputs = [
        SecretStrInput(
            name="client_id",
            display_name="Client ID",
            info="ADP developer client ID.",
            required=True,
        ),
        SecretStrInput(
            name="client_secret",
            display_name="Client Secret",
            info="ADP developer client secret.",
            required=True,
        ),
        TabInput(
            name="cert_source",
            display_name="Cert Source",
            options=["File Path", "PEM"],
            value="File Path",
            info="How to supply the mTLS client certificate and key.",
            real_time_refresh=True,
        ),
        MessageTextInput(
            name="cert_path",
            display_name="Client Certificate Path",
            info="Absolute path to the client certificate (PEM).",
        ),
        MessageTextInput(
            name="key_path",
            display_name="Client Key Path",
            info="Absolute path to the client private key (PEM).",
        ),
        SecretStrInput(
            name="cert_pem",
            display_name="Client Certificate (PEM)",
            info="Paste the client certificate contents.",
            show=False,
        ),
        SecretStrInput(
            name="key_pem",
            display_name="Client Key (PEM)",
            info="Paste the client private key contents.",
            show=False,
        ),
        MessageTextInput(
            name="token_url",
            display_name="Token URL",
            info="OAuth token endpoint. Override only for staging/testing.",
            value=DEFAULT_TOKEN_URL,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Connection", name="connection", method="build_connection"),
    ]

    async def build_connection(self) -> ADPConnection:
        client_id = (self.client_id or "").strip()
        client_secret = (self.client_secret or "").strip()
        if not client_id:
            msg = "client_id is required"
            raise ValueError(msg)
        if not client_secret:
            msg = "client_secret is required"
            raise ValueError(msg)

        source = "path" if self.cert_source == "File Path" else "pem"
        if source == "path":
            if not (self.cert_path or "").strip():
                msg = "cert_path is required when Cert Source is File Path"
                raise ValueError(msg)
            if not (self.key_path or "").strip():
                msg = "key_path is required when Cert Source is File Path"
                raise ValueError(msg)
        else:
            if not (self.cert_pem or "").strip():
                msg = "cert_pem is required when Cert Source is PEM"
                raise ValueError(msg)
            if not (self.key_pem or "").strip():
                msg = "key_pem is required when Cert Source is PEM"
                raise ValueError(msg)

        conn = ADPConnection(
            client_id=client_id,
            client_secret=client_secret,
            cert_source=source,
            cert_path=self.cert_path or None,
            key_path=self.key_path or None,
            cert_pem=self.cert_pem or None,
            key_pem=self.key_pem or None,
            token_url=(self.token_url or DEFAULT_TOKEN_URL).strip(),
        )
        await fetch_token(conn)
        return conn

    def update_build_config(self, build_config: dotdict, field_value, field_name: str | None = None) -> dotdict:
        if field_name == "cert_source":
            is_path = field_value == "File Path"
            set_field_display(build_config, "cert_path", value=is_path)
            set_field_display(build_config, "key_path", value=is_path)
            set_field_display(build_config, "cert_pem", value=not is_path)
            set_field_display(build_config, "key_pem", value=not is_path)
        return build_config
```

- [x] **Step 4: Run tests to verify they pass**

Run: `uv run --directory src/lfx pytest tests/unit/components/adp/test_adp_auth.py -v`
Expected: 4 passed

- [x] **Step 5: Commit**

```bash
git add src/lfx/src/lfx/components/adp/adp_auth.py src/lfx/tests/unit/components/adp/test_adp_auth.py
git commit -m "feat(adp): add ADPAuthComponent with cert-source toggle"
```

---

## Task 6: `ADPAPIRequestComponent` — endpoint resolution and single request

**Files:**
- Create: `src/lfx/src/lfx/components/adp/adp_api_request.py`
- Create: `src/lfx/tests/unit/components/adp/conftest.py`
- Create: `src/lfx/tests/unit/components/adp/test_adp_api_request.py`

- [x] **Step 1: Write shared fixture**

Create `src/lfx/tests/unit/components/adp/conftest.py`:

```python
from datetime import datetime, timedelta, timezone

import pytest

from lfx.components.adp._shared import ADPConnection


@pytest.fixture
def adp_connection(tmp_path) -> ADPConnection:
    cert = tmp_path / "cert.pem"
    key = tmp_path / "key.pem"
    cert.write_text("c")
    key.write_text("k")
    conn = ADPConnection(
        client_id="cid",
        client_secret="sec",
        cert_source="path",
        cert_path=str(cert),
        key_path=str(key),
    )
    conn.access_token = "test-token"
    conn.token_expires_at = datetime.now(tz=timezone.utc) + timedelta(minutes=30)
    return conn
```

- [x] **Step 2: Write failing tests for endpoint resolution and single request**

Create `src/lfx/tests/unit/components/adp/test_adp_api_request.py`:

```python
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from lfx.components.adp.adp_api_request import ADPAPIRequestComponent


def _make_component(connection, **overrides) -> ADPAPIRequestComponent:
    defaults = {
        "connection": connection,
        "endpoint": "Workers",
        "custom_path": "",
        "resource_id": "",
        "method": "GET",
        "query_params": None,
        "body": [],
        "result_mode": "Top 20",
        "timeout": 30,
    }
    defaults.update(overrides)
    return ADPAPIRequestComponent(**defaults)


def test_resolve_path_workers_list(adp_connection):
    c = _make_component(adp_connection, endpoint="Workers")
    assert c._resolve_path() == "/hr/v2/workers"


def test_resolve_path_workers_by_id(adp_connection):
    c = _make_component(adp_connection, endpoint="Workers", resource_id="G3ABC")
    assert c._resolve_path() == "/hr/v2/workers/G3ABC"


def test_resolve_path_pay_statements_requires_id(adp_connection):
    c = _make_component(adp_connection, endpoint="Pay Statements", resource_id="G3ABC")
    assert c._resolve_path() == "/payroll/v1/workers/G3ABC/pay-statements"


def test_resolve_path_pay_statements_missing_id_raises(adp_connection):
    c = _make_component(adp_connection, endpoint="Pay Statements", resource_id="")
    with pytest.raises(ValueError, match="resource_id is required"):
        c._resolve_path()


def test_resolve_path_custom(adp_connection):
    c = _make_component(
        adp_connection,
        endpoint="Other (custom path)",
        custom_path="/staffing/v1/positions",
    )
    assert c._resolve_path() == "/staffing/v1/positions"


def test_resolve_path_custom_missing_raises(adp_connection):
    c = _make_component(
        adp_connection,
        endpoint="Other (custom path)",
        custom_path="",
    )
    with pytest.raises(ValueError, match="custom_path is required"):
        c._resolve_path()


@pytest.mark.asyncio
async def test_make_request_top_20_single_call(adp_connection):
    c = _make_component(adp_connection, endpoint="Workers", result_mode="Top 20")

    fake_response = httpx.Response(200, json={"workers": [{"id": 1}, {"id": 2}]})

    with patch.object(c, "_execute_request", new=AsyncMock(return_value=fake_response)) as mock_exec:
        result = await c.make_api_request()

    assert mock_exec.call_count == 1
    # Top 20 must include $top=20
    call_kwargs = mock_exec.call_args.kwargs
    assert call_kwargs["params"]["$top"] == 20
    assert "$skip" not in call_kwargs["params"]
    assert result.data["result"]["workers"] == [{"id": 1}, {"id": 2}]
    assert result.data["status_code"] == 200
```

- [x] **Step 3: Run tests to verify they fail**

Run: `uv run --directory src/lfx pytest tests/unit/components/adp/test_adp_api_request.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [x] **Step 4: Implement `ADPAPIRequestComponent` skeleton**

Create `src/lfx/src/lfx/components/adp/adp_api_request.py`:

```python
"""ADPAPIRequestComponent — authenticated mTLS requests to api.adp.com."""

from __future__ import annotations

from typing import Any

import httpx

from lfx.custom.custom_component.component import Component
from lfx.io import (
    DataInput,
    DropdownInput,
    HandleInput,
    IntInput,
    MessageTextInput,
    Output,
    TabInput,
    TableInput,
)
from lfx.schema.data import Data

from ._shared import ADPConnection, build_mtls_httpx_client, fetch_token

# Endpoint catalog: display name → (path template, requires_id)
# ``{aoid}`` is substituted with resource_id when present; otherwise the
# ``requires_id`` flag decides whether to fail or to hit the list endpoint.
ENDPOINT_CATALOG: dict[str, tuple[str, bool]] = {
    "Workers": ("/hr/v2/workers", False),
    "Worker Demographics": ("/hr/v2/worker-demographics", False),
    "Pay Statements": ("/payroll/v1/workers/{aoid}/pay-statements", True),
    "Time Cards": ("/time/v2/workers/{aoid}/time-cards", True),
    "Jobs": ("/hr/v1/jobs", False),
    "Meta": ("/core/v1/meta", False),
    "Other (custom path)": ("", False),
}

MAX_PAGINATION_ITERATIONS = 1000
PAGE_SIZE_FOR_ALL = 100


class ADPAPIRequestComponent(Component):
    display_name = "ADP API Request"
    description = "Call ADP REST APIs using an ADPConnection. Authenticated with mTLS + Bearer token."
    icon = "Globe"
    name = "ADPAPIRequest"

    inputs = [
        HandleInput(
            name="connection",
            display_name="ADP Connection",
            input_types=["ADPConnection"],
            info="Connection produced by an ADP Auth component.",
            required=True,
        ),
        DropdownInput(
            name="endpoint",
            display_name="Endpoint",
            options=list(ENDPOINT_CATALOG.keys()),
            value="Workers",
            info="ADP API endpoint to call.",
            real_time_refresh=True,
        ),
        MessageTextInput(
            name="custom_path",
            display_name="Custom Path",
            info="Path (e.g. /hr/v2/workers) when Endpoint is 'Other'.",
            show=False,
        ),
        MessageTextInput(
            name="resource_id",
            display_name="Resource ID (aoid)",
            info="Leave empty for list endpoints; set to a worker ID for by-ID lookups.",
        ),
        DropdownInput(
            name="method",
            display_name="HTTP Method",
            options=["GET", "POST", "PATCH", "PUT", "DELETE"],
            value="GET",
            advanced=True,
        ),
        DataInput(
            name="query_params",
            display_name="Query Parameters",
            info="Extra OData filters (e.g. $filter, $select).",
            advanced=True,
        ),
        TableInput(
            name="body",
            display_name="Body",
            info="Request body for non-GET methods.",
            table_schema=[
                {"name": "key", "display_name": "Key", "type": "str"},
                {"name": "value", "display_name": "Value"},
            ],
            value=[],
            advanced=True,
        ),
        TabInput(
            name="result_mode",
            display_name="Result Mode",
            options=["Top 20", "All"],
            value="Top 20",
            info="'Top 20' returns a single page of 20; 'All' auto-paginates.",
        ),
        IntInput(
            name="timeout",
            display_name="Timeout (seconds)",
            value=30,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="API Response", name="data", method="make_api_request"),
    ]

    def _resolve_path(self) -> str:
        endpoint = self.endpoint
        if endpoint == "Other (custom path)":
            path = (self.custom_path or "").strip()
            if not path:
                msg = "custom_path is required when Endpoint is 'Other (custom path)'"
                raise ValueError(msg)
            if not path.startswith("/"):
                path = "/" + path
            return path

        template, requires_id = ENDPOINT_CATALOG[endpoint]
        resource_id = (self.resource_id or "").strip()

        if "{aoid}" in template:
            if not resource_id:
                msg = f"resource_id is required for endpoint {endpoint!r}"
                raise ValueError(msg)
            return template.replace("{aoid}", resource_id)

        if requires_id and not resource_id:
            msg = f"resource_id is required for endpoint {endpoint!r}"
            raise ValueError(msg)

        if resource_id:
            return f"{template}/{resource_id}"
        return template

    def _build_query_params(self) -> dict[str, Any]:
        if self.query_params is None:
            return {}
        if hasattr(self.query_params, "data"):
            data = self.query_params.data or {}
        else:
            data = self.query_params
        if not isinstance(data, dict):
            return {}
        return dict(data)

    async def _execute_request(
        self,
        client: httpx.AsyncClient,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        params: dict[str, Any],
        json_body: Any,
        timeout: float,
    ) -> httpx.Response:
        return await client.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=json_body if method != "GET" else None,
            timeout=timeout,
        )

    async def make_api_request(self) -> Data:
        conn: ADPConnection = self.connection
        path = self._resolve_path()
        url = conn.api_base_url + path
        method = (self.method or "GET").upper()
        base_params = self._build_query_params()

        if self.result_mode == "Top 20":
            params = {**base_params, "$top": 20}
        else:
            params = {**base_params, "$top": PAGE_SIZE_FOR_ALL}

        headers = {"Authorization": f"Bearer {conn.access_token}"}

        async with build_mtls_httpx_client(conn, timeout=self.timeout) as client:
            response = await self._execute_request(
                client,
                method=method,
                url=url,
                headers=headers,
                params=params,
                json_body=None,
                timeout=self.timeout,
            )

            if response.status_code == 401:
                await fetch_token(conn, force=True)
                headers["Authorization"] = f"Bearer {conn.access_token}"
                response = await self._execute_request(
                    client,
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json_body=None,
                    timeout=self.timeout,
                )

            try:
                body = response.json()
            except ValueError:
                body = response.text

        return Data(
            data={
                "source": url,
                "status_code": response.status_code,
                "result": body,
            }
        )
```

- [x] **Step 5: Run tests to verify they pass**

Run: `uv run --directory src/lfx pytest tests/unit/components/adp/test_adp_api_request.py -v`
Expected: 7 passed

- [x] **Step 6: Commit**

```bash
git add src/lfx/src/lfx/components/adp/adp_api_request.py \
        src/lfx/tests/unit/components/adp/conftest.py \
        src/lfx/tests/unit/components/adp/test_adp_api_request.py
git commit -m "feat(adp): add ADPAPIRequestComponent with endpoint resolution and Top 20 mode"
```

---

## Task 7: `ADPAPIRequestComponent` — auto-pagination (All) and 401 retry

**Files:**
- Modify: `src/lfx/src/lfx/components/adp/adp_api_request.py`
- Modify: `src/lfx/tests/unit/components/adp/test_adp_api_request.py`

- [x] **Step 1: Write failing tests for pagination and 401 retry**

Append to `src/lfx/tests/unit/components/adp/test_adp_api_request.py`:

```python
@pytest.mark.asyncio
async def test_make_request_all_paginates_until_empty(adp_connection):
    c = _make_component(adp_connection, endpoint="Workers", result_mode="All")

    responses = [
        httpx.Response(200, json={"workers": [{"id": i} for i in range(100)]}),
        httpx.Response(200, json={"workers": [{"id": i} for i in range(100, 150)]}),
        httpx.Response(200, json={"workers": []}),
    ]
    mock_exec = AsyncMock(side_effect=responses)

    with patch.object(c, "_execute_request", new=mock_exec):
        result = await c.make_api_request()

    assert mock_exec.call_count == 3
    assert len(result.data["result"]["workers"]) == 150
    # Verify $top / $skip progression
    skip_values = [call.kwargs["params"].get("$skip", 0) for call in mock_exec.call_args_list]
    assert skip_values == [0, 100, 200]


@pytest.mark.asyncio
async def test_make_request_all_stops_on_short_page(adp_connection):
    c = _make_component(adp_connection, endpoint="Workers", result_mode="All")
    responses = [
        httpx.Response(200, json={"workers": [{"id": i} for i in range(50)]}),  # less than 100 → stop
    ]
    mock_exec = AsyncMock(side_effect=responses)
    with patch.object(c, "_execute_request", new=mock_exec):
        result = await c.make_api_request()
    assert mock_exec.call_count == 1
    assert len(result.data["result"]["workers"]) == 50


@pytest.mark.asyncio
async def test_make_request_401_triggers_force_refresh_and_retry(adp_connection):
    c = _make_component(adp_connection, endpoint="Workers", result_mode="Top 20")

    responses = [
        httpx.Response(401, json={"error": "expired"}),
        httpx.Response(200, json={"workers": [{"id": 1}]}),
    ]
    mock_exec = AsyncMock(side_effect=responses)

    async def fake_force_refresh(conn, *, force=False):
        assert force is True
        conn.access_token = "new-token"

    with patch.object(c, "_execute_request", new=mock_exec), \
         patch("lfx.components.adp.adp_api_request.fetch_token", new=AsyncMock(side_effect=fake_force_refresh)):
        result = await c.make_api_request()

    assert mock_exec.call_count == 2
    # Second call must use the refreshed token
    second_call_headers = mock_exec.call_args_list[1].kwargs["headers"]
    assert second_call_headers["Authorization"] == "Bearer new-token"
    assert result.data["status_code"] == 200


@pytest.mark.asyncio
async def test_make_request_401_twice_still_fails(adp_connection):
    c = _make_component(adp_connection, endpoint="Workers", result_mode="Top 20")

    responses = [
        httpx.Response(401, json={"error": "expired"}),
        httpx.Response(401, json={"error": "still-bad"}),
    ]
    mock_exec = AsyncMock(side_effect=responses)

    with patch.object(c, "_execute_request", new=mock_exec), \
         patch("lfx.components.adp.adp_api_request.fetch_token", new=AsyncMock()):
        result = await c.make_api_request()

    assert result.data["status_code"] == 401
    assert mock_exec.call_count == 2
```

- [x] **Step 2: Run tests to verify pagination and advanced 401 tests fail**

Run: `uv run --directory src/lfx pytest tests/unit/components/adp/test_adp_api_request.py -v`
Expected: 2 pagination tests FAIL (current impl only runs once in "All" mode). 401 tests may pass or partially pass.

- [x] **Step 3: Replace `make_api_request` with pagination-aware version**

In `src/lfx/src/lfx/components/adp/adp_api_request.py`, replace the existing `make_api_request` method body with:

```python
    async def make_api_request(self) -> Data:
        conn: ADPConnection = self.connection
        path = self._resolve_path()
        url = conn.api_base_url + path
        method = (self.method or "GET").upper()
        base_params = self._build_query_params()
        headers = {"Authorization": f"Bearer {conn.access_token}"}

        if self.result_mode == "Top 20":
            params = {**base_params, "$top": 20}
            async with build_mtls_httpx_client(conn, timeout=self.timeout) as client:
                response = await self._call_with_401_retry(
                    client, method=method, url=url, headers=headers, params=params, conn=conn,
                )
                return self._response_to_data(url, response)

        # "All" mode — auto-paginate
        combined: dict[str, Any] = {}
        collection_key: str | None = None
        skip = 0
        iterations = 0
        final_response: httpx.Response | None = None

        async with build_mtls_httpx_client(conn, timeout=self.timeout) as client:
            while iterations < MAX_PAGINATION_ITERATIONS:
                iterations += 1
                params = {**base_params, "$top": PAGE_SIZE_FOR_ALL}
                if skip:
                    params["$skip"] = skip

                response = await self._call_with_401_retry(
                    client, method=method, url=url, headers=headers, params=params, conn=conn,
                )
                final_response = response

                if response.status_code >= 400:
                    return self._response_to_data(url, response)

                try:
                    page = response.json()
                except ValueError:
                    return self._response_to_data(url, response)

                if collection_key is None:
                    collection_key = self._detect_collection_key(page)
                    combined = {collection_key: []} if collection_key else {}

                if not collection_key:
                    # Not a paginated collection — return single page
                    return self._response_to_data(url, response)

                items = page.get(collection_key, [])
                combined[collection_key].extend(items)

                if len(items) < PAGE_SIZE_FOR_ALL:
                    break
                skip += PAGE_SIZE_FOR_ALL

        return Data(
            data={
                "source": url,
                "status_code": final_response.status_code if final_response else 200,
                "result": combined,
            }
        )

    async def _call_with_401_retry(
        self,
        client: httpx.AsyncClient,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        params: dict[str, Any],
        conn: ADPConnection,
    ) -> httpx.Response:
        response = await self._execute_request(
            client, method=method, url=url, headers=headers, params=params, json_body=None, timeout=self.timeout,
        )
        if response.status_code == 401:
            await fetch_token(conn, force=True)
            headers["Authorization"] = f"Bearer {conn.access_token}"
            response = await self._execute_request(
                client, method=method, url=url, headers=headers, params=params, json_body=None, timeout=self.timeout,
            )
        return response

    @staticmethod
    def _detect_collection_key(page: Any) -> str | None:
        """ADP list responses wrap items in a top-level key (e.g. 'workers', 'items', 'payStatements').

        Heuristic: first key whose value is a list.
        """
        if not isinstance(page, dict):
            return None
        for k, v in page.items():
            if isinstance(v, list):
                return k
        return None

    def _response_to_data(self, url: str, response: httpx.Response) -> Data:
        try:
            body = response.json()
        except ValueError:
            body = response.text
        return Data(data={"source": url, "status_code": response.status_code, "result": body})
```

- [x] **Step 4: Run full test file**

Run: `uv run --directory src/lfx pytest tests/unit/components/adp/test_adp_api_request.py -v`
Expected: 11 passed

- [x] **Step 5: Commit**

```bash
git add src/lfx/src/lfx/components/adp/adp_api_request.py \
        src/lfx/tests/unit/components/adp/test_adp_api_request.py
git commit -m "feat(adp): auto-paginate All mode and retry on 401 with forced token refresh"
```

---

## Task 8: `ADPMCPComponent`

**Files:**
- Create: `src/lfx/src/lfx/components/adp/adp_mcp.py`
- Create: `src/lfx/tests/unit/components/adp/test_adp_mcp.py`

**Context for implementer:** The existing `MCPStreamableHttpClient` in `src/lfx/src/lfx/base/mcp/util.py` (line 1262+) does not currently accept a custom httpx client for mTLS. For v1 we call it with auth headers and document the mTLS limitation; a follow-up can extend the base client. If, while reading `util.py`, you find that `MCPStreamableHttpClient` already accepts an `httpx_client` or `ssl_context`, wire mTLS through that path and update the test accordingly.

- [x] **Step 1: Read the existing MCP client to confirm the interface**

Run: `grep -n "def _connect_to_server\|class MCPStreamableHttpClient\|async def connect_to_server" src/lfx/src/lfx/base/mcp/util.py`

Note the exact signature and what headers param it accepts. If the signature differs materially from what this plan assumes, update Step 3 below to match — but keep the test shape.

- [x] **Step 2: Write failing tests for `ADPMCPComponent`**

Create `src/lfx/tests/unit/components/adp/test_adp_mcp.py`:

```python
from unittest.mock import AsyncMock, patch

import pytest

from lfx.components.adp.adp_mcp import ADPMCPComponent


def _make_component(connection, **overrides):
    defaults = {
        "connection": connection,
        "mcp_url": "",
        "tool_filter": "",
    }
    defaults.update(overrides)
    return ADPMCPComponent(**defaults)


@pytest.mark.asyncio
async def test_mcp_component_uses_connection_base_url_by_default(adp_connection):
    c = _make_component(adp_connection)
    fake_tools = [{"name": "list_workers"}, {"name": "get_worker"}]

    async def fake_list(url, headers, **kwargs):
        assert url == adp_connection.mcp_base_url
        assert headers["Authorization"] == f"Bearer {adp_connection.access_token}"
        return fake_tools

    with patch.object(c, "_list_tools", new=AsyncMock(side_effect=fake_list)):
        tools = await c.build_tools()

    assert [t["name"] for t in tools] == ["list_workers", "get_worker"]


@pytest.mark.asyncio
async def test_mcp_component_override_url(adp_connection):
    c = _make_component(adp_connection, mcp_url="https://custom.adp.example/mcp")
    captured: dict = {}

    async def fake_list(url, headers, **kwargs):
        captured["url"] = url
        return []

    with patch.object(c, "_list_tools", new=AsyncMock(side_effect=fake_list)):
        await c.build_tools()
    assert captured["url"] == "https://custom.adp.example/mcp"


@pytest.mark.asyncio
async def test_mcp_component_tool_filter(adp_connection):
    c = _make_component(adp_connection, tool_filter="list_workers, get_worker")
    fake_tools = [
        {"name": "list_workers"},
        {"name": "get_worker"},
        {"name": "list_pay_statements"},
    ]
    with patch.object(c, "_list_tools", new=AsyncMock(return_value=fake_tools)):
        tools = await c.build_tools()
    assert [t["name"] for t in tools] == ["list_workers", "get_worker"]


@pytest.mark.asyncio
async def test_mcp_component_401_triggers_force_refresh(adp_connection):
    c = _make_component(adp_connection)

    call_count = {"n": 0}

    async def fake_list(url, headers, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            from httpx import HTTPStatusError, Request, Response
            req = Request("GET", url)
            resp = Response(401, request=req)
            raise HTTPStatusError("unauthorized", request=req, response=resp)
        return [{"name": "list_workers"}]

    async def fake_force(conn, *, force=False):
        assert force is True
        conn.access_token = "refreshed"

    with patch.object(c, "_list_tools", new=AsyncMock(side_effect=fake_list)), \
         patch("lfx.components.adp.adp_mcp.fetch_token", new=AsyncMock(side_effect=fake_force)):
        tools = await c.build_tools()

    assert call_count["n"] == 2
    assert tools[0]["name"] == "list_workers"
```

- [x] **Step 3: Implement `ADPMCPComponent`**

Create `src/lfx/src/lfx/components/adp/adp_mcp.py`:

```python
"""ADPMCPComponent — exposes ADP MCP server tools to a Langflow Agent."""

from __future__ import annotations

from typing import Any

import httpx

from lfx.custom.custom_component.component import Component
from lfx.io import HandleInput, MessageTextInput, Output

from ._shared import ADPConnection, fetch_token


class ADPMCPComponent(Component):
    display_name = "ADP MCP"
    description = "Connect to ADP's MCP server and expose its tools to an Agent component."
    icon = "Plug"
    name = "ADPMCP"

    inputs = [
        HandleInput(
            name="connection",
            display_name="ADP Connection",
            input_types=["ADPConnection"],
            required=True,
        ),
        MessageTextInput(
            name="mcp_url",
            display_name="MCP URL",
            info="Override the default ADP MCP URL on the connection.",
            advanced=True,
        ),
        MessageTextInput(
            name="tool_filter",
            display_name="Tool Filter",
            info="Comma-separated list of tool names to expose (leave blank for all).",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Tools", name="tools", method="build_tools"),
    ]

    async def build_tools(self) -> list[Any]:
        conn: ADPConnection = self.connection
        url = (self.mcp_url or "").strip() or conn.mcp_base_url
        headers = {"Authorization": f"Bearer {conn.access_token}"}

        try:
            tools = await self._list_tools(url, headers)
        except httpx.HTTPStatusError as e:
            if e.response.status_code != 401:
                raise
            await fetch_token(conn, force=True)
            headers["Authorization"] = f"Bearer {conn.access_token}"
            tools = await self._list_tools(url, headers)

        filter_value = (self.tool_filter or "").strip()
        if filter_value:
            wanted = {t.strip() for t in filter_value.split(",") if t.strip()}
            tools = [t for t in tools if self._tool_name(t) in wanted]

        return tools

    @staticmethod
    def _tool_name(tool: Any) -> str:
        if isinstance(tool, dict):
            return tool.get("name", "")
        return getattr(tool, "name", "")

    async def _list_tools(self, url: str, headers: dict[str, str]) -> list[Any]:
        """Connect to the MCP server and return its tool list.

        Thin wrapper so tests can replace it. The real implementation delegates
        to lfx.base.mcp.util.MCPStreamableHttpClient. NOTE: mTLS is not currently
        plumbed through that base client; this is tracked as a follow-up. For now
        the Bearer token alone is sent — confirmed with ADP during bundle design.
        """
        from lfx.base.mcp.util import MCPStreamableHttpClient

        client = MCPStreamableHttpClient()
        try:
            tools_raw = await client._connect_to_server(url=url, headers=headers)
        finally:
            # Ensure any session started by _connect_to_server is closed.
            aclose = getattr(client, "aclose", None)
            if aclose is not None:
                await aclose()
        # Normalize: MCPStreamableHttpClient may return ClientSession + tools tuple.
        # Adjust based on actual signature discovered in Step 1.
        if isinstance(tools_raw, tuple) and len(tools_raw) == 2:
            _session, tools = tools_raw
            return tools
        return tools_raw
```

**Implementer note:** If `_connect_to_server`'s actual return shape differs from what's handled above, adapt the normalization in `_list_tools`. Tests mock this method entirely, so the component logic is decoupled from that detail.

- [x] **Step 4: Run tests to verify they pass**

Run: `uv run --directory src/lfx pytest tests/unit/components/adp/test_adp_mcp.py -v`
Expected: 4 passed

- [x] **Step 5: Commit**

```bash
git add src/lfx/src/lfx/components/adp/adp_mcp.py src/lfx/tests/unit/components/adp/test_adp_mcp.py
git commit -m "feat(adp): add ADPMCPComponent with Bearer auth and 401 retry"
```

---

## Task 9: Bundle registration — `__init__.py` re-exports + full-suite verification

**Files:**
- Modify: `src/lfx/src/lfx/components/adp/__init__.py`

- [x] **Step 1: Write failing test for bundle-level imports**

Create `src/lfx/tests/unit/components/adp/test_bundle_init.py`:

```python
def test_bundle_exports_all_components():
    from lfx.components.adp import (
        ADPAPIRequestComponent,
        ADPAuthComponent,
        ADPMCPComponent,
    )

    assert ADPAuthComponent.name == "ADPAuth"
    assert ADPAPIRequestComponent.name == "ADPAPIRequest"
    assert ADPMCPComponent.name == "ADPMCP"
```

- [x] **Step 2: Run test to verify failure**

Run: `uv run --directory src/lfx pytest tests/unit/components/adp/test_bundle_init.py -v`
Expected: FAIL — `ImportError: cannot import name 'ADPAuthComponent'`

- [x] **Step 3: Update `__init__.py` to re-export**

Replace `src/lfx/src/lfx/components/adp/__init__.py` with:

```python
"""ADP connector bundle: Auth, API Request, MCP."""

from .adp_api_request import ADPAPIRequestComponent
from .adp_auth import ADPAuthComponent
from .adp_mcp import ADPMCPComponent

__all__ = [
    "ADPAPIRequestComponent",
    "ADPAuthComponent",
    "ADPMCPComponent",
]
```

- [x] **Step 4: Run the entire ADP test suite**

Run: `uv run --directory src/lfx pytest tests/unit/components/adp -v`
Expected: all tests passed across 5 test files (≈24 tests total)

- [x] **Step 5: Run repo linters on the new bundle**

Run: `uv run --directory src/lfx ruff check src/lfx/components/adp tests/unit/components/adp`
Fix any reported issues; common cases: unused imports, long lines.

- [x] **Step 6: Commit**

```bash
git add src/lfx/src/lfx/components/adp/__init__.py src/lfx/tests/unit/components/adp/test_bundle_init.py
git commit -m "feat(adp): register bundle components via __init__.py"
```

---

## Task 10: Manual smoke flow in Langflow UI

> **Partial automation (2026-04-24):** The static subset of these checks now lives in `src/lfx/tests/unit/components/adp/test_adp_bundle_smoke.py` (12 passing). That suite covers bundle size (33), foundation components present, Auth v2 field schema + no legacy `cert_source`, API Request endpoint catalog, `ADPConnection` wire types on API Request + MCP, and representative tool-component instantiation. The *interactive* parts below (live Langflow UI render, actual ADP credentials, browser feel) still require a human; the automated tests just tell you if the schema drifted before you start.

**Files:** none (manual verification)

- [ ] **Step 1: Start Langflow dev server**

From repo root:
```bash
uv run langflow run
```

- [ ] **Step 2: Open the UI at `http://localhost:7860`, create a new flow**

Verify the **ADP** bundle appears in the component sidebar. As of 2026-04-24 the bundle exports **33 components** (foundation: `ADP Auth`, `ADP API Request`, `ADP MCP`, `ADP Trigger`; plus 29 WFN tile tool-components — Worker*, Pay*, Time*, Talent, Benefits, JobRequisitions, JobApplicants, ApplicantOnboarding, DataCollectionEntries, DeductionConfigurations, USTaxProfiles, WorkSchedules, TeamTimeCards, TimeCards, TimeOff).

- [ ] **Step 3: Smoke the Auth → API Request wire**

Drop **ADP Auth** and **ADP API Request**. Connect Auth's `Connection` output to API Request's `ADP Connection` input. Confirm the wire accepts the connection (UI type check on `input_types=["ADPConnection"]`).

- [ ] **Step 4: Verify Auth v2 fields**

On ADP Auth, confirm four secret/file fields render: `Client ID`, `Client Secret` (both `SecretStrInput` — reveal/hide button), and `Client Certificate (PEM)`, `Client Key (PEM)` (both `TextFileSecretInput` — paste or upload). The old `Cert Source` File-Path/PEM toggle was removed in v2; if you see it, the loaded component is stale — force a reload.

Paste dummy but PEM-shaped values (e.g. `-----BEGIN CERTIFICATE-----\nAAAA\n-----END CERTIFICATE-----`) into `cert_pem` and `key_pem`, plus any string into client_id/client_secret. Trigger a build. Expected: no crypto crash on validation (token fetch will fail at runtime against ADP — that's fine; we're verifying field plumbing, not reachability).

- [ ] **Step 5: Verify API Request dropdown behavior**

On API Request, toggle `Endpoint` through the catalog (`Workers`, `Worker Demographics`, `Pay Statements`, `Time Cards`, `Jobs`, `Meta`, `Other (custom path)`). The `custom_path` field should only be meaningful for `Other`.

*Known deferred cosmetic:* Field show/hide for `custom_path` is not yet wired through `update_build_config` (TODO comment at `adp_api_request.py:71`). `custom_path` will always be visible today — not blocking for v1. If you find it actually show/hides, great; otherwise no action.

- [ ] **Step 6: Verify MCP component**

Drop **ADP MCP**. Connect Auth's `Connection` to its `ADP Connection` input. Confirm the `MCP URL` and `Tool Filter` fields render and `Tools` output is available.

- [ ] **Step 7: Sanity check a WFN tile tool-component**

Drop any one `ADP*ToolsComponent` (e.g. `ADP Worker Tools`). Connect Auth's `Connection`. Confirm inputs render and no import/validation error fires. This verifies the `_shared.py` + per-tile dispatch plumbing at least loads in the UI.

- [ ] **Step 8: Document outcome**

No commit for this step. If you find UI bugs (not failures), capture them as follow-ups in the PR description. Expected outcome: all 4 foundation + 1 tile component drop, wire, and build without tracebacks.

---

## Self-review notes (performed while writing this plan)

**Spec coverage:**
- 3 components — Tasks 5, 6+7, 8 ✓
- ADPConnection shape — Task 1 ✓
- mTLS file-path + PEM — Tasks 2 and 3 ✓
- Token 55-min cache + force refresh — Task 4 ✓
- x-www-form-urlencoded token POST — Task 4 (`_post_token_request` sets the header + uses `data=`) ✓
- Endpoint dropdown + "Other" + list/by-ID — Task 6 ✓
- Top 20 / All pagination + 1000-iter cap — Tasks 6 and 7 ✓
- 401 auto-retry with forced refresh — Task 7 (API) and Task 8 (MCP) ✓
- MCP toolbox via Streamable HTTP — Task 8 ✓
- Bundle registration — Task 9 ✓

**Known deferred items (captured in code comments, not hidden):**
- mTLS is not plumbed through `MCPStreamableHttpClient` — documented in `adp_mcp.py._list_tools` docstring. Follow-up.
- API Request field show/hide for `custom_path` — not wired through `update_build_config`. Follow-up (cosmetic).
- Integration tests against ADP sandbox — spec already lists as optional; no task, intentional.

**Type consistency check:**
- `ADPConnection.cert_source` is `"path" | "pem"` everywhere; Auth component translates from `"File Path" | "PEM"` UI labels to these values explicitly.
- `connection.access_token` always accessed through the connection object — no separate token plumbing.
- `fetch_token` signature `(conn, *, force=False)` consistent across all callers.

---

## WFN tile-component buildout — status as of 2026-04-24

Tasks 1–9 of this plan shipped the foundation (Auth / API Request / MCP / bundle registration). Subsequent work has built **per-tile agent-tool components** wrapping the ADP WFN API Explorer tiles. Each tile lives under `src/lfx/src/lfx/components/adp/` as an `ADP*ToolsComponent`; spec harvest lives under `docs/adp-api-specs/<domain>/<tile>/<version>/` (swagger + resolved schemas + REPORT.md + optional `har-samples.json` of sanitized request payloads).

**Patterns in use:**
- Reads consolidated with optional `{entity}_id` (list vs. detail in one tool) when shape allows.
- Writes consolidated via `action` / `scope` / `kind` / `view` literals across related endpoints.
- Narrow structured pydantic args where per-kind shape is uniform; `fields: dict[str, Any]` escape hatches for divergent per-kind payloads, with the tool description enumerating the ADP-documented fields per kind.
- Every mutation is gated behind `enable_mutations: bool = False`.
- `_post_event` helper on every component does a single 401 → `fetch_token(force=True)` retry.

### Built tiles (39 total)

**HR domain**
- [x] `hr/workers v2` — `ADPWorkerToolsComponent` (9 read tools: name/addresses/contact/job/compensation/ids/dates/status/business-communication).
- [x] `hr/workers-biological-data-management v2` — `ADPWorkerBiologicalToolsComponent`.
- [x] `hr/workers-business-communication-management v2` — `ADPWorkerBusinessCommunicationToolsComponent` (15 endpoints consolidated).
- [x] `hr/workers-compensation-management v2` — `ADPWorkerCompensationToolsComponent`.
- [x] `hr/workers-demographic-data-management v2` — `ADPWorkerDemographicToolsComponent`.
- [x] `hr/workers-identification-management v2` — `ADPWorkerIdentificationToolsComponent`.
- [x] `hr/workers-lifecycle-management v2` — `ADPWorkerLifecycleToolsComponent`.
- [x] `hr/workers-personal-communication-management v2` — `ADPWorkerPersonalCommunicationToolsComponent`.
- [x] `hr/workers-work-assignment-management v2` — `ADPWorkerAssignmentToolsComponent`.
- [x] `hr/hr-work-assignment-management v3` — `ADPWorkerAssignmentV3ToolsComponent`.
- [x] `hr/hr-worker-profiles v1` — `ADPWorkerHrProfilesToolsComponent`.
- [x] `hr/worker-leaves v2` — `ADPWorkerLeavesToolsComponent`.
- [x] `hr/workers-work-deployment-management v2` — `ADPWorkerDeploymentToolsComponent`.

**Payroll domain**
- [x] `payroll/pay-data-input v1` — `ADPPayDataInputToolsComponent`.
- [x] `payroll/pay-distributions v2` — `ADPPayDistributionsToolsComponent` (read + consolidated add/update/inactivate/remove-all).
- [x] `payroll/pay-statements v1` — `ADPPayStatementsToolsComponent` (list+detail + binary image fetch).
- [x] `payroll/us-tax-profiles v1` + `v2` — `ADPUSTaxProfilesToolsComponent` (federal/state/local × add/change/remove consolidated).
- [x] `payroll/worker-payroll-instructions v1` — `ADPWorkerPayrollInstructionsToolsComponent` (read + start/change/stop general-deduction consolidated).
- [x] `payroll/deduction-configurations v3` — `ADPDeductionConfigurationsToolsComponent` (catalog read).

**Staffing domain**
- [x] `staffing/applicant-onboarding v2` — `ADPApplicantOnboardingToolsComponent`.
- [x] `staffing/job-requisitions v1` — `ADPJobRequisitionsToolsComponent` (list+detail).
- [x] `staffing/job-applicants v2` — `ADPJobApplicantsToolsComponent` (screening-agency integration: initiate/status updates + package publish).

**Time domain**
- [x] `time/data-collection-entries v1` — `ADPDataCollectionEntriesToolsComponent`.
- [x] `time/team-time-cards v2` — `ADPTeamTimeCardsToolsComponent`.
- [x] `time/time-cards v2` — `ADPTimeCardsToolsComponent`.
- [x] `time/time-off-requests v2` + `v3` + `time-off-balances v3` — `ADPTimeOffToolsComponent` (3 consolidated tools across 3 tiles).
- [x] `time/work-schedules v1` — `ADPWorkSchedulesToolsComponent` (v2 after HAR-sample review corrected the envelope shape).

**Talent domain**
- [x] All 7 associate-KSAOC tiles consolidated into single `ADPTalentToolsComponent`: `certifications`, `competencies`, `educational-degrees`, `languages`, `licenses`, `memberships`, `recognitions`. Two tools, `kind` literal picks entity.

**Benefits domain**
- [x] `benefits/beneficiaries v1` + `dependents v1` + `external-plans v1` — `ADPBenefitsToolsComponent` (2 reads + 2 gated passthrough writes for the PascalCase carrier-feed).

### Lower-priority — HAR samples would verify swagger-inferred envelopes

No current bug, but real payloads would catch any shape drift:

- [ ] `payroll/us-tax-profiles v1` — HAR for federal + local add/change/remove events.
- [ ] `payroll/us-tax-profiles v2` — HAR for state add/change events.
- [ ] `time/time-off-balances v3` — HAR for `time-off-balances.modify` event.
- [ ] `time/data-collection-entries v1` — HAR for `data-collection-entries.process` event.
- [ ] `talent/associate-languages v2` — HAR for language add/change/remove (currently inferred).
- [ ] `talent/associate-competencies v2` — HAR for competency add/change/remove (currently inferred).

### Blocked — require ADP authenticated access (public HAR won't help)

These tiles are behind ADP's logged-in developer portal, so neither swagger nor examples are fetchable without creds:

- [ ] `hcm/wfn-codelists v3`
- [ ] `payroll/pay-statements v2` (v1 shipped; v2 only viewable by an authenticated account)
- [ ] `time/work-schedule-entry-uploads v2`
- [ ] `benefits/spending-account-plans v1`
- [ ] `benefits/spending-account-enrollments v1`

### Supporting infrastructure

- `scripts/adp_spec_harvester.py` — downloads each tile's swagger + resolves external `$ref`s, writes `REPORT.md` with per-operation schema size + split recommendations. Maintains a master `docs/adp-api-specs/README.md` index.
- HAR-sample extraction — raw developer-portal HAR captures (`developers.adp.com*.har`) are gitignored; the sanitized request-payload extracts (`har-samples.json` per tile) are committed.
- Test suite — 383 tests across the ADP bundle (from 40-ish at end of Task 9), all passing.
