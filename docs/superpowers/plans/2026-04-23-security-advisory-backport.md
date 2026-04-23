# Security Advisory Backport Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **User-specific commit discipline:** This user has a standing rule — pause and ask before every `git commit`, even when this plan instructs one. The commit commands in each task are the exact commands to run *after* the user approves; do not run them unprompted.

**Goal:** Close the four still-exposed items from the 2026-04-23 langflow-ai/langflow security-advisory triage on `platform-multi-tenant`: three upstream fixes that were undone by the 2026-04-15 release-merge revert (CVE-2026-33017, CVE-2026-33484, CVE-2026-33309) plus one fork-specific mitigation for the Agentic Assistant validation RCE (CVE-2026-33873), and audit the revert for other re-exposed security surfaces.

**Architecture:** Four independent code slices plus one pure-investigation audit. Tasks 1–3 restore deterministic backend-endpoint protections (remove unauthenticated `data:` parameter, restore ownership dep on image downloads, add path-traversal sanitization + containment on uploads). Task 4 plumbs the existing `LANGFLOW_ALLOW_CUSTOM_COMPONENTS` gate (via `resolve_component_gate_flags`) into `agentic/helpers/validation.py::validate_component_code` so `lfx.custom.validate.create_class()` — which ends in unconstrained `exec()` — is not invoked unless the caller is a platform admin *or* the deployment has opted in. When the gate is off, validation downgrades to AST-only syntactic checks and returns a structured "not executed" validation result. Task 5 does not ship code; it enumerates every security-adjacent file reverted by `642e39fcb8` and files follow-ups for anything that wasn't in the 14 published advisories.

**Tech Stack:** Python 3.11+, FastAPI, SQLModel (async), pytest-asyncio, `lfx.custom.validate` (AST), `langflow.api.utils.core.resolve_component_gate_flags`.

**Revert context (shared across Tasks 1–3):** Commit `642e39fcb8` (Adam Aghili, 2026-04-15) reverted the merge "Chore(release): merge release 1.9.0 into main (#12710)" across 2,374 files / −266k lines. It undid upstream PRs `#12160` (data-param RCE), `#12234` (image-download IDOR), and the `v2/files.py` + `storage/local.py` path-traversal hardening that went with release 1.9.0. Those commits are still reachable from `platform-multi-tenant` in `git log`, but their changes are not present on HEAD. Tasks 1–3 re-apply each fix directly on HEAD; a cherry-pick of the revert-of-revert is not attempted because the revert also removed unrelated 1.9.0 changes we do *not* want to resurrect.

**Out of scope:**
- The ten advisories marked APPLIED in `docs/superpowers/security-review-2026-04-23/advisories-{a,b,c}.md` (no further action needed).
- Re-applying the entire 1.9.0 release merge — the revert appears to have been deliberate (diverges from upstream product shape). We restore only the individual security fixes and let Task 5 surface anything else worth attention.
- Upstream PR creation. Per memory rule, no pushes or PRs to `langflow-ai/langflow`. All work stays on `platform-multi-tenant`.

**Cross-references:**
- Research reports: `docs/superpowers/security-review-2026-04-23/advisories-{a,b,c}.md`
- Existing security fixes plan (templates + assistant key encryption): `docs/superpowers/plans/2026-04-22-platform-multi-tenant-security-fixes.md`
- Existing follow-ups file: `docs/superpowers/followups.md`

---

## File Structure

**Modified:**
- `src/backend/base/langflow/api/v1/chat.py:580-659` — Task 1. Remove `data` param from `build_public_tmp` + from its `start_flow_build` call.
- `src/backend/base/langflow/api/build.py:218-338` — Task 1. Defensive: when `source_flow_id` is set (indicating a public-flow build), ignore any inbound `data`.
- `src/backend/base/langflow/api/v1/files.py:138-164` — Task 2. Add `Depends(get_flow)` to `download_image`.
- `src/backend/base/langflow/api/v2/files.py:160-220` — Task 3. Sanitize `file.filename` before any downstream use.
- `src/backend/base/langflow/services/storage/local.py:100-126` — Task 3. Containment check on resolved path.
- `src/backend/base/langflow/agentic/helpers/validation.py` — Task 4. Gate `create_class()` on `allow_custom_components` / `caller_is_platform_admin`; fall back to AST-only validation when gated off.
- `src/backend/base/langflow/agentic/services/assistant_service.py:78, 299` — Task 4. Plumb gate flags into the two `validate_component_code` call sites.

**Created:**
- `src/backend/tests/unit/api/v1/test_build_public_tmp_data_removed.py` — Task 1 regression suite.
- `src/backend/tests/unit/api/v1/test_download_image_ownership.py` — Task 2 regression suite.
- `src/backend/tests/unit/api/v2/test_files_path_traversal.py` — Task 3 regression suite.
- `src/backend/tests/unit/agentic/helpers/test_validation_gated.py` — Task 4 regression suite.
- `docs/superpowers/security-review-2026-04-23/revert-audit.md` — Task 5 audit output.
- Appendix in `docs/superpowers/followups.md` — Task 5 follow-up entries.

---

## Task 1: Close CVE-2026-33017 — remove `data` from `build_public_tmp`

**Vulnerability:** `src/backend/base/langflow/api/v1/chat.py:580-659` — `build_public_tmp` is an unauthenticated endpoint that still accepts `data: Annotated[FlowDataRequest | None, Body(embed=True)] = None` (line 586). That parameter is forwarded to `start_flow_build(..., data=data, ...)` (line 639) and ultimately reaches `generate_flow_events.create_graph`'s `build_graph_from_data(payload=data.model_dump(), ...)` branch (`api/build.py:330-338`), which materialises user-supplied flow definitions and executes their components. The upstream PR #12160 fix (`73b6612e3e` — reachable but reverted by `642e39fcb8`) removed the parameter so that the public endpoint can only load a flow by ID from the DB.

**Files:**
- Modify: `src/backend/base/langflow/api/v1/chat.py:580-659`
- Modify: `src/backend/base/langflow/api/build.py:299-338` (defensive guard)
- Test: `src/backend/tests/unit/api/v1/test_build_public_tmp_data_removed.py` (create)

- [ ] **Step 1: Write the failing regression test**

Create `src/backend/tests/unit/api/v1/test_build_public_tmp_data_removed.py`:

```python
"""Regression: build_public_tmp must not accept a user-supplied flow graph.

Covers CVE-2026-33017 (GHSA-vwmf-pq79-vjvx). Upstream PR #12160 was reverted
on 2026-04-15; this test asserts the fix is back in place.
"""

from __future__ import annotations

import uuid

import pytest


async def test_build_public_tmp_rejects_data_param(client):
    """POSTing a `data` body to the public build endpoint must be rejected.

    FastAPI returns 422 for unknown body fields when the endpoint has no
    matching parameter, which is the desired behavior — the attacker's flow
    graph is rejected at the schema layer rather than executed.
    """
    bogus_flow_id = uuid.uuid4()
    payload = {
        "data": {
            "nodes": [
                {
                    "id": "attacker_node",
                    "data": {"node": {"template": {"code": {"value": "print('RCE')"}}}},
                }
            ],
            "edges": [],
        },
        "inputs": {},
    }
    resp = await client.post(
        f"api/v1/build_public_tmp/{bogus_flow_id}/flow",
        json=payload,
    )
    # 422 is the ideal FastAPI response when `data` is not an accepted field.
    # Any 4xx that is NOT "attacker's data was executed" is acceptable; the
    # test's core claim is that the endpoint refuses to run attacker payload.
    assert resp.status_code in (400, 403, 404, 422), resp.text
    # Belt-and-braces: make sure the response body does not contain evidence
    # that our attacker node was parsed/executed.
    assert "attacker_node" not in resp.text
```

- [ ] **Step 2: Run the test — confirm it fails on the current MISSING state**

Run:
```bash
uv run --active pytest src/backend/tests/unit/api/v1/test_build_public_tmp_data_removed.py::test_build_public_tmp_rejects_data_param -v
```
Expected: FAIL or, at minimum, show that the endpoint accepts the `data` field (may 404 later in the handler due to missing flow, but the schema-layer gate is not present).

- [ ] **Step 3: Remove `data` from the public endpoint signature**

Edit `src/backend/base/langflow/api/v1/chat.py`. Find (lines 580–595):

```python
@router.post("/build_public_tmp/{flow_id}/flow")
async def build_public_tmp(
    *,
    background_tasks: LimitVertexBuildBackgroundTasks,
    flow_id: uuid.UUID,
    inputs: Annotated[InputValueRequest | None, Body(embed=True)] = None,
    data: Annotated[FlowDataRequest | None, Body(embed=True)] = None,
    files: list[str] | None = None,
    stop_component_id: str | None = None,
    start_component_id: str | None = None,
    log_builds: bool | None = True,
    flow_name: str | None = None,
    request: Request,
    queue_service: Annotated[JobQueueService, Depends(get_queue_service)],
    event_delivery: EventDeliveryType = EventDeliveryType.POLLING,
):
```

Replace with:

```python
@router.post("/build_public_tmp/{flow_id}/flow")
async def build_public_tmp(
    *,
    background_tasks: LimitVertexBuildBackgroundTasks,
    flow_id: uuid.UUID,
    inputs: Annotated[InputValueRequest | None, Body(embed=True)] = None,
    files: list[str] | None = None,
    stop_component_id: str | None = None,
    start_component_id: str | None = None,
    log_builds: bool | None = True,
    flow_name: str | None = None,
    request: Request,
    queue_service: Annotated[JobQueueService, Depends(get_queue_service)],
    event_delivery: EventDeliveryType = EventDeliveryType.POLLING,
):
```

- [ ] **Step 4: Remove `data` from the `start_flow_build` call**

In the same file, find (around line 634):

```python
        job_id = await start_flow_build(
            flow_id=new_flow_id,
            source_flow_id=flow_id,
            background_tasks=background_tasks,
            inputs=inputs,
            data=data,
            files=files,
            stop_component_id=stop_component_id,
            start_component_id=start_component_id,
            log_builds=log_builds or False,
            current_user=owner_user,
            queue_service=queue_service,
            flow_name=flow_name or f"{client_id}_{flow_id}",
        )
```

Replace with (remove the `data=data,` line):

```python
        job_id = await start_flow_build(
            flow_id=new_flow_id,
            source_flow_id=flow_id,
            background_tasks=background_tasks,
            inputs=inputs,
            files=files,
            stop_component_id=stop_component_id,
            start_component_id=start_component_id,
            log_builds=log_builds or False,
            current_user=owner_user,
            queue_service=queue_service,
            flow_name=flow_name or f"{client_id}_{flow_id}",
        )
```

- [ ] **Step 5: Add defensive guard in `generate_flow_events.create_graph`**

Edit `src/backend/base/langflow/api/build.py`. In the inner `create_graph` function (around lines 299–338), add a defensive check at the top that forces `data=None` whenever `source_flow_id` is provided. `source_flow_id` is set only by the public-flow path, so this protects future regressions. Find:

```python
    async def create_graph(fresh_session, flow_id_str: str, flow_name: str | None) -> Graph:
        if inputs is not None and getattr(inputs, "session", None) is not None:
            effective_session_id = inputs.session
        else:
            effective_session_id = flow_id_str

        # Custom-component gate: read deployment posture + caller identity so
        # Graph.from_payload can enforce before any vertex is materialised.
        allow_custom_components, caller_is_platform_admin = resolve_component_gate_flags(current_user)

        if not data:
```

Replace with:

```python
    async def create_graph(fresh_session, flow_id_str: str, flow_name: str | None) -> Graph:
        if inputs is not None and getattr(inputs, "session", None) is not None:
            effective_session_id = inputs.session
        else:
            effective_session_id = flow_id_str

        # Custom-component gate: read deployment posture + caller identity so
        # Graph.from_payload can enforce before any vertex is materialised.
        allow_custom_components, caller_is_platform_admin = resolve_component_gate_flags(current_user)

        # CVE-2026-33017 defense-in-depth: public-flow builds (identified by
        # source_flow_id being set) must never execute an attacker-supplied
        # `data` payload. Force DB-load path even if some caller threads data
        # through start_flow_build.
        effective_data = None if source_flow_id is not None else data

        if not effective_data:
```

Then also replace the subsequent reference to `data.model_dump()` (around line 332) to use `effective_data`:

Find:

```python
        return await build_graph_from_data(
            flow_id=flow_id_str,
            payload=data.model_dump(),
            user_id=str(current_user.id),
            flow_name=flow_name,
            session_id=effective_session_id,
            allow_custom_components=allow_custom_components,
            caller_is_platform_admin=caller_is_platform_admin,
        )
```

Replace with:

```python
        return await build_graph_from_data(
            flow_id=flow_id_str,
            payload=effective_data.model_dump(),
            user_id=str(current_user.id),
            flow_name=flow_name,
            session_id=effective_session_id,
            allow_custom_components=allow_custom_components,
            caller_is_platform_admin=caller_is_platform_admin,
        )
```

- [ ] **Step 6: Run the test to verify it passes**

Run:
```bash
uv run --active pytest src/backend/tests/unit/api/v1/test_build_public_tmp_data_removed.py -v
```
Expected: PASS — the endpoint now returns 4xx (likely 422) when `data` is supplied.

- [ ] **Step 7: Regression-run existing public-build suites**

Run:
```bash
uv run --active pytest src/backend/tests/unit/api/v1/ -v -k "public_tmp or build_public or shareable_playground"
```
Expected: all PASS. If any test was relying on passing `data` to the public endpoint — that test was exercising the vulnerability. Update the test to POST to the authenticated endpoint instead, or mark it xfail with a reference to this CVE.

- [ ] **Step 8: Ask the user before committing, then commit**

Proposed commit message:
```
fix(security): prevent RCE via data parameter in build_public_tmp (CVE-2026-33017)

Remove the `data` request-body field from the unauthenticated public-flow
build endpoint; public flows must be loaded from the database only, never
from an attacker-supplied FlowDataRequest. Add a defense-in-depth guard
in generate_flow_events so any caller that still threads data into the
public path is ignored when source_flow_id is set.

Re-applies the effect of upstream PR #12160, which was reverted on our
branch by commit 642e39fcb8 (2026-04-15 release-merge revert).

Refs: GHSA-vwmf-pq79-vjvx, CVE-2026-33017.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

Command:
```bash
git add \
  src/backend/base/langflow/api/v1/chat.py \
  src/backend/base/langflow/api/build.py \
  src/backend/tests/unit/api/v1/test_build_public_tmp_data_removed.py
git commit -m "$(cat <<'EOF'
fix(security): prevent RCE via data parameter in build_public_tmp (CVE-2026-33017)

Remove the `data` request-body field from the unauthenticated public-flow
build endpoint; public flows must be loaded from the database only, never
from an attacker-supplied FlowDataRequest. Add a defense-in-depth guard
in generate_flow_events so any caller that still threads data into the
public path is ignored when source_flow_id is set.

Re-applies the effect of upstream PR #12160, which was reverted on our
branch by commit 642e39fcb8 (2026-04-15 release-merge revert).

Refs: GHSA-vwmf-pq79-vjvx, CVE-2026-33017.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Close CVE-2026-33484 — restore ownership check on `download_image`

**Vulnerability:** `src/backend/base/langflow/api/v1/files.py:138-164` — `download_image` currently takes `flow_id: UUID, file_name: ValidatedFileName` and fetches from storage with no authentication or ownership check. A sibling endpoint `download_file` at line 107 uses `flow: Annotated[Flow, Depends(get_flow)]` to enforce `flow.user_id == current_user.id` (`get_flow` helper at `files.py:62-72`). Upstream PR #12234 added the same dep to `download_image`; the 2026-04-15 revert removed it. The current endpoint is effectively an unauthenticated IDOR on any image inside any flow.

**Files:**
- Modify: `src/backend/base/langflow/api/v1/files.py:138-164`
- Test: `src/backend/tests/unit/api/v1/test_download_image_ownership.py` (create)

- [ ] **Step 1: Write the failing regression test**

Create `src/backend/tests/unit/api/v1/test_download_image_ownership.py`:

```python
"""Regression: /api/v1/files/images/{flow_id}/{file_name} must enforce ownership.

Covers CVE-2026-33484 (GHSA-7grx-3xcx-2xv5). Upstream PR #12234 was reverted
on 2026-04-15; this test asserts the Depends(get_flow) dep is back.
"""

from __future__ import annotations

import uuid

import pytest
from sqlmodel import select

from langflow.services.auth.utils import get_password_hash
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope


@pytest.fixture
async def two_users_with_flow():
    """Create user_a (owns flow), user_b (does not own flow)."""
    slug = uuid.uuid4().hex[:8]
    async with session_scope() as session:
        user_a = User(username=f"imga-{slug}", password=get_password_hash("testpassword"), is_active=True)
        user_b = User(username=f"imgb-{slug}", password=get_password_hash("testpassword"), is_active=True)
        session.add_all([user_a, user_b])
        await session.flush()
        flow = Flow(name=f"imgflow-{slug}", data={"nodes": [], "edges": []}, user_id=user_a.id)
        session.add(flow)
        await session.commit()
        for obj in (user_a, user_b, flow):
            await session.refresh(obj)
        ids = {
            "user_a_username": user_a.username,
            "user_b_username": user_b.username,
            "flow_id": flow.id,
        }
    yield ids
    async with session_scope() as session:
        row = await session.get(Flow, ids["flow_id"])
        if row is not None:
            await session.delete(row)
        for uname in (ids["user_a_username"], ids["user_b_username"]):
            u = (await session.exec(select(User).where(User.username == uname))).first()
            if u is not None:
                await session.delete(u)
        await session.commit()


async def _login(client, username: str) -> dict[str, str]:
    resp = await client.post("api/v1/login", data={"username": username, "password": "testpassword"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def test_download_image_requires_authentication(client, two_users_with_flow):
    # No auth → 401/403.
    resp = await client.get(f"api/v1/files/images/{two_users_with_flow['flow_id']}/x.png")
    assert resp.status_code in (401, 403), resp.text


async def test_download_image_denies_cross_user(client, two_users_with_flow):
    # user_b (not the flow owner) must not be able to enumerate.
    headers = await _login(client, two_users_with_flow["user_b_username"])
    resp = await client.get(
        f"api/v1/files/images/{two_users_with_flow['flow_id']}/x.png",
        headers=headers,
    )
    # 404 to match download_file's behavior (hide existence).
    assert resp.status_code == 404, resp.text
```

- [ ] **Step 2: Run the tests — confirm they fail**

Run:
```bash
uv run --active pytest src/backend/tests/unit/api/v1/test_download_image_ownership.py -v
```
Expected: both tests FAIL. `download_image` currently accepts anonymous calls and returns 500 ("content type not found") rather than a 4xx, meaning the endpoint is reachable without auth.

- [ ] **Step 3: Add `Depends(get_flow)` to `download_image`**

Edit `src/backend/base/langflow/api/v1/files.py`. Find (lines 138–164):

```python
@router.get("/images/{flow_id}/{file_name}")
async def download_image(
    file_name: ValidatedFileName,
    flow_id: UUID,
):
    """Download image from storage for browser rendering."""
    storage_service = get_storage_service()
    extension = file_name.split(".")[-1]
    flow_id_str = str(flow_id)

    if not extension:
        raise HTTPException(status_code=500, detail=f"Extension not found for file {file_name}")
    try:
        content_type = build_content_type_from_extension(extension)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    if not content_type:
        raise HTTPException(status_code=500, detail=f"Content type not found for extension {extension}")
    if not content_type.startswith("image"):
        raise HTTPException(status_code=500, detail=f"Content type {content_type} is not an image")

    try:
        file_content = await storage_service.get_file(flow_id=flow_id_str, file_name=file_name)
        return StreamingResponse(BytesIO(file_content), media_type=content_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
```

Replace with:

```python
@router.get("/images/{flow_id}/{file_name}")
async def download_image(
    file_name: ValidatedFileName,
    flow: Annotated[Flow, Depends(get_flow)],
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
):
    """Download image from storage for browser rendering.

    Authorization handled by the ``get_flow`` dependency, which returns 404
    for both non-existent flows and flows the caller does not own. The
    ``{flow_id}`` path parameter is consumed by ``get_flow`` — do not
    re-parse it here.
    """
    flow_id_str = str(flow.id)
    extension = file_name.split(".")[-1]

    if not extension:
        raise HTTPException(status_code=500, detail=f"Extension not found for file {file_name}")
    try:
        content_type = build_content_type_from_extension(extension)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    if not content_type:
        raise HTTPException(status_code=500, detail=f"Content type not found for extension {extension}")
    if not content_type.startswith("image"):
        raise HTTPException(status_code=500, detail=f"Content type {content_type} is not an image")

    try:
        file_content = await storage_service.get_file(flow_id=flow_id_str, file_name=file_name)
        return StreamingResponse(BytesIO(file_content), media_type=content_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
```

Note: `Annotated`, `Depends`, `Flow`, `StorageService`, and `get_storage_service` are already imported at the top of the file (lines 6, 10, 17, 19, 18 respectively). No import changes needed.

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```bash
uv run --active pytest src/backend/tests/unit/api/v1/test_download_image_ownership.py -v
```
Expected: both tests PASS.

- [ ] **Step 5: Regression-run existing v1/files tests**

Run:
```bash
uv run --active pytest src/backend/tests/unit/api/v1/ -v -k files
```
Expected: all PASS. If any legacy test was calling `download_image` without a bearer token, update it to authenticate and to scope to its own flow.

- [ ] **Step 6: Ask the user before committing, then commit**

```bash
git add \
  src/backend/base/langflow/api/v1/files.py \
  src/backend/tests/unit/api/v1/test_download_image_ownership.py
git commit -m "$(cat <<'EOF'
fix(security): require flow ownership for GET /files/images/{flow_id}/{file_name} (CVE-2026-33484)

Re-apply Depends(get_flow) on download_image so image downloads enforce
authentication + flow ownership, matching the sibling download_file
endpoint. Upstream PR #12234 had this dep; it was removed on our branch
by commit 642e39fcb8 (2026-04-15 release-merge revert).

Refs: GHSA-7grx-3xcx-2xv5, CVE-2026-33484.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Close CVE-2026-33309 — sanitize v2 file uploads at two layers

**Vulnerability:** Two coupled gaps.

1. `src/backend/base/langflow/api/v2/files.py:165` sets `new_filename = file.filename` with no path-traversal stripping. A multipart `filename="../../etc/passwd"` is carried verbatim into DB record naming and eventually passed to the storage layer.
2. `src/backend/base/langflow/services/storage/local.py:114-116`:
   ```python
   folder_path = self.data_dir / flow_id
   await folder_path.mkdir(parents=True, exist_ok=True)
   file_path = folder_path / file_name
   ```
   No check that `file_path.resolve()` is contained within `folder_path.resolve()`. A `file_name` of `../../../../tmp/evil.sh` would escape.

Upstream fixed both layers: strip directory components at the API boundary with `pathlib.Path(name).name`, then enforce containment with `resolve().is_relative_to(base)` at the storage layer. Both go-away in our revert.

**Files:**
- Modify: `src/backend/base/langflow/api/v2/files.py:160-175`
- Modify: `src/backend/base/langflow/services/storage/local.py:100-126`
- Test: `src/backend/tests/unit/api/v2/test_files_path_traversal.py` (create)

- [ ] **Step 1: Write the failing test**

Create `src/backend/tests/unit/api/v2/test_files_path_traversal.py`:

```python
"""Regression: v2 file upload must sanitize filenames and contain paths.

Covers CVE-2026-33309 (GHSA-g2j9-7rj2-gm6c). Tests both layers:
- API sanitization (`../` stripped / rejected at file boundary)
- Storage layer containment (resolved path stays inside flow_id folder)
"""

from __future__ import annotations

import io
import uuid

import pytest

from langflow.services.deps import get_settings_service


async def test_v2_upload_rejects_path_traversal_filename(client, logged_in_headers):
    """A multipart upload with a `../../` filename must be rejected before
    it lands on disk."""
    traversal_name = "../../evil.txt"
    files = {"file": (traversal_name, io.BytesIO(b"attacker"), "text/plain")}
    resp = await client.post("api/v2/files", headers=logged_in_headers, files=files)
    # Accept any 4xx — schema rejection (422) or explicit 400 both prove the
    # sanitization fired. 2xx would be the vulnerability.
    assert 400 <= resp.status_code < 500, resp.text
    # Make absolutely sure the file did not land on disk escaping the user's
    # storage dir.
    settings = get_settings_service().settings
    from pathlib import Path as P

    escape_target = P(settings.config_dir).resolve().parent / "evil.txt"
    assert not escape_target.exists(), (
        f"path traversal landed at {escape_target}"
    )


@pytest.mark.asyncio
async def test_local_storage_containment(tmp_path):
    """The LocalStorageService must refuse to write outside `data_dir/flow_id/`."""
    from langflow.services.storage.local import LocalStorageService

    # Minimal stub — we only need data_dir resolved to tmp_path.
    class _Settings:
        config_dir = str(tmp_path)

    class _Svc:
        settings = _Settings()

    svc = LocalStorageService.__new__(LocalStorageService)
    svc.data_dir = tmp_path
    # Bypass StorageService.__init__ — we need neither session nor settings.

    with pytest.raises((ValueError, OSError)):
        await svc.save_file(flow_id="victim", file_name="../../escapee.txt", data=b"payload")

    # Confirm the file did NOT land outside tmp_path.
    from pathlib import Path

    assert not (tmp_path.parent / "escapee.txt").exists()
```

Note: the storage-layer test `__new__` + direct attribute assignment is the minimum-invasive way to exercise `save_file` without the session/service wiring. If the real `StorageService.__init__` needs running, a fuller fixture may be swapped in; the core assertion is containment.

- [ ] **Step 2: Run the tests — confirm they fail**

Run:
```bash
uv run --active pytest src/backend/tests/unit/api/v2/test_files_path_traversal.py -v
```
Expected: both tests FAIL — current API accepts `../../evil.txt`; current storage layer happily writes to `<data_dir>/victim/../../escapee.txt` which resolves outside `<data_dir>`.

- [ ] **Step 3: Sanitize filename at the v2 API boundary**

Edit `src/backend/base/langflow/api/v2/files.py`. Find (around line 165):

```python
    # Create a new database record for the uploaded file.
    try:
        # Enforce unique constraint on name, except for the special _mcp_servers file
        new_filename = file.filename
        try:
            root_filename, file_extension = new_filename.rsplit(".", 1)
        except ValueError:
            root_filename, file_extension = new_filename, ""
```

Replace with:

```python
    # Create a new database record for the uploaded file.
    try:
        # CVE-2026-33309: strip any path components the client injected and
        # reject empties / pure dots. `Path.name` returns just the final
        # component with no separators, so "../../../etc/passwd" → "passwd"
        # and "" → "" (caught by the check below).
        from pathlib import Path as _StdPath

        raw_filename = file.filename or ""
        new_filename = _StdPath(raw_filename).name
        if not new_filename or new_filename in {".", ".."}:
            raise HTTPException(status_code=400, detail="Invalid file name")
        # Enforce unique constraint on name, except for the special _mcp_servers file
        try:
            root_filename, file_extension = new_filename.rsplit(".", 1)
        except ValueError:
            root_filename, file_extension = new_filename, ""
```

- [ ] **Step 4: Add containment check in `LocalStorageService.save_file`**

Edit `src/backend/base/langflow/services/storage/local.py`. Find (around lines 113–117):

```python
        folder_path = self.data_dir / flow_id
        await folder_path.mkdir(parents=True, exist_ok=True)
        file_path = folder_path / file_name

        try:
```

Replace with:

```python
        folder_path = self.data_dir / flow_id
        await folder_path.mkdir(parents=True, exist_ok=True)
        file_path = folder_path / file_name

        # CVE-2026-33309 defense-in-depth: even if the API layer fails to
        # sanitize the filename, refuse to write outside the flow's folder.
        # `anyio.Path.resolve` is async; we use the sync pathlib equivalent
        # on the string form because resolution is a filesystem operation.
        from pathlib import Path as _StdPath

        resolved = _StdPath(str(file_path)).resolve()
        folder_resolved = _StdPath(str(folder_path)).resolve()
        try:
            resolved.relative_to(folder_resolved)
        except ValueError as exc:
            msg = f"Refusing to write {file_name!r}: resolves outside {folder_resolved}"
            raise ValueError(msg) from exc

        try:
```

- [ ] **Step 5: Run the tests to verify they pass**

Run:
```bash
uv run --active pytest src/backend/tests/unit/api/v2/test_files_path_traversal.py -v
```
Expected: both tests PASS.

- [ ] **Step 6: Regression-run v2 files suite**

Run:
```bash
uv run --active pytest src/backend/tests/unit/api/v2/ -v -k files
```
Expected: all PASS. If any existing test uploads with a legitimate filename that happens to contain a subdirectory-looking prefix, the sanitization will trim it — update the test to use plain filenames.

- [ ] **Step 7: Ask the user before committing, then commit**

```bash
git add \
  src/backend/base/langflow/api/v2/files.py \
  src/backend/base/langflow/services/storage/local.py \
  src/backend/tests/unit/api/v2/test_files_path_traversal.py
git commit -m "$(cat <<'EOF'
fix(security): sanitize v2 upload filenames + contain storage paths (CVE-2026-33309)

Two-layer defense against path traversal in v2 file uploads:
1. Strip directory components at the API boundary using pathlib.Path(name).name
   and reject empty / "." / ".." names with HTTP 400.
2. In LocalStorageService.save_file, refuse to write if the resolved file
   path is not contained within the flow's folder_path.

Re-applies the effect of the release-1.9.0 upstream hardening, which was
reverted on our branch by commit 642e39fcb8 (2026-04-15).

Refs: GHSA-g2j9-7rj2-gm6c, CVE-2026-33309.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Close CVE-2026-33873 — gate Agentic Assistant validation on ALLOW_CUSTOM_COMPONENTS (fork-specific mitigation)

**Vulnerability:** `src/backend/base/langflow/agentic/helpers/validation.py:27-59` — `validate_component_code(code)` calls `lfx.custom.validate.create_class(code, class_name)` which ends in an unconstrained `exec(compiled_class, exec_globals, exec_locals)` at `src/lfx/src/lfx/custom/validate.py:442`. The agentic assistant routes LLM-generated component code through this validator server-side, so an authenticated user who can influence the model's output can trigger arbitrary Python execution in the langflow process. Upstream 1.9.0 is marked as patched; the fix was undone on our branch by the 2026-04-15 revert, and the user has opted for a fork-specific mitigation rather than an upstream cherry-pick.

**Mitigation design — rationale:**

Our fork already has a `LANGFLOW_ALLOW_CUSTOM_COMPONENTS` gate: the central helper `resolve_component_gate_flags(user) → (allow_custom_components, caller_is_platform_admin)` at `src/backend/base/langflow/api/utils/core.py:240`. The gate's semantics are exactly what this vulnerability needs — it asks "is this deployment (or this caller) allowed to run Python code that was not part of the shipped component set?" — and it already threads through flow-build, flow-run, upload, and template-create. Reusing it for the agentic validator keeps the deployment posture coherent: a tenant whose deploy denies custom components should *also* not be able to trigger exec() via the Assistant.

**Gate behavior when off (multi-tenant default):**
- `validate_component_code` does NOT call `create_class`.
- It runs AST-only checks: `ast.parse(code)` to verify syntax; `_safe_extract_class_name(code)` to confirm a class declaration exists.
- Returns `ValidationResult(is_valid=<bool>, code=code, class_name=<name_or_None>, error=<AST error or None>, executed=False)` — with an added explicit `executed: bool = False` field so downstream callers (and the assistant's user-facing messages) can distinguish "code parsed, but we didn't instantiate" from "code ran and __init__ succeeded".

**Gate behavior when on (opt-in or platform admin):** existing behavior — `create_class` + instantiation trigger `__init__` checks (overlapping I/O names etc.).

**Files:**
- Modify: `src/backend/base/langflow/agentic/helpers/validation.py`
- Modify: `src/backend/base/langflow/agentic/services/assistant_service.py:78, 299`
- Modify: `src/backend/base/langflow/agentic/api/schemas.py` — add `executed: bool = False` to `ValidationResult` (non-breaking; default preserves current callers).
- Test: `src/backend/tests/unit/agentic/helpers/test_validation_gated.py` (create)

- [ ] **Step 1: Write the failing test**

Create `src/backend/tests/unit/agentic/helpers/test_validation_gated.py`:

```python
"""Regression: agentic validation must not exec() LLM-generated code unless
the LANGFLOW_ALLOW_CUSTOM_COMPONENTS gate is open (or the caller is a
platform admin).

Covers CVE-2026-33873 (GHSA-v8hw-mh8c-jxfc). Fork-specific mitigation — see
docs/superpowers/plans/2026-04-23-security-advisory-backport.md Task 4.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from langflow.agentic.helpers.validation import validate_component_code


# A class definition whose `__init__` would raise at runtime — if create_class
# + instantiation fires, we'll see that runtime error; if we're AST-only, the
# value is simply `is_valid=True, executed=False`.
_BOOM_CODE = '''
from langflow.custom import Component

class Boom(Component):
    def __init__(self):
        raise RuntimeError("detonated at runtime — we should never see this when gated off")
'''


def test_validation_gated_off_does_not_exec():
    """With allow_custom_components=False and caller not a platform admin,
    validate_component_code must NOT call create_class/exec. Detect by
    ensuring the deliberate runtime error in __init__ does NOT surface."""
    with patch(
        "langflow.agentic.helpers.validation.create_class"
    ) as mock_create_class:
        result = validate_component_code(
            _BOOM_CODE,
            allow_custom_components=False,
            caller_is_platform_admin=False,
        )
        mock_create_class.assert_not_called()
        assert result.is_valid is True
        assert result.executed is False
        assert result.class_name == "Boom"


def test_validation_gated_off_rejects_syntax_errors():
    """AST-only mode still refuses genuinely broken code."""
    result = validate_component_code(
        "class Broken(:\n    pass",  # syntax error
        allow_custom_components=False,
        caller_is_platform_admin=False,
    )
    assert result.is_valid is False
    assert result.executed is False


def test_validation_gate_allows_when_flag_on():
    """When deployment opts in, original behavior resumes."""
    # Use a benign class — just assert create_class was called.
    benign = '''
from langflow.custom import Component

class Benign(Component):
    def __init__(self):
        super().__init__()
'''
    with patch(
        "langflow.agentic.helpers.validation.create_class"
    ) as mock_create_class:
        # Make create_class return a factory that produces a no-op class.
        class _Noop:
            def __init__(self):
                pass

        mock_create_class.return_value = _Noop
        validate_component_code(
            benign,
            allow_custom_components=True,
            caller_is_platform_admin=False,
        )
        mock_create_class.assert_called_once()


def test_validation_gate_allows_for_platform_admin():
    """Platform admins bypass the gate even when the deployment flag is off."""
    benign = '''
from langflow.custom import Component

class Benign(Component):
    def __init__(self):
        super().__init__()
'''
    with patch(
        "langflow.agentic.helpers.validation.create_class"
    ) as mock_create_class:
        class _Noop:
            def __init__(self):
                pass

        mock_create_class.return_value = _Noop
        validate_component_code(
            benign,
            allow_custom_components=False,
            caller_is_platform_admin=True,
        )
        mock_create_class.assert_called_once()
```

- [ ] **Step 2: Run the tests — confirm they fail**

Run:
```bash
uv run --active pytest src/backend/tests/unit/agentic/helpers/test_validation_gated.py -v
```
Expected: FAIL — current signature does not accept gate kwargs, so all four tests raise `TypeError`.

- [ ] **Step 3: Add `executed` field to `ValidationResult`**

Inspect the schema first:
```bash
grep -n "class ValidationResult" src/backend/base/langflow/agentic/api/schemas.py
```

Edit `src/backend/base/langflow/agentic/api/schemas.py`. Add `executed: bool = True` to the `ValidationResult` model. Default `True` preserves the semantics of existing callers (they were calling `create_class`, so "executed" was implicit). Locate the class and add the field:

```python
class ValidationResult(BaseModel):
    is_valid: bool
    code: str
    class_name: str | None = None
    error: str | None = None
    executed: bool = True  # False when gated-off AST-only validation was used
```

If the `ValidationResult` class has a different shape than expected (e.g. uses a `dataclass`), adapt the field addition accordingly — the essential property is that new callers can read `.executed` and old callers that ignore the field still compile.

- [ ] **Step 4: Gate `create_class` in `validate_component_code`**

Replace `src/backend/base/langflow/agentic/helpers/validation.py` in full:

```python
"""Component code validation."""

import ast
import re

from lfx.custom.validate import create_class, extract_class_name

from langflow.agentic.api.schemas import ValidationResult

# Regex pattern to extract class name that inherits from Component
CLASS_NAME_PATTERN = re.compile(r"class\s+(\w+)\s*\([^)]*Component[^)]*\)")


def _extract_class_name_regex(code: str) -> str | None:
    """Extract class name using regex (fallback for syntax errors)."""
    match = CLASS_NAME_PATTERN.search(code)
    return match.group(1) if match else None


def _safe_extract_class_name(code: str) -> str | None:
    """Extract class name with fallback to regex for broken code."""
    try:
        return extract_class_name(code)
    except (ValueError, SyntaxError, TypeError):
        return _extract_class_name_regex(code)


def _ast_only_validate(code: str) -> ValidationResult:
    """Validate code without executing it. Used when the ALLOW_CUSTOM_COMPONENTS
    gate is closed — this is the multi-tenant default and the mitigation for
    CVE-2026-33873 (Agentic Assistant Validation RCE).

    Performs:
    - ``ast.parse`` to confirm syntactic validity.
    - Class-name extraction to confirm a ``class X(Component)`` declaration
      is present.

    Does NOT:
    - Import the code's referenced modules.
    - Instantiate the class (no ``__init__`` checks).
    - Call ``exec()`` on any compiled form of the user's code.
    """
    class_name = _safe_extract_class_name(code)
    try:
        ast.parse(code)
    except SyntaxError as exc:
        return ValidationResult(
            is_valid=False,
            code=code,
            class_name=class_name,
            error=f"SyntaxError: {exc}",
            executed=False,
        )
    if class_name is None:
        return ValidationResult(
            is_valid=False,
            code=code,
            class_name=None,
            error="Could not extract a Component subclass declaration",
            executed=False,
        )
    return ValidationResult(
        is_valid=True,
        code=code,
        class_name=class_name,
        executed=False,
    )


def validate_component_code(
    code: str,
    *,
    allow_custom_components: bool = False,
    caller_is_platform_admin: bool = False,
) -> ValidationResult:
    """Validate component code.

    Security: when the deployment's ``LANGFLOW_ALLOW_CUSTOM_COMPONENTS`` flag
    is off AND the caller is not a platform admin, this function performs
    AST-only validation and does NOT call ``create_class`` (which ends in
    ``exec()``). This mitigates CVE-2026-33873 — authenticated code execution
    via the Agentic Assistant's validation path — for multi-tenant deploys
    where LLM output may be attacker-influenced.

    When the gate is open (opt-in or caller is a platform admin), the full
    create-and-instantiate path runs to catch ``__init__``-time errors like
    overlapping input/output names.

    Args:
        code: Python source of the component to validate.
        allow_custom_components: Deployment-level gate flag, typically from
            ``resolve_component_gate_flags``.
        caller_is_platform_admin: True when the request's user has
            ``is_platform_admin=True``.

    Returns:
        A ``ValidationResult`` whose ``executed`` flag indicates whether the
        full create/instantiate path ran or whether validation was AST-only.
    """
    if not (allow_custom_components or caller_is_platform_admin):
        return _ast_only_validate(code)

    class_name = _safe_extract_class_name(code)

    try:
        if class_name is None:
            msg = "Could not extract class name from code"
            raise ValueError(msg)

        # create_class returns the class (not an instance)
        component_class = create_class(code, class_name)

        # Instantiate the class to trigger __init__ validation
        # This catches errors like overlapping input/output names
        component_class()

        return ValidationResult(is_valid=True, code=code, class_name=class_name, executed=True)
    except (
        ValueError,
        TypeError,
        SyntaxError,
        NameError,
        ModuleNotFoundError,
        AttributeError,
        ImportError,
        RuntimeError,
        KeyError,
    ) as e:
        return ValidationResult(
            is_valid=False,
            code=code,
            error=f"{type(e).__name__}: {e}",
            class_name=class_name,
            executed=True,
        )
```

- [ ] **Step 5: Plumb gate flags through the two call sites in `assistant_service.py`**

Inspect the two call sites first:
```bash
grep -n "validate_component_code" src/backend/base/langflow/agentic/services/assistant_service.py
```

For each call site (lines 78 and 299 per the grep result), the surrounding function likely has access to either a `current_user` or has already computed gate flags upstream. For each:

**Pattern A — if the function already has access to `current_user`:**

```python
from langflow.api.utils.core import resolve_component_gate_flags
...
    allow_custom_components, caller_is_platform_admin = resolve_component_gate_flags(current_user)
    validation = validate_component_code(
        code,
        allow_custom_components=allow_custom_components,
        caller_is_platform_admin=caller_is_platform_admin,
    )
```

**Pattern B — if the function does not currently receive a user:** add a `*, current_user: User | None = None` kwarg to its signature and to any internal caller, and apply Pattern A. Do NOT default the gate flags to `True`. If the call chain cannot plumb a user for some reason, default to `allow_custom_components=False, caller_is_platform_admin=False` — the secure default.

Read each call site's function enclosing the `validate_component_code` call and apply the appropriate pattern. Record the exact changes made.

- [ ] **Step 6: Run the tests to verify they pass**

Run:
```bash
uv run --active pytest src/backend/tests/unit/agentic/helpers/test_validation_gated.py -v
```
Expected: all four tests PASS.

- [ ] **Step 7: Regression-run the broader agentic test suite**

Run:
```bash
uv run --active pytest src/backend/tests/unit/agentic/ -v
```
Expected: all PASS. If any existing test exercises `validate_component_code` without gate flags, it will hit the new `_ast_only_validate` path — that's correct behavior for "no flags supplied" (secure default). If the test's intent was to exercise the exec path, update it to pass `allow_custom_components=True` explicitly.

- [ ] **Step 8: Ask the user before committing, then commit**

```bash
git add \
  src/backend/base/langflow/agentic/helpers/validation.py \
  src/backend/base/langflow/agentic/services/assistant_service.py \
  src/backend/base/langflow/agentic/api/schemas.py \
  src/backend/tests/unit/agentic/helpers/test_validation_gated.py
git commit -m "$(cat <<'EOF'
fix(security): gate Agentic Assistant validation on ALLOW_CUSTOM_COMPONENTS (CVE-2026-33873)

validate_component_code used to call create_class, which ends in an
unconstrained exec() in lfx.custom.validate.build_class_constructor —
giving authenticated users an LLM-mediated path to server-side Python
execution.

Fork-specific mitigation: reuse the existing LANGFLOW_ALLOW_CUSTOM_COMPONENTS
deployment gate (via resolve_component_gate_flags). When the gate is closed
and the caller is not a platform admin (the multi-tenant default),
validation downgrades to AST-only — ast.parse + class-name extraction,
no imports, no instantiation, no exec. ValidationResult gains an
`executed: bool` field so callers/UI can distinguish parsed-only from
parsed-and-ran.

When the gate is opened (opt-in deployment, or platform-admin caller),
original create-and-instantiate behavior resumes.

Refs: GHSA-v8hw-mh8c-jxfc, CVE-2026-33873.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Revert audit — enumerate what else `642e39fcb8` re-exposed

**Rationale:** The 2026-04-15 revert touched 2,374 files. The 14 published security advisories that we've triaged are only the *publicly disclosed* surface; the revert also removed non-advisory hardenings, refactors, and defense-in-depth improvements that shipped in the 1.9.0 release. This task is pure investigation — no code changes — producing an enumeration of the revert's security-adjacent impact so the team can decide what else deserves a backport.

**Files:**
- Create: `docs/superpowers/security-review-2026-04-23/revert-audit.md`
- Modify: `docs/superpowers/followups.md` (append structured follow-up entries)

- [ ] **Step 1: Inventory the revert**

Run:
```bash
git show --stat 642e39fcb8 | grep -E "^ " | awk '{print $1}' | sort -u > /tmp/reverted-files.txt
wc -l /tmp/reverted-files.txt
```
Expected: ~2,374 file paths (matches the earlier `git show --stat` tail).

- [ ] **Step 2: Filter to security-adjacent directories**

Run:
```bash
grep -E '(api/v1|api/v2|api/utils|auth|services/storage|services/database/models|ssrf|agentic/helpers|initial_setup|services/variable|crypto|security|sanitiz|validate|\.github/workflows)' /tmp/reverted-files.txt | sort > /tmp/reverted-sec-files.txt
wc -l /tmp/reverted-sec-files.txt
head -80 /tmp/reverted-sec-files.txt
```
Expected: several hundred paths. Scan visually for files not already handled by Tasks 1–4 that smell like hardening (`ssrf_protection`, `sanitize`, `validate`, `auth/utils.py`, `api_key`, `profile_pictures`, etc.).

- [ ] **Step 3: For each candidate, fetch the revert's diff for that file and classify it**

For each file path the user or reviewer flags as potentially interesting, run:
```bash
git show 642e39fcb8 -- <path> | head -200
```
Classify the change into one of:
- **Security fix** (auth added, sanitizer added, ownership check, dep bump): candidate for re-application.
- **Refactor coincident with a security fix:** candidate for partial re-application (just the security-relevant hunk).
- **Feature / UI / test** with no security implication: skip.
- **Non-applicable to our fork** (file was replaced on our branch, e.g. watsonx, custom-components gate): skip with note.

- [ ] **Step 4: Write the audit report**

Create `docs/superpowers/security-review-2026-04-23/revert-audit.md` with the following structure:

```markdown
# 2026-04-15 Release-Merge Revert — Security-Adjacent Audit

**Revert commit:** `642e39fcb8` (Adam Aghili, 2026-04-15)
**Reverted merge:** `fe42df76214e621b11abf1e1e338a240ae32cc6e` ("Chore(release): merge release 1.9.0 into main (#12710)")
**Scope:** 2,374 files, −266,104 lines.
**Already handled by 2026-04-23 security plan:** Tasks 1–4.

---

## Candidate re-applies (not in the 14 published advisories)

### <path/to/file.py>

- **What the revert removed:** <1–2 lines summarising the hunk>
- **Security relevance:** <why this might matter>
- **Recommendation:** `RE-APPLY` | `INVESTIGATE` | `SKIP (reason)`
- **Follow-up id:** FU-<n>

(repeat per candidate file)

---

## Non-security changes observed (informational)

<brief notes on large non-security categories — starter flow content,
SDK package, agent/skill documentation, etc. — so the reader doesn't
re-investigate them>

## Summary

- <N> RE-APPLY candidates — ordered by severity.
- <N> INVESTIGATE candidates — need human judgment.
- <N> SKIP with recorded reason.
```

- [ ] **Step 5: Append structured follow-ups**

For each `RE-APPLY` or `INVESTIGATE` candidate, append an entry to `docs/superpowers/followups.md` under a new section:

```markdown
## 2026-04-23 — Revert-audit follow-ups (commit 642e39fcb8)

**Source:** `docs/superpowers/security-review-2026-04-23/revert-audit.md`

### FU-<n>: <short title>

- **File(s):** `<path>`
- **What was reverted:** <summary>
- **Recommendation:** RE-APPLY | INVESTIGATE
- **Priority:** P0 | P1 | P2
- **Notes:** <anything load-bearing>

(repeat per candidate)
```

- [ ] **Step 6: Ask the user before committing, then commit**

```bash
git add \
  docs/superpowers/security-review-2026-04-23/revert-audit.md \
  docs/superpowers/followups.md
git commit -m "$(cat <<'EOF'
docs(security): 2026-04-15 release-merge revert — security-adjacent audit

Enumerates the non-advisory security-adjacent changes removed by commit
642e39fcb8 and files per-candidate follow-ups. Complements the four
coding tasks (CVE-2026-33017, -33484, -33309, -33873) in the 2026-04-23
security-advisory backport plan.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Final Verification

After all five tasks land on `platform-multi-tenant`:

- [ ] `uv run --active pytest src/backend/tests/unit/api/v1/test_build_public_tmp_data_removed.py src/backend/tests/unit/api/v1/test_download_image_ownership.py src/backend/tests/unit/api/v2/test_files_path_traversal.py src/backend/tests/unit/agentic/helpers/test_validation_gated.py -v` — all PASS.
- [ ] `uv run --active pytest src/backend/tests/unit/api/ src/backend/tests/unit/agentic/ -v` — no new failures vs. baseline.
- [ ] `git diff --stat 642e39fcb8..HEAD | grep -E '(api/v1/chat|api/v1/files|api/v2/files|storage/local|agentic/helpers/validation|agentic/api/schemas|agentic/services/assistant_service)\.py'` — exactly the expected files, nothing unexpected.
- [ ] `docs/superpowers/security-review-2026-04-23/revert-audit.md` exists and enumerates candidates.
- [ ] `docs/superpowers/followups.md` has a new `## 2026-04-23 — Revert-audit follow-ups` section.
- [ ] No commits have been pushed anywhere; branch is still `platform-multi-tenant` locally.

---

## Self-Review Notes

1. **Spec coverage:**
   - CVE-2026-33017 → Task 1 (endpoint + defense-in-depth) ✓
   - CVE-2026-33484 → Task 2 (Depends(get_flow)) ✓
   - CVE-2026-33309 → Task 3 (two-layer: API sanitization + storage containment) ✓
   - CVE-2026-33873 → Task 4 (fork-specific gate mitigation — option b per user) ✓
   - Revert audit → Task 5 (user requested: include) ✓
   - 10 APPLIED advisories → called out as Out of Scope in front matter with explicit pointer to the three research reports.

2. **Placeholder scan:** No TBDs. Every code block is copy-pasteable. Task 4 Step 5 explicitly tells the engineer to `grep -n` the call sites and apply Pattern A/B depending on what `current_user` plumbing already exists — this is concrete instruction, not a placeholder. Task 5 lists exact `git show` commands per candidate; the audit is investigative by nature so its *output* is a filled-in template, not a pre-specified diff.

3. **Type consistency:**
   - `resolve_component_gate_flags(user) → tuple[bool, bool]` used identically in Tasks 1 (existing call site in `api/build.py`) and 4 (new call site in `assistant_service.py`).
   - `validate_component_code(code, *, allow_custom_components, caller_is_platform_admin) → ValidationResult` signature is consistent between the declaration in Task 4 Step 4 and the call sites in Task 4 Step 5.
   - `ValidationResult.executed: bool` is added in Step 3, referenced in Step 4 returns, asserted in Step 1 test.

4. **Scope match:** Four coding tasks mirror four missing/partial advisories. One audit task is investigative and produces docs + follow-ups, not code. Test file names are unique; no fixture name collisions with the 2026-04-22 security-fixes plan (`two_tenants` vs. `two_users_with_flow`, `assistant_user` vs. no fixture in Task 4's call-graph-mocking tests).

5. **Commit discipline:** Every task ends with "Ask the user before committing, then commit." No `git push` anywhere. No upstream PRs. No `--no-verify`, no `--amend`.
