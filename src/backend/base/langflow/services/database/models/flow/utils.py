import secrets

from langflow.utils.version import get_version_info

from .model import Flow


_WEBHOOK_NODE_ID_PREFIXES: tuple[str, ...] = ("Webhook", "ADPTrigger")


def _is_webhook_like_node(node: dict) -> bool:
    node_id = node.get("id") or ""
    return any(prefix in node_id for prefix in _WEBHOOK_NODE_ID_PREFIXES)


def get_webhook_component_in_flow(flow_data: dict):
    """Get the first webhook-like component (Webhook or ADP Trigger) in flow data."""
    if "nodes" in flow_data:
        for node in flow_data.get("nodes", []):
            if _is_webhook_like_node(node):
                return node
    return None


def get_all_webhook_components_in_flow(flow_data: dict | None):
    """Get all webhook-like components (Webhook or ADP Trigger) in flow data."""
    if not flow_data:
        return []
    return [node for node in flow_data.get("nodes", []) if _is_webhook_like_node(node)]


def get_components_versions(flow: Flow):
    versions: dict[str, str] = {}
    if flow.data is None:
        return versions
    nodes = flow.data.get("nodes", [])
    for node in nodes:
        data = node.get("data", {})
        data_node = data.get("node", {})
        if "lf_version" in data_node:
            versions[node["id"]] = data_node["lf_version"]
    return versions


def get_outdated_components(flow: Flow):
    component_versions = get_components_versions(flow)
    lf_version = get_version_info()["version"]
    outdated_components = []
    for key, value in component_versions.items():
        if value != lf_version:
            outdated_components.append(key)
    return outdated_components


def generate_webhook_api_key() -> str:
    """Generate a per-flow webhook API key.

    Format: ADP-APICPRO-{48 URL-safe base64 characters}
    Provides ~256 bits of entropy.
    """
    return f"ADP-APICPRO-{secrets.token_urlsafe(36)}"
