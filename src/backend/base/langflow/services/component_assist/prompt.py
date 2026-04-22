"""Build the per-turn system prompt for the component assist service."""
from __future__ import annotations

import json

from langflow.services.component_assist.schemas import NodeSnapshot

_BASE = """You are ADP Assist, helping the user configure a single component in a Langflow flow.

Scope rules (strict):
- You MAY propose changes to the target component's template field values only.
- You MAY read neighbor component snapshots to understand the data shapes flowing in and out.
- You MUST NOT propose adding, removing, or rewiring components, or editing other components.

When you have a concrete configuration change to propose, call the `propose_config_update`
tool with the target `node_id` and a `patch` mapping of field names to new values, plus a
one-sentence `rationale` the user will see.

If the user's intent is ambiguous, ask a short clarifying question before proposing anything.
"""


def _snapshot_view(s: NodeSnapshot) -> dict:
    return {
        "node_id": s.node_id,
        "type": s.type,
        "display_name": s.display_name,
        "description": s.description,
        "template": s.template,
        "outputs": s.outputs,
    }


def build_system_prompt(
    *,
    node_snapshot: NodeSnapshot,
    neighbor_snapshots: list[NodeSnapshot],
    guide: str | None,
) -> str:
    parts: list[str] = [_BASE]
    if guide:
        parts.append("Component-specific guidance:\n" + guide.strip())

    parts.append(
        "Target component (this is the ONLY node you may propose changes to):\n"
        + json.dumps(_snapshot_view(node_snapshot), indent=2, default=str)
    )

    if neighbor_snapshots:
        parts.append(
            "Connected neighbors (read-only context — do not propose changes here):\n"
            + json.dumps(
                [_snapshot_view(s) for s in neighbor_snapshots],
                indent=2,
                default=str,
            )
        )
    else:
        parts.append(
            "This component has no connected neighbors. If upstream data shape matters for"
            " your suggestion, ask the user to describe or paste it."
        )

    return "\n\n".join(parts)
