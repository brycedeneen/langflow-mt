"""Auto-Variable lifecycle helpers for TextFileSecretInput fields.

Hidden Variables are created per-flow-per-node-per-field so that secret content
(PEMs, API keys, service-account JSON, etc.) is encrypted at rest via Fernet
in the Variable service, not stored plaintext in the flow's `data` column.

These helpers are invoked from the flow save/delete/download endpoints.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from lfx.log.logger import logger
from pydantic import BaseModel
from sqlmodel import select

from langflow.services.variable.constants import CREDENTIAL_TYPE

if TYPE_CHECKING:
    from lfx.services.secret_store.base import SecretStore
    from sqlalchemy.ext.asyncio import AsyncSession

    from langflow.services.variable.service import VariableService


AUTOSECRET_PREFIX = "__autosecret|"


class RefusedSecretField(BaseModel):
    """A (node_id, field_name) pair whose Branch-5 plaintext write was refused
    because a different autosecret already exists in Vault.

    Surfaced on the flow save response so the UI can warn the user that an
    intentional rotation didn't take effect (the most likely culprit is
    password-manager autofill clobber, but a real rotation also lands here).
    """

    node_id: str
    field_name: str
    display_name: str | None = None


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
    organization_id: UUID,
    user_id: UUID,
    secret_store: SecretStore,
    variable_service: VariableService,
    session: AsyncSession,
) -> tuple[dict, list[RefusedSecretField]]:
    """Walk a flow's template, promote plaintext secrets into Vault, and
    rewrite the field to reference the value via a stable marker.

    ``organization_id`` is passed in by the caller (already in scope at every
    flow CRUD endpoint) rather than looked up from the Flow row, because POST
    ``/flows/`` runs promotion *before* the row is inserted — a DB lookup
    would return None and silently no-op the promotion.

    Returns ``(flow_data, refused)`` where ``refused`` lists every Branch-5
    overwrite that was refused (existing autosecret with a different value).
    Callers surface this list to the UI so a legitimate credential rotation
    that bypassed the "clear field first" path doesn't silently fail.

    Branches:
      1. Empty value, no Vault secret existing → clean save (clear the field).
      2. Empty value, Vault secret exists → preserve marker (Issue 1 fix).
      3. Already a current-format autosecret marker → passthrough.
      3b. Legacy underscore-delimited marker → clear (dev-data hygiene).
      4. User-picked user-managed Variable name → passthrough.
      5. Typed-in plaintext → write Vault, point field at marker.
         Refuses overwrite of an existing autosecret to block password-manager
         autofill clobber; pairs with the frontend autoComplete + ignore attrs.
    """
    org_id = organization_id
    refused: list[RefusedSecretField] = []

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

        # Branch 5: typed-in plaintext. Refuse overwrite of an existing
        # autosecret with a non-matching value — protects against
        # password-manager autofill clobber on flow open.
        existing = await secret_store.get(path)
        if existing and existing.get("value"):
            if existing.get("value") == value:
                field["value"] = marker
                field["load_from_db"] = True
                continue
            logger.warning(
                "auto_secrets: refusing to overwrite existing autosecret at "
                f"{path} from flow save (likely password-manager autofill). "
                "Vault payload preserved; field rewritten to marker. If this "
                "was an intentional rotation, clear the field first and re-save."
            )
            field["value"] = marker
            field["load_from_db"] = True
            display_name = field.get("display_name")
            refused.append(
                RefusedSecretField(
                    node_id=node_id,
                    field_name=field_name,
                    display_name=display_name if isinstance(display_name, str) else None,
                )
            )
            continue

        await secret_store.put(path, {"value": value})
        field["value"] = marker
        field["load_from_db"] = True

    return flow_data, refused


async def cleanup_orphaned_autosecrets(
    *,
    flow_data: dict,
    flow_id: UUID,
    organization_id: UUID,
    user_id: UUID,
    secret_store: SecretStore,
    session: AsyncSession,
) -> None:
    """Delete Vault autosecrets whose (node_id, field_name) is no longer
    present in the flow's current template."""
    org_id = organization_id
    base = f"{org_id}/flows/{flow_id}/autosecrets/"
    existing: set[tuple[str, str]] = set()
    for node_entry in await secret_store.list(base):
        if not node_entry.endswith("/"):
            # Defensive: leaf at node-id depth shouldn't exist; skip.
            continue
        node_id = node_entry.rstrip("/")
        for field_entry in await secret_store.list(f"{base}{node_id}/"):
            if field_entry.endswith("/"):
                # Defensive: sub-dir at field-name depth shouldn't exist; skip.
                continue
            existing.add((node_id, field_entry))

    current = {(node_id, field_name) for node_id, field_name, _ in _iter_promotable_fields(flow_data)}

    for node_id, field_name in existing - current:
        await secret_store.delete(f"{base}{node_id}/{field_name}")


async def delete_autosecrets_for_flow(
    *,
    flow_id: UUID,
    organization_id: UUID,
    user_id: UUID,
    secret_store: SecretStore,
    session: AsyncSession,
) -> None:
    """Delete every Vault autosecret owned by this flow. Call on flow delete."""
    org_id = organization_id
    base = f"{org_id}/flows/{flow_id}/autosecrets/"
    for node_entry in await secret_store.list(base):
        if not node_entry.endswith("/"):
            continue
        node_id = node_entry.rstrip("/")
        for field_entry in await secret_store.list(f"{base}{node_id}/"):
            if field_entry.endswith("/"):
                continue
            await secret_store.delete(f"{base}{node_id}/{field_entry}")


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
