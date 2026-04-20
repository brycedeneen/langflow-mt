"""Password hashing helpers backed by direct bcrypt.

Replaces the prior passlib.CryptContext-based implementation. Hashes produced
here are byte-compatible with passlib's bcrypt scheme — every legacy `$2b$`
hash in the database verifies unchanged.

bcrypt truncates inputs at 72 bytes at the algorithm level. Both passlib and
direct bcrypt inherit this behavior identically — no user-visible change.
"""

from __future__ import annotations

import bcrypt


def hash_password(plain: str) -> str:
    """Hash a plaintext password with bcrypt, using the library's default cost factor."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash.

    Accepts `$2a$`, `$2b$`, and `$2y$` variants — every hash produced by
    legacy passlib installs verifies correctly.
    """
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
