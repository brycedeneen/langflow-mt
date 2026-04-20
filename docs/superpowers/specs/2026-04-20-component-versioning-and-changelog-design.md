# Component Versioning and Changelog

**Date:** 2026-04-20
**Status:** Design approved, ready for implementation plan
**Owner:** bryced

## Summary

Today, when the Update components modal appears, users see a list of outdated components labeled "Breaking" or "Standard" — but nothing about *what* changed or *what they may need to do*. This design adds:

1. An opt-in **author-supplied changelog** on each component class — keyed by an explicit integer `version`.
2. Modal UI that renders the stacked changelog entries spanning the user's version → latest, with `changes` and `notes` sections written in markdown.
3. A companion Claude authoring skill (`langflow-component-authoring`) that enforces the version-bump and changelog-append ritual whenever a component is edited.

There are no existing production migrations to worry about: any flow without a stored version reads as `v0`, so everything is backward-compatible without a data migration.

## Goals

- Surface *why* an update is offered, not just *that* one exists.
- Surface *action-required* guidance when a breaking change needs user intervention.
- Keep the change additive: components that don't opt in behave exactly as today.
- Make the authoring ritual hard to skip by baking it into the Claude workflow.

## Non-goals

- No CI-side lint for missing changelog entries (natural follow-up; out of scope).
- No auto-generated structural diff ("Added input X") — all copy is author-written.
- No change to the existing structural breaking-change detection; the `Breaking` / `Standard` label remains authoritative and independent of the changelog.
- No per-version cherry-picking. Updating a component is atomic: user goes from their version to the latest, applying every entry in between together.
- No version bumps for internal-only edits (refactors, comments, logging).

## Data model — Python

Two new optional class attributes on `Component` subclasses.

```python
from langflow.custom.custom_component.component import Component, ChangelogEntry
from typing import ClassVar

class APIRequestComponent(Component):
    version: int = 3

    changelog: ClassVar[list[ChangelogEntry]] = [
        ChangelogEntry(
            version=3,
            changes="Renamed `api_key` → `auth_token`.",
            notes="If you used the API key field, re-enter the value under Bearer Token.",
        ),
        ChangelogEntry(
            version=2,
            changes="- Added Bearer token auth option\n- Added mTLS support",
            notes=None,
        ),
    ]
```

### `ChangelogEntry`

A pydantic model defined alongside `Component` (consistent with the rest of the Langflow backend):

```python
class ChangelogEntry(BaseModel):
    version: int
    changes: str                 # required, markdown
    notes: str | None = None     # optional, markdown
```

### Defaults

- `version` missing → `0`.
- `changelog` missing → `[]`.

### Validation (startup-time, non-fatal warnings)

The component registry warns but does not refuse to load when:

- `max(entry.version for entry in changelog) > cls.version`
- Two entries share a `version`.
- An entry has `version <= 0`.

These are author mistakes, surfaced in logs. They do not break the component.

## Lifecycle & storage

### Node JSON

A new `version: int` field on `data.node` (alongside `outputs`, `template`, `edited`, etc.).

- Defaults to `0` when missing (all existing flows read as v0 — no data migration).
- Written on every save.

### When `data.node.version` is set

| Event                         | Value written                      |
|-------------------------------|------------------------------------|
| Sidebar drop (new node)       | `cls.version ?? 0`                 |
| Component update action       | `cls.version ?? 0`                 |
| Existing flow loaded pre-feat | (no field, reads as `0`)           |

### Which entries the modal renders, per component

```
userVersion   = data.node.version ?? 0
latestVersion = templates[data.type].version ?? 0

entries = changelog
  .filter(e => e.version > userVersion && e.version <= latestVersion)
  .sort(by version desc)          // newest first
```

## Backend API

Additive changes only. No endpoints are renamed, removed, or repurposed.

### Component schema (emitted by the component registry / custom-component endpoints)

Every component response gains:

```jsonc
{
  "...existing fields...": "",
  "version": 3,
  "changelog": [
    {"version": 3, "changes": "…", "notes": "…"},
    {"version": 2, "changes": "…", "notes": null}
  ]
}
```

Populated from the class attributes; defaults `version: 0` / `changelog: []` when unset.

### Node payload (flow JSON)

`data.node.version: int` is added. Serialized on save; tolerated as absent on load.

### Endpoints touched

- `GET /api/v1/all` — component schema now includes `version` / `changelog`.
- `POST` validate/update custom-component endpoints — same schema addition on their response.
- Flow save/load endpoints — no code change required; node shape is additive.

### Tests (backend)

- `ChangelogEntry` model roundtrip.
- Component schema serialization includes `version` / `changelog` when set, defaults when unset.
- Registry warnings fire for malformed changelog setups.

## Frontend

### Types

At `src/frontend/src/types/zustand/flow/index.ts`, extend `ComponentsToUpdateType`:

```ts
export type ChangelogEntry = {
  version: number;
  changes: string;
  notes: string | null;
};

export type ComponentsToUpdateType = {
  id: string;
  icon?: string;
  display_name: string;
  outdated: boolean;
  breakingChange: boolean;
  userEdited: boolean;
  // new:
  userVersion: number;
  latestVersion: number;
  changelogEntries: ChangelogEntry[];   // already filtered + sorted desc
};
```

A matching `ChangelogEntry` type is added to the component template types so `templates[data.type].version` and `templates[data.type].changelog` are typed.

### Logic

`checkCodeValidity` at `src/frontend/src/CustomNodes/helpers/check-code-validity.ts` computes `userVersion`, `latestVersion`, and `changelogEntries` alongside the existing `outdated` / `breakingChange` outputs. Filtering and sorting happen here — the modal stays presentational.

`flowStore.updateComponentsToUpdate` at `src/frontend/src/stores/flowStore.ts` passes the new fields through unchanged.

### UI — Update components modal

File: `src/frontend/src/modals/updateComponentModal/index.tsx`.

#### Multi-component view

- Adds a new leading chevron column (`▸` / `▾`) for expand/collapse on each row.
- Breaking rows start **expanded**. Standard rows start **collapsed**. Users can toggle any row.
- The expanded region is a single cohesive "What's changed" panel (not a list of selectable items):
  - Panel header: the label "What's changed" + a right-aligned `v{user} → v{latest}` range indicator.
  - Stacked per-version sections inside the panel, newest first, divided by a soft dashed rule. Each section has a small uppercase `v3` / `v2` label, then a **Changes** block, then a **Notes** block (omitted if null).
  - Styling: subtle background (`bg-muted` or equivalent), left accent border in `--accent-amber-foreground` for breaking rows, plain border for standard rows.
- Per-component row checkbox stays — users can still skip a whole component this round. Per-version cherry-picking is not supported.

#### Single-component view

- Same "What's changed" panel, always visible below the existing descriptive paragraphs.
- If no changelog entries apply → panel hidden entirely (the existing modal copy is enough).

#### Markdown rendering

`changes` and `notes` render through the existing markdown renderer used elsewhere in Langflow. Supports bullets, inline code, bold, italics, and links. No images, no raw HTML.

#### Fallback states

| Condition                                               | Rendered                                                                                     |
|---------------------------------------------------------|-----------------------------------------------------------------------------------------------|
| Outdated + no changelog entries apply (multi-component) | Row still shows; expanded panel reads: "No changelog entries available. This update may still change behavior." |
| Outdated + no changelog entries apply (single)          | "What's changed" panel omitted entirely.                                                     |

### Tests (frontend)

- `checkCodeValidity` returns correct `userVersion` / `latestVersion` / filtered entries across: no-version-on-node, no-version-on-class, normal bump, multi-version stack, degenerate cases (user > latest).
- Modal renders expanded panel for breaking rows by default, collapsed for standard, toggleable.
- Markdown in `changes` / `notes` renders safely (no raw HTML).
- Fallback message shows when outdated with empty `changelogEntries`.

## Companion skill — `langflow-component-authoring`

Location: `.claude/skills/langflow-component-authoring/SKILL.md` (checked into the repo so every contributor and every Claude session inherits it).

### Activation

Triggers when Claude is editing or creating a file under:

- `src/backend/base/langflow/components/**`
- `src/lfx/src/lfx/components/**`

…and the file defines a subclass of `Component`.

### Enforcement checklist

The skill walks the author (or Claude) through these in order:

1. **Classify the change.** User-visible (template, outputs, input_types, behavior) or internal-only (refactor, comment, logging)? If internal-only → skip the rest.
2. **Bump `version`.** Require `version` on the class to be incremented by 1. If the class has no `version` yet, introduce it starting at `1`.
3. **Append a changelog entry.** Add a new `ChangelogEntry(version=<new>, changes=..., notes=...)` to the `changelog` list. Must be appended, never inserted or edited in place.
4. **Fill `changes`.** Always required. Short markdown describing what changed from the user's perspective (not internals).
5. **Fill `notes` when structurally breaking.** The skill prompts the author to consider whether the diff renames/removes an output, renames/removes a template key, or narrows `input_types` — if so, `notes` is required and must explain what the user should do to adapt. (The skill doesn't automatically diff the code; it asks the author to answer yes/no.)
6. **Preserve history.** Refuse to edit existing entries or reorder the list. Changelog is append-only.

### Input-type guidance

Separately from the changelog flow, the skill carries a table of Langflow's input/output primitives so it picks the right one when an author adds or modifies an input. The table lives inside the skill file (not discovered at runtime) so the skill is self-contained. At minimum it covers:

- **Text-ish:** `StrInput`, `MessageTextInput`, `MultilineInput`, `SecretStrInput`, `PromptInput`
- **Booleans & numbers:** `BoolInput`, `IntInput`, `FloatInput`, `SliderInput`
- **Choices:** `DropdownInput`, `MultiselectInput`
- **Structured:** `DictInput`, `DataInput`, `DataFrameInput`, `NestedDictInput`, `TableInput`
- **Files:** `FileInput`
- **Outputs:** `Output` with the common `types` values (`Message`, `Data`, `DataFrame`, etc.)

For each entry the skill records: when to use it, common pitfalls (e.g. `SecretStrInput` for credentials, `MessageTextInput` vs. `StrInput` when the value may come from another node's `Message`, `input_types` containment rules when allowing connections from specific upstream types), and the minimal constructor shape.

The skill then uses this table proactively: when the author is writing or editing `build_config()` / `inputs = [...]`, it recommends the right input class rather than letting the author default to whatever looks closest. If the skill is unsure between two options, it asks one clarifying question instead of guessing.

When Langflow adds new input types, they must be added to the skill's table as part of that change (enforced by a short note at the top of the skill file).

### What the skill does not do

- No runtime enforcement. Claude-time guard only.
- No CI lint (follow-up project).
- No auto-generated copy from the structural diff — the author describes intent; the skill makes sure intent is captured.

## Out of scope / follow-ups

- CI lint that refuses to merge a component change without a matching version bump + changelog entry.
- Auto-suggesting `changes` copy from the structural diff (added input, removed output, etc.).
- Rendering changelog from outside the Update modal (e.g., a "What's new" hover on the node, a per-component history page).
- Semver-style version format (we chose integer for simplicity; revisit if severity signaling matters later).

## Success criteria

- An author editing any component under `components/**` is prompted by the skill to bump `version` and append a `ChangelogEntry`.
- The Update components modal renders the "What's changed" panel for opted-in components, stacked correctly across the user-latest version span.
- Components that haven't opted in behave exactly as today — no regressions in the modal, no schema changes users can observe.
- Existing flows loaded pre-feature update without touching node data beyond what the user explicitly updates.
