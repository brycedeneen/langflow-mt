from __future__ import annotations

from typing import Any

from langflow.services.deps import get_variable_service, session_scope
from lfx.services.secret_store import get_secret_store


class FlowInspectionTools:
    """Read-only inspection of the active flow's node state.

    Sibling to FlowMutationTools. Used by the assistant to surface
    field values (e.g. an endpoint a component computed) back to the
    user. For webhook api_keys, use get_webhook_credentials — they
    live in the secret store, not the node template.
    """

    def __init__(
        self,
        flow_data: dict[str, Any],
        *,
        flow_id: Any | None = None,
        org_id: Any | None = None,
        user_id: Any | None = None,
        base_url: str | None = None,
    ) -> None:
        self.flow_data = flow_data
        self.flow_id = flow_id
        self.org_id = org_id
        self.user_id = user_id
        self.base_url = base_url

    def get_node_field_value(self, node_id: str, field_name: str) -> str:
        """Return the current value of one field on one node as a string.

        Returns the string value, or a clear error string:
        - "node not found: <id>" when node_id doesn't exist.
        - "field not found on node: <name>" when field_name is absent.
        Empty values return "".
        """
        node = next((n for n in self.flow_data.get("nodes", []) if n.get("id") == node_id), None)
        if node is None:
            return f"node not found: {node_id}"
        template = node.get("data", {}).get("node", {}).get("template", {})
        if field_name not in template:
            return f"field not found on node: {field_name}"
        value = template[field_name].get("value", "")
        if value is None:
            return ""
        return str(value)

    async def get_webhook_credentials(self) -> dict[str, str]:
        """Return the webhook URL and API key for the active flow.

        Reads the api_key from the secret store at {org_id}/webhooks/{flow_id}
        (provisioned by _provision_webhook_api_key when the flow is saved).
        Returns {"endpoint": ..., "api_key": ...} on success or
        {"error": ...} when no key has been provisioned yet.
        """
        if self.org_id is None or self.flow_id is None or self.base_url is None:
            return {"error": "webhook credentials unavailable: missing flow context"}
        store = get_secret_store()
        entry = await store.get(f"{self.org_id}/webhooks/{self.flow_id}")
        if not entry or not entry.get("api_key"):
            return {
                "error": (
                    "no webhook api_key provisioned for this flow yet — make "
                    "sure an ADP Trigger or Webhook component is in the flow "
                    "and the change has been persisted"
                ),
            }
        base = self.base_url.rstrip("/")
        return {
            "endpoint": f"{base}/api/v1/webhook/{self.flow_id}",
            "api_key": entry["api_key"],
        }

    async def list_user_variables(self) -> dict[str, Any]:
        """Return the names of secret variables already stored for the user.

        Use this BEFORE asking the user for credentials — they may have
        already configured them in a previous conversation. If a name
        like ``adp_client_id`` already exists, reference it directly via
        ``set_field_value(node_id, '<field>', 'adp_client_id')`` instead
        of asking the user to re-enter the secret.

        Returns ``{"variable_names": [...]}`` (names only, never values)
        or ``{"error": ...}`` when user context is missing.
        """
        if self.user_id is None:
            return {"error": "cannot list variables: missing user context"}
        try:
            service = get_variable_service()
            async with session_scope() as session:
                names = await service.list_variables(user_id=self.user_id, session=session)
        except Exception as e:  # noqa: BLE001
            return {"error": f"failed to list variables: {e}"}
        return {"variable_names": [n for n in names if n is not None]}
