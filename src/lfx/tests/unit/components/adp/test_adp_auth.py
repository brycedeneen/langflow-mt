from unittest.mock import AsyncMock, patch

import pytest
from lfx.components.adp._shared import ADPConnection
from lfx.components.adp.adp_auth import ADPAuthComponent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_CERT = "-----BEGIN CERTIFICATE-----\nAAA\n-----END CERTIFICATE-----\n"
VALID_KEY = "-----BEGIN PRIVATE KEY-----\nAAA\n-----END PRIVATE KEY-----\n"
VALID_TOKEN_URL = "https://accounts.adp.com/auth/oauth/v2/token"


async def _make_component_and_call(**overrides):
    defaults = dict(
        client_id="cid",
        client_secret="secret",  # noqa: S106
        cert_pem=VALID_CERT,
        key_pem=VALID_KEY,
        token_url=VALID_TOKEN_URL,
    )
    defaults.update(overrides)
    component = ADPAuthComponent(**defaults)

    async def fake_fetch(conn, *, force=False):  # noqa: ARG001
        conn.access_token = "abc"  # noqa: S105

    with patch("lfx.components.adp.adp_auth.fetch_token", new=AsyncMock(side_effect=fake_fetch)):
        return await component.build_connection()


# ---------------------------------------------------------------------------
# Shape / metadata tests
# ---------------------------------------------------------------------------


def test_adp_auth_has_five_inputs():
    """ADPAuthComponent after v2 migration has exactly 5 inputs, no cert_source."""
    component = ADPAuthComponent()
    names = [inp.name for inp in component.inputs]
    assert names == ["client_id", "client_secret", "cert_pem", "key_pem", "token_url"]


def test_adp_auth_cert_pem_and_key_pem_are_text_file_secret_input():
    from lfx.inputs.inputs import TextFileSecretInput

    component = ADPAuthComponent()
    by_name = {inp.name: inp for inp in component.inputs}
    assert isinstance(by_name["cert_pem"], TextFileSecretInput)
    assert isinstance(by_name["key_pem"], TextFileSecretInput)
    assert by_name["cert_pem"].file_types == ["pem", "crt"]
    assert by_name["key_pem"].file_types == ["pem", "key"]


def test_adp_auth_version_and_changelog():
    assert ADPAuthComponent.version == 2
    assert len(ADPAuthComponent.changelog) == 1
    assert ADPAuthComponent.changelog[0].version == 2
    assert ADPAuthComponent.changelog[0].notes is not None


# ---------------------------------------------------------------------------
# build_connection — happy path
# ---------------------------------------------------------------------------


async def test_build_connection_happy_path():
    result = await _make_component_and_call()
    assert isinstance(result, ADPConnection)
    assert result.client_id == "cid"
    assert result.access_token == "abc"  # noqa: S105


# ---------------------------------------------------------------------------
# build_connection — required-field validation
# ---------------------------------------------------------------------------


async def test_auth_component_missing_client_id_raises():
    component = ADPAuthComponent(
        client_id="",
        client_secret="secret",  # noqa: S106
        cert_pem=VALID_CERT,
        key_pem=VALID_KEY,
        token_url=VALID_TOKEN_URL,
    )
    with pytest.raises(ValueError, match="client_id"):
        await component.build_connection()


async def test_auth_component_missing_client_secret_raises():
    component = ADPAuthComponent(
        client_id="cid",
        client_secret="",
        cert_pem=VALID_CERT,
        key_pem=VALID_KEY,
        token_url=VALID_TOKEN_URL,
    )
    with pytest.raises(ValueError, match="client_secret"):
        await component.build_connection()


async def test_auth_component_missing_cert_pem_raises():
    component = ADPAuthComponent(
        client_id="cid",
        client_secret="secret",  # noqa: S106
        cert_pem="",
        key_pem=VALID_KEY,
        token_url=VALID_TOKEN_URL,
    )
    with pytest.raises(ValueError, match="cert_pem is required"):
        await component.build_connection()


async def test_auth_component_missing_key_pem_raises():
    component = ADPAuthComponent(
        client_id="cid",
        client_secret="secret",  # noqa: S106
        cert_pem=VALID_CERT,
        key_pem="",
        token_url=VALID_TOKEN_URL,
    )
    with pytest.raises(ValueError, match="key_pem is required"):
        await component.build_connection()


# ---------------------------------------------------------------------------
# build_connection — token_url allowlist
# ---------------------------------------------------------------------------


async def test_auth_component_rejects_off_allowlist_token_url():
    component = ADPAuthComponent(
        client_id="cid",
        client_secret="secret",  # noqa: S106
        cert_pem=VALID_CERT,
        key_pem=VALID_KEY,
        token_url="https://attacker.example.com/token",  # noqa: S106
    )
    mock_fetch = AsyncMock()
    with (
        patch("lfx.components.adp.adp_auth.fetch_token", new=mock_fetch),
        pytest.raises(ValueError, match="token_url"),
    ):
        await component.build_connection()
    mock_fetch.assert_not_awaited()
