"""Tests for PEM helpers that were extracted from adp/_shared.py so both
API Request and ADP components can share them."""

from lfx.base.api_request.mtls import _normalize_pem, _write_secure_tempfile


def test_normalize_pem_fixes_literal_backslash_n():
    raw = r"-----BEGIN CERTIFICATE-----\nAAAA\n-----END CERTIFICATE-----"
    out = _normalize_pem(raw)
    assert "\\n" not in out
    assert out.startswith("-----BEGIN CERTIFICATE-----\n")
    assert out.endswith("-----END CERTIFICATE-----\n")


def test_normalize_pem_preserves_well_formed_input():
    body = "A" * 128
    raw = (
        "-----BEGIN CERTIFICATE-----\n"
        + "\n".join([body[i : i + 64] for i in range(0, len(body), 64)])
        + "\n-----END CERTIFICATE-----\n"
    )
    assert _normalize_pem(raw) == raw


def test_normalize_pem_adds_trailing_newline():
    raw = "-----BEGIN CERTIFICATE-----\nAAAA\n-----END CERTIFICATE-----"
    out = _normalize_pem(raw)
    assert out.endswith("\n")


def test_write_secure_tempfile_writes_0600():
    path = _write_secure_tempfile("hello", suffix=".pem")
    try:
        assert path.read_text() == "hello"
        assert oct(path.stat().st_mode & 0o777) == "0o600"
    finally:
        path.unlink(missing_ok=True)


import pytest
from pathlib import Path

from lfx.base.api_request.mtls import mtls_temp_files

VALID_CERT = (
    "-----BEGIN CERTIFICATE-----\n"
    "MIIBkTCB+wIJAKGj+YSnf2MxMA0GCSqGSIb3DQEBCwUAMBQxEjAQBgNVBAMMCWxv\n"
    "Y2FsaG9zdDAeFw0yMDAxMDEwMDAwMDBaFw0zMDAxMDEwMDAwMDBaMBQxEjAQBgNV\n"
    "BAMMCWxvY2FsaG9zdDBcMA0GCSqGSIb3DQEBAQUAA0sAMEgCQQDCertDataOnly\n"
    "TestingPurposesNotARealKeyChainJustBase64Padding12345678901234567\n"
    "AgMBAAEwDQYJKoZIhvcNAQELBQADQQBfake-signature-bytes-for-testing\n"
    "-----END CERTIFICATE-----\n"
)
VALID_KEY = (  # noqa: S105
    "-----BEGIN PRIVATE KEY-----\n"
    "MIIBVAIBADANBgkqhkiG9w0BAQEFAASCAT4wggE6AgEAAkEAfakeprivatekey-\n"
    "base64paddingnotarealkey012345678901234567890123456789012345678\n"
    "-----END PRIVATE KEY-----\n"
)


@pytest.mark.asyncio
async def test_mtls_temp_files_yields_none_when_both_empty():
    async with mtls_temp_files(None, None) as result:
        assert result is None


@pytest.mark.asyncio
async def test_mtls_temp_files_yields_none_when_both_empty_strings():
    async with mtls_temp_files("", "") as result:
        assert result is None


@pytest.mark.asyncio
async def test_mtls_temp_files_writes_files_and_yields_two_tuple():
    async with mtls_temp_files(VALID_CERT, VALID_KEY) as tup:
        assert tup is not None
        assert len(tup) == 2
        cert_path, key_path = tup
        assert Path(cert_path).exists()
        assert Path(key_path).exists()
        assert Path(cert_path).read_text().startswith("-----BEGIN CERTIFICATE-----")
        assert Path(key_path).read_text().startswith("-----BEGIN PRIVATE KEY-----")
    assert not Path(cert_path).exists()
    assert not Path(key_path).exists()


@pytest.mark.asyncio
async def test_mtls_temp_files_yields_three_tuple_with_password():
    async with mtls_temp_files(VALID_CERT, VALID_KEY, "s3cret") as tup:
        assert len(tup) == 3
        assert tup[2] == "s3cret"


@pytest.mark.asyncio
async def test_mtls_temp_files_raises_if_only_cert():
    with pytest.raises(ValueError, match="both a client certificate and a client key"):
        async with mtls_temp_files(VALID_CERT, None):
            pass


@pytest.mark.asyncio
async def test_mtls_temp_files_raises_if_only_key():
    with pytest.raises(ValueError, match="both a client certificate and a client key"):
        async with mtls_temp_files(None, VALID_KEY):
            pass


@pytest.mark.asyncio
async def test_mtls_temp_files_cleanup_on_exception():
    captured: list[str] = []
    with pytest.raises(RuntimeError, match="boom"):
        async with mtls_temp_files(VALID_CERT, VALID_KEY) as tup:
            captured.extend(tup)
            raise RuntimeError("boom")
    for p in captured:
        assert not Path(p).exists()


@pytest.mark.asyncio
async def test_mtls_temp_files_fixes_literal_backslash_n_on_paste():
    # Mimic what happens when a user pastes a PEM and the textarea converts
    # real newlines into literal "\n" sequences.
    mangled_cert = VALID_CERT.replace("\n", r"\n")
    async with mtls_temp_files(mangled_cert, VALID_KEY) as tup:
        assert tup is not None
        cert_path, _ = tup
        content = Path(cert_path).read_text()
        assert "\\n" not in content
        assert content.startswith("-----BEGIN CERTIFICATE-----\n")
