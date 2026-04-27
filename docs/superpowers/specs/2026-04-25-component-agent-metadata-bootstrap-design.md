# Component Agent Metadata Bootstrap — Design

**Date:** 2026-04-25
**Status:** Design draft, pending review
**Author:** bryced (with assist)

## Summary

Generate starting `agent_summary` and `agent_usage_notes` content for every assist-enabled, non-legacy component in the Langflow catalog, persist it in source control as YAML, and seed it into the existing `component_metadata` DB table at startup. Admin edits via `/api/v1/admin/component_metadata` are protected via the existing `updated_by` "ownership" convention — once an admin edits a row, re-seeds skip it.

The pipes the assistant uses to read this metadata (`fetch_component_summaries`, `fetch_component_usage_notes`) already exist and are wired into the catalog tools. What's missing is content — this design fills that gap.

## Why

`agent_summary` and `agent_usage_notes` are surfaced to the assistant's tool-calling loop:

- `search_components` returns `agent_summary` per result — the assistant sees it during the **picking** moment, when choosing one component out of many candidates.
- `get_component_schema(component_name)` returns `agent_usage_notes` — the assistant reads it during the **configuring** moment, when it has chosen a component and is collecting input values from the user.

Today both fields are `NULL` for every component. The assistant falls back to the bare component description, which is too thin for picking among similar components and gives no per-input guidance for configuration. The existing `assist_guide` field (string class-attribute, YAML bundle) overlaps with `agent_usage_notes` but lives outside the DB and has no admin-editable surface.

This work bootstraps content for both fields and lays the path for `assist_guide` to be retired in a later cleanup once `component_metadata` covers everything.

## Decisions

The decisions taken during brainstorming, with the rejected options noted:

1. **Storage form: hybrid YAML-in-source + DB seeder.** Generated drafts live in per-category YAML files under source control (reviewable in PRs); a startup seeder upserts them into `component_metadata` only when no row exists for that component yet. Rejected: pure-DB seeding (no PR review surface), pure-YAML lookup (admin edits would need a different write path).
2. **Scope: assist-enabled AND non-legacy components.** Skip components opted out via `assist_enabled: ClassVar[bool] = False` and skip components flagged `legacy = True`. Rejected: all components (wastes tokens on rarely-used legacy code), single-category lists (can be added later via `--category` flag).
3. **Relationship to `assist_guide`: supersede via fallback chain.** `guide_registry.resolve()` reads from the DB first, then falls back to the existing class-attribute / YAML / None chain. No big-bang migration. Rejected: coexist forever (drift), full migration in one PR (blast radius).
4. **`agent_usage_notes` shape: markdown with fixed headings.** Sections: `## What it does`, `## Inputs to ask about`, `## Outputs`, `## Notes`. Empty sections render `_None._`. Rejected: free prose (less predictable for the assistant), structured JSON (admin edit UI is plain-text).
5. **`agent_summary` shape: 1–3 sentences, 30–120 words.** Sentence 1: what it does. Sentence 2 (optional): when it's a good fit. Sentence 3 (optional, only when a peer truly overlaps): the tradeoff (`Prefer over <peer> when …`). Rejected: single sentence (loses the "when to pick" signal), full paragraph (bloats search results).
6. **Generation: LLM-driven, mirroring the existing `assist_guide` generator.** New script `scripts/generate_component_agent_metadata.py` using Claude Sonnet 4.6, two calls per component (one for summary, one for usage notes), concurrent, with `--dry-run`, `--overwrite`, `--category`, `--concurrency`, `--fail-fast` flags and a markdown review report. Rejected: extending the existing generator (mixes concerns), no auto-seeder (forces every consumer to know the YAML fallback).

## Architecture

```
┌──────────────────────────────────────┐
│  scripts/generate_component_         │      reuses
│  agent_metadata.py                   │ ─────► scripts/_assist_guide_gen/
│  (offline, run-on-demand)            │        {extract,walker}.py
└──────────────┬───────────────────────┘
               │ writes YAML bundle
               ▼
┌──────────────────────────────────────┐      committed in PR
│  src/backend/base/langflow/services/ │ ◄──── reviewed by humans
│  component_assist/agent_metadata/    │
│  ├── adp.yaml                        │
│  ├── models.yaml                     │
│  ├── processing.yaml                 │
│  └── …                               │
└──────────────┬───────────────────────┘
               │ read at startup
               ▼
┌──────────────────────────────────────┐
│  create_or_update_component_         │      called from
│  agent_metadata (in setup.py)        │ ◄──── main.py lifespan
│  (3-state upsert by `updated_by`)    │        (sibling of
└──────────────┬───────────────────────┘         create_or_update_template_metadata)
               │ upsert
┌──────────────────────────────────────┐
│  component_metadata table            │ ◄──── /api/v1/admin/component_metadata
│  (agent_summary, agent_usage_notes)  │       (admin edits — always win)
└──────────────┬───────────────────────┘
               │ read by
               ▼
┌──────────────────────────────────────┐
│  fetch_component_summaries           │ ◄──── search_components
│  fetch_component_usage_notes         │ ◄──── get_component_schema
│  guide_registry.resolve (async)      │ ◄──── /api/v1/component_assist
│  (DB → assist_guide → YAML → None)   │       (only call site)
└──────────────────────────────────────┘
```

## File / module layout

### New files

- `scripts/generate_component_agent_metadata.py` — entry point. Argparse with `--dry-run`, `--overwrite`, `--category`, `--concurrency` (default 5), `--fail-fast`. ThreadPoolExecutor, mirrors `scripts/generate_component_assist_guides.py` structure.
- `scripts/_agent_metadata_gen/__init__.py`
- `scripts/_agent_metadata_gen/synthesize.py` — prompt construction, two LLM calls per component (summary + usage notes), fallback when LLM returns empty.
- `scripts/_agent_metadata_gen/peers.py` — builds the per-category sibling list (display name + 1-line description) used in the summary prompt. Includes opted-out, excludes legacy, excludes the component being generated.
- `scripts/_agent_metadata_gen/emit.py` — writes per-category YAML files. Entries sorted by `component_name` for stable diffs.
- `src/backend/base/langflow/services/component_assist/agent_metadata/` — output directory. Empty initially; populated by the generator.
- (no separate seeder module) — the seeder is added as `create_or_update_component_agent_metadata` in `src/backend/base/langflow/initial_setup/setup.py`, alongside the existing `create_or_update_template_metadata` (~line 1016).
- `docs/component-agent-metadata-generation-report.md` — review report (per-component status + completeness, written by the generator).

### Reused

- `scripts/_assist_guide_gen/walker.py` — `iter_all`, `FileCandidate`. Reused as-is.
- `src/backend/base/langflow/services/database/models/component_metadata/model.py` — no schema changes.
- `src/backend/base/langflow/services/assistant/tools/metadata_lookup.py` — already reads from `component_metadata`; nothing to change.
- `src/backend/base/langflow/services/assistant/tools/catalog.py` — already merges `agent_summary` / `agent_usage_notes` into catalog responses.

### Reused with a small backwards-compatible extension

- `scripts/_assist_guide_gen/extract.py` — `InputMetadata` gains three optional fields: `field_type: str | None` (the Input class name, e.g., `"SecretStrInput"`, `"TableInput"`), `required: bool` (default `False`), `advanced: bool` (default `False`). `extract_metadata` populates them from `getattr(raw, "field_type", None)` / `getattr(raw, "required", False)` / `getattr(raw, "advanced", False)`. Old callers (the existing `assist_guide` synthesizer) keep working — they only read `name` and `info`. The new synthesizer uses the extended fields to decide which inputs are LLM-relevant.

### Modified

- `src/backend/base/langflow/services/component_assist/guide_registry.py` — `resolve()` becomes async; gains a DB-first lookup step before the existing class-attribute / YAML chain. Existing `is_assist_enabled` and `reset_cache` unchanged.
- `src/backend/base/langflow/api/v1/component_assist.py:157` — the only production call site. Updated to `await resolve_guide(...)`. (Confirmed via `grep`: no other call sites exist in `src/`.)
- `src/backend/base/langflow/initial_setup/setup.py` — adds `create_or_update_component_agent_metadata` next to the existing `create_or_update_template_metadata` (~line 1108).
- `src/backend/base/langflow/main.py` — adds an `await create_or_update_component_agent_metadata()` call in the lifespan, right after the existing `create_or_update_template_metadata()` invocation (~line 206), wrapped in the same try/except shape.

## Generation pipeline

For each `FileCandidate` returned by `iter_all(COMPONENT_ROOTS)`:

1. Import the module, find Component subclasses defined in it.
2. For each class, in this order, decide whether to skip:
   - `is_assist_enabled(cls) is False` → status `skipped-opted-out`. **Class is still added to the per-category peer index** (still picker-eligible).
   - `getattr(cls, "legacy", False) is True` → status `skipped-legacy`. **Excluded from peer index.**
   - Component name already in YAML bundle and `--overwrite` not passed → status `skipped-existing`.
3. Otherwise, extract metadata (`extract_metadata(cls)`) and queue for generation.

Once all classes are scanned, build a `peers_by_category: dict[str, list[PeerEntry]]` map. **The peer index includes every non-legacy class in the category — regardless of generation outcome.** That means `skipped-opted-out` (e.g., DataMapper), `skipped-existing` (already in the bundle), and queued-for-generation classes all participate as peers in *other* components' summary prompts. Only `legacy = True` classes are excluded from peers. For each queued class, the prompt is built with its category's peer list with self filtered out.

For each queued class, two LLM calls — concurrent at the file-candidate level via the existing ThreadPoolExecutor (one future per FileCandidate; each future runs its classes sequentially, mirroring `_process_one` in `generate_component_assist_guides.py`):
- **Summary call** — prompt below, target 30–120 words.
- **Usage notes call** — prompt below, target 120–300 words.

Empty LLM response triggers the metadata-only fallback **per call independently** — a component can have a generated summary and a fallback usage-notes (or vice versa).

Write per-category YAML files. Each file is a list of `{component_name, agent_summary, agent_usage_notes}` entries, sorted by `component_name`. Append a row per component to the markdown review report. The report row carries two status columns (`summary_status` and `usage_status`), each one of `generated | fallback-used | errored`, plus a top-level `outcome` of `skipped-opted-out | skipped-legacy | skipped-existing | processed`.

### Hand-authored peer hints

A small dict in `scripts/_agent_metadata_gen/peers.py` carries entries for components that are explicitly worth referencing as alternatives but have no LLM-generated row of their own (currently: DataMapper). These are merged into peer-context blocks for siblings. Entries:

```python
HAND_AUTHORED_PEERS: dict[str, PeerEntry] = {
    "DataMapper": PeerEntry(
        component_name="DataMapper",
        category="processing",
        display_name="Data Mapper",
        description=(
            "Hyper-precise field-to-field mapping with an explicit schema and transforms. "
            "Very low cost per run; requires technical expertise to author the mapping. "
            "Has its own dedicated configuration agent."
        ),
    ),
}
```

This is the canonical "competing components" example. Future hand-authored peers can be added the same way.

## Prompts

### `agent_summary` prompt

```
Write a 1–3 sentence summary of this component for an AI assistant
choosing it from a list of candidates.

Sentence 1 (required): what the component does. Be concrete — name the
thing it produces, transforms, or connects to.

Sentence 2 (optional): when this is a good fit, or what it pairs with.

Sentence 3 (optional, ONLY when one or more peers below genuinely
overlaps): the tradeoff. Format: "Prefer over <peer display name> when
…". Use this only when you can articulate a clear, one-line "use this
when … / use the peer when …" distinction. If no peer materially
overlaps, omit sentence 3 — do not write filler.

Rules:
- Second person ("you help the user…").
- Don't repeat the display name verbatim.
- Don't invent capabilities not in the metadata.
- No marketing language. No markdown.
- 30–120 words. Return only the summary text.

Component metadata:
- Class: {class_name}
- Display name: {display_name}
- Description: {description}
- Documentation URL: {documentation}
- Class docstring: {docstring}
- Inputs ({input_count}):
{inputs}
- Outputs: {outputs}

Other components in the same category (peers):
{peers}
```

The `{peers}` block lists each peer as `- <component_name> — <display_name> — <description>` (1 line each). Empty when no peers exist.

### `agent_usage_notes` prompt

```
Write configuration notes for an AI assistant configuring this
component. Use this exact markdown structure — emit each heading even
if a section is empty (write `_None._` in that case):

## What it does
One short paragraph (1–3 sentences).

## Inputs to ask about
- **<input_name>** — what to ask the user, plus a suggested default if
  one is obvious from the metadata.
- (one bullet per non-trivial input — skip inputs marked
  advanced=True unless they are commonly required; skip inputs that
  are secret-typed, since the assistant uses a separate
  variable-creation flow for those)

## Outputs
- **<output_name>** — what it produces and what it commonly feeds
  into.

## Notes
- Gotchas, constraints, or pairings worth flagging. Use `_None._` if
  nothing notable.

Rules:
- Second person ("ask the user…").
- Don't invent capabilities not in the metadata.
- One line per bullet — keep it scannable.
- 120–300 words.
- Return only the markdown body. No preamble, no fencing.

Component metadata:
- Class: {class_name}
- Display name: {display_name}
- Description: {description}
- Documentation URL: {documentation}
- Class docstring: {docstring}
- Inputs ({input_count}):
{inputs}
- Outputs: {outputs}
```

The `{inputs}` block is one line per input as `- <name> [type, required, advanced]: <info>` so the LLM can decide which to skip and how to phrase the ask.

### Fallback content

When the LLM returns an empty string for a call, synthesize a minimal stub:

- **Summary fallback:** `"You help users with {display_name}. {description}"` truncated to 120 words.
- **Usage notes fallback:** the four headings populated as: `What it does` = `description`; `Inputs to ask about` = one bullet per required input (`- **{name}** — ask the user for {info}.`); `Outputs` = one bullet per output name; `Notes` = `_None._`.

These stubs are clearly marked `fallback-used` in the review report so they can be hand-rewritten.

## YAML bundle shape

One file per category, named `<category>.yaml`. Top-level is a list:

```yaml
- component_name: StructuredOutput
  agent_summary: |
    You help users coerce upstream Data or Message into a structured
    schema using natural-language instructions to an LLM. Pick this
    when the user can describe the target shape in plain English and
    cost-per-run is not a binding constraint. Prefer over Data Mapper
    when the user lacks the technical context to author an explicit
    mapping or when run volume is low enough that LLM cost is
    acceptable.
  agent_usage_notes: |
    ## What it does
    Runs an LLM call that extracts a structured object from upstream
    text or Data, returning a typed Data output that downstream
    components can read field-by-field.

    ## Inputs to ask about
    - **schema** — ask the user which fields they want to extract and
      whether each should be required.
    - **prompt** — ask for plain-English instructions describing what
      to extract.

    ## Outputs
    - **structured_data** — produces a Data object containing the
      extracted fields; commonly feeds into downstream Agents,
      database writes, or templated messages.

    ## Notes
    - Cost scales with the number of LLM calls; for very high run
      volume consider Data Mapper instead.

- component_name: …
```

YAML uses `|` (literal block scalars) for both fields so multiline content stays human-readable in diffs and admin UI.

## Resolver fallback chain

`guide_registry.resolve(component_cls)` becomes async. New order:

1. **DB lookup** — `fetch_component_usage_notes(component_cls.__name__)`. If non-null and non-empty, return it.
2. **Class attribute** — `getattr(component_cls, "assist_guide", None)`. If non-empty string, return it. *(Existing path.)*
3. **YAML bundle** — the existing `services/component_assist/guides/` lookup keyed by class name. *(Existing path.)*
4. `None`.

Step 2 and 3 are unchanged; step 1 is the only addition. The per-process YAML cache stays. No DB-level cache is added; if profiling shows the lookup is hot we can add an LRU later.

The async signature change touches a single production call site (`api/v1/component_assist.py:157`, already an async handler). Test call sites in `test_guide_registry.py` get updated to `await` and `pytest.mark.asyncio`. A sync `resolve_sync` wrapper that opens its own session would be tempting but locks us into a worse pattern.

## Seeder behavior

`create_or_update_component_agent_metadata` lives in `setup.py` next to the existing `create_or_update_template_metadata` and is called from `main.py` in the lifespan, immediately after the template-metadata seeder. The seeder uses the **same three-state upsert policy** the template seeder already established:

1. Glob `services/component_assist/agent_metadata/*.yaml` and merge into `entries: list[Entry]`. Each entry is `{component_name, agent_summary, agent_usage_notes}`.
2. For each entry, in a single `session_scope()`:
   - `SELECT … WHERE component_name = ?`.
   - **No existing row** → INSERT with `updated_by = None`, `updated_at = now()`.
   - **Existing row, `updated_by IS NULL`** → UPDATE `agent_summary` / `agent_usage_notes` from YAML (re-seed). This is what makes regenerating the YAML actually push fresh content to admin-untouched rows on the next boot.
   - **Existing row, `updated_by IS NOT NULL`** → SKIP (admin took ownership via the admin endpoint, which sets `updated_by` to the admin's user UUID).
3. On INSERT, swallow `IntegrityError` from a concurrent worker that won the race (the `component_name` unique constraint catches duplicates) and log at debug level.
4. Log a single summary line: `"Component agent metadata seed: inserted N, re-seeded M, skipped K (admin-owned)"`.

`updated_by = None` is the existing convention for system-seeded rows. `template_metadata`'s alembic migration already made `updated_by` nullable, and `component_metadata` follows the same `AgentMetadataMixin`.

The three-state policy is what makes the YAML the source of truth for *content* while admin edits remain authoritative once made — exactly what we want for a generator-driven workflow. No `--force` flag, no file lock; concurrency is handled by the unique-constraint guard. To "release" admin ownership and pick up regenerated YAML again, the admin endpoint can clear the row (or a future tool can null `updated_by`); both are out of scope here.

## Testing

### Generator unit tests — `tests/unit/agent_metadata_gen/`

- `test_synthesize.py`
  - Both prompts include class name, inputs (with name + info), and outputs.
  - Summary prompt's `{peers}` block contains every non-legacy peer in the same category and excludes the component itself.
  - Hand-authored peer entries (e.g., DataMapper) appear in the peer block when they share a category.
  - LLM stub returning `""` triggers the metadata-only fallback for both fields.
  - LLM stub returning malformed-but-nonempty markdown is preserved as-is (no post-validation; admins can edit later).
- `test_emit.py`
  - Bundle file is grouped by category.
  - Entries sorted by `component_name` for stable diffs.
  - `--overwrite` replaces existing entries with matching `component_name`; default skips them.
- `test_filters.py`
  - `assist_enabled = False` → `skipped-opted-out`, no LLM call.
  - `legacy = True` → `skipped-legacy`, no LLM call.
  - Opted-out components still appear in *other* components' peer-context block (the DataMapper case).
  - Legacy components are excluded from peers.

### Seeder tests — `src/backend/tests/unit/initial_setup/test_component_agent_metadata_seeding.py`

- Empty DB + non-empty YAML → all entries inserted with `updated_by = None`.
- Pre-existing row with `updated_by IS NULL` → updated from YAML on re-seed (re-seed-when-untouched).
- Pre-existing row with `updated_by` set → seeder leaves it untouched (admin-edit preservation).
- Malformed YAML file is logged and skipped; sibling YAML files in the directory still seed successfully.
- Concurrent seeder simulates IntegrityError on insert → swallowed; row count remains correct.

### Resolver tests — extends `src/backend/tests/unit/services/component_assist/test_guide_registry.py`

- DB row present → returned, class-attr/YAML not consulted.
- DB row absent, class-attr present → class-attr returned.
- DB row absent, YAML entry present → YAML returned.
- All absent → `None`.
- DB row present but `agent_usage_notes IS NULL` → falls through to next step.

### End-to-end smoke

- Boot the app with a fixture YAML containing one component; assert `fetch_component_summaries(["FixtureComponent"])` returns the seeded summary.
- Hit `/api/v1/component_assist` for the fixture component; assert the system prompt includes the seeded `agent_usage_notes`.

### Explicit non-tests

- LLM output quality (we don't pin model prose; the review report covers spot-checking).
- Migrations (no schema change).
- Frontend (no UI surface; admin metadata editor already exists).

## Risks to verify before coding

These need to be confirmed in task 1 of the implementation plan:

1. **`guide_registry.resolve()` async conversion is contained.** Audit all call sites (`grep guide_registry.resolve`) to confirm they are all already in async contexts. If any sync caller exists, plan a sync wrapper instead.
2. **`metadata_lookup.fetch_component_usage_notes` is safe to call from inside the resolver.** It opens a session via `session_scope()`. Confirm the call sites of `resolve()` are not already inside an open session that would conflict.
3. **`legacy` class attribute is reliably present on legacy components.** Spot-check 5–10 components in `src/lfx/src/lfx/components/legacy/` (if such a directory exists) or wherever the `legacy: ClassVar[bool] = True` flag is set today.
4. **Seeder lifespan position.** The reference is `create_or_update_template_metadata` in `setup.py` (~line 1016) called from `main.py:206`. Add the new seeder immediately after it in both files, mirroring the try/except shape.
5. **YAML bundle directory naming doesn't collide.** `agent_metadata/` is a sibling of the existing `guides/` directory under `component_assist/`. Confirm no test fixture or import path uses that name.

## Out of scope (followups)

- Removing the `assist_guide` class-attribute and `guides/` YAML bundle — done in a later cleanup PR once `component_metadata` covers everything.
- Admin UI for component metadata that knows about the `## Inputs to ask about` markdown structure (richer editor). The plain-text editor is sufficient for now.
- A `--force` flag on the seeder to bulk-overwrite admin edits.
- Per-input structured fields (schema-shaped `inputs: [...]` instead of markdown bullets). Considered and rejected for this round; markdown is the lowest-friction shape that the existing admin UI already supports.
- Telemetry on which `agent_summary` entries actually drive picks. Useful but a separate observability project.
