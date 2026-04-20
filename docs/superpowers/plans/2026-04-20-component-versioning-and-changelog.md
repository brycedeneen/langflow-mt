# Component Versioning and Changelog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface author-written per-version changelog entries in the Update components modal so users see *what changed* and *what to do*, and add a Claude skill that enforces the version-bump + changelog-append ritual and guides input-type selection.

**Architecture:** Python `Component` subclasses opt in to `version: int` and `changelog: ClassVar[list[ChangelogEntry]]`. Both fields propagate through the component schema builder (`build_custom_component_template*`) onto the `FrontendNode` model, which means every component response JSON gains `version` and `changelog`. On the frontend, `APIClassType` gains the same fields — so both template lookups and saved node data (`data.node`) carry the user's version automatically via existing spreads. `checkCodeValidity` computes the filtered entry list; a new `ChangelogPanel` component renders it. The Update modal adds a chevron/expand column and wraps the panel inline per row. A companion skill at `.claude/skills/langflow-component-authoring/SKILL.md` enforces the author workflow.

**Tech Stack:** Python 3.12 / pydantic v2 / pytest (backend) • React 18 / TypeScript / Vitest / react-markdown (frontend) • Claude skill (Markdown)

**Spec:** `docs/superpowers/specs/2026-04-20-component-versioning-and-changelog-design.md`

---

## File Map

### Backend (Python, lives in lfx)

- **Create** `src/lfx/src/lfx/custom/custom_component/changelog.py` — `ChangelogEntry` pydantic model + `validate_changelog(cls)` helper
- **Modify** `src/lfx/src/lfx/custom/custom_component/component.py` — add `version`, `changelog` class attributes and `__init_subclass__` validation call
- **Modify** `src/lfx/src/lfx/template/frontend_node/base.py` — add `version: int = 0` and `changelog: list[dict] = []` fields to `FrontendNode`
- **Modify** `src/lfx/src/lfx/custom/utils.py` — add `apply_component_versioning(frontend_node, custom_component)` helper; call from both template builders
- **Create** `src/lfx/tests/unit/custom/test_component_changelog.py` — tests for the model, Component subclass validation, and builder integration

### Frontend (TypeScript, React)

- **Modify** `src/frontend/src/types/api/index.ts` — add `ChangelogEntry` type and `version?: number; changelog?: ChangelogEntry[]` on `APIClassType`
- **Modify** `src/frontend/src/types/zustand/flow/index.ts` — extend `ComponentsToUpdateType` with `userVersion`, `latestVersion`, `changelogEntries`
- **Modify** `src/frontend/src/CustomNodes/helpers/check-code-validity.ts` — compute and return the version fields
- **Create** `src/frontend/src/modals/updateComponentModal/changelogPanel.tsx` — reusable "What's changed" panel
- **Modify** `src/frontend/src/modals/updateComponentModal/index.tsx` — chevron column, expand/collapse, inline panel; single-component panel
- **Create** `src/frontend/src/CustomNodes/helpers/__tests__/check-code-validity.test.ts`
- **Create** `src/frontend/src/modals/updateComponentModal/__tests__/changelogPanel.test.tsx`

### Claude skill

- **Create** `.claude/skills/langflow-component-authoring/SKILL.md`

---

## Testing Conventions

- **Backend:** run individual tests with `uv run --project src/lfx pytest <path> -v`. Follow the pattern in `src/backend/tests/unit/test_custom_component.py`.
- **Frontend:** run individual tests with `npx vitest run <path>` from `src/frontend`.
- **All commits:** honor the user's memory — ask before committing. Each task below has a "Commit" step that is a *prompt to the user*, not an automatic action.

---

## Task 1: `ChangelogEntry` pydantic model

**Files:**
- Create: `src/lfx/src/lfx/custom/custom_component/changelog.py`
- Test: `src/lfx/tests/unit/custom/test_component_changelog.py`

- [ ] **Step 1: Write the failing test**

Create `src/lfx/tests/unit/custom/test_component_changelog.py`:

```python
import pytest
from pydantic import ValidationError

from lfx.custom.custom_component.changelog import ChangelogEntry


class TestChangelogEntry:
    def test_minimal_fields(self):
        entry = ChangelogEntry(version=1, changes="Initial release")
        assert entry.version == 1
        assert entry.changes == "Initial release"
        assert entry.notes is None

    def test_with_notes(self):
        entry = ChangelogEntry(
            version=2,
            changes="Renamed `api_key` to `auth_token`.",
            notes="Re-enter your key under Bearer Token.",
        )
        assert entry.notes == "Re-enter your key under Bearer Token."

    def test_changes_required(self):
        with pytest.raises(ValidationError):
            ChangelogEntry(version=1)  # type: ignore[call-arg]

    def test_version_must_be_int(self):
        with pytest.raises(ValidationError):
            ChangelogEntry(version="1", changes="x")  # type: ignore[arg-type]

    def test_model_dump_includes_null_notes(self):
        entry = ChangelogEntry(version=1, changes="x")
        dumped = entry.model_dump()
        assert dumped == {"version": 1, "changes": "x", "notes": None}
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run --project src/lfx pytest src/lfx/tests/unit/custom/test_component_changelog.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'lfx.custom.custom_component.changelog'`.

- [ ] **Step 3: Implement the model**

Create `src/lfx/src/lfx/custom/custom_component/changelog.py`:

```python
"""Changelog primitives surfaced by the Update components modal."""

from pydantic import BaseModel


class ChangelogEntry(BaseModel):
    """A single changelog entry tied to a component `version` bump.

    Authors append one of these per version bump. `changes` and `notes`
    both accept markdown and are rendered in the Update components modal.
    """

    version: int
    changes: str
    notes: str | None = None
```

- [ ] **Step 4: Run to verify pass**

```bash
uv run --project src/lfx pytest src/lfx/tests/unit/custom/test_component_changelog.py -v
```
Expected: PASS — 5 tests.

- [ ] **Step 5: Ask the user to commit**

Propose (do not run yet):

```bash
git add src/lfx/src/lfx/custom/custom_component/changelog.py src/lfx/tests/unit/custom/test_component_changelog.py
git commit -m "feat(lfx): add ChangelogEntry model for component versioning"
```

---

## Task 2: `validate_changelog` helper with non-fatal warnings

**Files:**
- Modify: `src/lfx/src/lfx/custom/custom_component/changelog.py`
- Modify: `src/lfx/tests/unit/custom/test_component_changelog.py`

- [ ] **Step 1: Write the failing test**

Append to `src/lfx/tests/unit/custom/test_component_changelog.py`:

```python
import logging

from lfx.custom.custom_component.changelog import ChangelogEntry, validate_changelog


class _Holder:
    """Stand-in for a Component subclass during validation tests."""

    __name__ = "StubComponent"
    version = 0
    changelog: list[ChangelogEntry] = []


class TestValidateChangelog:
    def test_happy_path_no_warnings(self, caplog):
        cls = type(
            "C",
            (_Holder,),
            {
                "version": 2,
                "changelog": [
                    ChangelogEntry(version=1, changes="x"),
                    ChangelogEntry(version=2, changes="y"),
                ],
            },
        )
        with caplog.at_level(logging.WARNING):
            validate_changelog(cls)
        assert not caplog.records

    def test_warns_when_entry_version_exceeds_class_version(self, caplog):
        cls = type(
            "C",
            (_Holder,),
            {
                "version": 1,
                "changelog": [ChangelogEntry(version=3, changes="x")],
            },
        )
        with caplog.at_level(logging.WARNING):
            validate_changelog(cls)
        assert any("exceeds class version" in r.message for r in caplog.records)

    def test_warns_on_duplicate_versions(self, caplog):
        cls = type(
            "C",
            (_Holder,),
            {
                "version": 2,
                "changelog": [
                    ChangelogEntry(version=1, changes="x"),
                    ChangelogEntry(version=1, changes="y"),
                ],
            },
        )
        with caplog.at_level(logging.WARNING):
            validate_changelog(cls)
        assert any("duplicate version" in r.message for r in caplog.records)

    def test_warns_on_non_positive_entry_version(self, caplog):
        cls = type(
            "C",
            (_Holder,),
            {
                "version": 1,
                "changelog": [ChangelogEntry(version=0, changes="x")],
            },
        )
        with caplog.at_level(logging.WARNING):
            validate_changelog(cls)
        assert any("must be >= 1" in r.message for r in caplog.records)

    def test_skips_when_changelog_empty(self, caplog):
        cls = _Holder
        with caplog.at_level(logging.WARNING):
            validate_changelog(cls)
        assert not caplog.records
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run --project src/lfx pytest src/lfx/tests/unit/custom/test_component_changelog.py::TestValidateChangelog -v
```
Expected: FAIL with `ImportError: cannot import name 'validate_changelog'`.

- [ ] **Step 3: Implement the validator**

Append to `src/lfx/src/lfx/custom/custom_component/changelog.py`:

```python
import logging

logger = logging.getLogger(__name__)


def validate_changelog(cls: type) -> None:
    """Emit non-fatal warnings for malformed component version / changelog setups.

    Called from `Component.__init_subclass__`. Never raises — bad changelog data
    is an author mistake, not a reason to refuse to load the component.
    """
    entries = getattr(cls, "changelog", None) or []
    if not entries:
        return

    class_version = getattr(cls, "version", 0) or 0
    seen: set[int] = set()

    for entry in entries:
        if entry.version < 1:
            logger.warning(
                "%s.changelog entry version must be >= 1, got %s.",
                cls.__name__,
                entry.version,
            )
        if entry.version in seen:
            logger.warning(
                "%s.changelog has duplicate version %s.",
                cls.__name__,
                entry.version,
            )
        seen.add(entry.version)
        if entry.version > class_version:
            logger.warning(
                "%s.changelog entry version %s exceeds class version %s.",
                cls.__name__,
                entry.version,
                class_version,
            )
```

- [ ] **Step 4: Run to verify pass**

```bash
uv run --project src/lfx pytest src/lfx/tests/unit/custom/test_component_changelog.py -v
```
Expected: PASS — all tests.

- [ ] **Step 5: Ask the user to commit**

```bash
git add src/lfx/src/lfx/custom/custom_component/changelog.py src/lfx/tests/unit/custom/test_component_changelog.py
git commit -m "feat(lfx): add validate_changelog helper with non-fatal warnings"
```

---

## Task 3: Add `version` and `changelog` to `Component` base class

**Files:**
- Modify: `src/lfx/src/lfx/custom/custom_component/component.py:112-116` (class declaration)

- [ ] **Step 1: Write the failing test**

Append to `src/lfx/tests/unit/custom/test_component_changelog.py`:

```python
from typing import ClassVar

from lfx.custom.custom_component.component import Component


class TestComponentVersionAttrs:
    def test_defaults(self):
        class Plain(Component):
            display_name = "Plain"

        assert Plain.version == 0
        assert Plain.changelog == []

    def test_subclass_can_override(self):
        class Versioned(Component):
            display_name = "Versioned"
            version: int = 2
            changelog: ClassVar[list[ChangelogEntry]] = [
                ChangelogEntry(version=1, changes="Initial"),
                ChangelogEntry(version=2, changes="Second"),
            ]

        assert Versioned.version == 2
        assert len(Versioned.changelog) == 2

    def test_subclass_triggers_validation_warning(self, caplog):
        with caplog.at_level(logging.WARNING):
            class Bad(Component):
                display_name = "Bad"
                version: int = 1
                changelog: ClassVar[list[ChangelogEntry]] = [
                    ChangelogEntry(version=5, changes="x"),  # exceeds class version
                ]
        assert any("exceeds class version" in r.message for r in caplog.records)
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run --project src/lfx pytest src/lfx/tests/unit/custom/test_component_changelog.py::TestComponentVersionAttrs -v
```
Expected: FAIL — `AttributeError: type object 'Plain' has no attribute 'version'` or similar.

- [ ] **Step 3: Add the attributes and `__init_subclass__`**

In `src/lfx/src/lfx/custom/custom_component/component.py`, at the top of the file add the import (near the other `from lfx.custom...` imports):

```python
from typing import ClassVar

from lfx.custom.custom_component.changelog import ChangelogEntry, validate_changelog
```

Replace lines 112-116 (the `Component` class declaration + its class-level attrs) with:

```python
class Component(CustomComponent):
    inputs: list[InputTypes] = []
    outputs: list[Output] = []
    selected_output: str | None = None
    code_class_base_inheritance: ClassVar[str] = "Component"

    # Authoring-opt-in: see docs/superpowers/specs/2026-04-20-component-versioning-and-changelog-design.md
    version: int = 0
    changelog: ClassVar[list[ChangelogEntry]] = []

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        validate_changelog(cls)
```

- [ ] **Step 4: Run to verify pass**

```bash
uv run --project src/lfx pytest src/lfx/tests/unit/custom/test_component_changelog.py -v
```
Expected: PASS — all tests including the new three.

- [ ] **Step 5: Run the broader lfx custom-component tests to catch regressions**

```bash
uv run --project src/lfx pytest src/lfx/tests -k "custom" -x
```
Expected: existing tests continue to pass. If not, investigate before moving on.

- [ ] **Step 6: Ask the user to commit**

```bash
git add src/lfx/src/lfx/custom/custom_component/component.py
git commit -m "feat(lfx): add version and changelog attrs to Component"
```

---

## Task 4: Add `version` and `changelog` to `FrontendNode`

**Files:**
- Modify: `src/lfx/src/lfx/template/frontend_node/base.py:9-67` (FrontendNode field list)

- [ ] **Step 1: Write the failing test**

Create `src/lfx/tests/unit/template/test_frontend_node_versioning.py`:

```python
from lfx.template.frontend_node.base import FrontendNode


class TestFrontendNodeVersioning:
    def test_defaults(self):
        node = FrontendNode(base_classes=["Foo"], template={"type_name": "Foo", "fields": []})
        assert node.version == 0
        assert node.changelog == []

    def test_serialize_roundtrip(self):
        node = FrontendNode(
            base_classes=["Foo"],
            template={"type_name": "Foo", "fields": []},
            version=3,
            changelog=[
                {"version": 3, "changes": "c3", "notes": "n3"},
                {"version": 2, "changes": "c2", "notes": None},
            ],
        )
        dumped = node.to_dict()
        # `to_dict` wraps under `name`; grab the inner dict
        inner = next(iter(dumped.values()))
        assert inner["version"] == 3
        assert inner["changelog"] == [
            {"version": 3, "changes": "c3", "notes": "n3"},
            {"version": 2, "changes": "c2", "notes": None},
        ]
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run --project src/lfx pytest src/lfx/tests/unit/template/test_frontend_node_versioning.py -v
```
Expected: FAIL — `AttributeError` or `ValidationError` on unknown field.

- [ ] **Step 3: Add the fields**

In `src/lfx/src/lfx/template/frontend_node/base.py`, after line 67 (the `tool_mode` field) and before line 69 (`def set_documentation`), add:

```python
    version: int = 0
    """Author-declared version of this component. Defaults to 0."""
    changelog: list[dict] = []
    """Per-version changelog entries (dumped `ChangelogEntry` dicts). Newest last."""
```

- [ ] **Step 4: Run to verify pass**

```bash
uv run --project src/lfx pytest src/lfx/tests/unit/template/test_frontend_node_versioning.py -v
```
Expected: PASS — 2 tests.

- [ ] **Step 5: Ask the user to commit**

```bash
git add src/lfx/src/lfx/template/frontend_node/base.py src/lfx/tests/unit/template/test_frontend_node_versioning.py
git commit -m "feat(lfx): serialize version and changelog on FrontendNode"
```

---

## Task 5: Propagate `version` / `changelog` through the template builders

**Files:**
- Modify: `src/lfx/src/lfx/custom/utils.py:464` and `:540` (both builder functions)

- [ ] **Step 1: Write the failing test**

Append to `src/lfx/tests/unit/custom/test_component_changelog.py`:

```python
from lfx.custom.custom_component.component import Component
from lfx.custom.utils import build_custom_component_template


class TestBuilderPropagation:
    def test_version_and_changelog_emitted(self):
        class VC(Component):
            display_name = "VC"
            version: int = 2
            changelog: ClassVar[list[ChangelogEntry]] = [
                ChangelogEntry(version=1, changes="a"),
                ChangelogEntry(version=2, changes="b", notes="do X"),
            ]

            def build(self):
                return "ok"

        instance = VC()
        frontend_dict, _ = build_custom_component_template(instance)
        assert frontend_dict["version"] == 2
        assert frontend_dict["changelog"] == [
            {"version": 1, "changes": "a", "notes": None},
            {"version": 2, "changes": "b", "notes": "do X"},
        ]

    def test_defaults_when_unset(self):
        class Plain(Component):
            display_name = "Plain"

            def build(self):
                return "ok"

        instance = Plain()
        frontend_dict, _ = build_custom_component_template(instance)
        assert frontend_dict["version"] == 0
        assert frontend_dict["changelog"] == []
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run --project src/lfx pytest src/lfx/tests/unit/custom/test_component_changelog.py::TestBuilderPropagation -v
```
Expected: FAIL — `KeyError: 'version'` because the fields aren't written onto the frontend_node yet.

- [ ] **Step 3: Add the helper**

In `src/lfx/src/lfx/custom/utils.py`, directly above `build_custom_component_template_from_inputs` (line 464), add:

```python
def apply_component_versioning(frontend_node, custom_component) -> None:
    """Copy opt-in `version` and `changelog` from a Component onto its FrontendNode.

    Safe on CustomComponent subclasses that don't declare either attr — both
    default to `0` and `[]` respectively.
    """
    frontend_node.version = getattr(custom_component, "version", 0) or 0
    entries = getattr(custom_component, "changelog", None) or []
    frontend_node.changelog = [
        entry.model_dump() if hasattr(entry, "model_dump") else entry
        for entry in entries
    ]
```

Then call it in both builders.

In `build_custom_component_template_from_inputs` (line 464), after the line `frontend_node.set_base_classes_from_outputs()` (line 500) — or anywhere after `frontend_node` is fully built but before `.to_dict()` on line 504 — add:

```python
    apply_component_versioning(frontend_node, cc_instance)
```

In `build_custom_component_template` (line 540), after `reorder_fields(frontend_node, custom_instance._get_field_order())` (line 594) and before the `if module_name:` on line 596, add:

```python
        apply_component_versioning(frontend_node, custom_instance)
```

- [ ] **Step 4: Run to verify pass**

```bash
uv run --project src/lfx pytest src/lfx/tests/unit/custom/test_component_changelog.py -v
```
Expected: PASS — including the two new `TestBuilderPropagation` tests.

- [ ] **Step 5: Run the broader custom-component suite**

```bash
uv run --project src/lfx pytest src/lfx/tests/unit/custom -x
```
Expected: existing tests continue to pass.

- [ ] **Step 6: Ask the user to commit**

```bash
git add src/lfx/src/lfx/custom/utils.py src/lfx/tests/unit/custom/test_component_changelog.py
git commit -m "feat(lfx): propagate version and changelog through template builders"
```

---

## Task 6: Frontend types — `APIClassType` and `ComponentsToUpdateType`

**Files:**
- Modify: `src/frontend/src/types/api/index.ts:31-68` (APIClassType)
- Modify: `src/frontend/src/types/zustand/flow/index.ts:55-62` (ComponentsToUpdateType)

- [ ] **Step 1: Add the `ChangelogEntry` type and extend `APIClassType`**

In `src/frontend/src/types/api/index.ts`, add a new type above `APIClassType` (above line 31):

```ts
export type ChangelogEntry = {
  version: number;
  changes: string;
  notes: string | null;
};
```

Add the following to `APIClassType` (inside the object definition, near `edited?: boolean;` on line 37):

```ts
  version?: number;
  changelog?: ChangelogEntry[];
```

Then update the index-signature union (lines 58-67) to include the new value types by appending:

```ts
    | number
    | ChangelogEntry[]
```

to the `[key: string]:` union.

- [ ] **Step 2: Extend `ComponentsToUpdateType`**

In `src/frontend/src/types/zustand/flow/index.ts`, add the import at the top (alongside existing type imports):

```ts
import type { ChangelogEntry } from "@/types/api";
```

Replace lines 55-62 with:

```ts
export type ComponentsToUpdateType = {
  id: string;
  icon?: string;
  display_name: string;
  outdated: boolean;
  breakingChange: boolean;
  userEdited: boolean;
  userVersion: number;
  latestVersion: number;
  changelogEntries: ChangelogEntry[];
};
```

- [ ] **Step 3: Typecheck**

```bash
cd src/frontend && npx tsc --noEmit
```
Expected: PASS. If errors appear in callers that construct `ComponentsToUpdateType`, they'll be addressed in Task 7 (`check-code-validity.ts`). If other callers fail outside that file, fix them to supply defaults (`userVersion: 0, latestVersion: 0, changelogEntries: []`).

- [ ] **Step 4: Ask the user to commit**

```bash
git add src/frontend/src/types/api/index.ts src/frontend/src/types/zustand/flow/index.ts
git commit -m "feat(frontend): type version and changelog on APIClassType"
```

---

## Task 7: Compute changelog-aware fields in `checkCodeValidity`

**Files:**
- Modify: `src/frontend/src/CustomNodes/helpers/check-code-validity.ts`
- Create: `src/frontend/src/CustomNodes/helpers/__tests__/check-code-validity.test.ts`

- [ ] **Step 1: Write the failing test**

Create `src/frontend/src/CustomNodes/helpers/__tests__/check-code-validity.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import checkCodeValidity from "../check-code-validity";

const fakeNode = (nodeOverrides: Record<string, unknown> = {}) => ({
  id: "n1",
  type: "MyComp",
  node: {
    display_name: "MyComp",
    description: "",
    documentation: "",
    template: { code: { value: "old code" } },
    outputs: [],
    ...nodeOverrides,
  } as any,
});

const template = (latestVersion: number, entries: Array<Record<string, unknown>> = [], code = "new code") => ({
  MyComp: {
    template: { code: { value: code } },
    outputs: [],
    version: latestVersion,
    changelog: entries,
  },
});

describe("checkCodeValidity — version fields", () => {
  it("returns defaults when neither node nor template declare version", () => {
    const result = checkCodeValidity(fakeNode() as any, template(0));
    expect(result?.userVersion).toBe(0);
    expect(result?.latestVersion).toBe(0);
    expect(result?.changelogEntries).toEqual([]);
  });

  it("filters and sorts entries between user and latest, newest first", () => {
    const entries = [
      { version: 1, changes: "c1", notes: null },
      { version: 2, changes: "c2", notes: "n2" },
      { version: 3, changes: "c3", notes: null },
    ];
    const result = checkCodeValidity(
      fakeNode({ version: 1 }) as any,
      template(3, entries),
    );
    expect(result?.userVersion).toBe(1);
    expect(result?.latestVersion).toBe(3);
    expect(result?.changelogEntries.map((e) => e.version)).toEqual([3, 2]);
  });

  it("includes all entries when node has no version (treated as 0)", () => {
    const entries = [
      { version: 1, changes: "c1", notes: null },
      { version: 2, changes: "c2", notes: null },
    ];
    const result = checkCodeValidity(fakeNode() as any, template(2, entries));
    expect(result?.userVersion).toBe(0);
    expect(result?.changelogEntries.map((e) => e.version)).toEqual([2, 1]);
  });

  it("ignores entries past latest version (author mistake)", () => {
    const entries = [
      { version: 1, changes: "c1", notes: null },
      { version: 5, changes: "c5", notes: null },
    ];
    const result = checkCodeValidity(fakeNode() as any, template(2, entries));
    expect(result?.changelogEntries.map((e) => e.version)).toEqual([1]);
  });

  it("returns empty changelog when user version equals latest", () => {
    const entries = [{ version: 2, changes: "c2", notes: null }];
    const result = checkCodeValidity(fakeNode({ version: 2 }) as any, template(2, entries));
    expect(result?.changelogEntries).toEqual([]);
  });
});
```

- [ ] **Step 2: Run to verify failure**

```bash
cd src/frontend && npx vitest run src/CustomNodes/helpers/__tests__/check-code-validity.test.ts
```
Expected: FAIL — `userVersion` is undefined on the return value.

- [ ] **Step 3: Update `checkCodeValidity` to compute the new fields**

In `src/frontend/src/CustomNodes/helpers/check-code-validity.ts`, update the imports at the top:

```ts
import { componentsToIgnoreUpdate } from "@/constants/constants";
import type { ChangelogEntry, OutputFieldType } from "@/types/api";
import type { NodeDataType } from "../../types/flow";
```

Replace the `checkCodeValidity` function (lines 53-81) with:

```ts
export const checkCodeValidity = (
  data: NodeDataType,
  templates: { [key: string]: any },
) => {
  if (!data?.node || !templates) return;
  const template = templates[data.type]?.template;
  const currentCode = template?.code?.value;
  const thisNodesCode = data.node!.template?.code?.value;
  const originalOutputs = templates[data.type]?.outputs;
  const userOutputs = data.node?.outputs;
  const originalTemplate = template;
  const userTemplate = data.node?.template;
  const isOutdated = codeIsOutdated(currentCode, thisNodesCode, data.type);

  const hasBreakingChange = isOutdated
    ? codeHasBreakingChange(
        originalOutputs,
        userOutputs,
        originalTemplate,
        userTemplate,
      )
    : false;

  const userVersion: number = data.node?.version ?? 0;
  const latestVersion: number = templates[data.type]?.version ?? 0;
  const rawEntries: ChangelogEntry[] = templates[data.type]?.changelog ?? [];
  const changelogEntries: ChangelogEntry[] = rawEntries
    .filter((e) => e.version > userVersion && e.version <= latestVersion)
    .sort((a, b) => b.version - a.version);

  return {
    outdated: isOutdated,
    breakingChange: hasBreakingChange,
    userEdited: data.node?.edited ?? false,
    userVersion,
    latestVersion,
    changelogEntries,
  };
};
```

- [ ] **Step 4: Run to verify pass**

```bash
cd src/frontend && npx vitest run src/CustomNodes/helpers/__tests__/check-code-validity.test.ts
```
Expected: PASS — 5 tests.

- [ ] **Step 5: Plumb the new fields through `flowStore.updateComponentsToUpdate`**

Open `src/frontend/src/stores/flowStore.ts` and find `updateComponentsToUpdate` (around line 95-113). It should already pass every field returned by `checkCodeValidity` into `componentsToUpdate`. If it uses spread (`...result`), no change needed. If it hand-picks properties, add `userVersion`, `latestVersion`, `changelogEntries` to the mapping.

Verify with `grep -n "userVersion\|latestVersion\|changelogEntries" src/frontend/src/stores/flowStore.ts` → should find the new fields in the output object. If they're not there and the store hand-picks, add them:

```ts
{
  id: node.id,
  icon: node.data.node.icon,
  display_name: node.data.node.display_name,
  outdated,
  breakingChange,
  userEdited,
  userVersion,
  latestVersion,
  changelogEntries,
}
```

- [ ] **Step 6: Typecheck**

```bash
cd src/frontend && npx tsc --noEmit
```
Expected: PASS.

- [ ] **Step 7: Ask the user to commit**

```bash
git add src/frontend/src/CustomNodes/helpers/check-code-validity.ts \
        src/frontend/src/CustomNodes/helpers/__tests__/check-code-validity.test.ts \
        src/frontend/src/stores/flowStore.ts
git commit -m "feat(frontend): compute changelog entries in checkCodeValidity"
```

---

## Task 8: `ChangelogPanel` — the reusable "What's changed" block

**Files:**
- Create: `src/frontend/src/modals/updateComponentModal/changelogPanel.tsx`
- Create: `src/frontend/src/modals/updateComponentModal/__tests__/changelogPanel.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `src/frontend/src/modals/updateComponentModal/__tests__/changelogPanel.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ChangelogPanel from "../changelogPanel";

describe("ChangelogPanel", () => {
  it("renders version range and entries in the given order", () => {
    render(
      <ChangelogPanel
        userVersion={1}
        latestVersion={3}
        breaking={false}
        entries={[
          { version: 3, changes: "c3", notes: "n3" },
          { version: 2, changes: "c2", notes: null },
        ]}
      />,
    );
    expect(screen.getByText(/v1 → v3/)).toBeInTheDocument();
    expect(screen.getByText("v3")).toBeInTheDocument();
    expect(screen.getByText("v2")).toBeInTheDocument();
    expect(screen.getByText("c3")).toBeInTheDocument();
    expect(screen.getByText("n3")).toBeInTheDocument();
    expect(screen.getByText("c2")).toBeInTheDocument();
  });

  it("omits the Notes heading when notes is null", () => {
    const { container } = render(
      <ChangelogPanel
        userVersion={0}
        latestVersion={1}
        breaking={false}
        entries={[{ version: 1, changes: "c1", notes: null }]}
      />,
    );
    expect(container.textContent).not.toMatch(/Notes/);
  });

  it("renders fallback copy when entries is empty but outdated", () => {
    render(
      <ChangelogPanel
        userVersion={1}
        latestVersion={1}
        breaking={true}
        entries={[]}
        showEmptyFallback
      />,
    );
    expect(
      screen.getByText(/No changelog entries available/i),
    ).toBeInTheDocument();
  });

  it("returns null when entries is empty and showEmptyFallback is false", () => {
    const { container } = render(
      <ChangelogPanel
        userVersion={1}
        latestVersion={1}
        breaking={false}
        entries={[]}
      />,
    );
    expect(container.firstChild).toBeNull();
  });
});
```

- [ ] **Step 2: Run to verify failure**

```bash
cd src/frontend && npx vitest run src/modals/updateComponentModal/__tests__/changelogPanel.test.tsx
```
Expected: FAIL — `Cannot find module '../changelogPanel'`.

- [ ] **Step 3: Implement the panel**

Create `src/frontend/src/modals/updateComponentModal/changelogPanel.tsx`:

```tsx
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChangelogEntry } from "@/types/api";
import { cn } from "@/utils/utils";

type Props = {
  userVersion: number;
  latestVersion: number;
  entries: ChangelogEntry[];
  breaking: boolean;
  showEmptyFallback?: boolean;
  className?: string;
};

export default function ChangelogPanel({
  userVersion,
  latestVersion,
  entries,
  breaking,
  showEmptyFallback = false,
  className,
}: Props) {
  if (entries.length === 0) {
    if (!showEmptyFallback) return null;
    return (
      <div
        className={cn(
          "rounded-md border bg-muted/40 p-3 text-xs text-muted-foreground",
          breaking && "border-l-2 border-l-accent-amber-foreground",
          className,
        )}
      >
        No changelog entries available. This update may still change behavior — see the Breaking/Standard label.
      </div>
    );
  }

  return (
    <div
      className={cn(
        "rounded-md border bg-muted/40 p-3 text-xs",
        breaking && "border-l-2 border-l-accent-amber-foreground",
        className,
      )}
      data-testid="changelog-panel"
    >
      <div className="mb-2 flex items-baseline justify-between">
        <strong className="text-sm">What's changed</strong>
        <span className="text-[10px] text-muted-foreground">
          v{userVersion} → v{latestVersion}
        </span>
      </div>

      {entries.map((entry, i) => (
        <div
          key={entry.version}
          className={cn(
            i > 0 && "mt-2 border-t border-dashed border-border pt-2",
          )}
        >
          <div className="mb-1 text-[10px] uppercase tracking-wide text-muted-foreground">
            v{entry.version}
          </div>
          <div className="mb-1 font-semibold">Changes</div>
          <div className="prose prose-sm max-w-none dark:prose-invert">
            <Markdown remarkPlugins={[remarkGfm]}>{entry.changes}</Markdown>
          </div>
          {entry.notes ? (
            <>
              <div className="mt-2 mb-1 font-semibold">Notes</div>
              <div className="prose prose-sm max-w-none dark:prose-invert">
                <Markdown remarkPlugins={[remarkGfm]}>{entry.notes}</Markdown>
              </div>
            </>
          ) : null}
        </div>
      ))}
    </div>
  );
}
```

Notes on deps: `react-markdown` and `remark-gfm` are already used elsewhere in the frontend — no new deps. Run `cd src/frontend && grep "react-markdown\|remark-gfm" package.json` to verify.

- [ ] **Step 4: Run to verify pass**

```bash
cd src/frontend && npx vitest run src/modals/updateComponentModal/__tests__/changelogPanel.test.tsx
```
Expected: PASS — 4 tests.

- [ ] **Step 5: Ask the user to commit**

```bash
git add src/frontend/src/modals/updateComponentModal/changelogPanel.tsx \
        src/frontend/src/modals/updateComponentModal/__tests__/changelogPanel.test.tsx
git commit -m "feat(frontend): add ChangelogPanel for the update modal"
```

---

## Task 9: Wire the panel into the Update components modal

**Files:**
- Modify: `src/frontend/src/modals/updateComponentModal/index.tsx`

- [ ] **Step 1: Add chevron column + expansion state (multi-component path)**

In `src/frontend/src/modals/updateComponentModal/index.tsx`:

Add an import at the top:

```ts
import ChangelogPanel from "./changelogPanel";
```

Inside `UpdateComponentModal`, add an `expandedRows` state alongside `selectedComponents` (line 30):

```ts
const [expandedRows, setExpandedRows] = useState<Set<string>>(
  new Set(components.filter((c) => c.breakingChange).map((c) => c.id)),
);
```

And update the `useEffect` at line 104 so expansion resets when the modal opens:

```ts
useEffect(() => {
  if (open) {
    setBackupFlow(true);
    setSelectedComponents(
      new Set(components.filter((c) => !c.breakingChange).map((c) => c.id)),
    );
    setExpandedRows(
      new Set(components.filter((c) => c.breakingChange).map((c) => c.id)),
    );
  }
}, [open]);
```

- [ ] **Step 2: Add the chevron column and detail-row renderer**

Prepend a new column to `columnDefs` (above the existing `id` hidden column at line 62):

```ts
{
  field: "expand",
  headerName: "",
  width: 28,
  resizable: false,
  suppressMovable: true,
  cellRenderer: (params: any) => {
    const id = params.data.id;
    const isOpen = expandedRows.has(id);
    return (
      <button
        type="button"
        aria-label={isOpen ? "Collapse" : "Expand"}
        className="p-1 text-muted-foreground"
        onClick={(e) => {
          e.stopPropagation();
          setExpandedRows((prev) => {
            const next = new Set(prev);
            next.has(id) ? next.delete(id) : next.add(id);
            return next;
          });
        }}
      >
        <ForwardedIconComponent
          name={isOpen ? "ChevronDown" : "ChevronRight"}
          className="h-4 w-4"
        />
      </button>
    );
  },
},
```

ag-grid's built-in detail-row / `masterDetail` feature isn't enabled in the existing `TableComponent` setup. To keep scope small, **render the expanded panel *outside* the grid**: below each ag-grid row visually. The simplest implementation is to replace the grid with a plain `<ul>`-style rendering because:

1. Inline row expansion in ag-grid requires enterprise features we don't use.
2. The data is simple (components, ≤ a few dozen) — custom rendering is cheap.

Replace the `<TableComponent ... />` block (lines 172-193) with a plain list:

```tsx
{isMultiple && (
  <div className="max-h-[320px] overflow-y-auto -mx-4">
    <div className="grid grid-cols-[28px_28px_1fr_100px] items-center gap-2 border-b px-4 py-1 text-[11px] text-muted-foreground">
      <span />
      <Checkbox
        checked={
          components.length > 0 &&
          selectedComponents.size === components.length
        }
        onCheckedChange={(checked) => {
          if (checked === true) {
            setSelectedComponents(new Set(components.map((c) => c.id)));
          } else {
            setSelectedComponents(new Set());
          }
        }}
        aria-label="Select all"
      />
      <span>Component</span>
      <span>Update Type</span>
    </div>

    {components.map((c) => {
      const isSelected = selectedComponents.has(c.id);
      const isOpen = expandedRows.has(c.id);
      return (
        <div key={c.id} className="border-b last:border-b-0 px-4 py-2">
          <div className="grid grid-cols-[28px_28px_1fr_100px] items-center gap-2">
            <button
              type="button"
              aria-label={isOpen ? "Collapse" : "Expand"}
              className="text-muted-foreground"
              onClick={() =>
                setExpandedRows((prev) => {
                  const next = new Set(prev);
                  next.has(c.id) ? next.delete(c.id) : next.add(c.id);
                  return next;
                })
              }
            >
              <ForwardedIconComponent
                name={isOpen ? "ChevronDown" : "ChevronRight"}
                className="h-4 w-4"
              />
            </button>
            <Checkbox
              checked={isSelected}
              onCheckedChange={(checked) => {
                setSelectedComponents((prev) => {
                  const next = new Set(prev);
                  if (checked === true) next.add(c.id);
                  else next.delete(c.id);
                  return next;
                });
              }}
              aria-label={`Select ${c.display_name}`}
            />
            <div className="flex items-center gap-2">
              {c.icon && (
                <ForwardedIconComponent
                  name={c.icon}
                  className="h-4 w-4"
                />
              )}
              <span>{c.display_name}</span>
            </div>
            <span
              className={cn(
                "text-mmd",
                c.breakingChange
                  ? "font-semibold text-accent-amber-foreground"
                  : "text-muted-foreground",
              )}
            >
              {c.breakingChange ? "Breaking" : "Standard"}
            </span>
          </div>

          {isOpen && (c.outdated) && (
            <div className="mt-2 ml-14">
              <ChangelogPanel
                userVersion={c.userVersion}
                latestVersion={c.latestVersion}
                entries={c.changelogEntries}
                breaking={c.breakingChange}
                showEmptyFallback
              />
            </div>
          )}
        </div>
      );
    })}
  </div>
)}
```

Remove the now-unused `columnDefs`, `agGrid` ref, and the old ag-grid-specific `useEffect` (line 113-123). Remove imports for `ColDef`, `AgGridReact`, `TableComponent` if they're no longer referenced.

- [ ] **Step 3: Render the panel in the single-component path**

After the descriptive paragraphs block (ends at line 169) and before the `{isMultiple && ...}` block, add a single-component panel:

```tsx
{!isMultiple && components[0]?.outdated && (
  <ChangelogPanel
    userVersion={components[0].userVersion}
    latestVersion={components[0].latestVersion}
    entries={components[0].changelogEntries}
    breaking={components[0].breakingChange}
  />
)}
```

(No fallback message for single-component — the current modal copy is enough, as specified.)

- [ ] **Step 4: Typecheck + smoke-test the frontend build**

```bash
cd src/frontend && npx tsc --noEmit
```
Expected: PASS.

```bash
cd src/frontend && npm run build
```
Expected: PASS. Watch for unresolved imports or removed-but-still-referenced symbols.

- [ ] **Step 5: Manually test the UI**

Run the dev server (`make frontend` or the existing command the user uses). Open a flow with:
- A single component with a changelog bump → single-component modal shows the panel.
- A single component with a changelog bump but a non-breaking update → panel shows, `Standard` label.
- A single outdated component with no changelog entries → panel is hidden, modal reads like today.
- Multiple components, some breaking → breaking rows auto-open, standard rows collapsed; chevron toggles each row.

Confirm markdown renders (bold, inline code, bullet lists).

- [ ] **Step 6: Ask the user to commit**

```bash
git add src/frontend/src/modals/updateComponentModal/index.tsx
git commit -m "feat(frontend): render changelog panel in Update components modal"
```

---

## Task 10: Preserve `data.node.version` on sidebar drop and update

**Files:**
- Verify: `src/frontend/src/CustomNodes/hooks/use-update-node-code.ts`
- Check: wherever sidebar drops create a node's `data` — likely `src/frontend/src/utils/utils.ts` or `src/frontend/src/stores/flowStore.ts` (new-node creation)

- [ ] **Step 1: Verify update action already propagates version**

Open `src/frontend/src/CustomNodes/hooks/use-update-node-code.ts`. Confirm that line 24 (`node: { ...newNodeClass, edited: false }`) spreads `newNodeClass` — which now carries `version` via the extended `APIClassType`. No change needed; document in a comment:

```ts
// `newNodeClass` carries the latest `version` and `changelog` from the
// template; they land on `data.node` via this spread.
node: { ...newNodeClass, edited: false },
```

- [ ] **Step 2: Find the sidebar-drop node-creation path**

Run:

```bash
grep -rn "data:\s*{\s*node:" src/frontend/src/pages src/frontend/src/utils src/frontend/src/stores src/frontend/src/components | head -20
```

Expected: several matches. Identify the one invoked on sidebar drop (likely a helper that deep-clones the template and sets initial `data.node`). If the helper assigns `node: cloneDeep(templateClass)`, the `version` field rides along automatically. If it hand-picks fields, add `version: templateClass.version ?? 0`.

- [ ] **Step 3: Add a targeted test or manual verification**

If the node-creation helper is a plain function, write a unit test (vitest) asserting that the resulting `data.node.version` equals the template's version. Otherwise, manually: drop a new component, open DevTools Redux-like store inspector / React DevTools, confirm `data.node.version` is set on the new node.

- [ ] **Step 4: Run the full frontend type check**

```bash
cd src/frontend && npx tsc --noEmit
```
Expected: PASS.

- [ ] **Step 5: Ask the user to commit (only if code changed)**

If changes were made:

```bash
git add <files>
git commit -m "feat(frontend): persist version on newly-dropped component nodes"
```

---

## Task 11: Pilot — add `version` + `changelog` to one real component

**Files:**
- Modify: the API Request component (pick one under `src/backend/base/langflow/components/` or `src/lfx/src/lfx/components/` that recently changed — recent commits touched `bearer token auth` and `mTLS`)

- [ ] **Step 1: Locate the component**

Find the API Request component source:

```bash
grep -rn "class.*APIRequest" src/backend/base/langflow/components src/lfx/src/lfx/components | head -3
```

- [ ] **Step 2: Add `version` and `changelog`**

Edit the component class. Example (adapt values/wording to match the real recent changes to that component):

```python
from typing import ClassVar

from lfx.custom.custom_component.changelog import ChangelogEntry

class APIRequestComponent(Component):
    display_name = "API Request"
    description = "..."
    version: int = 2
    changelog: ClassVar[list[ChangelogEntry]] = [
        ChangelogEntry(
            version=2,
            changes="- Added Bearer token authentication\n- Added mTLS support\n- Added form-urlencoded body option",
            notes=None,
        ),
        # If prior versions existed with breakage, list them here. If not, this is the only entry.
    ]
```

- [ ] **Step 3: Manually smoke-test**

Open a flow that contains an API Request component saved before this change (so `data.node.version` is missing → reads as 0). Trigger the Update components modal. Confirm:

- The row shows the "Breaking" label if the existing structural check says so (else Standard).
- The expanded panel shows the `v2` section with the authored `Changes` text.
- The version range reads `v0 → v2`.

Then click Update. Reopen the modal. The node should no longer appear in the outdated list.

- [ ] **Step 4: Ask the user to commit**

```bash
git add <the component file>
git commit -m "feat: add changelog to API Request component"
```

---

## Task 12: Claude skill — `langflow-component-authoring`

**Files:**
- Create: `.claude/skills/langflow-component-authoring/SKILL.md`

- [ ] **Step 1: Check current `.claude/skills/` structure and `.gitignore`**

```bash
ls -la .claude/skills/ 2>/dev/null
grep -E "^\.claude" .gitignore 2>/dev/null
```

If `.claude/skills/` is git-ignored, ask the user before writing (the skill needs to be committed to be shared with other contributors). If `.claude/` itself is git-ignored, consider putting the skill under `docs/ai-skills/langflow-component-authoring.md` and adding a project-level pointer.

- [ ] **Step 2: Write the skill file**

Create `.claude/skills/langflow-component-authoring/SKILL.md`:

````markdown
---
name: langflow-component-authoring
description: Use when creating or editing any file under `src/backend/base/langflow/components/**` or `src/lfx/src/lfx/components/**`. Enforces the Component version-bump and changelog-append ritual, and guides selection of the right Langflow input type.
---

# Langflow Component Authoring

Invoke this skill whenever you are creating a new Langflow Component or editing an existing one. It enforces two things:

1. **Version + changelog discipline** — every user-visible change must bump `version` and append a `ChangelogEntry`.
2. **Correct input-type selection** — use the right Langflow input primitive for each input on the component.

## Before you edit

Classify the change you are about to make:

- **User-visible** — affects `inputs`, `outputs`, `input_types`, defaults, or the component's externally-observable behavior.
- **Internal-only** — refactor, log message change, comment, rename of a local variable, tightening a type hint with no behavioral effect.

If internal-only, skip the version/changelog checklist. Otherwise, follow every step below.

## Version + changelog checklist

For every user-visible change:

1. **Bump `version`**: increment by 1. If the class doesn't yet declare a `version`, add `version: int = 1`.
2. **Append a `ChangelogEntry`** to the `changelog` class attribute with the new version.
   - If `changelog` doesn't yet exist, add it: `changelog: ClassVar[list[ChangelogEntry]] = [...]`.
   - **Append only** — never edit or reorder existing entries. Changelog history is immutable.
3. **Fill `changes`** (always required): short markdown describing what changed from the user's perspective. Use bullets for multiple changes.
4. **Decide whether `notes` is needed**. Ask yourself:
   - Does the change rename or remove an output?
   - Does it rename or remove a template field (input)?
   - Does it narrow an input's accepted `input_types`?
   - Does it change a default value a user might be relying on?
   
   If **any** answer is yes → `notes` is required and must explain what the user should do. If all answers are no, `notes=None` is fine.

Example:

```python
from typing import ClassVar
from lfx.custom.custom_component.changelog import ChangelogEntry

class MyComponent(Component):
    display_name = "My Component"
    version: int = 3
    changelog: ClassVar[list[ChangelogEntry]] = [
        ChangelogEntry(version=1, changes="Initial release"),
        ChangelogEntry(
            version=2,
            changes="- Added Bearer token authentication\n- Added mTLS support",
        ),
        ChangelogEntry(
            version=3,
            changes="Renamed `api_key` → `auth_token`.",
            notes="If you used the API key field, re-enter the value under Bearer Token.",
        ),
    ]
```

## Input type picker

When adding or changing an `Input`, pick the most specific primitive. Default reflex: if you find yourself using `StrInput` or `DictInput` for something that has a more specific option, switch.

### Text-like

| Use when...                                                      | Class                                    |
|------------------------------------------------------------------|-------------------------------------------|
| Short free-form text                                             | `StrInput`                                |
| Multi-line free text (system prompt, instructions)               | `MultilineInput`                          |
| May receive a `Message` object from an upstream chat node        | `MessageTextInput`                        |
| Credentials / API keys (stored encrypted, masked in UI)          | `SecretStrInput`                          |
| Multi-line secret (e.g. a PEM certificate)                       | `MultilineSecretInput`                    |
| Prompt template authoring                                        | `PromptInput`                             |
| Code (Python, SQL, etc.)                                         | `CodeInput`                               |
| Free-form user query to search/filter                            | `QueryInput`                              |

### Numeric + boolean

| Use when...                                      | Class           |
|--------------------------------------------------|------------------|
| True/false toggle                                | `BoolInput`     |
| Integer                                          | `IntInput`      |
| Float                                            | `FloatInput`    |
| Bounded numeric with a visible slider            | `SliderInput`   |

### Choices

| Use when...                                                | Class                |
|------------------------------------------------------------|-----------------------|
| Pick one from a fixed list                                 | `DropdownInput`      |
| Pick many from a fixed list                                | `MultiselectInput`   |
| Pick one from a list rendered as tabs (visually distinct)  | `TabInput`           |

### Structured data

| Use when...                                                          | Class                 |
|----------------------------------------------------------------------|------------------------|
| Arbitrary `dict[str, Any]`                                           | `DictInput`            |
| Nested dictionary (multi-level key-value editor)                     | `NestedDictInput`      |
| A Langflow `Data` object (often from an upstream data source)        | `DataInput`            |
| A Langflow `DataFrame`                                               | `DataFrameInput`       |
| A small tabular editor                                               | `TableInput`           |

### Resources + connections

| Use when...                                                            | Class            |
|------------------------------------------------------------------------|-------------------|
| File upload / path                                                     | `FileInput`      |
| Authentication reference to a vault-backed secret                      | `AuthInput`      |
| A typed handle connection (rare — most inputs use a connection via `input_types` instead) | `HandleInput`    |
| Tool list (e.g. for agents)                                            | `ToolsInput`     |
| LLM model picker                                                       | `ModelInput`     |
| MCP server picker                                                      | `McpInput`       |
| URL / link                                                             | `LinkInput`      |
| Chat `Message` object                                                  | `MessageInput`   |

### `input_types` guidance

`input_types` controls which upstream node outputs can connect to an input. Narrowing `input_types` on an existing field is a **breaking change** — it requires a version bump and `notes` copy. Widening it is safe (standard, non-breaking).

### When unsure between two

If you're stuck between two types (e.g. `StrInput` vs. `MessageTextInput`), stop and ask the user which one they want. Do not guess.

## After the edit

Before finishing the task:

- Run the lfx test suite for the touched component area: `uv run --project src/lfx pytest src/lfx/tests/unit/custom -x`.
- Verify the component still loads by starting the langflow dev server (or by running the existing starter-flow validation tests).

## Invariants

- **Do not edit or reorder existing `ChangelogEntry` items.** History is append-only.
- **Do not introduce a version bump without a changelog entry.** The backend warns at startup, but author intent matters more than the warning.
- **Do not decrement `version`.**
- **When Langflow adds a new input type**, add a row to the "Input type picker" tables above as part of that change.
````

- [ ] **Step 3: Ask the user to commit**

```bash
git add .claude/skills/langflow-component-authoring/SKILL.md
git commit -m "docs: add langflow-component-authoring Claude skill"
```

---

## Task 13: End-to-end verification

- [ ] **Step 1: Backend test run**

```bash
uv run --project src/lfx pytest src/lfx/tests/unit/custom src/lfx/tests/unit/template -x
```
Expected: PASS.

- [ ] **Step 2: Frontend test run**

```bash
cd src/frontend && npx vitest run src/CustomNodes/helpers src/modals/updateComponentModal
```
Expected: PASS.

- [ ] **Step 3: Frontend typecheck + build**

```bash
cd src/frontend && npx tsc --noEmit && npm run build
```
Expected: PASS.

- [ ] **Step 4: Manual UI walk-through**

Start the dev server. Exercise each UI path called out in Task 9 Step 5. Confirm:

- Single-component modal with changelog: panel visible.
- Single-component modal without changelog: panel absent, old copy unchanged.
- Multi-component modal: chevrons, expansion, breaking rows auto-open, panel renders markdown.
- Updating a node moves `data.node.version` forward (reopen the modal — the component should no longer be outdated).
- A new component dragged from the sidebar gets `data.node.version` = template's version (no outdated state immediately after drop).

- [ ] **Step 5: Update memory / notes**

No auto-memory change needed (this is a project-scoped feature, not a user preference). If the user has observations they want remembered — e.g., a convention they want enforced — capture them then.

- [ ] **Step 6: Final commit**

No code should change here. If everything passes, summarize results to the user and ask whether to open a PR (per user memory: no PRs to upstream; platform-multi-tenant is the effective main).

---

## Self-review against spec

- [x] **Python data model:** Tasks 1-3 create `ChangelogEntry`, validator, class attrs.
- [x] **Lifecycle & storage:** Task 10 verifies drop + update paths carry `data.node.version`. Existing flows default to `0`.
- [x] **Backend API:** Tasks 4-5 add fields to `FrontendNode` + propagate through both builders.
- [x] **Frontend types + logic:** Tasks 6-7 add `APIClassType` fields, extend `ComponentsToUpdateType`, compute filtered entries in `checkCodeValidity`.
- [x] **UI (multi + single):** Tasks 8-9 build `ChangelogPanel` and wire it into the modal with expand/collapse + breaking auto-open + single-component always-visible.
- [x] **Fallback + edge cases:** Task 8 `showEmptyFallback` prop + Task 9 Step 3 `components[0]?.outdated` guard.
- [x] **Markdown rendering:** Task 8 uses `react-markdown` + `remark-gfm`.
- [x] **Companion skill:** Task 12 creates `.claude/skills/langflow-component-authoring/SKILL.md` with version/changelog checklist + input-type picker.
- [x] **Pilot real component:** Task 11 adds version/changelog to API Request (the recently-changed component).
- [x] **Commits:** each task's commit step prompts the user first (honors the user memory).

No placeholders detected.
