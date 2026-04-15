from unittest.mock import AsyncMock, patch

import pytest
from lfx.components.adp._shared import ADPConnection
from lfx.components.adp.adp_auth import ADPAuthComponent


async def test_auth_component_returns_connection_with_token(tmp_path):
    cert = tmp_path / "c.pem"
    key = tmp_path / "k.pem"
    cert.write_text("c")
    key.write_text("k")

    component = ADPAuthComponent(
        client_id="cid",
        client_secret="secret",  # noqa: S106
        cert_source="File Path",
        cert_path=str(cert),
        key_path=str(key),
        cert_pem="",
        key_pem="",
        token_url="https://accounts.adp.com/auth/oauth/v2/token",  # noqa: S106
    )

    async def fake_fetch(conn, *, force=False):  # noqa: ARG001
        conn.access_token = "abc"  # noqa: S105

    with patch("lfx.components.adp.adp_auth.fetch_token", new=AsyncMock(side_effect=fake_fetch)):
        result = await component.build_connection()

    assert isinstance(result, ADPConnection)
    assert result.client_id == "cid"
    assert result.cert_source == "path"
    assert result.cert_path == str(cert)
    assert result.access_token == "abc"  # noqa: S105


async def test_auth_component_pem_mode():
    component = ADPAuthComponent(
        client_id="cid",
        client_secret="secret",  # noqa: S106
        cert_source="PEM",
        cert_path="",
        key_path="",
        cert_pem="-----BEGIN CERTIFICATE-----\nabc\n",
        key_pem="-----BEGIN PRIVATE KEY-----\nxyz\n",
        token_url="https://accounts.adp.com/auth/oauth/v2/token",  # noqa: S106
    )
    with patch("lfx.components.adp.adp_auth.fetch_token", new=AsyncMock()):
        result = await component.build_connection()
    assert result.cert_source == "pem"
    assert "BEGIN CERTIFICATE" in result.cert_pem


async def test_auth_component_missing_client_id_raises():
    component = ADPAuthComponent(
        client_id="",
        client_secret="secret",  # noqa: S106
        cert_source="File Path",
        cert_path="/tmp/c.pem",
        key_path="/tmp/k.pem",
        cert_pem="",
        key_pem="",
        token_url="https://accounts.adp.com/auth/oauth/v2/token",  # noqa: S106
    )
    with pytest.raises(ValueError, match="client_id"):
        await component.build_connection()


async def test_auth_component_rejects_off_allowlist_token_url(tmp_path):
    cert = tmp_path / "c.pem"
    key = tmp_path / "k.pem"
    cert.write_text("c")
    key.write_text("k")
    component = ADPAuthComponent(
        client_id="cid",
        client_secret="secret",  # noqa: S106
        cert_source="File Path",
        cert_path=str(cert),
        key_path=str(key),
        cert_pem="",
        key_pem="",
        token_url="https://attacker.example.com/token",  # noqa: S106
    )
    mock_fetch = AsyncMock()
    with (
        patch("lfx.components.adp.adp_auth.fetch_token", new=mock_fetch),
        pytest.raises(ValueError, match="token_url"),
    ):
        await component.build_connection()
    mock_fetch.assert_not_awaited()


async def test_auth_component_path_mode_missing_cert_raises():
    component = ADPAuthComponent(
        client_id="cid",
        client_secret="secret",  # noqa: S106
        cert_source="File Path",
        cert_path="",
        key_path="/tmp/k.pem",
        cert_pem="",
        key_pem="",
        token_url="https://accounts.adp.com/auth/oauth/v2/token",  # noqa: S106
    )
    with pytest.raises(ValueError, match="cert_path"):
        await component.build_connection()
