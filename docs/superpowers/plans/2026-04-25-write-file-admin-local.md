# Write File: admin-only Local + File Location Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restrict the "Local" storage option in the Write File component to super admins / platform admins, and add a separate "File Location" directory field with a sensible default.

**Architecture:** Single-file backend change in `lfx`. `update_build_config` becomes async and loads the caller's admin status to filter the storage-location dropdown. `save_to_file` re-checks at runtime. A new `file_location` `StrInput` adds an explicit directory field for Local; default resolves lazily to `<config_dir>/outputs`. The `file_name` field is documented as basename-only and is force-stripped via `Path.name`.

**Tech Stack:** Python 3.11+, `pytest`, `pytest-asyncio`, `unittest.mock` (`AsyncMock`/`MagicMock`/`patch`). No new dependencies.

**Spec:** `docs/superpowers/specs/2026-04-25-write-file-admin-local-design.md`

---

## File Map

- **Modify:** `src/lfx/src/lfx/components/files_and_knowledge/save_file.py` — `SaveToFileComponent` (display name "Write File"). Adds `version` and `changelog`, an admin-aware option helper, async `update_build_config`, runtime guard, `file_location` input, basename strip, lazy default location.
- **Modify:** `src/backend/tests/unit/components/processing/test_save_file_component.py` — pre-existing comprehensive test class; adapt one existing sync test to async, add new test cases for admin gating and file-location behavior.

No other files change. No new files created.

---

## Conventions

- All new tests are `@pytest.mark.asyncio` async unless noted.
- Run tests with: `uv run pytest src/backend/tests/unit/components/processing/test_save_file_component.py -v`
- The existing test file uses `tests.base.ComponentTestBaseWithoutClient` and patches `langflow.services.database.models.user.crud.get_user_by_id`. Reuse that mock target.
- Existing tests pass `mock_get_user.return_value = MagicMock()`. A bare `MagicMock` has truthy attributes for `is_superuser` and `is_platform_admin`, so existing Local-flow tests will continue to pass the new admin checks without modification. **Only the new tests need explicit `is_superuser`/`is_platform_admin` boolean assignments.**
- Per the langflow-component-authoring skill, every user-visible change requires a `version` bump and a `ChangelogEntry`. This component currently has neither; we add both in Task 7.
- The user has `feedback_no_git_commits.md` in memory: do NOT run `git commit` without explicit per-task user permission. The "Commit" steps below are still listed for completeness; pause and ask before each one.

---

## Task 1: Refactor storage-location options helper to accept `is_admin`

**Files:**
- Modify: `src/lfx/src/lfx/components/files_and_knowledge/save_file.py:20-25`
- Modify: `src/lfx/src/lfx/components/files_and_knowledge/save_file.py:55-66` (the `inputs = [SortableListInput(...)]` block — pass `is_admin=False` to the seed call)
- Test: `src/backend/tests/unit/components/processing/test_save_file_component.py` (append a new test method to `TestSaveToFileComponent`)

- [ ] **Step 1: Write failing test**

Append to `TestSaveToFileComponent`:

```python
    def test_storage_location_options_helper_admin_includes_local(self):
        """Admin sees Local + AWS + Google Drive."""
        from lfx.components.files_and_knowledge.save_file import _get_storage_location_options

        with patch(
            "lfx.components.files_and_knowledge.save_file.is_astra_cloud_environment",
            return_value=False,
        ):
            options = _get_storage_location_options(is_admin=True)
        names = [o["name"] for o in options]
        assert names == ["Local", "AWS", "Google Drive"]

    def test_storage_location_options_helper_non_admin_excludes_local(self):
        """Non-admin sees only AWS + Google Drive."""
        from lfx.components.files_and_knowledge.save_file import _get_storage_location_options

        with patch(
            "lfx.components.files_and_knowledge.save_file.is_astra_cloud_environment",
            return_value=False,
        ):
            options = _get_storage_location_options(is_admin=False)
        names = [o["name"] for o in options]
        assert names == ["AWS", "Google Drive"]

    def test_storage_location_options_helper_astra_admin_excludes_local(self):
        """Astra environment hides Local even for admins."""
        from lfx.components.files_and_knowledge.save_file import _get_storage_location_options

        with patch(
            "lfx.components.files_and_knowledge.save_file.is_astra_cloud_environment",
            return_value=True,
        ):
            options = _get_storage_location_options(is_admin=True)
        names = [o["name"] for o in options]
        assert names == ["AWS", "Google Drive"]
```

- [ ] **Step 2: Run tests, verify FAIL**

```
uv run pytest src/backend/tests/unit/components/processing/test_save_file_component.py::TestSaveToFileComponent::test_storage_location_options_helper_admin_includes_local -v
```

Expected: FAIL with `TypeError: _get_storage_location_options() got an unexpected keyword argument 'is_admin'`.

- [ ] **Step 3: Implement — refactor helper to accept `is_admin`**

Replace the existing `_get_storage_location_options` function (lines 20–25) with:

```python
def _get_storage_location_options(*, is_admin: bool):
    """Return storage-location options.

    `Local` is included only when the caller is an admin (super admin or platform
    admin) AND the process is not running in an Astra cloud environment.
    """
    cloud = [{"name": "AWS", "icon": "Amazon"}, {"name": "Google Drive", "icon": "google"}]
    if is_admin and not is_astra_cloud_environment():
        return [{"name": "Local", "icon": "hard-drive"}, *cloud]
    return cloud
```

Update the seed call inside the `inputs = [...]` block (around line 61) from:

```python
            options=_get_storage_location_options(),
```

to:

```python
            options=_get_storage_location_options(is_admin=False),
```

The class-level seed assumes non-admin; per-user filtering happens on the first `update_build_config` call.

Also update the default `value` line (around line 64) from:

```python
            value=[{"name": "Local", "icon": "hard-drive"}],
```

to:

```python
            value=[{"name": "AWS", "icon": "Amazon"}],
```

The default selection must be a value present in the seeded options. (Local is no longer in the default seed since the seed assumes non-admin.) Admin users will still get Local listed and selectable after `update_build_config` fires.

- [ ] **Step 4: Run tests, verify PASS**

```
uv run pytest src/backend/tests/unit/components/processing/test_save_file_component.py::TestSaveToFileComponent::test_storage_location_options_helper_admin_includes_local src/backend/tests/unit/components/processing/test_save_file_component.py::TestSaveToFileComponent::test_storage_location_options_helper_non_admin_excludes_local src/backend/tests/unit/components/processing/test_save_file_component.py::TestSaveToFileComponent::test_storage_location_options_helper_astra_admin_excludes_local -v
```

Expected: 3 passed.

- [ ] **Step 5: Update one pre-existing test that asserts the default**

The existing `test_storage_location_defaults_to_local` (around line 479) hard-asserts the default is Local. It now defaults to AWS. Replace its body:

```python
    def test_storage_location_defaults_to_aws(self, component_class):
        """Storage_location seed defaults to AWS — non-admin users never see Local in the seed."""
        storage_input = next(i for i in component_class.inputs if i.name == "storage_location")
        assert storage_input.value == [{"name": "AWS", "icon": "Amazon"}]
```

(Rename the method too — the old name is now wrong.)

- [ ] **Step 6: Run the renamed test, plus the existing options-related tests, verify PASS**

```
uv run pytest src/backend/tests/unit/components/processing/test_save_file_component.py::TestSaveToFileComponent::test_storage_location_defaults_to_aws src/backend/tests/unit/components/processing/test_save_file_component.py::TestSaveToFileComponent::test_storage_location_is_advanced -v
```

Expected: 2 passed.

- [ ] **Step 7: Pause for user approval, then commit**

Stage exactly:
```
git add src/lfx/src/lfx/components/files_and_knowledge/save_file.py src/backend/tests/unit/components/processing/test_save_file_component.py
```

Suggested message:
```
refactor(save-file): admin-aware storage-location helper

Turns _get_storage_location_options into a kwarg-only function gated by
is_admin. Default seed uses non-admin (no Local). Sets default selection
to AWS so non-admin users get a valid initial value.
```

(Per `feedback_no_git_commits.md`: ask the user before running `git commit`.)

---

## Task 2: Make `update_build_config` async + admin-aware

**Files:**
- Modify: `src/lfx/src/lfx/components/files_and_knowledge/save_file.py:182-253` (the `update_build_config` method)
- Test: `src/backend/tests/unit/components/processing/test_save_file_component.py` (add new tests + adapt existing `test_append_mode_hidden_for_cloud_storage` to async)

- [ ] **Step 1: Adapt the existing sync test to await the now-async method**

Replace the existing `test_append_mode_hidden_for_cloud_storage` method (around line 442–477) with:

```python
    @pytest.mark.asyncio
    async def test_append_mode_hidden_for_cloud_storage(self, component_class):
        """append_mode is hidden for AWS / Google Drive, visible for Local (admin user)."""
        component = component_class(_user_id=str(uuid4()))

        admin_user = MagicMock()
        admin_user.is_superuser = True
        admin_user.is_platform_admin = False

        with (
            patch("lfx.services.deps.session_scope") as mock_session,
            patch(
                "langflow.services.database.models.user.crud.get_user_by_id", new_callable=AsyncMock
            ) as mock_get_user,
        ):
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            mock_get_user.return_value = admin_user

            # Local
            build_config = {
                "storage_location": {"options": []},
                "file_name": {"show": False},
                "append_mode": {"show": False},
                "local_format": {"show": False},
            }
            result = await component.update_build_config(
                build_config, [{"name": "Local"}], "storage_location"
            )
            assert result["append_mode"]["show"] is True
            assert result["file_name"]["show"] is True
            assert result["local_format"]["show"] is True

            # AWS
            build_config = {
                "storage_location": {"options": []},
                "file_name": {"show": False},
                "append_mode": {"show": False},
                "aws_format": {"show": False},
            }
            result = await component.update_build_config(
                build_config, [{"name": "AWS"}], "storage_location"
            )
            assert result["append_mode"]["show"] is False
            assert result["file_name"]["show"] is True
            assert result["aws_format"]["show"] is True

            # Google Drive
            build_config = {
                "storage_location": {"options": []},
                "file_name": {"show": False},
                "append_mode": {"show": False},
                "gdrive_format": {"show": False},
            }
            result = await component.update_build_config(
                build_config, [{"name": "Google Drive"}], "storage_location"
            )
            assert result["append_mode"]["show"] is False
            assert result["file_name"]["show"] is True
            assert result["gdrive_format"]["show"] is True
```

Key changes vs. the old version: `@pytest.mark.asyncio`, `async def`, `await`, mocks for `session_scope` + `get_user_by_id` returning an admin user, `build_config["storage_location"]` is seeded so the option-rewriting code can find it.

- [ ] **Step 2: Add new tests for admin gating in `update_build_config`**

```python
    @pytest.mark.asyncio
    async def test_update_build_config_filters_local_for_non_admin(self, component_class):
        """Non-admin user: storage_location options exclude Local."""
        component = component_class(_user_id=str(uuid4()))

        non_admin = MagicMock()
        non_admin.is_superuser = False
        non_admin.is_platform_admin = False

        with (
            patch("lfx.services.deps.session_scope") as mock_session,
            patch(
                "langflow.services.database.models.user.crud.get_user_by_id", new_callable=AsyncMock
            ) as mock_get_user,
            patch(
                "lfx.components.files_and_knowledge.save_file.is_astra_cloud_environment",
                return_value=False,
            ),
        ):
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            mock_get_user.return_value = non_admin

            build_config = {
                "storage_location": {"options": [], "value": [{"name": "AWS"}]},
                "file_name": {"show": False},
                "append_mode": {"show": False},
                "aws_format": {"show": False},
                "aws_access_key_id": {"show": False, "advanced": True},
                "aws_secret_access_key": {"show": False, "advanced": True},
                "bucket_name": {"show": False, "advanced": True},
                "aws_region": {"show": False, "advanced": True},
                "s3_prefix": {"show": False, "advanced": True},
            }
            result = await component.update_build_config(
                build_config, [{"name": "AWS"}], "storage_location"
            )
            names = [o["name"] for o in result["storage_location"]["options"]]
            assert "Local" not in names
            assert names == ["AWS", "Google Drive"]

    @pytest.mark.asyncio
    async def test_update_build_config_includes_local_for_admin(self, component_class):
        """Admin user: storage_location options include Local."""
        component = component_class(_user_id=str(uuid4()))

        admin_user = MagicMock()
        admin_user.is_superuser = False
        admin_user.is_platform_admin = True  # platform admin path

        with (
            patch("lfx.services.deps.session_scope") as mock_session,
            patch(
                "langflow.services.database.models.user.crud.get_user_by_id", new_callable=AsyncMock
            ) as mock_get_user,
            patch(
                "lfx.components.files_and_knowledge.save_file.is_astra_cloud_environment",
                return_value=False,
            ),
        ):
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            mock_get_user.return_value = admin_user

            build_config = {
                "storage_location": {"options": [], "value": [{"name": "Local"}]},
                "file_name": {"show": False},
                "append_mode": {"show": False},
                "local_format": {"show": False},
            }
            result = await component.update_build_config(
                build_config, [{"name": "Local"}], "storage_location"
            )
            names = [o["name"] for o in result["storage_location"]["options"]]
            assert names == ["Local", "AWS", "Google Drive"]

    @pytest.mark.asyncio
    async def test_update_build_config_no_user_id_treats_as_non_admin(self, component_class):
        """If user_id is unset, treat as non-admin (defensive default)."""
        component = component_class()  # no _user_id

        with patch(
            "lfx.components.files_and_knowledge.save_file.is_astra_cloud_environment",
            return_value=False,
        ):
            build_config = {
                "storage_location": {"options": [], "value": [{"name": "AWS"}]},
                "file_name": {"show": False},
                "append_mode": {"show": False},
                "aws_format": {"show": False},
                "aws_access_key_id": {"show": False, "advanced": True},
                "aws_secret_access_key": {"show": False, "advanced": True},
                "bucket_name": {"show": False, "advanced": True},
                "aws_region": {"show": False, "advanced": True},
                "s3_prefix": {"show": False, "advanced": True},
            }
            result = await component.update_build_config(
                build_config, [{"name": "AWS"}], "storage_location"
            )
            names = [o["name"] for o in result["storage_location"]["options"]]
            assert "Local" not in names
```

- [ ] **Step 3: Run new tests, verify FAIL**

```
uv run pytest src/backend/tests/unit/components/processing/test_save_file_component.py::TestSaveToFileComponent::test_update_build_config_filters_local_for_non_admin src/backend/tests/unit/components/processing/test_save_file_component.py::TestSaveToFileComponent::test_update_build_config_includes_local_for_admin -v
```

Expected: FAIL — `update_build_config` is currently sync and does not await; the tests will fail with `TypeError: object dict can't be used in 'await' expression` or similar.

- [ ] **Step 4: Implement async `update_build_config` with admin resolution**

Replace the entire `update_build_config` method (lines 182–253) with:

```python
    async def _resolve_is_admin(self) -> bool:
        """Return True if the current caller is a super admin or platform admin.

        Falls back to False when there is no user_id (defensive default for tests
        and synthetic component instances).
        """
        if not getattr(self, "_user_id", None) and not getattr(self, "user_id", None):
            return False
        from langflow.services.database.models.user.crud import get_user_by_id

        async with session_scope() as db:
            user = await get_user_by_id(db, self.user_id)
            if user is None:
                return False
            return bool(getattr(user, "is_superuser", False) or getattr(user, "is_platform_admin", False))

    async def update_build_config(self, build_config, field_value, field_name=None):
        """Update build config to show/hide fields and filter storage options per role."""
        is_admin = await self._resolve_is_admin()

        # Refresh storage_location options every call so per-user filtering applies.
        if "storage_location" in build_config:
            updated_options = _get_storage_location_options(is_admin=is_admin)
            build_config["storage_location"]["options"] = updated_options
            allowed_names = {o["name"] for o in updated_options}
            current_value = build_config["storage_location"].get("value") or []
            current_name = current_value[0].get("name") if current_value else None
            if current_name not in allowed_names and updated_options:
                build_config["storage_location"]["value"] = [updated_options[0]]

        if field_name != "storage_location":
            return build_config

        selected = [location["name"] for location in field_value] if isinstance(field_value, list) else []

        dynamic_fields = [
            "file_name",
            "append_mode",
            "local_format",
            "aws_format",
            "gdrive_format",
            "aws_access_key_id",
            "aws_secret_access_key",
            "bucket_name",
            "aws_region",
            "s3_prefix",
            "service_account_key",
            "folder_id",
        ]
        for f_name in dynamic_fields:
            if f_name in build_config:
                build_config[f_name]["show"] = False

        if len(selected) == 1:
            location = selected[0]
            if "file_name" in build_config:
                build_config["file_name"]["show"] = True
            if "append_mode" in build_config:
                build_config["append_mode"]["show"] = location == "Local"

            if location == "Local":
                if "local_format" in build_config:
                    build_config["local_format"]["show"] = True
            elif location == "AWS":
                aws_fields = [
                    "aws_format",
                    "aws_access_key_id",
                    "aws_secret_access_key",
                    "bucket_name",
                    "aws_region",
                    "s3_prefix",
                ]
                for f_name in aws_fields:
                    if f_name in build_config:
                        build_config[f_name]["show"] = True
                        build_config[f_name]["advanced"] = False
            elif location == "Google Drive":
                gdrive_fields = ["gdrive_format", "service_account_key", "folder_id"]
                for f_name in gdrive_fields:
                    if f_name in build_config:
                        build_config[f_name]["show"] = True
                        build_config[f_name]["advanced"] = False

        return build_config
```

Notes on the implementation:
- `session_scope` is already imported at the top of the file (line 15).
- `get_user_by_id` is imported lazily inside `_resolve_is_admin` to avoid import-order issues at module load (the existing `_upload_file` at line 325 follows the same pattern).
- Selected-value reset: when the current value's name (e.g. "Local") is no longer in the allowed set, we replace it with the first allowed option. `field_value` for the rest of the function still reflects the user's just-clicked value — that's fine; visible-field decisions use `field_value`, persisted dropdown value uses `build_config["storage_location"]["value"]`.

- [ ] **Step 5: Run all tests touched by this change, verify PASS**

```
uv run pytest src/backend/tests/unit/components/processing/test_save_file_component.py::TestSaveToFileComponent::test_append_mode_hidden_for_cloud_storage src/backend/tests/unit/components/processing/test_save_file_component.py::TestSaveToFileComponent::test_update_build_config_filters_local_for_non_admin src/backend/tests/unit/components/processing/test_save_file_component.py::TestSaveToFileComponent::test_update_build_config_includes_local_for_admin src/backend/tests/unit/components/processing/test_save_file_component.py::TestSaveToFileComponent::test_update_build_config_no_user_id_treats_as_non_admin -v
```

Expected: 4 passed.

- [ ] **Step 6: Run the entire test file to catch unintended regressions**

```
uv run pytest src/backend/tests/unit/components/processing/test_save_file_component.py -v
```

Expected: all green. (The pre-existing Local-flow tests pass because their `MagicMock()` user has truthy `is_superuser`/`is_platform_admin` attributes.)

- [ ] **Step 7: Pause for user approval, then commit**

```
git add src/lfx/src/lfx/components/files_and_knowledge/save_file.py src/backend/tests/unit/components/processing/test_save_file_component.py
```

Suggested message:
```
feat(save-file): async update_build_config with admin-only Local

update_build_config now loads the caller via get_user_by_id and filters
the storage_location dropdown so only super admins / platform admins
see "Local". Resets the selected value to the first allowed option when
the current value is filtered out. Adapts the existing append_mode
visibility test for the new async signature.
```

---

## Task 3: Runtime guard in `save_to_file`

**Files:**
- Modify: `src/lfx/src/lfx/components/files_and_knowledge/save_file.py:255-284` (the `save_to_file` method)
- Test: `src/backend/tests/unit/components/processing/test_save_file_component.py`

- [ ] **Step 1: Write failing test**

```python
    @pytest.mark.asyncio
    async def test_save_to_file_local_blocked_for_non_admin(self, component_class):
        """Non-admin attempting Local storage at runtime gets ValueError."""
        component = component_class(_user_id=str(uuid4()))
        df = DataFrame([{"col1": 1}])
        component.set_attributes(
            {"input": df, "file_name": "test_output", "local_format": "csv", "storage_location": [{"name": "Local"}]}
        )

        non_admin = MagicMock()
        non_admin.is_superuser = False
        non_admin.is_platform_admin = False

        with (
            patch("lfx.services.deps.session_scope") as mock_session,
            patch(
                "langflow.services.database.models.user.crud.get_user_by_id", new_callable=AsyncMock
            ) as mock_get_user,
        ):
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            mock_get_user.return_value = non_admin

            with pytest.raises(ValueError, match="platform administrators"):
                await component.save_to_file()
```

- [ ] **Step 2: Run test, verify FAIL**

```
uv run pytest src/backend/tests/unit/components/processing/test_save_file_component.py::TestSaveToFileComponent::test_save_to_file_local_blocked_for_non_admin -v
```

Expected: FAIL — currently `save_to_file` does not check admin status, so the test will instead try to actually save and either succeed or fail with an unrelated error.

- [ ] **Step 3: Implement runtime guard**

In `save_to_file`, after the `storage_location` is resolved and before dispatching to `_save_to_local`, add the admin check. Replace the block (lines 277–282) that currently reads:

```python
        # Route to appropriate save method based on storage location
        if storage_location == "Local":
            return await self._save_to_local()
        if storage_location == "AWS":
            return await self._save_to_aws()
        if storage_location == "Google Drive":
            return await self._save_to_google_drive()
```

with:

```python
        # Route to appropriate save method based on storage location
        if storage_location == "Local":
            if not await self._resolve_is_admin():
                msg = "Local storage is restricted to platform administrators."
                raise ValueError(msg)
            return await self._save_to_local()
        if storage_location == "AWS":
            return await self._save_to_aws()
        if storage_location == "Google Drive":
            return await self._save_to_google_drive()
```

`_resolve_is_admin` was added in Task 2 and is reused here.

- [ ] **Step 4: Run new test, verify PASS**

```
uv run pytest src/backend/tests/unit/components/processing/test_save_file_component.py::TestSaveToFileComponent::test_save_to_file_local_blocked_for_non_admin -v
```

Expected: PASS.

- [ ] **Step 5: Re-run pre-existing Local-flow tests to confirm no regression**

```
uv run pytest src/backend/tests/unit/components/processing/test_save_file_component.py::TestSaveToFileComponent::test_save_dataframe_to_csv src/backend/tests/unit/components/processing/test_save_file_component.py::TestSaveToFileComponent::test_save_data_to_json src/backend/tests/unit/components/processing/test_save_file_component.py::TestSaveToFileComponent::test_save_message_to_txt -v
```

Expected: all PASS. (Pre-existing tests use `MagicMock()` users with truthy admin attributes, so the guard returns admin=True for them.)

- [ ] **Step 6: Pause for user approval, then commit**

```
git add src/lfx/src/lfx/components/files_and_knowledge/save_file.py src/backend/tests/unit/components/processing/test_save_file_component.py
```

Suggested message:
```
feat(save-file): runtime guard for non-admin Local writes

save_to_file re-checks the caller's admin status before dispatching to
_save_to_local. Defends against tampered flow JSON or non-admin users
loading flows that another user saved with Local selected.
```

---

## Task 4: Add `file_location` input + show/hide

**Files:**
- Modify: `src/lfx/src/lfx/components/files_and_knowledge/save_file.py` (`inputs` list, `dynamic_fields` list, Local branch in `update_build_config`)
- Test: `src/backend/tests/unit/components/processing/test_save_file_component.py`

- [ ] **Step 1: Write failing test**

```python
    @pytest.mark.asyncio
    async def test_file_location_visible_only_for_local(self, component_class):
        """file_location is shown when storage_location == Local; hidden otherwise."""
        component = component_class(_user_id=str(uuid4()))

        admin_user = MagicMock()
        admin_user.is_superuser = True
        admin_user.is_platform_admin = False

        with (
            patch("lfx.services.deps.session_scope") as mock_session,
            patch(
                "langflow.services.database.models.user.crud.get_user_by_id", new_callable=AsyncMock
            ) as mock_get_user,
        ):
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            mock_get_user.return_value = admin_user

            # Local — file_location visible
            build_config = {
                "storage_location": {"options": [], "value": [{"name": "Local"}]},
                "file_name": {"show": False},
                "file_location": {"show": False},
                "append_mode": {"show": False},
                "local_format": {"show": False},
            }
            result = await component.update_build_config(
                build_config, [{"name": "Local"}], "storage_location"
            )
            assert result["file_location"]["show"] is True

            # AWS — file_location hidden
            build_config = {
                "storage_location": {"options": [], "value": [{"name": "AWS"}]},
                "file_name": {"show": False},
                "file_location": {"show": False},
                "append_mode": {"show": False},
                "aws_format": {"show": False},
                "aws_access_key_id": {"show": False, "advanced": True},
                "aws_secret_access_key": {"show": False, "advanced": True},
                "bucket_name": {"show": False, "advanced": True},
                "aws_region": {"show": False, "advanced": True},
                "s3_prefix": {"show": False, "advanced": True},
            }
            result = await component.update_build_config(
                build_config, [{"name": "AWS"}], "storage_location"
            )
            assert result["file_location"]["show"] is False

    def test_file_location_input_exists(self, component_class):
        """file_location StrInput is registered on the component."""
        names = [i.name for i in component_class.inputs]
        assert "file_location" in names
        file_location = next(i for i in component_class.inputs if i.name == "file_location")
        assert file_location.required is False
        assert file_location.show is False
```

- [ ] **Step 2: Run, verify FAIL**

```
uv run pytest src/backend/tests/unit/components/processing/test_save_file_component.py::TestSaveToFileComponent::test_file_location_visible_only_for_local src/backend/tests/unit/components/processing/test_save_file_component.py::TestSaveToFileComponent::test_file_location_input_exists -v
```

Expected: FAIL — `file_location` not declared.

- [ ] **Step 3: Add the `StrInput`**

Insert into the `inputs = [...]` list, immediately after the `file_name` `StrInput` block (around line 76–83):

```python
        StrInput(
            name="file_location",
            display_name="File Location",
            info=(
                "Directory where the file will be saved. Defaults to the Langflow "
                "config dir's outputs/ folder if blank."
            ),
            required=False,
            show=False,
        ),
```

- [ ] **Step 4: Wire show/hide in `update_build_config`**

In the `dynamic_fields` list inside `update_build_config`, add `"file_location"` immediately after `"append_mode"`:

```python
        dynamic_fields = [
            "file_name",
            "file_location",
            "append_mode",
            "local_format",
            ...
```

In the `if location == "Local":` branch, after `if "local_format" in build_config:` block, add:

```python
                if "file_location" in build_config:
                    build_config["file_location"]["show"] = True
```

- [ ] **Step 5: Run, verify PASS**

```
uv run pytest src/backend/tests/unit/components/processing/test_save_file_component.py::TestSaveToFileComponent::test_file_location_visible_only_for_local src/backend/tests/unit/components/processing/test_save_file_component.py::TestSaveToFileComponent::test_file_location_input_exists -v
```

Expected: 2 passed.

- [ ] **Step 6: Pause for user approval, then commit**

```
git add src/lfx/src/lfx/components/files_and_knowledge/save_file.py src/backend/tests/unit/components/processing/test_save_file_component.py
```

Suggested message:
```
feat(save-file): add File Location input for Local storage

New file_location StrInput appears only when Local is selected. Empty
default — resolution to <config_dir>/outputs/ happens at save time
(Task 5).
```

---

## Task 5: Use `file_location` in `_save_to_local` + basename strip + lazy default + info-text update

**Files:**
- Modify: `src/lfx/src/lfx/components/files_and_knowledge/save_file.py:529-563` (`_save_to_local`)
- Modify: `src/lfx/src/lfx/components/files_and_knowledge/save_file.py:76-83` (`file_name` StrInput info text)
- Test: `src/backend/tests/unit/components/processing/test_save_file_component.py`

- [ ] **Step 1: Write failing tests**

```python
    @pytest.mark.asyncio
    async def test_save_to_local_uses_file_location(self, component_class, tmp_path):
        """Explicit file_location places the file in that directory."""
        component = component_class(_user_id=str(uuid4()))
        df = DataFrame([{"col1": 1}])
        component.set_attributes(
            {
                "input": df,
                "file_name": "out",
                "file_location": str(tmp_path),
                "local_format": "csv",
                "storage_location": [{"name": "Local"}],
            }
        )

        with (
            patch("langflow.api.v2.files.upload_user_file", new_callable=AsyncMock) as mock_upload,
            patch("lfx.services.deps.session_scope") as mock_session,
            patch(
                "langflow.services.database.models.user.crud.get_user_by_id", new_callable=AsyncMock
            ) as mock_get_user,
        ):
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            mock_get_user.return_value = MagicMock()  # admin by default
            mock_upload.return_value = "out.csv"

            result = await component.save_to_file()

            written = tmp_path / "out.csv"
            assert written.exists()
            assert "out.csv" in result.text

    @pytest.mark.asyncio
    async def test_save_to_local_default_location_is_config_outputs(self, component_class, tmp_path):
        """Empty file_location resolves to <config_dir>/outputs/."""
        component = component_class(_user_id=str(uuid4()))
        df = DataFrame([{"col1": 1}])
        component.set_attributes(
            {
                "input": df,
                "file_name": "default_out",
                "file_location": "",
                "local_format": "csv",
                "storage_location": [{"name": "Local"}],
            }
        )

        fake_settings = MagicMock()
        fake_settings.settings.config_dir = str(tmp_path)

        with (
            patch("langflow.api.v2.files.upload_user_file", new_callable=AsyncMock) as mock_upload,
            patch("lfx.services.deps.session_scope") as mock_session,
            patch(
                "langflow.services.database.models.user.crud.get_user_by_id", new_callable=AsyncMock
            ) as mock_get_user,
            patch(
                "lfx.components.files_and_knowledge.save_file.get_settings_service",
                return_value=fake_settings,
            ),
        ):
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            mock_get_user.return_value = MagicMock()
            mock_upload.return_value = "default_out.csv"

            await component.save_to_file()

            written = tmp_path / "outputs" / "default_out.csv"
            assert written.exists()

    @pytest.mark.asyncio
    async def test_save_to_local_strips_path_components_from_file_name(self, component_class, tmp_path):
        """file_name with embedded slashes/traversal is reduced to basename."""
        component = component_class(_user_id=str(uuid4()))
        df = DataFrame([{"col1": 1}])
        component.set_attributes(
            {
                "input": df,
                "file_name": "../escape/foo",
                "file_location": str(tmp_path),
                "local_format": "csv",
                "storage_location": [{"name": "Local"}],
            }
        )

        with (
            patch("langflow.api.v2.files.upload_user_file", new_callable=AsyncMock) as mock_upload,
            patch("lfx.services.deps.session_scope") as mock_session,
            patch(
                "langflow.services.database.models.user.crud.get_user_by_id", new_callable=AsyncMock
            ) as mock_get_user,
        ):
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            mock_get_user.return_value = MagicMock()
            mock_upload.return_value = "foo.csv"

            await component.save_to_file()

            assert (tmp_path / "foo.csv").exists()
            # No traversal happened — nothing exists at the parent of tmp_path under "escape"
            assert not (tmp_path.parent / "escape" / "foo.csv").exists()
```

- [ ] **Step 2: Run, verify FAIL**

```
uv run pytest src/backend/tests/unit/components/processing/test_save_file_component.py::TestSaveToFileComponent::test_save_to_local_uses_file_location src/backend/tests/unit/components/processing/test_save_file_component.py::TestSaveToFileComponent::test_save_to_local_default_location_is_config_outputs src/backend/tests/unit/components/processing/test_save_file_component.py::TestSaveToFileComponent::test_save_to_local_strips_path_components_from_file_name -v
```

Expected: FAIL — current `_save_to_local` ignores `file_location` and treats `file_name` as a full path.

- [ ] **Step 3: Update `_save_to_local` path resolution**

Replace the path-construction block at the top of `_save_to_local` (currently lines 541–545):

```python
        # Prepare file path
        file_path = Path(self.file_name).expanduser()
        if not file_path.parent.exists():
            file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path = self._adjust_file_path_with_format(file_path, file_format)
```

with:

```python
        # Prepare directory: explicit file_location wins, else default to <config_dir>/outputs/
        location_str = (getattr(self, "file_location", "") or "").strip()
        if location_str:
            directory = Path(location_str).expanduser()
        else:
            directory = Path(get_settings_service().settings.config_dir) / "outputs"

        # file_name is basename only — strip any path components an admin might paste in.
        basename = Path(self.file_name).name
        file_path = directory / basename
        file_path = self._adjust_file_path_with_format(file_path, file_format)
        if not file_path.parent.exists():
            file_path.parent.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 4: Update `file_name` info text to match new semantics**

Find the `file_name` `StrInput` (around lines 76–83) and change `info=`:

From:
```python
            info="Name file will be saved as (without extension).",
```

To:
```python
            info="File name only — no path, no extension. Use 'File Location' for the directory.",
```

- [ ] **Step 5: Run new tests, verify PASS**

```
uv run pytest src/backend/tests/unit/components/processing/test_save_file_component.py::TestSaveToFileComponent::test_save_to_local_uses_file_location src/backend/tests/unit/components/processing/test_save_file_component.py::TestSaveToFileComponent::test_save_to_local_default_location_is_config_outputs src/backend/tests/unit/components/processing/test_save_file_component.py::TestSaveToFileComponent::test_save_to_local_strips_path_components_from_file_name -v
```

Expected: 3 passed.

- [ ] **Step 6: Re-run all pre-existing Local-flow tests; some will now write to `<config_dir>/outputs/` and need adjustment**

```
uv run pytest src/backend/tests/unit/components/processing/test_save_file_component.py::TestSaveToFileComponent::test_save_dataframe_to_csv src/backend/tests/unit/components/processing/test_save_file_component.py::TestSaveToFileComponent::test_save_data_to_json src/backend/tests/unit/components/processing/test_save_file_component.py::TestSaveToFileComponent::test_save_message_to_txt src/backend/tests/unit/components/processing/test_save_file_component.py::TestSaveToFileComponent::test_cleanup_on_error src/backend/tests/unit/components/processing/test_save_file_component.py::TestSaveToFileComponent::test_file_name_with_extension_stripped src/backend/tests/unit/components/processing/test_save_file_component.py::TestSaveToFileComponent::test_append_mode_txt_file -v
```

Expected: most should still pass — they don't assert specific paths. If any fails because it relies on CWD-relative writes, fix by adding `"file_location": str(tmp_path)` to the `set_attributes` call (use the `tmp_path` fixture). If the failure is in `test_append_mode_txt_file`, which patches `Path` itself, the patch may need adjusting (it currently mocks `Path` to return a fixed value; with the new code it now calls `Path(location_str).expanduser()` and `Path(self.file_name).name` so the mock will misbehave). The fix for that specific test:

Replace its body so it sets `file_location` to the tmp file's parent and `file_name` to the basename, and stops patching `Path`:

```python
    @pytest.mark.asyncio
    async def test_append_mode_txt_file(self, component_class):
        """Append mode for text files."""
        from tempfile import NamedTemporaryFile

        with NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp_file:
            tmp_file.write("Existing content")
            tmp_path = Path(tmp_file.name)

        try:
            component = component_class(_user_id=str(uuid4()))
            component.set_attributes(
                {
                    "input": Message(text="New content"),
                    "file_name": tmp_path.stem,
                    "file_location": str(tmp_path.parent),
                    "local_format": "txt",
                    "storage_location": [{"name": "Local"}],
                    "append_mode": True,
                }
            )

            with (
                patch("langflow.api.v2.files.upload_user_file", new_callable=AsyncMock) as mock_upload,
                patch("lfx.services.deps.session_scope") as mock_session,
                patch(
                    "langflow.services.database.models.user.crud.get_user_by_id", new_callable=AsyncMock
                ) as mock_get_user,
            ):
                mock_db = AsyncMock()
                mock_session.return_value.__aenter__.return_value = mock_db
                mock_get_user.return_value = MagicMock()
                mock_upload.return_value = tmp_path.name

                result = await component.save_to_file()

                assert "appended to" in result.text
                assert tmp_path.read_text(encoding="utf-8") == "Existing content\nNew content"
        finally:
            if tmp_path.exists():
                tmp_path.unlink()
```

If `test_save_dataframe_to_csv`, `test_save_data_to_json`, `test_save_message_to_txt`, or `test_cleanup_on_error` fail, add `"file_location": str(tmp_path)` to their `set_attributes` calls and add `tmp_path` to the test signature.

- [ ] **Step 7: Run the full file**

```
uv run pytest src/backend/tests/unit/components/processing/test_save_file_component.py -v
```

Expected: all PASS.

- [ ] **Step 8: Pause for user approval, then commit**

```
git add src/lfx/src/lfx/components/files_and_knowledge/save_file.py src/backend/tests/unit/components/processing/test_save_file_component.py
```

Suggested message:
```
feat(save-file): file_location field + lazy default + basename strip

_save_to_local now uses an explicit file_location directory (defaulting
to <config_dir>/outputs/) and treats file_name as a basename via
Path(...).name, preventing directory-traversal via the file_name field.
Updates affected pre-existing tests to set file_location explicitly.
```

---

## Task 6: Version + changelog ritual

**Files:**
- Modify: `src/lfx/src/lfx/components/files_and_knowledge/save_file.py` (class body of `SaveToFileComponent`, near the `name = "SaveToFile"` line at 33)

Per the langflow-component-authoring skill, this component currently has neither `version` nor `changelog`. The change in this PR is user-visible — it removes `Local` from the dropdown for non-admins, changes the default storage selection from Local to AWS, adds a new `file_location` input, narrows `file_name` semantics, and changes the runtime error surface for non-admin Local writes. Notes are required because we narrow `file_name` semantics and change the default selected storage.

- [ ] **Step 1: Add `version` and `changelog`**

Add an import at the top of the file, alongside the other `lfx` imports (around line 10–17):

```python
from typing import ClassVar

from lfx.custom.custom_component.changelog import ChangelogEntry
```

(`ClassVar` may already be imported via something else in the file — check before adding a duplicate; if `from typing import Any` already exists, append `ClassVar` to that line instead.)

In the `SaveToFileComponent` class body, immediately after `name = "SaveToFile"` (line 33), add:

```python
    version: int = 1
    changelog: ClassVar[list[ChangelogEntry]] = [
        ChangelogEntry(
            version=1,
            changes=(
                "- Restricted **Local** storage to super admins / platform admins. "
                "Non-admin users see only AWS and Google Drive.\n"
                "- Added **File Location** input (Local only). Defaults to "
                "`<config_dir>/outputs/` when blank.\n"
                "- **File Name** is now strictly a basename: any path components are stripped. "
                "Use **File Location** for the directory.\n"
                "- Default selected storage changed from Local to AWS for the seeded options "
                "(per-user filtering still applies on first interaction)."
            ),
            notes=(
                "If you used **Local** storage and you are not a super admin / platform "
                "administrator, the flow will now fail at runtime with "
                '"Local storage is restricted to platform administrators." '
                "Switch to AWS or Google Drive, or ask an administrator. "
                "If you embedded path segments inside **File Name** (e.g. "
                "`subdir/output`), move those segments into the new **File Location** field."
            ),
        ),
    ]
```

- [ ] **Step 2: Run the changelog/versioning tests**

```
cd src/lfx && LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest tests/unit/custom/test_component_changelog.py -v
```

(`LFX_TEST_ALLOW_LANGFLOW=1` is the documented escape hatch for running `src/lfx` tests from the repo-level venv — see `MEMORY.md` `reference_lfx_test_env.md`.)

Expected: all PASS. If a test asserts that all components either have no `version` or a positive `version` with matching changelog, this entry should satisfy it. If a test fails with an unexpected schema error, inspect the error and adjust the entry; do not skip the test.

- [ ] **Step 3: Pause for user approval, then commit**

```
git add src/lfx/src/lfx/components/files_and_knowledge/save_file.py
```

Suggested message:
```
chore(save-file): add version=1 and changelog entry

Annotates the user-visible changes from this PR (admin-only Local,
file_location field, basename-only file_name) per the
langflow-component-authoring skill ritual.
```

---

## Task 7: Final validation

**Files:** none (verification only)

- [ ] **Step 1: Run the full Write File test file**

```
uv run pytest src/backend/tests/unit/components/processing/test_save_file_component.py -v
```

Expected: all PASS.

- [ ] **Step 2: Run the lfx changelog test file**

```
cd src/lfx && LFX_TEST_ALLOW_LANGFLOW=1 uv run pytest tests/unit/custom/test_component_changelog.py -v
```

Expected: all PASS.

- [ ] **Step 3: Run the related s3 component tests (they import `SaveToFileComponent`)**

```
uv run pytest src/backend/tests/unit/components/data_source/test_s3_components.py -v
```

Expected: all PASS. (No source code change should affect AWS path; this is a sanity check.)

- [ ] **Step 4: Manual smoke (optional but recommended)**

Start the dev server and:
1. Sign in as a non-admin user. Drop a Write File component. Click Storage Location → confirm only AWS and Google Drive appear.
2. Sign in as a super admin (`is_superuser=True`) or platform admin. Drop a Write File. Click Storage Location → confirm Local appears, and selecting it shows the new "File Location" field.
3. As admin, leave File Location blank and run the flow. Confirm the file appears under `<config_dir>/outputs/`.

If running the dev server isn't viable in this session, skip step 4 and note that manual smoke is pending.

- [ ] **Step 5: Final commit (if any unstaged docs/touch-ups)**

If everything is green and there are no further changes, this task ends here.

---

## Self-Review

**Spec coverage:**
- "Hide the `Local` storage option from non-admins" → Tasks 1, 2.
- "Reject `Local` at runtime if a non-admin somehow selects it" → Task 3.
- "Add a separate "File Location" (directory) input that appears only for Local" → Task 4.
- "Sensible default so admins don't have to type a path" → Task 5.
- "Keep AWS S3 and Google Drive paths unchanged" → Tasks 4, 5 (no AWS/GDrive code touched).
- Test cases 1–7 from spec → covered across Task 1's helper tests, Task 2's update_build_config tests, Task 3's runtime guard test, Task 4's file_location visibility test, and Task 5's path / default / traversal tests.
- Component-version ritual → Task 6.

**Placeholder scan:** No "TBD"/"TODO"/"implement later". Step bodies contain concrete code. No "Similar to Task N" without code.

**Type / signature consistency:** `_resolve_is_admin` is defined in Task 2 and reused in Task 3 — same name. `_get_storage_location_options(is_admin: bool)` defined in Task 1, called from Task 2 — kwarg-only, consistent. `file_location` attribute name consistent across input declaration (Task 4) and `_save_to_local` consumer (Task 5).

**Compatibility risks called out in the plan:** Existing `MagicMock()`-as-user mocks behave as admin (truthy attrs) — flagged in Task 2 step 6, Task 3 step 5, Task 5 step 6. No silent behavioral drift.
