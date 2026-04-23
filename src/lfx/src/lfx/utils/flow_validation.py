"""Shared flow validation helpers for custom component policy enforcement.

Ported from upstream PR #11893 (langflow-ai/langflow) with one behavioral
divergence for our platform-multi-tenant fork: ``validate_flow_components``
takes explicit ``allow_custom`` and ``caller_is_platform_admin`` kwargs
(both keyword-only) and short-circuits before any cache work when either
flag is set. See docs/superpowers/specs/2026-04-22-allow-custom-components-gate-design.md.

Upstream's ``check_flow_and_raise`` / ``validate_flow_for_current_settings``
and cache-loading helpers are preserved below so enforcement sites in
later tasks can reuse them if needed.
"""

from __future__ import annotations

import hashlib
import inspect
import pkgutil
from collections.abc import Mapping
from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.log.logger import logger
from lfx.utils.component_aliases import get_component_type_aliases

INITIALIZING_COMPONENT_TEMPLATES_MESSAGE = (
    "Flow build blocked: component templates are still initializing. Please try again in a few seconds."
)
SETTINGS_SERVICE_REQUIRED_MESSAGE = "Settings service must be initialized before validating flows."
MISSING_CODE_FIELD_MESSAGE = (
    "Flow build blocked: a node is missing its template code field. Custom-shaped payloads are not allowed."
)
CUSTOM_CODE_MESSAGE = (
    "Flow build blocked: custom component code is not allowed in this deployment."
)


class CustomComponentNotAllowedError(ValueError):
    """Raised when a flow fails custom-component policy validation.

    Subclasses ValueError so existing ``except ValueError`` handlers
    still catch it, but callers can catch this specifically to
    distinguish policy errors from other ValueErrors.
    """


# Backwards-compatible alias for upstream's name; some future upstream
# sync points may refer to ``CustomComponentValidationError``.
CustomComponentValidationError = CustomComponentNotAllowedError


def _compute_code_hash(code: str) -> str:
    """Compute the 12-char SHA256 prefix used by the component index."""
    return hashlib.sha256(code.encode("utf-8")).hexdigest()[:12]


def _normalize_flow_data(flow_data: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Normalize wrapped flow payloads to the raw graph data shape."""
    if flow_data is None:
        return None

    normalized: Mapping[str, Any] = flow_data
    if "data" in normalized and isinstance(normalized["data"], Mapping):
        normalized = normalized["data"]

    return normalized if isinstance(normalized, dict) else dict(normalized)


def _extract_graph_payload(graph: Any) -> Mapping[str, Any] | None:
    """Extract a graph payload from a Graph-like object for policy validation.

    Only uses ``raw_graph_data`` — the authoritative, unmodified graph
    payload stored at construction time.  We intentionally avoid falling
    back to ``graph.dump()`` because dump may omit nodes or return
    a reconstructed payload that doesn't reflect the original flow
    definition, which could silently bypass validation.
    """
    raw_graph_data = getattr(graph, "raw_graph_data", None)
    if isinstance(raw_graph_data, Mapping):
        return raw_graph_data

    return None


def _extract_flow_data(target: Mapping[str, Any] | Any | None) -> dict[str, Any] | None:
    """Normalize a flow payload or graph-like object to raw graph data."""
    if isinstance(target, Mapping) or target is None:
        return _normalize_flow_data(target)

    return _normalize_flow_data(_extract_graph_payload(target))


def collect_component_hash_lookups(
    all_types_dict: Mapping[str, Any],
) -> tuple[dict[str, set[str]], set[str]]:
    """Build code-hash lookups for components and their aliases.

    Each component type maps to a *set* of valid hashes so that
    custom components loaded from ``components_path`` can coexist
    with built-in components of the same name.
    """
    type_to_hash: dict[str, set[str]] = {}
    all_hashes: set[str] = set()

    for category_components in all_types_dict.values():
        if not isinstance(category_components, Mapping):
            continue

        for component_name, component_data in category_components.items():
            if not isinstance(component_data, Mapping):
                continue

            metadata = component_data.get("metadata")
            if not isinstance(metadata, Mapping):
                continue

            code_hash = metadata.get("code_hash")
            if not isinstance(code_hash, str) or not code_hash:
                continue

            all_hashes.add(code_hash)
            for alias in get_component_type_aliases(component_name, component_data):
                type_to_hash.setdefault(alias, set()).add(code_hash)

    return type_to_hash, all_hashes


# ---------------------------------------------------------------------------
# Shipped-component hash cache (lazy, module-local)
#
# Populated on first call by walking ``lfx.components`` (and ``langflow.components``
# if installed) and hashing ``inspect.getsource`` for every Component subclass.
# This is the authoritative set of "known shipped templates" for the gate.
#
# Fail-closed rule: if population fails (no components found), callers that
# require the cache MUST raise rather than silently accept everything.
# ---------------------------------------------------------------------------

_shipped_code_hashes: set[str] | None = None


def _iter_component_classes(package_name: str):
    """Yield every class found under ``package_name`` that looks like a Component.

    Best-effort: swallows ImportError on individual submodules so a single
    broken/optional dependency does not poison the whole cache.
    """
    try:
        package = __import__(package_name, fromlist=["__path__"])
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug(f"Could not import component package {package_name}: {exc}")
        return

    search_paths = getattr(package, "__path__", None)
    if not search_paths:
        return

    def _onerror(module_name: str) -> None:
        # Langflow's lazy __getattr__ shims may raise on missing optional deps
        # during walk_packages' internal __import__. Swallow — a single broken
        # component module must not poison the whole shipped-hash cache.
        logger.debug(f"Skipping component module {module_name} during walk (optional dep missing).")

    walker = pkgutil.walk_packages(search_paths, prefix=f"{package_name}.", onerror=_onerror)
    while True:
        try:
            module_info = next(walker)
        except StopIteration:
            break
        except Exception as exc:  # noqa: BLE001 - lazy getattr shims raise AttributeError here
            logger.debug(f"Skipping during component-package walk: {exc}")
            continue

        module_name = module_info.name
        # Skip dunder / private helpers to reduce noise
        leaf = module_name.rsplit(".", 1)[-1]
        if leaf.startswith("_"):
            continue
        try:
            module = __import__(module_name, fromlist=["*"])
        except Exception as exc:  # noqa: BLE001 - optional deps commonly raise here
            logger.debug(f"Skipping component module {module_name}: {exc}")
            continue

        for attr_name in dir(module):
            if attr_name.startswith("_"):
                continue
            try:
                attr = getattr(module, attr_name)
            except Exception:  # noqa: BLE001
                continue
            if not inspect.isclass(attr):
                continue
            # Only include classes actually defined in this module (skip re-exports)
            if getattr(attr, "__module__", None) != module_name:
                continue
            # Strict: only actual ``Component`` subclasses qualify as shipped.
            # A heuristic (name endswith "Component" or any string
            # ``name``/``display_name`` attr) would admit non-Component
            # classes whose open-source source could be copied into a
            # tenant flow's ``code.value`` to forge a matching hash.
            try:
                is_component = issubclass(attr, Component)
            except TypeError:
                # Metaclass mismatch or similar — not a Component.
                continue
            if not is_component:
                continue
            yield attr


def _populate_shipped_hashes() -> set[str]:
    """Populate and return the set of code hashes for shipped components.

    Walks ``lfx.components`` and ``langflow.components`` (if importable)
    and hashes ``inspect.getsource`` for each Component-like class.
    Result is memoized for the life of the process.
    """
    global _shipped_code_hashes  # noqa: PLW0603

    if _shipped_code_hashes is not None:
        return _shipped_code_hashes

    hashes: set[str] = set()
    seen_modules: set[str] = set()
    for package_name in ("lfx.components", "langflow.components"):
        for cls in _iter_component_classes(package_name):
            # Components are served to the frontend with template.code.value =
            # inspect.getsource(module) (Component.set_class_code), i.e. the whole
            # file including imports. Hash the same shape so non-admin builds can
            # match — class-only source would never line up with what's persisted.
            module = inspect.getmodule(cls)
            module_name = getattr(module, "__name__", None)
            if module is None or module_name in seen_modules:
                continue
            try:
                source = inspect.getsource(module)
            except (OSError, TypeError):  # pragma: no cover - defensive
                continue
            seen_modules.add(module_name)
            hashes.add(_compute_code_hash(source))

    _shipped_code_hashes = hashes
    return _shipped_code_hashes


def reset_shipped_hashes_cache() -> None:
    """Test hook: clear the lazy cache so the next call re-populates."""
    global _shipped_code_hashes  # noqa: PLW0603
    _shipped_code_hashes = None


def _get_invalid_components(
    nodes: list[dict],
    type_to_current_hash: dict[str, set[str]],
) -> tuple[list[str], list[str]]:
    """Walk nodes and classify invalid components.

    Preserved from upstream for use by ``check_flow_and_raise`` at
    enforcement sites that have already populated a typed-hash index.
    """
    blocked: list[str] = []
    outdated: list[str] = []

    for node in nodes:
        node_data = node.get("data", {})
        node_info = node_data.get("node", {})

        component_type = node_data.get("type")
        if not component_type:
            continue

        node_template = node_info.get("template", {})
        node_code_field = node_template.get("code", {})
        node_code = node_code_field.get("value") if isinstance(node_code_field, dict) else None

        if not node_code:
            continue

        display_name = node_info.get("display_name") or component_type
        node_id = node_data.get("id") or node.get("id", "unknown")
        label = f"{display_name} ({node_id})"

        expected_hashes = type_to_current_hash.get(component_type)
        if expected_hashes is None:
            blocked.append(label)
        else:
            node_hash = _compute_code_hash(node_code)
            if node_hash not in expected_hashes:
                outdated.append(label)

        flow_data = node_info.get("flow", {})
        if isinstance(flow_data, dict):
            nested_data = flow_data.get("data", {})
            nested_nodes = nested_data.get("nodes", [])
            if nested_nodes:
                nested_blocked, nested_outdated = _get_invalid_components(
                    nested_nodes,
                    type_to_current_hash,
                )
                blocked.extend(nested_blocked)
                outdated.extend(nested_outdated)

    return blocked, outdated


def code_hash_matches_any_template(code: str, all_known_hashes: set[str]) -> bool:
    """Check whether code matches any known component template hash."""
    return _compute_code_hash(code) in all_known_hashes


def check_flow_and_raise(
    flow_data: dict | None,
    *,
    allow_custom_components: bool,
    type_to_current_hash: dict[str, set[str]] | None = None,
) -> None:
    """Validate flow component code against known server templates.

    Preserved from upstream. Not the primary entry point for our fork;
    prefer :func:`validate_flow_components` which layers in the
    platform-admin bypass and uses a simpler "any known hash" matcher.
    """
    if allow_custom_components or not flow_data:
        return

    nodes = flow_data.get("nodes", [])
    if not nodes:
        return

    if type_to_current_hash is None:
        logger.error(
            "Flow validation requested but component hash lookups are not yet loaded. "
            "Blocking execution as a safety measure."
        )
        raise CustomComponentNotAllowedError(INITIALIZING_COMPONENT_TEMPLATES_MESSAGE)

    blocked, outdated = _get_invalid_components(nodes, type_to_current_hash)

    if blocked:
        blocked_names = ", ".join(blocked)
        logger.warning(f"Flow build blocked: unrecognized component code: {blocked_names}")
        message = f"Flow build blocked: custom components are not allowed: {blocked_names}"
        raise CustomComponentNotAllowedError(message)

    if outdated:
        outdated_names = ", ".join(outdated)
        logger.warning(f"Flow build blocked: outdated components must be updated: {outdated_names}")
        message = f"Flow build blocked: outdated components must be updated before running: {outdated_names}"
        raise CustomComponentNotAllowedError(message)


def get_component_hash_lookups_for_validation() -> dict[str, set[str]] | None:
    """Return the cached component hashes, building them synchronously if possible.

    Relies on ``component_cache.type_to_current_hash`` / ``all_types_dict``
    attributes. If our ``ComponentCache`` does not yet expose those fields,
    returns ``None`` (which, under ``allow_custom_components=False``, is
    the cold-cache-fail-closed signal to ``check_flow_and_raise``).
    """
    from lfx.interface.components import component_cache

    type_to_current_hash = getattr(component_cache, "type_to_current_hash", None)
    all_known_hashes = getattr(component_cache, "all_known_hashes", None)
    all_types_dict = getattr(component_cache, "all_types_dict", None)

    if type_to_current_hash is None and all_types_dict is not None:
        type_to_current_hash, all_known_hashes = collect_component_hash_lookups(all_types_dict)
        # Only write back when the cache exposes these slots.
        if hasattr(component_cache, "type_to_current_hash"):
            component_cache.type_to_current_hash = type_to_current_hash
        if hasattr(component_cache, "all_known_hashes"):
            component_cache.all_known_hashes = all_known_hashes

    return type_to_current_hash


def validate_flow_for_current_settings(target: Mapping[str, Any] | Any | None) -> None:
    """Enforce custom-component policy for a payload or graph-like object.

    Preserved from upstream for the Graph execution enforcement site that
    lands in Task 4. Reads ``allow_custom_components`` from settings. Does
    NOT consult ``caller_is_platform_admin`` — callers that need that
    bypass must use :func:`validate_flow_components` instead.
    """
    from lfx.services.deps import get_settings_service

    settings_service = get_settings_service()
    if settings_service is None:
        raise RuntimeError(SETTINGS_SERVICE_REQUIRED_MESSAGE)

    allow_custom_components = settings_service.settings.allow_custom_components
    normalized_flow_data = _extract_flow_data(target)

    # If custom components are disabled and we received a target but couldn't
    # extract any flow data from it, fail fast rather than silently skipping
    # validation — the caller passed something we can't verify.
    if not allow_custom_components and target is not None and normalized_flow_data is None:
        msg = (
            "Flow validation failed: could not extract graph data from the provided target. "
            "Ensure the flow payload or Graph object contains valid graph data."
        )
        raise CustomComponentNotAllowedError(msg)

    type_to_current_hash = get_component_hash_lookups_for_validation() if not allow_custom_components else None

    check_flow_and_raise(
        normalized_flow_data,
        allow_custom_components=allow_custom_components,
        type_to_current_hash=type_to_current_hash,
    )


async def ensure_component_hash_lookups_loaded() -> dict[str, set[str]] | None:
    """Ensure component hash lookups are available for CLI/runtime validation.

    Preserved from upstream.
    """
    from lfx.interface.components import component_cache, get_and_cache_all_types_dict
    from lfx.services.deps import get_settings_service

    settings_service = get_settings_service()
    if settings_service is None:
        raise RuntimeError(SETTINGS_SERVICE_REQUIRED_MESSAGE)

    allow_custom_components = getattr(settings_service.settings, "allow_custom_components", True)
    type_to_current_hash = getattr(component_cache, "type_to_current_hash", None)
    if not allow_custom_components and type_to_current_hash is None:
        try:
            await get_and_cache_all_types_dict(settings_service)
        except Exception as exc:
            logger.warning("Failed to populate component template hash lookups", exc_info=exc)
            raise

    return getattr(component_cache, "type_to_current_hash", None)


# ---------------------------------------------------------------------------
# Public entry point for the platform-multi-tenant fork.
# ---------------------------------------------------------------------------


def validate_flow_components(
    flow_data: Mapping[str, Any] | None,
    *,
    allow_custom: bool,
    caller_is_platform_admin: bool,
) -> None:
    """Raise ``CustomComponentNotAllowedError`` if the flow contains a node
    whose ``code`` does not match a cached component template.

    No-op when ``allow_custom`` is True or ``caller_is_platform_admin`` is True.

    Accepts either a bare flow dict (``{"nodes": [...], "edges": [...]}``) or
    a wrapped payload (``{"data": {"nodes": [...], ...}}``) — the latter is
    normalized via :func:`_normalize_flow_data` before enforcement.

    Semantics (stricter than upstream's ``check_flow_and_raise``):
    - Missing ``template.code.value`` on any node raises — we don't trust
      custom-shaped payloads to be benign.
    - Each node's code is hashed and checked against the global shipped-hash
      cache; mismatches raise.
    - Cold cache (no shipped hashes discovered) raises — fail closed.
    """
    # ADDED FOR platform-multi-tenant: single-point bypass (spec 2026-04-22).
    # MUST remain the first executable statement: a malformed ``flow_data``
    # must never blow up the admin / allow-custom path.
    if caller_is_platform_admin or allow_custom:
        return

    flow_data = _normalize_flow_data(flow_data)
    if not flow_data:
        return

    nodes = flow_data.get("nodes", [])
    if not nodes:
        return

    shipped_hashes = _populate_shipped_hashes()
    if not shipped_hashes:
        # Fail closed: if we couldn't enumerate any shipped components, we
        # cannot tell custom from shipped, so block rather than silently allow.
        logger.error(
            "Flow validation requested but shipped-component template cache is empty. "
            "Blocking execution as a safety measure."
        )
        raise CustomComponentNotAllowedError(INITIALIZING_COMPONENT_TEMPLATES_MESSAGE)

    for node in nodes:
        node_id = node.get("id", "unknown")
        node_data = node.get("data") or {}
        node_info = node_data.get("node") or {}
        template = node_info.get("template")

        # No template block at all — treat as shipped-shape with no custom code.
        # Upstream behaviour kept here; the stricter rule below catches templates
        # that exist but carry no code.
        if template is None:
            continue

        if not isinstance(template, Mapping):
            logger.warning(f"Flow validation: node {node_id} has a non-mapping template; rejecting.")
            raise CustomComponentNotAllowedError(MISSING_CODE_FIELD_MESSAGE)

        code_field = template.get("code")
        if code_field is None:
            # Stricter than upstream: refuse to let nodes hide code behind a
            # missing-field shape the walker doesn't recognise.
            logger.warning(f"Flow validation: node {node_id} has template without code field; rejecting.")
            raise CustomComponentNotAllowedError(MISSING_CODE_FIELD_MESSAGE)

        node_code = code_field.get("value") if isinstance(code_field, Mapping) else None
        if not isinstance(node_code, str) or not node_code:
            logger.warning(f"Flow validation: node {node_id} has empty/invalid code value; rejecting.")
            raise CustomComponentNotAllowedError(MISSING_CODE_FIELD_MESSAGE)

        if _compute_code_hash(node_code) not in shipped_hashes:
            logger.warning(f"Flow validation: node {node_id} code is not a known shipped component; rejecting.")
            raise CustomComponentNotAllowedError(CUSTOM_CODE_MESSAGE)

        # Recurse into nested flows embedded on the node (parity with upstream walker).
        nested_flow = node_info.get("flow")
        if isinstance(nested_flow, Mapping):
            nested_data = nested_flow.get("data")
            if isinstance(nested_data, Mapping):
                validate_flow_components(
                    dict(nested_data),
                    allow_custom=False,
                    caller_is_platform_admin=False,
                )
