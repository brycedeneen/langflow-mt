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
        client_secret="sec",  # noqa: S106
        cert_source="path",
        cert_path=str(cert),
        key_path=str(key),
    )
    conn.access_token = "test-token"  # noqa: S105
    conn.token_expires_at = datetime.now(tz=timezone.utc) + timedelta(minutes=30)
    return conn
