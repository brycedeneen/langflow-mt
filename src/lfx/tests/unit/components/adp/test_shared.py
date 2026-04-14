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
