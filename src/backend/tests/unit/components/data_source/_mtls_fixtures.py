"""Sample PEM-shaped strings for mTLS component tests. Not real keys; structure
is sufficient for _normalize_pem / httpx cert-tuple assertions. Actual SSL
handshakes are not exercised in these tests (we spy on httpx construction)."""

VALID_CERT_PEM = (
    "-----BEGIN CERTIFICATE-----\n"
    "MIIBkTCB+wIJAKGj+YSnf2MxMA0GCSqGSIb3DQEBCwUAMBQxEjAQBgNVBAMMCWxv\n"
    "Y2FsaG9zdDAeFw0yMDAxMDEwMDAwMDBaFw0zMDAxMDEwMDAwMDBaMBQxEjAQBgNV\n"
    "BAMMCWxvY2FsaG9zdDBcMA0GCSqGSIb3DQEBAQUAA0sAMEgCQQDCertDataOnly\n"
    "TestingPurposesNotARealKeyChainJustBase64Padding12345678901234567\n"
    "AgMBAAEwDQYJKoZIhvcNAQELBQADQQBfake-signature-bytes-for-testing\n"
    "-----END CERTIFICATE-----\n"
)

VALID_KEY_PEM = (  # noqa: S105
    "-----BEGIN PRIVATE KEY-----\n"
    "MIIBVAIBADANBgkqhkiG9w0BAQEFAASCAT4wggE6AgEAAkEAfakeprivatekey-\n"
    "base64paddingnotarealkey012345678901234567890123456789012345678\n"
    "-----END PRIVATE KEY-----\n"
)
