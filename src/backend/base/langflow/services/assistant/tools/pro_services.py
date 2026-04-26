"""Tool handler for ``suggest_professional_services``."""
from __future__ import annotations

from typing import Any


def suggest_professional_services(reason: str) -> dict[str, Any]:
    """Return a payload the frontend renders as a Professional Services suggestion card.

    The reason is echoed back to the LLM so its next turn can acknowledge the
    suggestion was shown without repeating it.
    """
    return {
        "shown": True,
        "reason": reason,
    }
