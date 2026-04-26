# `/custom_component/update` RCE-surface gate

**Date:** 2026-04-26
**Phase:** Security follow-up — close the pre-run RCE surface left open after the `e4867515e` over-gate revert
**Status:** Spec — pending plan

## Goal

Gate `POST /api/v1/custom_component/update` so it cannot compile arbitrary user-supplied Python at request time when the deployment's `LANGFLOW_ALLOW_CUSTOM_COMPONENTS` flag is off and the caller is not a platform admin.

## Why

`POST /api/v1/custom_component/update` accepts any `CurrentActiveUser` and unconditionally calls `Component(_code=code_request.code)` followed by `build_custom_component_template(...)`. That second call **compiles and imports** the user-supplied Python source as part of the dynamic-field-refresh flow. On `platform-multi-tenant` (our effective main, multi-tenant by default), every authenticated tenant — including stolen-credential or compromised-token attackers — has a pre-run RCE primitive against shared infrastructure.

A previous attempt to close this (`e4867515e`, "require superuser for custom component endpoints") was reverted the same day because the endpoint is the hot path for normal-user UI: every dynamic-field-refresh hits it. Specifically:

- `src/frontend/src/controllers/API/queries/nodes/use-refresh-model-inputs.ts:230` — Agent model dropdown refresh.
- `src/frontend/src/controllers/API/queries/nodes/use-post-template-value.ts:58` — every template value write.

Superuser-gating broke those flows with 403s for normal users. The proper fix has to *narrow* what the endpoint compiles when the gate is closed, not block the endpoint outright.

Threat model: equivalent to CVE-2026-33873 (Agentic Assistant Validation RCE), already mitigated in `validate_component_code` at `src/backend/base/langflow/agentic/helpers/validation.py:72` via the same `resolve_component_gate_flags` pattern this spec adopts. This work closes a sibling surface that the original CVE patch missed.

## Scope

In:
- Modify `POST /api/v1/custom_component/update` handler at `src/backend/base/langflow/api/v1/endpoints.py:1177-1244` to read gate flags and use canonical server-side code when the gate is closed.
- Add a small helper that looks up canonical component source by `template._type` from the in-memory `all_types_dict` registry.
- Three regression tests under `src/backend/tests/unit/api/v1/`.
- Flip the `/custom_component/update` follow-up in `docs/superpowers/followups.md` (lines ~158-166) from `[ ]` to `[x]` with a RESOLVED-by-commit reference.

Out:
- The sibling `POST /api/v1/custom_component` endpoint — already correctly gated on `get_current_active_superuser` (only invoked from the platform-admin-restricted Code-paste validator). Untouched.
- Frontend changes. The frontend already sends `template` (which carries `_type`) in every request. The fix is purely server-side.
- A schema-level requirement for `_type` on `template`. The handler does the runtime check. The schema stays a permissive `dict` so gate-open requests aren't forced to validate.
- Audit of `template._type` spoofing for privilege escalation. The lookup returns *registered* canonical code only — a spoofed `_type` swaps which canonical compiles, not which attacker code compiles. Same surface as opening the registered component in the canvas; no escalation.
- The other security follow-ups in `followups.md` (custom-components gate Task 12 manual verification, multi-tenant migration drift, `_new_flow` folder fallback bug, six failing tests in `test_templates_endpoints.py`, T2 regression test, `update_template` PUT). Each warrants its own slice.
- Performance optimization of `get_and_cache_all_types_dict` cache reads on the dynamic-field-refresh hot path. Captured as a risk; verify post-merge.

## Design

### Gate-flag resolution at the handler

Read flags via the existing `resolve_component_gate_flags` (`src/backend/base/langflow/api/utils/core.py:240`):

```python
allow_custom, is_platform_admin = resolve_component_gate_flags(user)
gate_open = allow_custom or is_platform_admin
```

`gate_open=True` means the deployment opted in via `LANGFLOW_ALLOW_CUSTOM_COMPONENTS=true` OR the caller has `is_platform_admin=True`. In either case, the user is authorized to run arbitrary code; existing behavior is preserved.

`gate_open=False` is the multi-tenant default. The handler must NOT compile `code_request.code`.

### Canonical-code lookup helper

```python
async def _resolve_canonical_component_code(component_type: str) -> str | None:
    """Return canonical Python source for a registered component type, or None if not registered.

    Reads from the cached all_types_dict populated at startup by
    `get_and_cache_all_types_dict`. The first call after server boot may
    block briefly while the cache is built; subsequent calls are O(1).
    """
    settings = get_settings_service()
    telemetry = get_telemetry_service()
    all_types = await get_and_cache_all_types_dict(settings, telemetry)
    for category in all_types.values():
        component = category.get(component_type)
        if component is None:
            continue
        # `template.code.value` is the canonical Python source string.
        return component.get("template", {}).get("code", {}).get("value")
    return None
```

**Verification during plan execution:** confirm the actual key path in `all_types_dict` for canonical code. The shape `template.code.value` is the standard pattern, but the implementer should `print` one entry during local dev to be certain before committing. If the actual shape differs, adjust the helper accordingly.

Place the helper in `src/backend/base/langflow/api/v1/endpoints.py` near the handler (private to the module). If a similar lookup helper already exists elsewhere (e.g., `src/lfx/src/lfx/interface/components.py`), reuse it instead of duplicating.

### Handler shape

```python
@router.post("/custom_component/update", status_code=HTTPStatus.OK, include_in_schema=False)
async def custom_component_update(
    code_request: UpdateCustomComponentRequest,
    user: CurrentActiveUser,
):
    allow_custom, is_platform_admin = resolve_component_gate_flags(user)
    gate_open = allow_custom or is_platform_admin

    if gate_open:
        code = code_request.code
    else:
        component_type = (
            code_request.template.get("_type")
            if isinstance(code_request.template, dict)
            else None
        )
        if not component_type:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Component type identifier ('template._type') is required "
                    "when LANGFLOW_ALLOW_CUSTOM_COMPONENTS is disabled."
                ),
            )
        canonical_code = await _resolve_canonical_component_code(component_type)
        if canonical_code is None:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Custom component type '{component_type}' is not registered; "
                    "cannot update without LANGFLOW_ALLOW_CUSTOM_COMPONENTS or "
                    "platform-admin privileges."
                ),
            )
        code = canonical_code

    try:
        component = Component(_code=code)
        component_node, cc_instance = build_custom_component_template(
            component,
            user_id=user.id,
        )

        component_node["tool_mode"] = code_request.tool_mode

        if hasattr(cc_instance, "set_attributes"):
            template = code_request.get_template()
            params = {}
            for key, value_dict in template.items():
                if isinstance(value_dict, dict):
                    value = value_dict.get("value")
                    input_type = str(value_dict.get("_input_type"))
                    params[key] = parse_value(value, input_type)

            load_from_db_fields = [
                field_name
                for field_name, field_dict in template.items()
                if isinstance(field_dict, dict)
                and field_dict.get("load_from_db")
                and field_dict.get("value")
            ]
            if isinstance(cc_instance, Component):
                params = await update_params_with_load_from_db_fields(
                    cc_instance, params, load_from_db_fields
                )
                cc_instance.set_attributes(params)
        updated_build_config = code_request.get_template()
        await update_component_build_config(
            cc_instance,
            build_config=updated_build_config,
            field_value=code_request.field_value,
            field_name=code_request.field,
        )
        if "code" not in updated_build_config or not updated_build_config.get("code", {}).get("value"):
            updated_build_config = add_code_field_to_build_config(updated_build_config, code)
        component_node["template"] = updated_build_config

        if isinstance(cc_instance, Component):
            await cc_instance.run_and_validate_update_outputs(
                frontend_node=component_node,
                field_name=code_request.field,
                field_value=code_request.field_value,
            )

    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        return jsonable_encoder(component_node)
    except Exception as exc:
        raise SerializationError.from_exception(exc, data=component_node) from exc
```

**Note:** the only behavioral changes vs. the current handler are the four-line gate block at the top and substituting `code` for `code_request.code` in the `Component(...)` and `add_code_field_to_build_config(...)` calls. Everything else is byte-identical.

### Tests

All in `src/backend/tests/unit/api/v1/test_custom_component_update_gate.py` (new file):

1. **`test_canonical_code_used_when_gate_closed`**
   - Settings: `allow_custom_components=False`. User: regular `CurrentActiveUser`, not platform admin.
   - Request body: `template._type = "<known-registered-type>"`, `code = "class Attacker(Component):\n    def build(self): __import__('os').system('echo PWNED > /tmp/PWNED')"`.
   - Assert: response is `HTTPStatus.OK`. Response body's compiled component reflects the canonical code (e.g., a known input/output structure for the registered type), NOT the attacker class.
   - Side-effect assert: `/tmp/PWNED` does not exist after the call (the attacker code never executed).

2. **`test_400_when_template_type_missing_and_gate_closed`**
   - Settings: `allow_custom_components=False`. User: regular.
   - Request body: `template = {}` (no `_type`).
   - Assert: 400 with the missing-identifier detail message.

3. **`test_403_when_template_type_unknown_and_gate_closed`**
   - Settings: `allow_custom_components=False`. User: regular.
   - Request body: `template._type = "ComponentTypeThatDoesNotExist"`.
   - Assert: 403 with the unknown-type detail message.

4. **`test_user_code_used_when_platform_admin`** + **`test_user_code_used_when_global_flag_open`**
   - Two cases:
     - `allow_custom_components=False` + user `is_platform_admin=True`.
     - `allow_custom_components=True` + user not platform admin.
   - In both: request body includes a small but recognizable `code` payload (e.g., a class with a unique input name `_unique_marker_input`).
   - Assert: response 200, response body's `template` carries the `_unique_marker_input`, proving the user's code (not canonical) was compiled.

Follow the patterns in existing security tests under `src/backend/tests/unit/api/v1/` — look at `test_create_flow_accepts_custom_component_for_platform_admin` (referenced in the followup) for the fixture style.

### Followup-doc flip

After commit, flip the entry at lines ~158-166 in `docs/superpowers/followups.md`:

- Section heading `## 2026-04-23 — `/custom_component/update` RCE surface still ungated` stays for historical context.
- Change all three sub-bullets from `- [ ]` to `- [x] **RESOLVED (2026-04-26 by <SHA>):**` followed by a one-sentence summary referring to this spec.

### Frontend impact

Verified: zero changes required. Both consumer hooks (`use-refresh-model-inputs.ts:230`, `use-post-template-value.ts:58`) already send the full `template` object including `_type`. The gate-closed code path is invisible to the caller — they receive the same response shape.

### Commit plan

1. **`feat(security): gate /custom_component/update against arbitrary code compilation`** — handler change + helper + 3 regression tests.
2. **`docs: flip /custom_component/update RCE followup`** — followups.md.

(Could combine into one if executor prefers — they're tightly coupled.)

## Risks

- **Hot-path latency.** `get_and_cache_all_types_dict` is async and may block on first call after server warm-up. Mitigation: the cache is populated at startup (`main.py:199`), so the first request after warm-up should hit a populated cache. Verify via timing during manual verification (open the Agent model dropdown a few times; latency should match pre-gate baseline).
- **Cache miss during warm-up.** A request that hits before startup populates the cache will see `None` from the lookup and 403. Acceptable — the user can retry; this matches the same warm-up window all other endpoints have.
- **Spoofed `template._type`.** A user could submit a `_type` for a different registered component than the one they intend to update. The lookup returns canonical code for the spoofed type, not user code, so this isn't an RCE. It might cause a confusing field-update result (the wrong canonical compiles). Acceptable — same surface as opening any registered component in the canvas.
- **`Component` import cost when canonical lookup falls back to a heavy component.** Canonical components import their full module tree. Same cost as the current request when the user submitted that component's code; not new.
- **Schema validation.** `template` stays a permissive `dict`. A pydantic-level `_type: str` requirement would break gate-open callers that don't bother to populate `_type`. Out of scope.

## References

- Vulnerable handler: `src/backend/base/langflow/api/v1/endpoints.py:1177-1244`.
- Sibling correctly-gated handler: `src/backend/base/langflow/api/v1/endpoints.py:1155-1174` (`POST /custom_component`).
- Gate primitive: `resolve_component_gate_flags` at `src/backend/base/langflow/api/utils/core.py:240`.
- Existing gate consumer (CVE-2026-33873 mitigation): `validate_component_code` at `src/backend/base/langflow/agentic/helpers/validation.py:72`.
- Canonical-code source: `get_and_cache_all_types_dict` (`src/lfx/src/lfx/interface/components.py`), populated at `src/backend/base/langflow/main.py:199`.
- Hot-path callers: `src/frontend/src/controllers/API/queries/nodes/use-refresh-model-inputs.ts:230`, `src/frontend/src/controllers/API/queries/nodes/use-post-template-value.ts:58`.
- Followup entries: `docs/superpowers/followups.md` lines ~158-166 (and the standing-context note at line ~130 about `update_template` PUT — out of scope here, separate slice).
- Reverted over-gate commit (the cautionary tale): `e4867515e`.
