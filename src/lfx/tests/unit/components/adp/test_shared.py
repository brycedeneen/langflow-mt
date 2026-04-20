import datetime as dt
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from lfx.components.adp._shared import (
    TOKEN_TTL_SECONDS,
    ADPConnection,
    build_mtls_httpx_client,
    fetch_token,
    validate_adp_url,
)


@pytest.mark.parametrize(
    "url",
    [
        "https://api.adp.com",
        "https://api.adp.com/",
        "https://accounts.adp.com/auth/oauth/v2/token",
        "https://mcp.adp.com/mcp",
        "https://adp.com",
        "https://api.adp.com:8443/x",
        "https://API.ADP.COM/x",
    ],
)
def test_validate_adp_url_accepts_adp_hosts(url):
    assert validate_adp_url(url, field_name="u") == url


@pytest.mark.parametrize(
    "url",
    [
        "http://api.adp.com",  # non-https
        "https://evil.com",
        "https://evil-adp.com",  # suffix spoof
        "https://adp.com.attacker.tld",  # suffix spoof
        "https://api.adp.com@attacker.tld",  # userinfo spoof
        "https://attacker.tld/?x=https://api.adp.com",
        "",
        "not a url",
        "https:///",
        "ftp://api.adp.com",
        "//api.adp.com/x",  # scheme-relative
    ],
)
def test_validate_adp_url_rejects_off_allowlist(url):
    with pytest.raises(ValueError, match="token_url|https|host|URL"):
        validate_adp_url(url, field_name="token_url")


def _make_self_signed_cert_and_key() -> tuple[bytes, bytes]:
    """Return (cert_pem, key_pem) bytes for a throwaway self-signed certificate."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test")])
    now = dt.datetime.now(dt.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + dt.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )
    return cert_pem, key_pem


def test_adp_connection_defaults():
    cert_pem_bytes, key_pem_bytes = _make_self_signed_cert_and_key()
    conn = ADPConnection(
        client_id="test-client",
        client_secret="test-secret",  # noqa: S106
        cert_pem=cert_pem_bytes.decode(),
        key_pem=key_pem_bytes.decode(),
    )
    assert conn.client_id == "test-client"
    assert conn.api_base_url == "https://api.adp.com"
    assert conn.mcp_base_url.startswith("https://mcp.adp.com")
    assert conn.access_token is None
    assert conn.token_expires_at is None


def test_adp_connection_with_pem():
    conn = ADPConnection(
        client_id="c",
        client_secret="s",  # noqa: S106
        cert_pem="-----BEGIN CERT-----\nabc\n-----END CERT-----\n",
        key_pem="-----BEGIN KEY-----\nxyz\n-----END KEY-----\n",
    )
    assert "BEGIN CERT" in conn.cert_pem
    assert "BEGIN KEY" in conn.key_pem


def test_adp_connection_token_fields_mutable():
    conn = ADPConnection(
        client_id="c",
        client_secret="s",  # noqa: S106
        cert_pem="-----BEGIN CERT-----\nabc\n-----END CERT-----\n",
        key_pem="-----BEGIN KEY-----\nxyz\n-----END KEY-----\n",
    )
    now = datetime.now(tz=timezone.utc)
    conn.access_token = "abc"  # noqa: S105
    conn.token_expires_at = now
    assert conn.access_token == "abc"  # noqa: S105
    assert conn.token_expires_at == now


@pytest.mark.asyncio
async def test_build_mtls_client_with_pem():
    cert_pem_bytes, key_pem_bytes = _make_self_signed_cert_and_key()
    conn = ADPConnection(
        client_id="c",
        client_secret="s",  # noqa: S106
        cert_pem=cert_pem_bytes.decode(),
        key_pem=key_pem_bytes.decode(),
    )
    async with build_mtls_httpx_client(conn) as client:
        assert isinstance(client, httpx.AsyncClient)


@pytest.mark.asyncio
async def test_build_mtls_client_pem_requires_both_cert():
    conn = ADPConnection(
        client_id="c",
        client_secret="s",  # noqa: S106
        cert_pem="",
        key_pem="-----BEGIN PRIVATE KEY-----\nxyz\n-----END PRIVATE KEY-----\n",
    )
    with pytest.raises(ValueError, match="both cert_pem and key_pem"):
        async with build_mtls_httpx_client(conn):
            pass


@pytest.mark.asyncio
async def test_build_mtls_client_pem_requires_both_key():
    conn = ADPConnection(
        client_id="c",
        client_secret="s",  # noqa: S106
        cert_pem="-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----\n",
        key_pem="",
    )
    with pytest.raises(ValueError, match="both cert_pem and key_pem"):
        async with build_mtls_httpx_client(conn):
            pass


# ---------------------------------------------------------------------------
# fetch_token tests
# ---------------------------------------------------------------------------


def _make_conn() -> ADPConnection:
    cert_pem, key_pem = _make_self_signed_cert_and_key()
    return ADPConnection(
        client_id="my-id",
        client_secret="my-secret",  # noqa: S106
        cert_pem=cert_pem.decode(),
        key_pem=key_pem.decode(),
    )


@pytest.mark.asyncio
async def test_fetch_token_populates_access_token_and_expiry():
    conn = _make_conn()

    fake_response = httpx.Response(
        200,
        json={"access_token": "tok-123", "token_type": "Bearer", "expires_in": 3600},
    )

    with patch("lfx.components.adp._shared._post_token_request", new=AsyncMock(return_value=fake_response)):
        await fetch_token(conn)

    assert conn.access_token == "tok-123"  # noqa: S105
    assert conn.token_expires_at is not None
    delta = conn.token_expires_at - datetime.now(tz=timezone.utc)
    assert abs(delta.total_seconds() - TOKEN_TTL_SECONDS) < 5


@pytest.mark.asyncio
async def test_fetch_token_uses_cache_when_not_expired():
    conn = _make_conn()
    conn.access_token = "cached-tok"  # noqa: S105
    conn.token_expires_at = datetime.now(tz=timezone.utc) + timedelta(minutes=30)

    mock_post = AsyncMock()
    with patch("lfx.components.adp._shared._post_token_request", new=mock_post):
        await fetch_token(conn)

    mock_post.assert_not_called()
    assert conn.access_token == "cached-tok"  # noqa: S105


@pytest.mark.asyncio
async def test_fetch_token_force_bypasses_cache():
    conn = _make_conn()
    conn.access_token = "old-tok"  # noqa: S105
    conn.token_expires_at = datetime.now(tz=timezone.utc) + timedelta(minutes=30)

    fake_response = httpx.Response(200, json={"access_token": "new-tok", "expires_in": 3600})
    with patch("lfx.components.adp._shared._post_token_request", new=AsyncMock(return_value=fake_response)):
        await fetch_token(conn, force=True)

    assert conn.access_token == "new-tok"  # noqa: S105


@pytest.mark.asyncio
async def test_fetch_token_expired_triggers_refresh():
    conn = _make_conn()
    conn.access_token = "old-tok"  # noqa: S105
    conn.token_expires_at = datetime.now(tz=timezone.utc) - timedelta(seconds=1)

    fake_response = httpx.Response(200, json={"access_token": "fresh-tok", "expires_in": 3600})
    with patch("lfx.components.adp._shared._post_token_request", new=AsyncMock(return_value=fake_response)):
        await fetch_token(conn)

    assert conn.access_token == "fresh-tok"  # noqa: S105


@pytest.mark.asyncio
async def test_fetch_token_surfaces_adp_error_body():
    conn = _make_conn()
    fake_response = httpx.Response(
        401,
        json={"error": "invalid_client", "error_description": "bad creds"},
    )
    mock_post = AsyncMock(return_value=fake_response)
    with (
        patch("lfx.components.adp._shared._post_token_request", new=mock_post),
        pytest.raises(RuntimeError, match="invalid_client"),
    ):
        await fetch_token(conn)
