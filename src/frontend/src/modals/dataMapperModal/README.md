# Data Mapper Modal

Visual editor for the `mapping_config` field on `DataMapperComponent` (Langflow `lfx.components.processing.data_mapper`).

## Public API

Import:

```tsx
import { DataMapperModal } from "@/modals/dataMapperModal";
```

Props: see `DataMapperModalProps` in `index.tsx`.

## Extension seam — `suggestionsSlot`

The modal accepts an optional `suggestionsSlot?: React.ReactNode` prop that renders in the modal header above the destination table. In production, the `MappingComponent` input renderer populates this slot with a `<MappingSuggestions>` component that provides LLM-driven auto-mapping via the shipped `DataMapperAutoMap` flow.

See `docs/superpowers/specs/2026-04-21-data-mapper-heavy-auto-mapping-design.md` for the full design.

Callers can still pass a custom `suggestionsSlot` for bespoke integrations — the contract is just a `ReactNode`.

## Pending suggestions

When `pendingSuggestions` is non-empty and `showPendingSuggestions` is true, the destination table renders proposed rows in a blue "pending" state with per-row ✓/✗ handlers (`onAcceptSuggestion(destination)` / `onRejectSuggestion(destination)`). The modal is agnostic about how suggestions are generated — it only renders what it's given.

## Shape of persisted value

The modal reads and writes the `mapping_config` field as a JSON-stringified `MapperConfig`. The Pydantic schema lives at `src/lfx/src/lfx/components/processing/_data_mapper/config_schema.py`; TS types mirror it at `types.ts`.

## Validation

On save, the modal POSTs the config to `/api/v1/validate/validate-mapping-config`. Non-empty errors keep the modal open with inline row decoration + a banner.
