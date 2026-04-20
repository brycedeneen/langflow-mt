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
