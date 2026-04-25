"""Webhook delivery for pro-service-quote.submitted events.

Synchronous best-effort dispatch from the submit handler. Failures are logged
at WARNING and otherwise silent — the in-product quote row is the source of
truth, and v1 explicitly does **not** retry. Implemented in Task 12.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID


def fire_quote_webhook(*, quote_id: UUID, base_url: str) -> None:  # noqa: ARG001
    """Stub — replaced in Task 12 with real HMAC-signed delivery."""
    return None


def build_webhook_payload(  # noqa: ARG001
    quote: Any,
    *,
    base_url: str,
    org_name: str,
    requester_label: str,
) -> dict[str, Any]:
    """Stub — replaced in Task 12."""
    return {}
