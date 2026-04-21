# Data Mapper Modal

Visual editor for the `mapping_config` field on `DataMapperComponent` (Langflow `lfx.components.processing.data_mapper`).

## Public API

Import:

```tsx
import { DataMapperModal } from "@/modals/dataMapperModal";
```

Props: see `DataMapperModalProps` in `index.tsx`.

## Extension seam — `suggestionsSlot`

The modal accepts an optional `suggestionsSlot?: React.ReactNode` prop. When provided, it renders in the modal header above the destination table.

Phase 1c (auto-mapping via the component assistant) injects a suggestions component through this seam. Expected contract:

```tsx
<DataMapperModal
  {...baseProps}
  suggestionsSlot={
    <MappingSuggestions
      currentConfig={parsedConfig}
      onApply={(proposed) => { /* Phase 1c caller writes to config */ }}
    />
  }
/>
```

The slot component is responsible for:

- Inspecting the current `MapperConfig` (via props from the caller, not from the modal itself).
- Proposing a new `MapperConfig` (or diff) via `onApply`.
- Its own UX for presenting suggestions (dialog, inline chips, etc.).

The modal stays agnostic of how suggestions are generated — it just renders the slot and waits for `onApply` calls. In Phase 1b, no caller provides the slot and it renders nothing.

## Shape of persisted value

The modal reads and writes the `mapping_config` field as a JSON-stringified `MapperConfig`. The Pydantic schema lives at `src/lfx/src/lfx/components/processing/_data_mapper/config_schema.py`; TS types mirror it at `types.ts`.

## Validation

On save, the modal POSTs the config to `/api/v1/validate/validate-mapping-config`. Non-empty errors keep the modal open with inline row decoration + a banner.
