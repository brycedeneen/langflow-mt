"""Shared helpers for ADP components: connection object, token fetch, mTLS client."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import httpx

from lfx.base.api_request.mtls import mtls_temp_files

DEFAULT_API_BASE_URL = "https://api.adp.com"
DEFAULT_MCP_BASE_URL = "https://mcp.adp.com/mcp"  # placeholder until real URL known
DEFAULT_TOKEN_URL = "https://accounts.adp.com/auth/oauth/v2/token"  # noqa: S105
TOKEN_TTL_SECONDS = 55 * 60  # 55 minutes
ALLOWED_ADP_HOST = "adp.com"
ALLOWED_ADP_HOST_SUFFIX = ".adp.com"


def validate_adp_url(url: str, *, field_name: str) -> str:
    """Require https + host is exactly 'adp.com' or ends in '.adp.com'.

    Rejects off-allowlist hosts, non-https schemes, URLs with userinfo, and
    missing/malformed hosts. Returns the url unchanged on success.
    """
    if not isinstance(url, str) or not url:
        msg = f"{field_name} must be a non-empty https URL on *.adp.com"
        raise ValueError(msg)
    try:
        parts = urlsplit(url)
    except ValueError as e:
        msg = f"{field_name} is not a valid URL: {e}"
        raise ValueError(msg) from e
    if parts.scheme != "https":
        msg = f"{field_name} must use https scheme (got {parts.scheme!r})"
        raise ValueError(msg)
    if "@" in (parts.netloc or ""):
        msg = f"{field_name} must not contain userinfo"
        raise ValueError(msg)
    host = (parts.hostname or "").lower()
    if not host:
        msg = f"{field_name} is missing a host"
        raise ValueError(msg)
    if host != ALLOWED_ADP_HOST and not host.endswith(ALLOWED_ADP_HOST_SUFFIX):
        msg = f"{field_name} host {host!r} is not on the ADP allowlist (*.adp.com)"
        raise ValueError(msg)
    return url


@dataclass
class ADPConnection:
    """Shared connection state produced by ADPAuthComponent, consumed by API/MCP components.

    Not frozen: token and expiry are mutated by the token-fetch helper.
    """

    client_id: str
    client_secret: str
    cert_pem: str
    key_pem: str
    api_base_url: str = DEFAULT_API_BASE_URL
    mcp_base_url: str = DEFAULT_MCP_BASE_URL
    token_url: str = DEFAULT_TOKEN_URL
    access_token: str | None = None
    token_expires_at: datetime | None = None


@asynccontextmanager
async def build_mtls_httpx_client(
    conn: ADPConnection,
    *,
    timeout: float = 30.0,
) -> AsyncIterator[httpx.AsyncClient]:
    """Async context manager yielding an httpx.AsyncClient configured with mTLS
    using the connection's PEMs. Temp files for cert/key are 0600 and are
    unlinked on exit.
    """
    if not conn.cert_pem or not conn.key_pem:
        msg = "ADPConnection requires both cert_pem and key_pem."
        raise ValueError(msg)

    async with mtls_temp_files(conn.cert_pem, conn.key_pem) as cert_tuple:
        async with httpx.AsyncClient(cert=cert_tuple, timeout=timeout) as client:
            yield client


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

    if response.status_code >= 400:  # noqa: PLR2004
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
