"""Auto-Variable lifecycle helpers for TextFileSecretInput fields.

Hidden Variables are created per-flow-per-node-per-field so that secret content
(PEMs, API keys, service-account JSON, etc.) is encrypted at rest via Fernet
in the Variable service, not stored plaintext in the flow's `data` column.

These helpers are invoked from the flow save/delete/download endpoints.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlmodel import select

from langflow.services.variable.constants import CREDENTIAL_TYPE

if TYPE_CHECKING:
    from lfx.services.secret_store.base import SecretStore
    from sqlalchemy.ext.asyncio import AsyncSession

    from langflow.services.variable.service import VariableService


AUTOSECRET_PREFIX = "__autosecret|"


def autosecret_flow_prefix(flow_id: UUID) -> str:
    """Name prefix shared by all legacy auto-Variables for a given flow.

    Retained for the Variable-service code path that still scans Postgres for
    pre-Vault rows; new writes use ``autosecret_vault_path``.
    """
    return f"{AUTOSECRET_PREFIX}{flow_id}_"


LEGACY_AUTOSECRET_PREFIX = "__autosecret_"
AUTOSECRET_DELIM = "|"
NEW_AUTOSECRET_PREFIX = "__autosecret" + AUTOSECRET_DELIM


def autosecret_marker(flow_id: UUID, node_id: str, field_name: str) -> str:
    """Build the marker stored in `field["value"]` for an autosecret-backed field."""
    return AUTOSECRET_DELIM.join(
        ["__autosecret", str(flow_id), node_id, field_name]
    )


def autosecret_vault_path(
    org_id: UUID, flow_id: UUID, node_id: str, field_name: str
) -> str:
    """Vault KV v2 path for a per-field autosecret."""
    return f"{org_id}/flows/{flow_id}/autosecrets/{node_id}/{field_name}"


def parse_autosecret_marker(marker: str) -> tuple[UUID, str, str]:
    """Inverse of autosecret_marker.

    Raises ValueError on malformed input. Specifically rejects the legacy
    underscore-delimited prefix; callers should treat that prefix separately
    via LEGACY_AUTOSECRET_PREFIX.
    """
    if not isinstance(marker, str) or not marker.startswith("__autosecret" + AUTOSECRET_DELIM):
        msg = f"not an autosecret marker: {marker!r}"
        raise ValueError(msg)
    parts = marker.split(AUTOSECRET_DELIM)
    if len(parts) != 4:
        msg = f"autosecret marker has wrong segment count: {marker!r}"
        raise ValueError(msg)
    _prefix, flow_id_str, node_id, field_name = parts
    try:
        flow_id = UUID(flow_id_str)
    except ValueError as exc:
        msg = f"autosecret marker has invalid flow_id: {flow_id_str!r}"
        raise ValueError(msg) from exc
    if not node_id or not field_name:
        msg = f"autosecret marker has empty node_id or field_name: {marker!r}"
        raise ValueError(msg)
    return flow_id, node_id, field_name


async def _get_org_id_for_flow(flow_id: UUID, *, session: AsyncSession) -> UUID | None:
    """Return the organization_id of the given flow, or None if the flow row is gone.

    Defensive: never raises. Callers fall through to a no-op when None is
    returned (treat as "flow no longer exists or untracked org").
    """
    from langflow.services.database.models.flow import Flow  # local import to avoid cycle

    stmt = select(Flow.organization_id).where(Flow.id == flow_id)
    result = await session.exec(stmt)
    return result.first()


def _iter_promotable_fields(flow_data: dict) -> list[tuple[str, str, dict]]:
    """Yield (node_id, field_name, field_dict) for every field marked auto_promote=True.

    Replaces the earlier _iter_textfilesecret_fields which matched on
    _input_type name. The new predicate consults the per-field auto_promote
    flag, which SecretStrInput and its subclasses (including
    TextFileSecretInput) set to True by default. Component authors can opt
    out per field with auto_promote=False.
    """
    out: list[tuple[str, str, dict]] = []
    for node in flow_data.get("nodes", []) or []:
        if not isinstance(node, dict):
            continue
        node_id = node.get("id")
        template = node.get("data", {}).get("node", {}).get("template", {})
        if not node_id or not isinstance(template, dict):
            continue
        for field_name, field in template.items():
            if not isinstance(field, dict):
                continue
            if field.get("auto_promote") is True:
                out.append((node_id, field_name, field))
    return out


async def promote_plaintext_secrets_to_variables(
    *,
    flow_data: dict,
    flow_id: UUID,
    user_id: UUID,
    secret_store: SecretStore,
    variable_service: VariableService,
    session: AsyncSession,
) -> dict:
    """Walk a flow's template, promote plaintext secrets into Vault, and
    rewrite the field to reference the value via a stable marker.

    Branches:
      1. Empty value, no Vault secret existing → clean save (clear the field).
      2. Empty value, Vault secret exists → preserve marker (Issue 1 fix).
      3. Already a current-format autosecret marker → passthrough.
      3b. Legacy underscore-delimited marker → clear (dev-data hygiene).
      4. User-picked user-managed Variable name → passthrough.
      5. Typed-in plaintext → write Vault, point field at marker.
    """
    org_id = await _get_org_id_for_flow(flow_id, session=session)
    if org_id is None:
        return flow_data

    for node_id, field_name, field in _iter_promotable_fields(flow_data):
        marker = autosecret_marker(flow_id, node_id, field_name)
        path = autosecret_vault_path(org_id, flow_id, node_id, field_name)
        value = field.get("value") or ""

        # Branch 1 + 2: empty value
        if not value:
            existing = await secret_store.get(path)
            if existing and existing.get("value"):
                # Issue 1 fix: user re-saved without retyping; preserve.
                field["value"] = marker
                field["load_from_db"] = True
            else:
                field["value"] = ""
                field["load_from_db"] = False
            continue

        # Branch 3: current-format marker
        if isinstance(value, str) and value.startswith(AUTOSECRET_PREFIX):
            continue

        # Branch 3b: legacy marker (dev-data hygiene; no prod data exists)
        if isinstance(value, str) and value.startswith(LEGACY_AUTOSECRET_PREFIX):
            field["value"] = ""
            field["load_from_db"] = False
            continue

        # Branch 4: user-picked user-managed Variable name
        if await variable_service.has_user_managed_variable(
            name=value, user_id=user_id, session=session,
        ):
            continue

        # Branch 5: typed-in plaintext
        await secret_store.put(path, {"value": value})
        field["value"] = marker
        field["load_from_db"] = True

    return flow_data


async def _list_autosecret_paths(secret_store: SecretStore, base: str) -> list[str]:
    """Walk a Vault-style two-level prefix and return absolute paths.

    Bridges the two SecretStore contracts in play:
      * InMemorySecretStore.list(prefix) returns full absolute keys (test backend).
      * VaultSecretStore.list(prefix) returns next-level relative entries with a
        trailing ``/`` for sub-directories (KV v2 LIST semantics).

    Returns absolute paths suitable for ``secret_store.delete``.
    """
    out: list[str] = []
    for entry in await secret_store.list(base):
        if entry.startswith(base):
            # InMemory contract: list returned a full absolute key.
            out.append(entry)
        elif entry.endswith("/"):
            # Vault contract: sub-directory entry; recurse one level.
            out.extend(await _list_autosecret_paths(secret_store, base + entry))
        else:
            # Vault contract: leaf entry under this prefix.
            out.append(base + entry)
    return out


async def cleanup_orphaned_autosecrets(
    *,
    flow_data: dict,
    flow_id: UUID,
    user_id: UUID,
    secret_store: SecretStore,
    session: AsyncSession,
) -> None:
    """Delete Vault autosecrets whose (node_id, field_name) is no longer
    present in the flow's current template."""
    org_id = await _get_org_id_for_flow(flow_id, session=session)
    if org_id is None:
        return

    base = f"{org_id}/flows/{flow_id}/autosecrets/"
    existing: set[tuple[str, str]] = set()
    for path in await _list_autosecret_paths(secret_store, base):
        suffix = path[len(base):]
        node_id, _, field_name = suffix.partition("/")
        if not node_id or not field_name:
            continue
        existing.add((node_id, field_name))

    current = {(node_id, field_name) for node_id, field_name, _ in _iter_promotable_fields(flow_data)}

    for node_id, field_name in existing - current:
        await secret_store.delete(f"{base}{node_id}/{field_name}")


async def delete_autosecrets_for_flow(
    *,
    flow_id: UUID,
    user_id: UUID,
    secret_store: SecretStore,
    session: AsyncSession,
) -> None:
    """Delete every Vault autosecret owned by this flow. Call on flow delete."""
    org_id = await _get_org_id_for_flow(flow_id, session=session)
    if org_id is None:
        return

    base = f"{org_id}/flows/{flow_id}/autosecrets/"
    for path in await _list_autosecret_paths(secret_store, base):
        await secret_store.delete(path)


def blank_autosecrets_for_export(flow_data: dict) -> dict:
    """Blank the value of every TextFileSecretInput field whose value looks
    like an auto-Variable reference. User-managed Variables (without the
    auto prefix) are left untouched so exports still carry those refs.

    The returned dict may share structure with the input; callers that need
    to preserve the original should deepcopy before calling.
    """
    for _node_id, _field_name, field in _iter_promotable_fields(flow_data):
        value = field.get("value") or ""
        if isinstance(value, str) and value.startswith(AUTOSECRET_PREFIX):
            field["value"] = ""
            # Keep load_from_db=True so the importer knows this field expects
            # a secret to be supplied.
    return flow_data
