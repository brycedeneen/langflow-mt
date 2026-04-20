"""Tests for lfx.services.auth.password — direct-bcrypt password hashing."""
from lfx.services.auth.password import hash_password, verify_password


def test_hash_password_returns_bcrypt_hash():
    """Output must be a well-formed bcrypt hash (`$2b$` wire format, length 60)."""
    hashed = hash_password("Str0ngP@ssword")  # pragma: allowlist secret
    assert hashed.startswith("$2b$")
    assert len(hashed) == 60


def test_hash_password_produces_unique_salts():
    """Two hashes of the same password must differ (random salts)."""
    pw = "same-password"  # pragma: allowlist secret
    assert hash_password(pw) != hash_password(pw)


def test_verify_password_roundtrip():
    """Hash a password, then verify it accepts the original and rejects a wrong one."""
    pw = "Str0ngP@ssword"  # pragma: allowlist secret
    hashed = hash_password(pw)
    assert verify_password(pw, hashed) is True
    assert verify_password("wrong", hashed) is False


def test_verify_legacy_passlib_hash():
    """Hash literal produced by passlib.context.CryptContext(schemes=["bcrypt"]).

    Generated against password 'correct-horse' under passlib 1.7.4 + bcrypt 4.0.1.
    Locks compatibility — the lockstep version of the AuthService-level test in
    src/backend/tests/unit/services/auth/test_auth_service.py.
    """
    legacy_hash = "$2b$12$59zWuSrdgXLXBk4Ptr5YbuLq1GxvPc2tahv7AF6F9c5urd75WHDTa"  # pragma: allowlist secret
    assert verify_password("correct-horse", legacy_hash) is True
    assert verify_password("wrong", legacy_hash) is False


def test_verify_legacy_2a_prefix_hash():
    """Older deployments may have ``$2a$``-prefixed hashes from older bcrypt installs.

    The verify_password docstring documents support for ``$2a$``/``$2b$``/``$2y$``;
    this test locks the ``$2a$`` claim with a frozen literal generated against the
    same password as the ``$2b$`` regression test.
    """
    legacy_2a_hash = "$2a$12$LhSKBxgIO1R1aYO2srqGguCC2JfTOy5IFUwSetpVwZARkxdqtUIVO"  # pragma: allowlist secret
    assert verify_password("correct-horse", legacy_2a_hash) is True
    assert verify_password("wrong", legacy_2a_hash) is False


def test_verify_password_handles_unicode():
    """UTF-8 multi-byte passwords must roundtrip."""
    pw = "пароль-🔐"  # pragma: allowlist secret
    hashed = hash_password(pw)
    assert verify_password(pw, hashed) is True
