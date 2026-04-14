import datetime as dt
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from lfx.components.adp._shared import TOKEN_TTL_SECONDS, ADPConnection, build_mtls_httpx_client, fetch_token


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
    conn = ADPConnection(
        client_id="test-client",
        client_secret="test-secret",  # noqa: S106
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
        client_secret="s",  # noqa: S106
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
        client_secret="s",  # noqa: S106
        cert_source="path",
        cert_path="/tmp/c.pem",
        key_path="/tmp/k.pem",
    )
    now = datetime.now(tz=timezone.utc)
    conn.access_token = "abc"  # noqa: S105
    conn.token_expires_at = now
    assert conn.access_token == "abc"  # noqa: S105
    assert conn.token_expires_at == now


async def test_build_mtls_client_with_paths(tmp_path):
    cert_pem, key_pem = _make_self_signed_cert_and_key()
    cert_file = tmp_path / "cert.pem"
    key_file = tmp_path / "key.pem"
    cert_file.write_bytes(cert_pem)
    key_file.write_bytes(key_pem)

    conn = ADPConnection(
        client_id="c",
        client_secret="s",  # noqa: S106
        cert_source="path",
        cert_path=str(cert_file),
        key_path=str(key_file),
    )
    client = build_mtls_httpx_client(conn)
    try:
        assert isinstance(client, httpx.AsyncClient)
    finally:
        await client.aclose()


def test_build_mtls_client_requires_both_paths():
    conn = ADPConnection(
        client_id="c",
        client_secret="s",  # noqa: S106
        cert_source="path",
        cert_path="/tmp/cert.pem",
        key_path=None,
    )
    with pytest.raises(ValueError, match="cert_path and key_path"):
        build_mtls_httpx_client(conn)


async def test_mtls_client_cleans_up_on_async_with():
    """Temp files must be unlinked when the client is used as an async context manager."""
    cert_pem, key_pem = _make_self_signed_cert_and_key()

    conn = ADPConnection(
        client_id="c",
        client_secret="s",  # noqa: S106
        cert_source="pem",
        cert_pem=cert_pem.decode(),
        key_pem=key_pem.decode(),
    )

    async with build_mtls_httpx_client(conn) as client:
        temp_paths = list(client._adp_temp_cert_paths)
        assert len(temp_paths) == 2, "Expected two temp PEM files"
        for p in temp_paths:
            assert p.exists(), f"Temp file should exist inside context: {p}"

    # After exiting the async context manager, temp files must be gone.
    for p in temp_paths:
        assert not p.exists(), f"Temp file should have been cleaned up: {p}"


async def test_build_mtls_client_with_pem_writes_temp_files():
    cert_pem_bytes, key_pem_bytes = _make_self_signed_cert_and_key()
    conn = ADPConnection(
        client_id="c",
        client_secret="s",  # noqa: S106
        cert_source="pem",
        cert_pem=cert_pem_bytes.decode("utf-8"),
        key_pem=key_pem_bytes.decode("utf-8"),
    )
    client = build_mtls_httpx_client(conn)
    temp_paths = client._adp_temp_cert_paths
    assert len(temp_paths) == 2
    for p in temp_paths:
        assert p.exists()
        mode = p.stat().st_mode & 0o777
        assert mode == 0o600

    await client.aclose()
    for p in temp_paths:
        assert not p.exists(), f"{p} should have been cleaned up on aclose"


def test_build_mtls_client_pem_requires_both():
    conn = ADPConnection(
        client_id="c",
        client_secret="s",  # noqa: S106
        cert_source="pem",
        cert_pem="-----BEGIN CERTIFICATE-----\n...\n",
        key_pem=None,
    )
    with pytest.raises(ValueError, match="cert_pem and key_pem"):
        build_mtls_httpx_client(conn)


def test_build_mtls_client_unknown_source():
    # Bypass the dataclass type hint at runtime to test the defensive branch.
    conn = ADPConnection(
        client_id="c",
        client_secret="s",  # noqa: S106
        cert_source="path",
        cert_path="/tmp/x",
        key_path="/tmp/y",
    )
    conn.cert_source = "bogus"  # type: ignore[assignment]
    with pytest.raises(ValueError, match="Unknown cert_source"):
        build_mtls_httpx_client(conn)


# ---------------------------------------------------------------------------
# fetch_token tests
# ---------------------------------------------------------------------------


def _make_conn(tmp_path) -> ADPConnection:
    cert_pem, key_pem = _make_self_signed_cert_and_key()
    cert = tmp_path / "c.pem"
    key = tmp_path / "k.pem"
    cert.write_bytes(cert_pem)
    key.write_bytes(key_pem)
    return ADPConnection(
        client_id="my-id",
        client_secret="my-secret",  # noqa: S106
        cert_source="path",
        cert_path=str(cert),
        key_path=str(key),
    )


async def test_fetch_token_populates_access_token_and_expiry(tmp_path):
    conn = _make_conn(tmp_path)

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


async def test_fetch_token_uses_cache_when_not_expired(tmp_path):
    conn = _make_conn(tmp_path)
    conn.access_token = "cached-tok"  # noqa: S105
    conn.token_expires_at = datetime.now(tz=timezone.utc) + timedelta(minutes=30)

    mock_post = AsyncMock()
    with patch("lfx.components.adp._shared._post_token_request", new=mock_post):
        await fetch_token(conn)

    mock_post.assert_not_called()
    assert conn.access_token == "cached-tok"  # noqa: S105


async def test_fetch_token_force_bypasses_cache(tmp_path):
    conn = _make_conn(tmp_path)
    conn.access_token = "old-tok"  # noqa: S105
    conn.token_expires_at = datetime.now(tz=timezone.utc) + timedelta(minutes=30)

    fake_response = httpx.Response(200, json={"access_token": "new-tok", "expires_in": 3600})
    with patch("lfx.components.adp._shared._post_token_request", new=AsyncMock(return_value=fake_response)):
        await fetch_token(conn, force=True)

    assert conn.access_token == "new-tok"  # noqa: S105


async def test_fetch_token_expired_triggers_refresh(tmp_path):
    conn = _make_conn(tmp_path)
    conn.access_token = "old-tok"  # noqa: S105
    conn.token_expires_at = datetime.now(tz=timezone.utc) - timedelta(seconds=1)

    fake_response = httpx.Response(200, json={"access_token": "fresh-tok", "expires_in": 3600})
    with patch("lfx.components.adp._shared._post_token_request", new=AsyncMock(return_value=fake_response)):
        await fetch_token(conn)

    assert conn.access_token == "fresh-tok"  # noqa: S105


async def test_fetch_token_surfaces_adp_error_body(tmp_path):
    conn = _make_conn(tmp_path)
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
