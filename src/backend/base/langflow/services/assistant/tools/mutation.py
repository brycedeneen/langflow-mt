"""Flow mutation tools -- modify a flow's data dict in-place.

``FlowMutationTools`` operates on the raw ``data`` JSON of a flow
(containing ``nodes``, ``edges``, ``viewport``).  Every mutation
returns a structured *patch* dict that the caller can stream to the
frontend as a ``flow_patch`` SSE event.

The class does **not** persist changes; the caller is responsible for
writing the updated ``flow_data`` back to the database.
"""

from __future__ import annotations

import copy
from typing import Any
from uuid import UUID, uuid4

from langflow.agentic.utils.component_search import get_component_by_name
from langflow.services.deps import get_variable_service, session_scope


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
        user_id: Optional user UUID. Required for tools that touch
            user-scoped state (e.g. ``create_secret_variable``).
        org_id: Optional organization UUID for multi-tenant scoping.
            Forwarded to the variable service when present.
    """

    def __init__(
        self,
        flow_data: dict[str, Any],
        *,
        user_id: UUID | str | None = None,
        org_id: UUID | str | None = None,
    ) -> None:
        self.flow_data = flow_data
        self.user_id = user_id
        self.org_id = org_id

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _find_node(self, node_id: str) -> dict | None:
        for node in self.flow_data["nodes"]:
            if node["id"] == node_id:
                return node
        return None

    @staticmethod
    def _encode_handle(obj: dict) -> str:
        """Encode a handle dict as an œ-delimited JSON string (frontend convention)."""
        import json

        return json.dumps(obj, separators=(",", ":")).replace('"', "\u0153")

    def _build_source_handle(self, node: dict, output_name: str) -> str:
        data = node.get("data", {})
        output_def = self._get_output_def(node, output_name)
        return self._encode_handle({
            "dataType": data.get("type", ""),
            "id": node["id"],
            "name": output_name,
            "output_types": output_def.get("types", []),
        })

    def _build_target_handle(self, node: dict, field_name: str) -> str:
        data = node.get("data", {})
        field = data.get("node", {}).get("template", {}).get(field_name, {})
        return self._encode_handle({
            "fieldName": field_name,
            "id": node["id"],
            "inputTypes": field.get("input_types", []),
            "type": field.get("type", "other"),
        })

    @staticmethod
    def _get_output_def(node: dict, output_name: str) -> dict:
        outputs = node.get("data", {}).get("node", {}).get("outputs", [])
        for o in outputs:
            if isinstance(o, dict) and o.get("name") == output_name:
                return o
        return {}

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

    async def add_component(
        self,
        component_type: str,
        position: dict | str | None = "auto",
        initial_fields: dict | None = None,
    ) -> dict[str, Any]:
        """Add a generic component node to the flow.

        Looks up the full component schema from the catalog so the node
        has all required metadata (display_name, template, outputs, etc.)
        that the frontend needs to render it.

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

        schema = await get_component_by_name(component_type, fields=None)

        if schema is not None:
            node_data = copy.deepcopy(schema)
            template = node_data.pop("template", {})
            outputs = node_data.pop("outputs", [])
            output_types = node_data.pop("output_types", [])
            node_data.pop("name", None)
            node_data.pop("type", None)
            if initial_fields:
                for field_name, value in initial_fields.items():
                    if field_name in template:
                        template[field_name]["value"] = value
                    else:
                        template[field_name] = {"type": "str", "value": value}
            node: dict[str, Any] = {
                "id": node_id,
                "type": "genericNode",
                "position": pos,
                "data": {
                    "type": component_type,
                    "id": node_id,
                    "node": {
                        **node_data,
                        "template": template,
                        "outputs": outputs,
                    },
                    "output_types": output_types,
                },
            }
        else:
            template: dict[str, Any] = {}
            if initial_fields:
                for field_name, value in initial_fields.items():
                    template[field_name] = {"type": "str", "value": value}
            node = {
                "id": node_id,
                "type": "genericNode",
                "position": pos,
                "data": {
                    "type": component_type,
                    "id": node_id,
                    "node": {
                        "display_name": component_type,
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

    async def create_secret_variable(self, name: str, value: str) -> dict[str, Any]:
        """Create a user-scoped secret variable in the variable store.

        Use this BEFORE ``set_field_value`` when the target field is a
        ``SecretStrInput`` (password, api_key, token). At runtime the
        framework treats those stored strings as variable *names* to
        look up — not literals — so the assistant must register the
        secret here and then write the variable name into the field.

        Returns a dict with ``variable_name`` and a ``next_step`` string
        spelling out the required follow-up call. Errors return
        ``{"error": ...}``. The underlying ``VariableService`` encrypts
        the value at rest for ``CREDENTIAL_TYPE`` (the default).
        """
        if self.user_id is None:
            return {"error": "cannot create secret variable: missing user context"}
        try:
            service = get_variable_service()
            async with session_scope() as session:
                await service.create_variable(
                    user_id=self.user_id,
                    name=name,
                    value=value,
                    session=session,
                    organization_id=self.org_id,
                )
        except Exception as e:  # noqa: BLE001
            return {"error": f"failed to create secret variable: {e}"}
        return {
            "variable_name": name,
            "next_step": (
                f"You MUST now call set_field_value(node_id, '<password_field_name>', '{name}') "
                "to wire this variable into the component. The variable is created but the "
                "component's field is still empty until you do this. Use the same node_id you "
                f"got from add_component, the field name from the schema (e.g. 'password'), and "
                f"'{name}' as the value."
            ),
        }

    def connect_edge(
        self,
        source_node_id: str,
        source_output: str,
        target_node_id: str,
        target_input: str,
    ) -> dict[str, Any]:
        """Create an edge between two existing nodes.

        Builds properly encoded handle objects that the frontend expects
        (œ-delimited JSON), using node metadata from the flow data.

        Raises:
            ValueError: If either node does not exist.
        """
        source_node = self._find_node(source_node_id)
        if source_node is None:
            msg = f"Source node not found: {source_node_id}"
            raise ValueError(msg)
        target_node = self._find_node(target_node_id)
        if target_node is None:
            msg = f"Target node not found: {target_node_id}"
            raise ValueError(msg)

        source_handle = self._build_source_handle(source_node, source_output)
        target_handle = self._build_target_handle(target_node, target_input)

        edge_id = f"reactflow__edge-{source_node_id}{source_handle}-{target_node_id}{target_handle}"

        source_data = source_node.get("data", {})
        target_data = target_node.get("data", {})
        source_output_def = self._get_output_def(source_node, source_output)
        target_field = target_data.get("node", {}).get("template", {}).get(target_input, {})

        edge: dict[str, Any] = {
            "id": edge_id,
            "source": source_node_id,
            "target": target_node_id,
            "sourceHandle": source_handle,
            "targetHandle": target_handle,
            "data": {
                "sourceHandle": {
                    "dataType": source_data.get("type", ""),
                    "id": source_node_id,
                    "name": source_output,
                    "output_types": source_output_def.get("types", []),
                },
                "targetHandle": {
                    "fieldName": target_input,
                    "id": target_node_id,
                    "inputTypes": target_field.get("input_types", []),
                    "type": target_field.get("type", "other"),
                },
            },
            "animated": False,
            "className": "",
            "selected": False,
        }

        self.flow_data["edges"].append(edge)

        patch = _empty_patch()
        patch["added_edges"].append(edge)
        return {"edge_id": edge_id, "applied_patch": patch}

    async def set_field_value(
        self,
        node_id: str,
        field_name: str,
        value: Any,
    ) -> dict[str, Any]:
        """Set (or create) a template field on a node.

        For ``auto_promote`` fields (SecretStrInput / TextFileSecretInput),
        the value is treated like a manual UI paste: actual content (PEMs,
        long secrets, anything multi-line or with non-identifier chars)
        flows through to the flow-save autopromotion ladder which encrypts
        it at rest — equivalent to typing or pasting in the UI.

        The one case we reject is a *short, identifier-shaped* string that
        doesn't match an existing user-managed Variable. That shape is
        almost always a model hallucinating a variable reference (e.g.
        ``adp_client_certificate`` when the real name is
        ``adp_client_cert``), and silently promoting it as plaintext
        stores the literal name as the "secret" — producing
        "Stored — type to replace" in the UI and `[SSL] PEM lib` at
        runtime for cert/key fields.

        Raises:
            ValueError: If the node or field does not exist.
        """
        node = self._find_node(node_id)
        if node is None:
            msg = f"Node not found: {node_id}"
            raise ValueError(msg)

        template = node["data"]["node"]["template"]
        if field_name not in template:
            available = [k for k in template if not k.startswith("_") and k != "code"]
            msg = f"Field '{field_name}' not found on node {node_id}. Available fields: {available}"
            raise ValueError(msg)

        field = template[field_name]
        if field.get("auto_promote") is True and value not in (None, "") and self.user_id is not None:
            error = await self._validate_auto_promote_value(value)
            if error is not None:
                return error

        field["value"] = value

        patch = _empty_patch()
        patch["updated_nodes"].append(node)
        return {"updated_node_id": node_id, "applied_patch": patch}

    @staticmethod
    def _looks_like_variable_reference(value: str) -> bool:
        """Heuristic: is ``value`` shaped like a user-Variable name?

        User Variable names in this codebase are Python-identifier-style:
        ``adp_client_id``, ``ANTHROPIC_API_KEY``, ``assistant.api_key``,
        ``sftp_password_xyz``. They start with a letter or underscore and
        contain only letters, digits, underscores, and (rarely) dots.

        Critically they do NOT contain hyphens — which is what makes
        UUIDs (a common shape for real client_id / client_secret /
        token values, e.g. ``15de1637-327a-4f19-8b66-4c0e05756cae``)
        cleanly separable. Hyphenated values, multi-line content, and
        strings with punctuation flow through unblocked to the
        autopromotion ladder, which encrypts them at rest exactly like
        a manual UI paste.
        """
        if not value or len(value) > 64:
            return False
        if "\n" in value or "\r" in value:
            return False
        stripped = value.strip()
        if not stripped:
            return False
        # Must start with a letter or underscore (Python-identifier rule).
        # UUIDs and hex IDs that start with a digit are excluded by this.
        if not (stripped[0].isalpha() or stripped[0] == "_"):
            return False
        # Allow letters, digits, underscores, and dots ("assistant.api_key").
        # Hyphens are NOT allowed — they're the discriminator that lets
        # UUID-shaped real secret values pass through.
        return all(c.isalnum() or c in "_." for c in stripped)

    async def _validate_auto_promote_value(self, value: Any) -> dict[str, Any] | None:
        """Reject only "looks-like-a-variable-name-but-isn't" writes.

        Returns ``None`` when the value is allowed (either it matches an
        existing user Variable, or it's clearly raw secret content that
        should be auto-promoted to encrypted storage). Returns an error
        dict with ``available_user_variables`` when the value is shaped
        like a variable name but doesn't match any — so the model can
        self-correct in one retry.
        """
        if not isinstance(value, str):
            # Non-string values aren't valid variable refs; let them through
            # to the assignment so existing call sites (e.g. numeric/bool
            # auto_promote fields, if any are added later) continue to work.
            return None
        if not self._looks_like_variable_reference(value):
            # Actual secret content — paste-equivalent path. Auto-promotion
            # at flow save time will encrypt it via the secret store.
            return None
        try:
            service = get_variable_service()
            async with session_scope() as session:
                exists = await service.has_user_managed_variable(
                    name=value, user_id=self.user_id, session=session,
                )
                if exists:
                    return None
                names = await service.list_variables(
                    user_id=self.user_id,
                    session=session,
                    organization_id=self.org_id,
                )
        except Exception as e:  # noqa: BLE001
            return {"error": f"failed to validate variable name: {e}"}
        available = sorted({
            n for n in names
            if n and not n.startswith("__autosecret")
        })
        return {
            "error": (
                f"'{value}' looks like a variable name but no user Variable "
                "with that name exists. Either call create_secret_variable "
                f"first to create '{value}', use one of the available names "
                "below, or — if you meant to write the actual secret content "
                "directly — pass the real value (a PEM, a long secret, etc.) "
                "and it will be encrypted at rest just like a manual paste."
            ),
            "available_user_variables": available,
        }

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
