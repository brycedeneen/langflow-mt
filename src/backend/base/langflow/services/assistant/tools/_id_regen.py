"""Backend equivalent of the frontend updateIds helper.

Used by apply_template to clone a template's flow.data into another flow
with fresh ids that won't collide with anything else in the component
catalog or event bus.
"""

from __future__ import annotations

import copy
import secrets
from typing import Any


def _new_suffix() -> str:
    """5-char lowercase-hex suffix. Matches the frontend getNodeId pattern."""
    return secrets.token_hex(3)[:5]


def _new_node_id(node_type: str) -> str:
    return f"{node_type}-{_new_suffix()}"


def regenerate_flow_ids(data: dict[str, Any]) -> dict[str, Any]:
    """Return a deep copy of `data` with fresh node and edge ids.

    - Each node gets a new id of the form `{type}-{5-char-hex}`.
    - Each node's `data.id` mirrors its new outer id.
    - Edge ids are regenerated as `reactflow__edge-{source}{sourceHandle}-{target}{targetHandle}`.
    - Edge `source` and `target` are remapped via an id-map built from the nodes.
    - `sourceHandle` / `targetHandle` keep their handle-name suffix but prepend the new node id.
      (Handle naming in reactflow typically includes the full originating node id; we
      preserve any existing suffix on the handle string and just swap the node-id prefix.)

    The input is not mutated — a deep copy is returned so the caller can keep the
    template flow intact on the session.
    """
    out = copy.deepcopy(data)
    nodes = out.get("nodes") or []
    edges = out.get("edges") or []

    # Build old_id → new_id map while renaming the nodes themselves
    id_map: dict[str, str] = {}
    for node in nodes:
        old_id = node["id"]
        node_type = (node.get("data") or {}).get("type") or old_id.split("-", 1)[0]
        new_id = _new_node_id(node_type)
        id_map[old_id] = new_id
        node["id"] = new_id
        node.setdefault("data", {})["id"] = new_id

    # Rewrite edges
    for edge in edges:
        old_src = edge.get("source")
        old_tgt = edge.get("target")
        new_src = id_map.get(old_src, old_src)
        new_tgt = id_map.get(old_tgt, old_tgt)
        edge["source"] = new_src
        edge["target"] = new_tgt
        # If the handle string starts with the old node id, replace that prefix.
        # Otherwise leave it alone (older exports may omit the id prefix).
        for handle_key, new_node_id in (("sourceHandle", new_src), ("targetHandle", new_tgt)):
            h = edge.get(handle_key)
            if isinstance(h, str) and old_src and h.startswith(old_src):
                edge[handle_key] = new_node_id + h[len(old_src):]
            elif isinstance(h, str) and old_tgt and h.startswith(old_tgt):
                edge[handle_key] = new_node_id + h[len(old_tgt):]
        # Rebuild the edge id
        src_h = edge.get("sourceHandle") or ""
        tgt_h = edge.get("targetHandle") or ""
        edge["id"] = f"reactflow__edge-{new_src}{src_h}-{new_tgt}{tgt_h}"

    out["nodes"] = nodes
    out["edges"] = edges
    return out
