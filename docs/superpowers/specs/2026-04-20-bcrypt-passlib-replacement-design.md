# Replace passlib with direct bcrypt

**Date:** 2026-04-20
**Branch:** platform-multi-tenant
**Scope:** Backend auth password hashing

## Problem

Langflow uses `passlib.CryptContext(schemes=["bcrypt"])` for password hashing. `passlib` has been effectively unmaintained for 5+ years (last release `1.7.4`, October 2020). `bcrypt` itself is pinned to an old `4.0.1`. The `CryptContext` abstraction buys nothing for a single-scheme setup.

## Goals

1. Remove `passlib` and `types-passlib` from all dependency files.
2. Bump `bcrypt` to the current major (`>=5.0,<6`).
3. Keep every existing password hash in the database verifying unchanged. No migration, no rehash-on-login.
4. Preserve the `AuthService.get_password_hash()` / `AuthService.verify_password()` wrapper API so every call site outside the password module is unaffected.

## Non-Goals

- Switching hash algorithms (argon2, scrypt, etc.).
- Adding API-layer password length validation.
- Making bcrypt rounds configurable.
- Changing the `AuthService` interface.

## Current State Inventory

| Concern | Location |
|---|---|
| Only `passlib` import | `src/lfx/src/lfx/services/settings/auth.py:6` |
| `pwd_context` definition | `src/lfx/src/lfx/services/settings/auth.py:134` — `CryptContext(schemes=["bcrypt"], deprecated="auto")` |
| `AuthService.get_password_hash` | `src/backend/base/langflow/services/auth/service.py:456` |
| `AuthService.verify_password` | `src/backend/base/langflow/services/auth/service.py:453`, consumed at `:651` |
| Wrapper helpers | `src/backend/base/langflow/services/auth/utils.py:333` (`verify_password`), `:337` (`get_password_hash`) |
| Hashing call sites (all via `AuthService` wrappers) | `api/v1/users.py:36,101,131`, `services/auth/service.py:485`, `services/flow/flow_runner.py:169` |
| Verification call sites (all via wrappers) | `services/auth/service.py:651`, `api/v1/users.py:128`, `services/utils.py:39,57` |
| User model password column | `services/database/models/user/model.py:31` — `AutoString`, unbounded |
| Backend dep pins | `src/backend/base/pyproject.toml`: `passlib>=1.7.4,<2.0.0`, `bcrypt==4.0.1`, `types-passlib>=1.7.7.13` |
| LFX dep pins | `src/lfx/pyproject.toml`: `passlib>=1.7.4,<2.0.0` |
| Existing tests | `tests/unit/services/auth/test_auth_service.py:129` (roundtrip), `:337`, `:355`; `tests/unit/test_user.py:208`; `tests/unit/test_setup_superuser.py:150` |

## Architecture

### New module: `src/lfx/src/lfx/services/auth/password.py`

Two module-level functions, no classes, no state:

```python
import bcrypt


def hash_password(plain: str) -> str:
    """Hash a plaintext password with bcrypt (default cost factor 12).

    Note: bcrypt truncates inputs at 72 bytes at the algorithm level.
    Matches prior passlib behavior exactly — existing hashes verify unchanged.
    """
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash.

    Accepts `$2a$`, `$2b$`, `$2y$` prefixes — all variants produced by
    legacy passlib installs verify correctly.
    """
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
```

### Wire-up

- Delete `pwd_context` attribute from `AuthSettings` (`src/lfx/.../settings/auth.py`).
- Delete `from passlib.context import CryptContext` import.
- `AuthService.get_password_hash` (`service.py:456`) calls `password.hash_password(password)` directly.
- `AuthService.verify_password` (`service.py:453`) calls `password.verify_password(plain, hashed)` directly.
- No other call sites change.

### Backward compatibility

`passlib.CryptContext(schemes=["bcrypt"])` emits standard `$2b$12$...` hashes — byte-for-byte equivalent to `bcrypt.hashpw(..., bcrypt.gensalt())`. All existing DB hashes verify under `bcrypt.checkpw` without modification. No data migration required.

### Dependency changes

**`src/backend/base/pyproject.toml`:**
- Remove: `passlib>=1.7.4,<2.0.0`
- Remove: `types-passlib>=1.7.7.13`
- Change: `bcrypt==4.0.1` → `bcrypt>=5.0,<6`

**`src/lfx/pyproject.toml`:**
- Remove: `passlib>=1.7.4,<2.0.0`
- Add: `bcrypt>=5.0,<6`

**Lockfile:** regenerate with `uv lock`.

## Testing

### Existing tests (should pass unchanged)

All tests route through `AuthService.get_password_hash` / `verify_password` wrappers — contract is unchanged.

- `test_password_helpers_roundtrip` — hash/verify roundtrip
- `test_authenticate_user_correct_password` — login success
- `test_authenticate_user_wrong_password` — login rejection
- `test_patch_reset_password` — reset flow
- `test_create_super_user_default` — superuser creation

### New regression test

Add a single test to `test_auth_service.py` that verifies a pre-generated passlib bcrypt hash:

```python
def test_verify_legacy_passlib_hash():
    """Locks backward-compat: hashes produced by passlib 1.7.4
    must continue to verify after passlib removal."""
    # Generated via: passlib.context.CryptContext(schemes=["bcrypt"]).hash("correct-horse")
    legacy_hash = "$2b$12$..."  # pre-computed, committed as a literal
    assert verify_password("correct-horse", legacy_hash) is True
    assert verify_password("wrong", legacy_hash) is False
```

This locks the compatibility invariant so a future `bcrypt` bump or refactor can't silently break existing users.

## Risks

### Python version floor

`bcrypt` 5.x requires Python ≥3.9. Langflow's `pyproject.toml` declares `>=3.10`, so this is fine — will re-confirm during plan writing.

### Transitive dependencies on passlib

Unlikely but possible. Plan will include a `uv tree | grep passlib` check. If anything transitively requires passlib, we either leave it as a transitive (no direct import remains, so we still accomplish the cleanup goal) or surface the blocker.

### bcrypt 5.x behavioral changes

bcrypt 5.x tightened some input validation versus 4.x. For our two call sites (`hashpw`, `checkpw`), the contract is stable. The regression test above would catch any unexpected drift.

## Rollout

Single merge to `platform-multi-tenant`. No feature flag — the swap is instantaneous and backward-compatible at the hash level.

## Out of Scope (Follow-ups)

1. **API-layer password length validator** — add Pydantic constraint rejecting passwords >72 bytes to make the bcrypt truncation explicit rather than silent.
2. **Argon2 migration** — move to argon2id with rehash-on-next-login for existing users. Would re-introduce a `pwdlib`-style abstraction.
3. **Configurable bcrypt rounds** — expose cost factor via `AuthSettings` for tuning under load.
