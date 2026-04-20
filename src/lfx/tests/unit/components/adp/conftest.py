from datetime import datetime, timedelta, timezone

import pytest
from lfx.components.adp._shared import ADPConnection


@pytest.fixture
def adp_connection() -> ADPConnection:
    conn = ADPConnection(
        client_id="cid",
        client_secret="sec",  # noqa: S106
        cert_pem="-----BEGIN CERTIFICATE-----\nFAKE\n-----END CERTIFICATE-----\n",
        key_pem="-----BEGIN PRIVATE KEY-----\nFAKE\n-----END PRIVATE KEY-----\n",  # noqa: S105
    )
    conn.access_token = "test-token"  # noqa: S105
    conn.token_expires_at = datetime.now(tz=timezone.utc) + timedelta(minutes=30)
    return conn
