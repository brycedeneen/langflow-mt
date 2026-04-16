"""Flow mutation tools -- modify a flow's data dict in-place.

``FlowMutationTools`` operates on the raw ``data`` JSON of a flow
(containing ``nodes``, ``edges``, ``viewport``).  Every mutation
returns a structured *patch* dict that the caller can stream to the
frontend as a ``flow_patch`` SSE event.

The class does **not** persist changes; the caller is responsible for
writing the updated ``flow_data`` back to the database.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4


def _empty_patch() -> dict[str, list]:
    """Return a blank patch structure."""
    return {
        "added_nodes": [],
        "added_edges": [],
        "updated_nodes": [],
        "removed_ids": [],
    }


class FlowMutationTools:
    """Mutate a flow's ``data`` dict (nodes / edges) in-place.

    Args:
        flow_data: The flow's ``data`` JSON containing ``nodes``,
            ``edges``, and ``viewport``.
    """

    def __init__(self, flow_data: dict[str, Any]) -> None:
        self.flow_data = flow_data

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _find_node(self, node_id: str) -> dict | None:
        for node in self.flow_data["nodes"]:
            if node["id"] == node_id:
                return node
        return None

    def _auto_position(self) -> dict[str, float]:
        """Compute an automatic position for a new node."""
        nodes = self.flow_data["nodes"]
        if not nodes:
            return {"x": 100, "y": 200}
        rightmost_x = max(n["position"]["x"] for n in nodes)
        avg_y = sum(n["position"]["y"] for n in nodes) / len(nodes)
        return {"x": rightmost_x + 300, "y": avg_y}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_component(
        self,
        component_type: str,
        position: dict | str | None = "auto",
        initial_fields: dict | None = None,
    ) -> dict[str, Any]:
        """Add a generic component node to the flow.

        Args:
            component_type: The component type name (e.g. ``"Prompt"``).
            position: ``{"x": ..., "y": ...}`` or ``"auto"``.
            initial_fields: Optional mapping of field names to values.

        Returns:
            Dict with ``node_id`` and ``applied_patch``.
        """
        node_id = f"{component_type}-{uuid4().hex[:5]}"

        if position == "auto" or position is None:
            pos = self._auto_position()
        else:
            pos = dict(position)  # type: ignore[arg-type]

        template: dict[str, Any] = {}
        if initial_fields:
            for field_name, value in initial_fields.items():
                template[field_name] = {"type": "str", "value": value}

        node: dict[str, Any] = {
            "id": node_id,
            "type": "genericNode",
            "position": pos,
            "data": {
                "type": component_type,
                "id": node_id,
                "node": {
                    "template": template,
                    "outputs": [],
                },
                "output_types": [],
            },
        }

        self.flow_data["nodes"].append(node)

        patch = _empty_patch()
        patch["added_nodes"].append(node)
        return {"node_id": node_id, "applied_patch": patch}

    def connect_edge(
        self,
        source_node_id: str,
        source_output: str,
        target_node_id: str,
        target_input: str,
    ) -> dict[str, Any]:
        """Create an edge between two existing nodes.

        Raises:
            ValueError: If either node does not exist.
        """
        if self._find_node(source_node_id) is None:
            msg = f"Source node not found: {source_node_id}"
            raise ValueError(msg)
        if self._find_node(target_node_id) is None:
            msg = f"Target node not found: {target_node_id}"
            raise ValueError(msg)

        edge_id = f"reactflow__edge-{source_node_id}{source_output}-{target_node_id}{target_input}"

        edge: dict[str, Any] = {
            "id": edge_id,
            "source": source_node_id,
            "target": target_node_id,
            "sourceHandle": source_output,
            "targetHandle": target_input,
        }

        self.flow_data["edges"].append(edge)

        patch = _empty_patch()
        patch["added_edges"].append(edge)
        return {"edge_id": edge_id, "applied_patch": patch}

    def set_field_value(
        self,
        node_id: str,
        field_name: str,
        value: Any,
    ) -> dict[str, Any]:
        """Set (or create) a template field on a node.

        Raises:
            ValueError: If the node does not exist.
        """
        node = self._find_node(node_id)
        if node is None:
            msg = f"Node not found: {node_id}"
            raise ValueError(msg)

        template = node["data"]["node"]["template"]
        if field_name in template:
            template[field_name]["value"] = value
        else:
            template[field_name] = {"type": "str", "value": value}

        patch = _empty_patch()
        patch["updated_nodes"].append(node)
        return {"updated_node_id": node_id, "applied_patch": patch}

    def remove_component(self, node_id: str) -> dict[str, Any]:
        """Remove a node and all its connected edges.

        Raises:
            ValueError: If the node does not exist.
        """
        node = self._find_node(node_id)
        if node is None:
            msg = f"Node not found: {node_id}"
            raise ValueError(msg)

        # Collect edges to remove
        removed_edge_ids: list[str] = []
        remaining_edges: list[dict] = []
        for edge in self.flow_data["edges"]:
            if edge["source"] == node_id or edge["target"] == node_id:
                removed_edge_ids.append(edge["id"])
            else:
                remaining_edges.append(edge)

        self.flow_data["edges"] = remaining_edges
        self.flow_data["nodes"] = [n for n in self.flow_data["nodes"] if n["id"] != node_id]

        patch = _empty_patch()
        patch["removed_ids"] = [node_id, *removed_edge_ids]
        return {"removed_node_id": node_id, "applied_patch": patch}

    def add_sticky_note(
        self,
        content: str,
        position: dict | str | None = "auto",
    ) -> dict[str, Any]:
        """Add a sticky-note node to the flow.

        Args:
            content: The text content of the note.
            position: ``{"x": ..., "y": ...}`` or ``"auto"``.

        Returns:
            Dict with ``node_id`` and ``applied_patch``.
        """
        node_id = f"note-{uuid4().hex[:5]}"

        if position == "auto" or position is None:
            auto = self._auto_position()
            pos = {"x": auto["x"] - 200, "y": auto["y"] - 150}
        else:
            pos = dict(position)  # type: ignore[arg-type]

        node: dict[str, Any] = {
            "id": node_id,
            "type": "noteNode",
            "position": pos,
            "width": 300,
            "height": 200,
            "data": {
                "type": "note",
                "id": node_id,
                "node": {
                    "description": content,
                    "template": {},
                },
            },
        }

        self.flow_data["nodes"].append(node)

        patch = _empty_patch()
        patch["added_nodes"].append(node)
        return {"node_id": node_id, "applied_patch": patch}
