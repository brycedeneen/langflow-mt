"""Consolidated talent/associate-KSAOC tools — module-level builder.

Backs 7 ADP WFN talent tiles that share an identical shape — one entity type
each (certifications, competencies, educational-degrees, languages, licenses,
memberships, recognitions) with a list+detail read plus add/change/remove
mutations.

Exposes 2 tools only:

- `get_associate_ksaoc_entries` — kind-aware read (list + detail consolidated)
- `manage_associate_ksaoc_entry` — kind-aware write, consolidates add/change/remove
  (gated behind `enable_mutations`).

Both tools take a `kind` Literal to pick which talent entity type to operate on.
The write tool uses a `fields: dict` escape hatch for the entity payload since
each kind has its own divergent field set; the tool description enumerates the
supported fields per kind so an agent can populate correctly.
"""

from __future__ import annotations

from typing import Any, Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from lfx.components.adp._shared import (
    HTTP_CLIENT_ERROR_MIN,
    HTTP_UNAUTHORIZED,
    ADPConnection,
    RequestCache,
    build_mtls_httpx_client,
    fetch_token,
    validate_adp_url,
)
from lfx.field_typing import Tool  # noqa: TC001 — runtime return annotation used by LangFlow registry

TalentKind = Literal[
    "certification",
    "competency",
    "educational_degree",
    "language",
    "license",
    "membership",
    "recognition",
]

TalentAction = Literal["add", "change", "remove"]


# kind → (list path segment, entity key in eventContext/transform, event-prefix slug)
_KIND_META: dict[str, dict[str, str]] = {
    "certification": {
        "list_segment": "associate-certifications",
        "entity_key": "associateCertification",
        "event_slug": "associate.ksaoc.certification",
    },
    "competency": {
        "list_segment": "associate-competencies",
        "entity_key": "associateCompetency",
        "event_slug": "associate.ksaoc.competency",
    },
    "educational_degree": {
        "list_segment": "associate-educational-degrees",
        "entity_key": "associateEducationalDegree",
        "event_slug": "associate.ksaoc.educational-degree",
    },
    "language": {
        "list_segment": "associate-languages",
        "entity_key": "associateLanguage",
        "event_slug": "associate.ksaoc.language",
    },
    "license": {
        "list_segment": "associate-licenses",
        "entity_key": "associateLicense",
        "event_slug": "associate.ksaoc.license",
    },
    "membership": {
        "list_segment": "associate-memberships",
        "entity_key": "associateMembership",
        "event_slug": "associate.ksaoc.membership",
    },
    "recognition": {
        "list_segment": "associate-recognitions",
        "entity_key": "associateRecognition",
        "event_slug": "associate.ksaoc.recognition",
    },
}

SERVICE_CATEGORY_CODE = "workerTalentManagement"


def _kind_meta(kind: str) -> dict[str, str]:
    try:
        return _KIND_META[kind]
    except KeyError as err:
        msg = f"Unknown talent kind {kind!r}; supported: {sorted(_KIND_META)}"
        raise ValueError(msg) from err


def read_path(kind: str, *, associate_oid: str, item_id: str | None = None) -> str:
    meta = _kind_meta(kind)
    base = f"/talent/v2/associates/{associate_oid}/{meta['list_segment']}"
    if item_id:
        return f"{base}/{item_id}"
    return base


def event_path(kind: str, action: str) -> str:
    meta = _kind_meta(kind)
    return f"/events/talent/v1/{meta['event_slug']}.{action}"


def build_ksaoc_event(
    *,
    kind: str,
    action: TalentAction,
    associate_oid: str,
    fields: dict[str, Any] | None = None,
    item_id: str | None = None,
    context_pin_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    meta = _kind_meta(kind)
    entity_key = meta["entity_key"]
    event_slug = meta["event_slug"]

    event_context: dict[str, Any] = {"associateOID": associate_oid}

    # change and remove need to pin the entity in eventContext — itemID and/or
    # a few key fields identify the row; default to itemID when caller provides it.
    if action in ("change", "remove"):
        entity_ctx: dict[str, Any] = {}
        if item_id:
            entity_ctx["itemID"] = item_id
        if context_pin_fields:
            entity_ctx.update(context_pin_fields)
        if action == "remove" and not entity_ctx:
            msg = "'remove' action requires item_id or context_pin_fields"
            raise ValueError(msg)
        if entity_ctx:
            event_context[entity_key] = entity_ctx

    data: dict[str, Any] = {"eventContext": event_context}
    # add and change carry the entity payload in transform; remove doesn't (the
    # eventContext alone identifies what to remove).
    if action in ("add", "change"):
        data["transform"] = {entity_key: dict(fields or {})}

    event: dict[str, Any] = {
        "data": data,
        "actor": {"associateOID": associate_oid},
        "serviceCategoryCode": {"codeValue": SERVICE_CATEGORY_CODE},
        "eventNameCode": {"codeValue": f"{event_slug}.{action}"},
    }
    return {"events": [event]}


class GetAssociateKsaocEntriesInput(BaseModel):
    kind: TalentKind = Field(
        description=(
            "Which talent entity to list: 'certification', 'competency', 'educational_degree', "
            "'language', 'license', 'membership', or 'recognition'."
        ),
    )
    associate_oid: str = Field(description="ADP associate OID of the worker.")
    item_id: str | None = Field(
        default=None,
        description="Specific entity ID to fetch; omit to list all entries for the worker.",
    )
    filter: str | None = Field(
        default=None,
        alias="$filter",
        description="Optional OData $filter. Only applies when listing (item_id omitted).",
    )
    skip: int | None = Field(default=None, alias="$skip", description="OData $skip.")
    top: int | None = Field(default=None, alias="$top", description="OData $top.")

    model_config = {"populate_by_name": True}


class ManageAssociateKsaocEntryInput(BaseModel):
    kind: TalentKind = Field(
        description=(
            "Which talent entity to operate on — see `get_associate_ksaoc_entries` for the list. "
            "Determines the event endpoint and transform key used."
        ),
    )
    action: TalentAction = Field(
        description="Event to fire: 'add' (new entry), 'change' (update), or 'remove'.",
    )
    associate_oid: str = Field(description="ADP associate OID of the worker.")
    item_id: str | None = Field(
        default=None,
        description=(
            "Entity itemID (from a prior list call). Required for 'remove'; required for "
            "'change' unless `context_pin_fields` identifies the row some other way."
        ),
    )
    fields: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Entity payload for 'add'/'change'. Supported fields per kind (pass nested ADP "
            "code/amount/date objects verbatim):\n"
            "- certification: certificationNameCode, certificationID, categoryCode, issuingParty, "
            "firstIssueDate, lastIssueDate, expirationDate, employerPaidAmount, comments, renewalComments.\n"
            "- competency: competencyNameCode, competencyDescription, categoryCode, acquisitionDate, "
            "lastUsedDate, experienceDuration, hasCompetencyIndicator, selfAssessedProficiencyScore, "
            "competencyDimensions, comments.\n"
            "- educational_degree: nameCode, typeCode, statusCode, startDate, expectedCompletionDate, "
            "actualCompletionDate, completionDuration, majorProgramNameCodes, minorProgramNameCodes, "
            "honorsProgramNameCodes, educationalInstitutionAttendances, academicScore, verificationDate, "
            "comments, employerPaidAmount.\n"
            "- language: languageCode, nativeLanguageIndicator, acquisitionDate, lastUsedDate, "
            "experienceDuration, selfAssessedProficiencyScore, hasCompetencyIndicator.\n"
            "- license: licenseNameCode, licenseID, categoryCode, issuingParty, firstIssueDate, "
            "expirationDate, employerPaidAmount, comments, renewalComments.\n"
            "- membership: membershipOrganization, typeCode, memberTitle, memberSinceDate, "
            "expirationDate, membershipID, employerPaidAmount, comments, issuingParty.\n"
            "- recognition: nameCode, typeCode, issuingParty, issueDate."
        ),
    )
    context_pin_fields: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Fields to pin the entity in eventContext on 'change'/'remove' when itemID isn't used "
            "(e.g. a natural-key lookup). Merged into the entity-level eventContext alongside itemID."
        ),
    )


async def _call_talent(
    conn: ADPConnection,
    *,
    method: str,
    path: str,
    params: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"{conn.api_base_url}{path}"
    validate_adp_url(url, field_name="api_base_url")
    headers = {"Authorization": f"Bearer {conn.access_token}"}

    async with build_mtls_httpx_client(conn, timeout=30.0) as client:
        response = await client.request(
            method=method, url=url, headers=headers, params=params, json=body, timeout=30.0,
        )
        if response.status_code == HTTP_UNAUTHORIZED:
            await fetch_token(conn, force=True)
            headers["Authorization"] = f"Bearer {conn.access_token}"
            response = await client.request(
                method=method, url=url, headers=headers, params=params, json=body, timeout=30.0,
            )

    if response.status_code >= HTTP_CLIENT_ERROR_MIN:
        try:
            detail = response.json()
        except ValueError:
            detail = response.text
        return {"error": detail, "status_code": response.status_code}
    try:
        return response.json()
    except ValueError:
        return {"ok": True, "status_code": response.status_code}


async def _post_event(conn: ADPConnection, *, path: str, body: dict[str, Any]) -> dict[str, Any]:
    return await _call_talent(conn, method="POST", path=path, body=body)


def build_talent_tools(
    connection: ADPConnection,
    request_cache: RequestCache,  # noqa: ARG001 — accepted for registry uniformity; unused (all calls are un-cached)
    *,
    enable_mutations: bool = False,
) -> list[Tool]:
    conn = connection

    async def _get_associate_ksaoc_entries(**kwargs: Any) -> dict[str, Any]:
        kind = kwargs["kind"]
        associate_oid = kwargs["associate_oid"]
        item_id = kwargs.get("item_id")
        path = read_path(kind, associate_oid=associate_oid, item_id=item_id)
        params: dict[str, Any] = {}
        if not item_id:
            for source_key, api_key in (("filter", "$filter"), ("skip", "$skip"), ("top", "$top")):
                val = kwargs.get(source_key)
                if val is not None:
                    params[api_key] = val
        return await _call_talent(conn, method="GET", path=path, params=params or None)

    tools: list[Tool] = [
        StructuredTool.from_function(
            name="get_associate_ksaoc_entries",
            description=(
                "Get a worker's talent/KSAOC entries for the selected kind "
                "(certification, competency, educational_degree, language, license, "
                "membership, recognition). If item_id is provided, fetches one; otherwise "
                "lists with optional OData $filter/$skip/$top. Each entry includes an "
                "itemID you can pass to `manage_associate_ksaoc_entry`."
            ),
            coroutine=_get_associate_ksaoc_entries,
            args_schema=GetAssociateKsaocEntriesInput,
        ),
    ]

    if not enable_mutations:
        return tools

    async def _manage_associate_ksaoc_entry(**kwargs: Any) -> dict[str, Any]:
        kind = kwargs["kind"]
        action = kwargs["action"]
        try:
            body = build_ksaoc_event(
                kind=kind,
                action=action,
                associate_oid=kwargs["associate_oid"],
                fields=kwargs.get("fields") or {},
                item_id=kwargs.get("item_id"),
                context_pin_fields=kwargs.get("context_pin_fields") or {},
            )
        except ValueError as err:
            return {"error": str(err), "status_code": 422}
        return await _post_event(conn, path=event_path(kind, action), body=body)

    tools.append(
        StructuredTool.from_function(
            name="manage_associate_ksaoc_entry",
            description=(
                "Add, change, or remove a worker's talent/KSAOC entry for the selected kind. "
                "For 'add': populate `fields` with the entity payload (per-kind field list in "
                "the input schema). For 'change': pass `item_id` + changed `fields`. For "
                "'remove': pass `item_id` (or `context_pin_fields` for natural-key pins)."
            ),
            coroutine=_manage_associate_ksaoc_entry,
            args_schema=ManageAssociateKsaocEntryInput,
        ),
    )

    return tools


# ---------------------------------------------------------------------------
# Back-compat stub — preserved for __init__.py / test_bundle_init.py imports.
# The Langflow registry uses build_talent_tools(); this class is never
# instantiated at runtime.
