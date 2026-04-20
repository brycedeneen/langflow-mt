"""Auto-Variable lifecycle helpers for TextFileSecretInput fields.

Hidden Variables are created per-flow-per-node-per-field so that secret content
(PEMs, API keys, service-account JSON, etc.) is encrypted at rest via Fernet
in the Variable service, not stored plaintext in the flow's `data` column.

These helpers are invoked from the flow save/delete/download endpoints.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from langflow.services.variable.constants import CREDENTIAL_TYPE

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from langflow.services.variable.service import VariableService


AUTOSECRET_PREFIX = "__autosecret_"


def autosecret_flow_prefix(flow_id: UUID) -> str:
    """Name prefix shared by all auto-Variables for a given flow.

    Single source of truth for both constructing a full auto-name (via
    ``autosecret_name``) and querying by LIKE-prefix in the service layer.
    """
    return f"{AUTOSECRET_PREFIX}{flow_id}_"


def autosecret_name(flow_id: UUID, node_id: str, field_name: str) -> str:
    """Deterministic name for a per-field hidden Variable."""
    return f"{autosecret_flow_prefix(flow_id)}{node_id}_{field_name}"


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
    variable_service: VariableService,
    session: AsyncSession,
) -> dict:
    """Upsert a hidden Variable for every promotable field whose value is
    typed-in plaintext; rewrite the field to reference the Variable by name.

    Preserves values that are:
    - already autosecret references (any flow_id), idempotent.
    - the name of an existing user-managed Variable (picked, not typed).

    Returns the (possibly-mutated) flow_data dict.
    """
    existing_names = set(
        await variable_service.list_autosecret_names_for_flow(
            flow_id=flow_id,
            user_id=user_id,
            session=session,
        )
    )

    for node_id, field_name, field in _iter_promotable_fields(flow_data):
        expected_name = autosecret_name(flow_id, node_id, field_name)
        value = field.get("value") or ""

        # Empty plaintext: clear any stale reference so the save is clean.
        # Orphaned autosecret Variables are garbage-collected by
        # cleanup_orphaned_autosecrets, which runs separately.
        if not value:
            field["value"] = ""
            field["load_from_db"] = False
            continue

        # Any autosecret reference (our flow_id's or a foreign one) is
        # preserved. Foreign refs (e.g. copied from another flow on import)
        # can't resolve at runtime, but the export blanker will zero them
        # out on next export — we don't re-wrap them.
        if isinstance(value, str) and value.startswith(AUTOSECRET_PREFIX):
            continue

        # User picked an existing user-managed Variable by name. Preserve.
        if await variable_service.has_user_managed_variable(
            name=value, user_id=user_id, session=session
        ):
            continue

        # Typed-in plaintext: upsert the autosecret Variable in place.
        if expected_name in existing_names:
            await variable_service.update_variable_value(
                name=expected_name,
                value=value,
                user_id=user_id,
                session=session,
            )
        else:
            await variable_service.create_variable(
                name=expected_name,
                value=value,
                user_id=user_id,
                type_=CREDENTIAL_TYPE,
                session=session,
            )
        field["value"] = expected_name
        field["load_from_db"] = True

    return flow_data


async def cleanup_orphaned_autosecrets(
    *,
    flow_data: dict,
    flow_id: UUID,
    user_id: UUID,
    variable_service: VariableService,
    session: AsyncSession,
) -> None:
    """Delete auto-Variables whose (node_id, field_name) is no longer present
    in the flow's current template.

    Called after a save to garbage-collect Variables left behind by node or
    field removals.
    """
    current_names = {
        autosecret_name(flow_id, node_id, field_name)
        for node_id, field_name, _ in _iter_promotable_fields(flow_data)
    }
    existing = await variable_service.list_autosecret_names_for_flow(
        flow_id=flow_id,
        user_id=user_id,
        session=session,
    )
    for name in existing:
        if name not in current_names:
            await variable_service.delete_variable(
                name=name,
                user_id=user_id,
                session=session,
            )


async def delete_autosecrets_for_flow(
    *,
    flow_id: UUID,
    user_id: UUID,
    variable_service: VariableService,
    session: AsyncSession,
) -> None:
    """Delete every auto-Variable owned by this flow. Call on flow delete."""
    names = await variable_service.list_autosecret_names_for_flow(
        flow_id=flow_id,
        user_id=user_id,
        session=session,
    )
    for name in names:
        await variable_service.delete_variable(
            name=name,
            user_id=user_id,
            session=session,
        )


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
