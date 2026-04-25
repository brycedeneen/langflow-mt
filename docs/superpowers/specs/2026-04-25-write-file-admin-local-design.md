# Write File: admin-only Local + File Location field

**Date:** 2026-04-25
**Component:** `SaveToFileComponent` (display name "Write File")
**File:** `src/lfx/src/lfx/components/files_and_knowledge/save_file.py`
**Scope:** one component file + tests. No frontend, no migration, no new settings.

## Problem

The Write File component lets any authenticated user pick `Local` as a storage destination, which writes to the Langflow server's filesystem. In a multi-tenant deployment that's a privilege a regular user shouldn't have. The existing `is_astra_cloud_environment()` check hides Local in Astra, but there's no per-user gate.

The component also conflates "where to save" with "what to call it" — `file_name` is documented as "without extension" but the implementation treats it as a full path (`Path(self.file_name).expanduser()`). For the admin-only Local flow we want an explicit, separate location field.

## Goals

1. Hide the `Local` storage option from non-admins in the Storage Location dropdown.
2. Reject `Local` at runtime if a non-admin somehow selects it (defense in depth against tampered flow JSON).
3. Add a separate "File Location" (directory) input that appears only for Local, with a sensible default so admins don't have to type a path.
4. Keep AWS S3 and Google Drive paths unchanged.

## Non-goals

- No new env vars, settings flags, or org-level permission matrix entries.
- No path-allowlist / sandboxing beyond stripping path components from `file_name`. Admins are trusted with the host filesystem.
- No frontend changes — `SortableListInput`'s `real_time_refresh=True` already triggers `update_build_config` on selection.

## Roles

`is_admin` for this component = `user.is_superuser or user.is_platform_admin`. Both flags exist on `User` (`src/backend/base/langflow/services/database/models/user/model.py:33-35`). The codebase already references both as the "admin bypass" pair (e.g. `src/backend/base/langflow/api/utils/authz.py`).

## Design

### Build-config filter (UX layer)

Convert `update_build_config` from sync to `async`. The dispatcher in `src/lfx/src/lfx/custom/utils.py:759-761` already awaits async overrides via `inspect.iscoroutinefunction`; many components in this repo use the async signature (`mcp_component.py`, `retrieval.py`, `agent.py`, etc.).

Inside the async `update_build_config`:

1. Resolve the caller's admin status:
   - If `self.user_id` is unset (e.g. unit-test path with no user context), treat as non-admin.
   - Otherwise open a session via `session_scope()` (already imported in this file) and call `get_user_by_id(db, self.user_id)` (already imported and used by `_upload_file` at line 325, 339).
   - `is_admin = bool(user and (user.is_superuser or user.is_platform_admin))`.
2. Compute the storage-location options as `_storage_location_options(is_admin=is_admin)`, a new helper replacing the module-level `_get_storage_location_options()`. Composition rules:
   - Always include AWS and Google Drive.
   - Include `Local` only if `is_admin and not is_astra_cloud_environment()`.
3. Write the filtered options back to `build_config["storage_location"]["options"]`, same as today.
4. If `Local` is the currently-selected value but is not in the filtered options (non-admin loading a flow saved by someone else, or initial render for a non-admin), reset the selected value to the first available option (AWS) so the UI doesn't show "Local selected" with no Local option visible.

The class-level `inputs = [...]` declaration keeps using the module helper for its initial seed; per-user filtering happens on the first `update_build_config` call.

### Runtime guard (security layer)

In `save_to_file`, before dispatching to `_save_to_local`, re-check the caller's admin status via the same `get_user_by_id` lookup. If the caller isn't an admin and `storage_location == "Local"`, raise `ValueError` with the existing message style:

> "Local storage is restricted to platform administrators."

Reasons we re-check at runtime instead of trusting `update_build_config`:
- The component's `storage_location` value comes from saved flow JSON, which is client-controlled.
- A non-admin could load a flow that has `Local` baked in, or hand-edit the JSON.
- Build-config is for UX, not authorization.

### File Location field

Add a new `StrInput` to the `inputs` list, placed adjacent to `file_name`:

```python
StrInput(
    name="file_location",
    display_name="File Location",
    info="Directory where the file will be saved. Defaults to the Langflow config dir's outputs/ folder if blank.",
    required=False,
    show=False,
)
```

Show rules in `update_build_config`: visible only when `storage_location == "Local"`, alongside the existing `local_format` / `append_mode` block. (`file_location` does not need to be visible for AWS or Google Drive — those already use `s3_prefix` and `folder_id`.)

Default-value resolution happens lazily inside `_save_to_local`, not at module import:

```python
location_str = (self.file_location or "").strip()
directory = (
    Path(location_str).expanduser()
    if location_str
    else Path(get_settings_service().settings.config_dir) / "outputs"
)
basename = Path(self.file_name).name  # strip any path components from filename
file_path = directory / basename
file_path = self._adjust_file_path_with_format(file_path, file_format)
if not file_path.parent.exists():
    file_path.parent.mkdir(parents=True, exist_ok=True)
```

`Path(self.file_name).name` deliberately strips directory components that an admin might paste into `file_name`. The two fields don't fight: directory comes from `file_location` only.

Update the `file_name` `info` text from `"Name file will be saved as (without extension)."` to `"File name only (no path, no extension)."` to match the new behavior.

### Why default to `<config_dir>/outputs`

`settings.config_dir` is the existing Langflow data root (referenced from `lfx/services/manager.py:139-144`). Defaulting outputs there:
- Matches the convention used by other Langflow state.
- Is admin-friendly without adding a new config knob.
- Is reachable from `get_settings_service().settings.config_dir`, which the component already touches in `_save_to_aws` (line 589).

A new `LANGFLOW_LOCAL_WRITE_DIR` env var was considered and rejected — adds a knob with no clear demand.

## Compatibility

- **Existing flows that wrote locally** (admin or not): on next save they re-evaluate. Non-admin flows with `storage_location: Local` will fail at runtime with the new error; this is the desired security behavior, and there should be no existing non-admin Local users in the multi-tenant deployment (this component was always server-disk-writing).
- **Saved `file_name` values containing paths**: those paths are now stripped to a basename. Admins who relied on `file_name="dir1/dir2/foo"` need to set `file_location="dir1/dir2"` and `file_name="foo"`. Acceptable break given the field semantics were always documented as "without extension" — the path-accepting behavior was a leak.

## Tests

Location: `src/lfx/tests/unit/components/files_and_knowledge/test_save_file.py` (create if missing; mirrors layout for adjacent components).

1. **Non-admin `update_build_config` filters Local out.** Mock `get_user_by_id` to return a user with both flags False. Assert `Local` not in `build_config["storage_location"]["options"]` names; assert default selection is no longer `Local`.
2. **Admin `update_build_config` includes Local.** `is_superuser=True` → `Local` present in options. Same for `is_platform_admin=True`.
3. **Astra + admin still hides Local.** Patch `is_astra_cloud_environment` to True; admin user. Assert `Local` not in options.
4. **Runtime guard.** Non-admin component instance with `storage_location=[{"name": "Local"}]` → `save_to_file()` raises `ValueError` containing "platform administrators".
5. **Default location resolution.** Admin component with `file_location=""` and a stub settings_service whose `config_dir` is a tmp path → file lands at `<config_dir>/outputs/<basename>.<fmt>`.
6. **Basename stripping.** Admin with `file_name="../escape/foo"` and `file_location=<tmp>` → file lands at `<tmp>/foo.<fmt>`, no traversal.
7. **`file_location` shown only for Local.** Selecting AWS or Google Drive in `update_build_config` leaves `file_location.show == False`.

Run with `LFX_TEST_ALLOW_LANGFLOW=1` from the repo-level venv (the lfx test isolation escape hatch).

## Component-version ritual

This component currently has no `_version` declaration. The langflow-component-authoring skill defines the version-bump + changelog-append ritual that the "Update components" modal surfaces to end users; the implementation plan must invoke that skill and apply whatever bump and changelog entry it prescribes for a behavior change like this. The spec does not pre-empt that ritual, but flags it as a required step.

## Risk and rollout

- Single-file Python change in `lfx`. Loaded at component-registry build time. No DB migration.
- Multi-tenant deployment is the consumer; the change tightens an existing capability for non-admins. No new attack surface introduced.
- Rollback = revert the file. No persisted state depends on the new behavior.
