from __future__ import annotations
import hmac
import hashlib


def sign_body(body: bytes, secret: str) -> str:
    mac = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={mac}"


def verify_body(body: bytes, secret: str, signature: str) -> bool:
    expected = sign_body(body, secret)
    return hmac.compare_digest(expected, signature)
