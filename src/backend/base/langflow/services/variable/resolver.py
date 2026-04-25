"""Dispatch helper for ``load_from_db`` field resolution.

Routes autosecret markers to Vault (per the new migration) and everything
else to the component's existing ``get_variable`` path (which itself layers
request-context overrides and the user-managed Variable service).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.log.logger import logger

from langflow.services.variable.auto_secrets import (
    NEW_AUTOSECRET_PREFIX,
    _get_org_id_for_flow,
    autosecret_vault_path,
    parse_autosecret_marker,
)

if TYPE_CHECKING:
    from lfx.services.secret_store.base import SecretStore
    from sqlalchemy.ext.asyncio import AsyncSession


async def resolve_secret_reference(
    *,
    custom_component,
    name: str,
    field: str,
    session: AsyncSession,
    secret_store: SecretStore,
) -> str:
    """Resolve a ``load_from_db`` reference to its plaintext value.

    Returns ``""`` for autosecret markers whose Vault path doesn't exist
    (foreign-flow marker, deleted flow, or malformed input). The component's
    own required-field validation runs after and produces a user-visible
    error in that case.

    Non-autosecret names defer to ``custom_component.get_variable``, which
    keeps the existing behavior for request-context overrides and
    user-managed Variables.
    """
    if isinstance(name, str) and name.startswith(NEW_AUTOSECRET_PREFIX):
        return await _resolve_autosecret(name=name, session=session, secret_store=secret_store)
    return await custom_component.get_variable(name=name, field=field, session=session)


async def _resolve_autosecret(
    *, name: str, session: AsyncSession, secret_store: SecretStore,
) -> str:
    try:
        flow_id, node_id, field_name = parse_autosecret_marker(name)
    except ValueError as exc:
        await logger.adebug(f"malformed autosecret marker: {exc}")
        return ""

    org_id = await _get_org_id_for_flow(flow_id, session=session)
    if org_id is None:
        await logger.adebug(f"autosecret marker references unknown flow: {flow_id}")
        return ""

    path = autosecret_vault_path(org_id, flow_id, node_id, field_name)
    payload = await secret_store.get(path)
    if not payload:
        await logger.adebug(f"autosecret missing in Vault at {path}")
        return ""
    return payload.get("value") or ""
