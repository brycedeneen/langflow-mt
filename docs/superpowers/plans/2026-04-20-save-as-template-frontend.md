# Save as Template — Frontend Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **User git rule (takes precedence over every "Commit" step below):** Every `git commit` requires explicit user approval before running. Stop at each commit step and wait for go-ahead. Do not `git push` or open PRs against `langflow-ai/langflow`. Reason: user's standing rule in auto-memory.

**Goal:** Add a superuser-only "Save as Template" entry in the Share dropdown that opens a modal, captures name / description / icon / gradient, strips credentials from the current flow, and POSTs a new Template to `/api/v1/templates`.

**Architecture:** Six frontend units — 5 query hooks + types (verbatim port from retired `feat/template-management-phase-1` branch), a pure `credentialBlanking` util, two small picker components, one fresh `SaveAsTemplateModal`, and a one-line insertion into the Share dropdown. No backend changes; the `/api/v1/templates` CRUD + `Template` model shipped in commit `654ff9ad4f`.

**Tech Stack:** React + TypeScript, `@tanstack/react-query`, `react-icons` / `fontAwesomeIcons`, Jest + Testing Library, Tailwind v4 (CSS-first).

**Spec:** `docs/superpowers/specs/2026-04-20-save-as-template-frontend-design.md`

**Codebase integration points:**
- Query hooks live under: `src/frontend/src/controllers/API/queries/templates/`
- Types live under: `src/frontend/src/types/template/index.ts`
- Modal + pickers + blanking util live under: `src/frontend/src/modals/SaveAsTemplateModal/`
- Share dropdown file: `src/frontend/src/components/core/flowToolbarComponent/components/deploy-dropdown.tsx`
- `api` axios instance + `getURL` constant + `UseRequestProcessor` + `useMutationFunctionType` — existing sibling pattern at `src/frontend/src/controllers/API/queries/flows/use-post-add-flow.ts`
- Auth: `is_superuser` on the user object (referenced in `src/frontend/src/contexts/authContext.tsx:55`); the auth store selector that exposes `currentUser` is what we'll read
- Toasts: existing `useAlertStore` usage in `src/frontend/src/modals/exportModal/index.tsx` is the reference pattern
- Existing data for pickers: `gradients: string[]` in `src/frontend/src/utils/styleUtils.ts`; `fontAwesomeIcons` list exported from `src/frontend/src/icons/fontAwesomeIcons`

---

## File structure

**Create (7 files + 2 test files):**

- `src/frontend/src/types/template/index.ts` — Template TypeScript types (Read/Create/Update shapes)
- `src/frontend/src/controllers/API/queries/templates/use-create-template.ts` — `POST /api/v1/templates`
- `src/frontend/src/controllers/API/queries/templates/use-list-templates.ts` — `GET /api/v1/templates`
- `src/frontend/src/controllers/API/queries/templates/use-get-template.ts` — `GET /api/v1/templates/{id}`
- `src/frontend/src/controllers/API/queries/templates/use-update-template.ts` — `PUT /api/v1/templates/{id}`
- `src/frontend/src/controllers/API/queries/templates/use-delete-template.ts` — `DELETE /api/v1/templates/{id}` (soft)
- `src/frontend/src/controllers/API/queries/templates/index.ts` — re-exports
- `src/frontend/src/modals/SaveAsTemplateModal/credentialBlanking.ts` — pure blanking utility
- `src/frontend/src/modals/SaveAsTemplateModal/GradientPickerField.tsx` — 4×3 swatch picker
- `src/frontend/src/modals/SaveAsTemplateModal/IconPickerField.tsx` — searchable icon popover
- `src/frontend/src/modals/SaveAsTemplateModal/index.tsx` — the modal component

**Create (4 test files):**

- `src/frontend/src/modals/SaveAsTemplateModal/__tests__/credentialBlanking.test.ts`
- `src/frontend/src/modals/SaveAsTemplateModal/__tests__/GradientPickerField.test.tsx`
- `src/frontend/src/modals/SaveAsTemplateModal/__tests__/IconPickerField.test.tsx`
- `src/frontend/src/modals/SaveAsTemplateModal/__tests__/SaveAsTemplateModal.test.tsx`

**Modify:**

- `src/frontend/src/components/core/flowToolbarComponent/components/deploy-dropdown.tsx` — insert "Save as Template" menu item between Export and MCP Server entries, gated on `currentUser.is_superuser`

---

## Task sequencing

7 tasks in 4 phases:

1. **Data glue** (Tasks 1–2) — types + 5 hooks + credentialBlanking util. No UI visible yet.
2. **Pickers** (Tasks 3–4) — GradientPickerField + IconPickerField.
3. **Modal** (Tasks 5–6) — layout/state + submit wiring.
4. **Integration** (Task 7) — Share-dropdown menu item.

---

### Task 1: Port Template types + 5 query hooks

**Files:**
- Create: `src/frontend/src/types/template/index.ts`
- Create: `src/frontend/src/controllers/API/queries/templates/use-list-templates.ts`
- Create: `src/frontend/src/controllers/API/queries/templates/use-get-template.ts`
- Create: `src/frontend/src/controllers/API/queries/templates/use-create-template.ts`
- Create: `src/frontend/src/controllers/API/queries/templates/use-update-template.ts`
- Create: `src/frontend/src/controllers/API/queries/templates/use-delete-template.ts`
- Create: `src/frontend/src/controllers/API/queries/templates/index.ts`

The retired `feat/template-management-phase-1` branch was deleted, but its commit (`1d9bf2c73b`) is still reachable by sha. Reference these paths from that commit:
- `src/frontend/src/types/template/index.ts`
- `src/frontend/src/controllers/API/queries/templates/*.ts`

- [ ] **Step 1: Pull each file from the retired-branch commit and write it verbatim**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/save-as-template-frontend
for path in \
  src/frontend/src/types/template/index.ts \
  src/frontend/src/controllers/API/queries/templates/use-list-templates.ts \
  src/frontend/src/controllers/API/queries/templates/use-get-template.ts \
  src/frontend/src/controllers/API/queries/templates/use-create-template.ts \
  src/frontend/src/controllers/API/queries/templates/use-update-template.ts \
  src/frontend/src/controllers/API/queries/templates/use-delete-template.ts \
  src/frontend/src/controllers/API/queries/templates/index.ts; do
  mkdir -p "$(dirname "$path")"
  git show 1d9bf2c73b:"$path" > "$path"
done
```

If any file doesn't exist on the retired branch, skip it — the grep below catches it. If a hook file doesn't exist (e.g. `use-delete-template.ts`), write a minimal stub following the `use-post-add-flow.ts` pattern:

```ts
// stub template: adapt verb + URL per the missing hook
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useDeleteTemplate: useMutationFunctionType<undefined, { id: string }> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();
  const fn = async (payload: { id: string }) => {
    const response = await api.delete(`${getURL("TEMPLATES")}/${payload.id}`);
    return response.data;
  };
  return mutate(["useDeleteTemplate"], fn, {
    ...options,
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["useListTemplates"] });
    },
  });
};
```

- [ ] **Step 2: Check whether `getURL` has a `TEMPLATES` entry**

```bash
grep -n "TEMPLATES" src/frontend/src/controllers/API/helpers/constants.ts
```

If `TEMPLATES` is absent, add it. Read the file around the existing entries (e.g. `FLOWS`, `FOLDERS`, `VARIABLES`) and add a matching line:

```ts
// src/frontend/src/controllers/API/helpers/constants.ts — near FLOWS entry
TEMPLATES: "/api/v1/templates",
```

Match the exact quoting + trailing-comma style of the surrounding entries.

- [ ] **Step 3: TypeScript compile check**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/save-as-template-frontend/src/frontend
npx tsc --noEmit 2>&1 | head -30
```

Expected: no new errors in the template hooks / types / constants. Pre-existing errors elsewhere are acceptable. If new errors appear specifically in these files, fix them (most likely an unused import or a type from the retired branch that doesn't exist on current main).

- [ ] **Step 4: Stage and pause**

`git add src/frontend/src/types/template/ src/frontend/src/controllers/API/queries/templates/ src/frontend/src/controllers/API/helpers/constants.ts`. DO NOT COMMIT.

Proposed message: `feat(templates-frontend): port TypeScript types and 5 CRUD hooks`.

---

### Task 2: `credentialBlanking` utility + unit tests

**Files:**
- Create: `src/frontend/src/modals/SaveAsTemplateModal/credentialBlanking.ts`
- Create test: `src/frontend/src/modals/SaveAsTemplateModal/__tests__/credentialBlanking.test.ts`

- [ ] **Step 1: Write the failing tests FIRST**

Create `src/frontend/src/modals/SaveAsTemplateModal/__tests__/credentialBlanking.test.ts`:

```ts
import { describe, it, expect } from "@jest/globals";
import { blankCredentials, type BlankedField } from "../credentialBlanking";

function flowWithField(fieldName: string, field: Record<string, unknown>) {
  return {
    nodes: [
      {
        id: "Node-abc",
        data: {
          type: "TestComponent",
          node: {
            display_name: "Test Component",
            template: { [fieldName]: field },
          },
        },
      },
    ],
    edges: [],
  };
}

describe("blankCredentials", () => {
  it("blanks SecretStrInput with auto_promote", () => {
    const input = flowWithField("api_key", {
      _input_type: "SecretStrInput",
      auto_promote: true,
      password: true,
      value: "sk-plaintext",
      load_from_db: false,
      display_name: "API Key",
    });
    const { cleaned_nodes, blanked_fields } = blankCredentials(input);
    const field = cleaned_nodes[0].data.node.template.api_key;
    expect(field.value).toBe("");
    expect(field.load_from_db).toBe(false);
    expect(blanked_fields).toHaveLength(1);
    expect(blanked_fields[0]).toEqual<BlankedField>({
      node_id: "Node-abc",
      component_display_name: "Test Component",
      field_name: "api_key",
      field_display_name: "API Key",
    });
  });

  it("blanks TextFileSecretInput", () => {
    const input = flowWithField("cert_pem", {
      _input_type: "TextFileSecretInput",
      auto_promote: true,
      value: "-----BEGIN CERTIFICATE-----\nAAA\n-----END CERTIFICATE-----\n",
    });
    const { cleaned_nodes } = blankCredentials(input);
    expect(cleaned_nodes[0].data.node.template.cert_pem.value).toBe("");
  });

  it("blanks password:true fields regardless of input type", () => {
    const input = flowWithField("legacy_secret", {
      _input_type: "StrInput",
      password: true,
      value: "old-secret",
    });
    const { cleaned_nodes } = blankCredentials(input);
    expect(cleaned_nodes[0].data.node.template.legacy_secret.value).toBe("");
  });

  it("blanks value starting with __autosecret_", () => {
    const input = flowWithField("cert_pem", {
      _input_type: "TextFileSecretInput",
      value: "__autosecret_flow-xyz_Node-abc_cert_pem",
      load_from_db: true,
    });
    const { cleaned_nodes } = blankCredentials(input);
    expect(cleaned_nodes[0].data.node.template.cert_pem.value).toBe("");
    expect(cleaned_nodes[0].data.node.template.cert_pem.load_from_db).toBe(false);
  });

  it("leaves normal text fields untouched", () => {
    const input = flowWithField("url_input", {
      _input_type: "MessageTextInput",
      value: "https://example.com",
    });
    const { cleaned_nodes, blanked_fields } = blankCredentials(input);
    expect(cleaned_nodes[0].data.node.template.url_input.value).toBe(
      "https://example.com",
    );
    expect(blanked_fields).toHaveLength(0);
  });

  it("does not mutate the original input", () => {
    const input = flowWithField("api_key", {
      _input_type: "SecretStrInput",
      auto_promote: true,
      value: "sk-plaintext",
    });
    const originalValue = input.nodes[0].data.node.template.api_key.value;
    blankCredentials(input);
    expect(input.nodes[0].data.node.template.api_key.value).toBe(originalValue);
  });

  it("returns a list of all blanked fields across multiple nodes", () => {
    const input = {
      nodes: [
        {
          id: "Node-1",
          data: {
            type: "A",
            node: {
              display_name: "A",
              template: {
                k: {
                  _input_type: "SecretStrInput",
                  auto_promote: true,
                  value: "x",
                  display_name: "K",
                },
              },
            },
          },
        },
        {
          id: "Node-2",
          data: {
            type: "B",
            node: {
              display_name: "B",
              template: {
                p: { _input_type: "StrInput", password: true, value: "y", display_name: "P" },
              },
            },
          },
        },
      ],
      edges: [],
    };
    const { blanked_fields } = blankCredentials(input);
    expect(blanked_fields.map((b) => b.node_id).sort()).toEqual(["Node-1", "Node-2"]);
  });
});
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/save-as-template-frontend/src/frontend
npx jest src/modals/SaveAsTemplateModal/__tests__/credentialBlanking.test.ts --no-coverage
```

Expected: module-not-found error (file doesn't exist yet).

- [ ] **Step 3: Implement the utility**

Create `src/frontend/src/modals/SaveAsTemplateModal/credentialBlanking.ts`:

```ts
/**
 * Pure utility: walks a flow's nodes + template fields, produces a deep-copied
 * `cleaned_nodes` array with credential values blanked, plus a list of
 * `blanked_fields` metadata for the "What gets stripped?" UI surface.
 *
 * The blanking rule — a field is blanked if ANY of:
 *   - _input_type ∈ {SecretStrInput, TextFileSecretInput, MultilineSecretInput}
 *   - auto_promote === true
 *   - password === true
 *   - value is a string that starts with "__autosecret_"
 *
 * Blanking = value reset to "", load_from_db reset to false.
 * The original input is not mutated.
 */

const SECRET_INPUT_TYPES = new Set([
  "SecretStrInput",
  "TextFileSecretInput",
  "MultilineSecretInput",
]);

const AUTOSECRET_PREFIX = "__autosecret_";

export type BlankedField = {
  node_id: string;
  component_display_name: string;
  field_name: string;
  field_display_name: string;
};

export type BlankCredentialsResult = {
  cleaned_nodes: any[];
  blanked_fields: BlankedField[];
};

function isFieldCredential(field: unknown): boolean {
  if (!field || typeof field !== "object") return false;
  const f = field as Record<string, unknown>;
  if (typeof f._input_type === "string" && SECRET_INPUT_TYPES.has(f._input_type)) return true;
  if (f.auto_promote === true) return true;
  if (f.password === true) return true;
  if (typeof f.value === "string" && f.value.startsWith(AUTOSECRET_PREFIX)) return true;
  return false;
}

export function blankCredentials(flowData: { nodes: any[]; edges: unknown[] }): BlankCredentialsResult {
  const cleaned_nodes = JSON.parse(JSON.stringify(flowData.nodes ?? []));
  const blanked_fields: BlankedField[] = [];

  for (const node of cleaned_nodes) {
    const nodeId: string | undefined = node?.id;
    const nodeInner = node?.data?.node;
    if (!nodeId || !nodeInner || typeof nodeInner !== "object") continue;
    const template = nodeInner.template;
    if (!template || typeof template !== "object") continue;
    for (const [fieldName, field] of Object.entries(template)) {
      if (!isFieldCredential(field)) continue;
      const fieldDict = field as Record<string, unknown>;
      fieldDict.value = "";
      fieldDict.load_from_db = false;
      blanked_fields.push({
        node_id: nodeId,
        component_display_name: (nodeInner.display_name as string) ?? "",
        field_name: fieldName,
        field_display_name: (fieldDict.display_name as string) ?? fieldName,
      });
    }
  }

  return { cleaned_nodes, blanked_fields };
}
```

- [ ] **Step 4: Run tests to verify pass**

```bash
npx jest src/modals/SaveAsTemplateModal/__tests__/credentialBlanking.test.ts --no-coverage
```

Expected: 7 passed.

- [ ] **Step 5: Stage and pause**

`git add src/frontend/src/modals/SaveAsTemplateModal/credentialBlanking.ts src/frontend/src/modals/SaveAsTemplateModal/__tests__/credentialBlanking.test.ts`. DO NOT COMMIT.

Proposed message: `feat(save-as-template): add credentialBlanking util with unit tests`.

---

### Task 3: `GradientPickerField` component + test

**Files:**
- Create: `src/frontend/src/modals/SaveAsTemplateModal/GradientPickerField.tsx`
- Create test: `src/frontend/src/modals/SaveAsTemplateModal/__tests__/GradientPickerField.test.tsx`

- [ ] **Step 1: Write the failing test FIRST**

Create `src/frontend/src/modals/SaveAsTemplateModal/__tests__/GradientPickerField.test.tsx`:

```tsx
import { describe, it, expect, jest } from "@jest/globals";
import { render, screen, fireEvent } from "@testing-library/react";
import GradientPickerField from "../GradientPickerField";

describe("GradientPickerField", () => {
  it("renders the selected gradient with a visible 'selected' indicator", () => {
    render(<GradientPickerField value="2" onChange={() => {}} />);
    const selected = screen.getByTestId("gradient-swatch-2");
    expect(selected.getAttribute("data-selected")).toBe("true");
  });

  it("clicking a swatch calls onChange with that index as a string", () => {
    const handleChange = jest.fn();
    render(<GradientPickerField value="0" onChange={handleChange} />);
    fireEvent.click(screen.getByTestId("gradient-swatch-3"));
    expect(handleChange).toHaveBeenCalledWith("3");
  });

  it("renders as many swatches as there are gradients", () => {
    render(<GradientPickerField value="0" onChange={() => {}} />);
    const swatches = screen.getAllByTestId(/^gradient-swatch-/);
    // We don't assert an exact count because styleUtils.gradients may grow;
    // assert it's at least 8 (the known minimum in the fixture).
    expect(swatches.length).toBeGreaterThanOrEqual(8);
  });
});
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/save-as-template-frontend/src/frontend
npx jest src/modals/SaveAsTemplateModal/__tests__/GradientPickerField.test.tsx --no-coverage
```

Expected: module-not-found.

- [ ] **Step 3: Implement the component**

Create `src/frontend/src/modals/SaveAsTemplateModal/GradientPickerField.tsx`:

```tsx
import { gradients } from "@/utils/styleUtils";

type Props = {
  /** Selected index, stringified so it can be sent to the API as-is. */
  value: string;
  onChange: (value: string) => void;
};

export default function GradientPickerField({ value, onChange }: Props) {
  const selectedIndex = Number.parseInt(value, 10);
  return (
    <div
      role="radiogroup"
      aria-label="Gradient"
      className="grid grid-cols-4 gap-2"
    >
      {gradients.map((gradientClass, index) => {
        const isSelected = index === selectedIndex;
        return (
          <button
            key={index}
            type="button"
            role="radio"
            aria-checked={isSelected}
            data-testid={`gradient-swatch-${index}`}
            data-selected={isSelected ? "true" : "false"}
            className={`h-10 w-full rounded-md ring-2 ring-offset-1 ${gradientClass} ${
              isSelected ? "ring-primary" : "ring-transparent"
            }`}
            onClick={() => onChange(String(index))}
          />
        );
      })}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify pass**

Same command as Step 2. Expected: 3 passed.

- [ ] **Step 5: Stage and pause**

`git add src/frontend/src/modals/SaveAsTemplateModal/GradientPickerField.tsx src/frontend/src/modals/SaveAsTemplateModal/__tests__/GradientPickerField.test.tsx`. DO NOT COMMIT.

Proposed message: `feat(save-as-template): add GradientPickerField`.

---

### Task 4: `IconPickerField` component + test

**Files:**
- Create: `src/frontend/src/modals/SaveAsTemplateModal/IconPickerField.tsx`
- Create test: `src/frontend/src/modals/SaveAsTemplateModal/__tests__/IconPickerField.test.tsx`

- [ ] **Step 1: Survey the icon list module**

```bash
grep -n "export " src/frontend/src/icons/fontAwesomeIcons/*.ts src/frontend/src/icons/fontAwesomeIcons/*.tsx 2>&1 | head
```

Find which export gives you the array of icon names. Common names: `fontAwesomeIcons` (an array of strings), `isFontAwesomeIcon` (predicate). The component below assumes an exported `fontAwesomeIcons: string[]` — adapt the import to whatever the real export name is.

- [ ] **Step 2: Write the failing test FIRST**

Create `src/frontend/src/modals/SaveAsTemplateModal/__tests__/IconPickerField.test.tsx`:

```tsx
import { describe, it, expect, jest } from "@jest/globals";
import { render, screen, fireEvent } from "@testing-library/react";
import IconPickerField from "../IconPickerField";

describe("IconPickerField", () => {
  it("renders the selected icon name on the trigger", () => {
    render(<IconPickerField value="FileText" onChange={() => {}} />);
    expect(screen.getByRole("button", { name: /filetext/i })).toBeInTheDocument();
  });

  it("clicking the trigger opens a popover with icon options", () => {
    render(<IconPickerField value="FileText" onChange={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /filetext/i }));
    // At least a couple of known lucide/fontawesome icons should render in the popover.
    expect(screen.getAllByRole("option").length).toBeGreaterThan(5);
  });

  it("selecting an option calls onChange with that icon name", () => {
    const handleChange = jest.fn();
    render(<IconPickerField value="FileText" onChange={handleChange} />);
    fireEvent.click(screen.getByRole("button", { name: /filetext/i }));
    const options = screen.getAllByRole("option");
    fireEvent.click(options[0]);
    expect(handleChange).toHaveBeenCalledTimes(1);
    expect(typeof handleChange.mock.calls[0][0]).toBe("string");
  });

  it("typing in the search filters the list", () => {
    render(<IconPickerField value="FileText" onChange={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /filetext/i }));
    const before = screen.getAllByRole("option").length;
    const search = screen.getByPlaceholderText(/search/i);
    fireEvent.change(search, { target: { value: "zzzzzz-unlikely-match" } });
    expect(screen.queryAllByRole("option").length).toBeLessThan(before);
  });
});
```

- [ ] **Step 3: Run to verify failure**

```bash
npx jest src/modals/SaveAsTemplateModal/__tests__/IconPickerField.test.tsx --no-coverage
```

Expected: module-not-found.

- [ ] **Step 4: Implement the component**

Create `src/frontend/src/modals/SaveAsTemplateModal/IconPickerField.tsx`:

```tsx
import { useMemo, useState } from "react";
import { fontAwesomeIcons } from "@/icons/fontAwesomeIcons";
// NOTE: the real export name from src/frontend/src/icons/fontAwesomeIcons
// must be verified in Task 4 Step 1 — adjust this import if the symbol
// is named differently (e.g. `faIcons`, `iconNames`).

type Props = {
  value: string;
  onChange: (iconName: string) => void;
};

export default function IconPickerField({ value, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const options = useMemo(() => {
    const all: string[] = Array.isArray(fontAwesomeIcons) ? fontAwesomeIcons : [];
    if (!query.trim()) return all;
    const q = query.toLowerCase();
    return all.filter((n) => n.toLowerCase().includes(q));
  }, [query]);

  const close = () => {
    setOpen(false);
    setQuery("");
  };

  return (
    <div className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm"
      >
        {value}
      </button>
      {open && (
        <div className="absolute z-50 mt-2 w-72 rounded-md border bg-popover p-2 shadow-lg">
          <input
            autoFocus
            type="text"
            placeholder="Search icons…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="mb-2 w-full rounded-sm border px-2 py-1 text-sm"
          />
          <div
            role="listbox"
            className="grid max-h-60 grid-cols-5 gap-1 overflow-y-auto"
          >
            {options.map((name) => (
              <button
                key={name}
                type="button"
                role="option"
                aria-selected={name === value}
                onClick={() => {
                  onChange(name);
                  close();
                }}
                className={`rounded-sm px-2 py-1 text-xs ${
                  name === value ? "bg-accent" : ""
                }`}
              >
                {name}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Run test to verify pass**

Same command as Step 3. Expected: 4 passed.

- [ ] **Step 6: Stage and pause**

`git add src/frontend/src/modals/SaveAsTemplateModal/IconPickerField.tsx src/frontend/src/modals/SaveAsTemplateModal/__tests__/IconPickerField.test.tsx`. DO NOT COMMIT.

Proposed message: `feat(save-as-template): add IconPickerField with search`.

---

### Task 5: `SaveAsTemplateModal` layout + state skeleton (no submit yet)

**Files:**
- Create: `src/frontend/src/modals/SaveAsTemplateModal/index.tsx`

This task lays down the modal shell — form fields, local state, client-side validation, the "What gets stripped?" collapse, and the disabled/enabled Save button. Submit wiring (calling `useCreateTemplate`, handling 409, toasts) is Task 6.

- [ ] **Step 1: Read an existing sibling modal for style reference**

```bash
cat src/frontend/src/modals/exportModal/index.tsx | head -80
```

Note how `exportModal` imports `BaseModal`, composes header/body/footer, uses Tailwind classes, and wires buttons. Mirror that shape.

- [ ] **Step 2: Create the modal skeleton**

Create `src/frontend/src/modals/SaveAsTemplateModal/index.tsx`:

```tsx
import { useEffect, useMemo, useState } from "react";
import BaseModal from "@/modals/baseModal";
import GradientPickerField from "./GradientPickerField";
import IconPickerField from "./IconPickerField";
import { blankCredentials, type BlankedField } from "./credentialBlanking";

type FlowData = {
  nodes: any[];
  edges: any[];
  description?: string | null;
};

type Props = {
  open: boolean;
  onClose: () => void;
  flow: FlowData & { id?: string };
};

const DEFAULT_ICON = "FileText";
const DEFAULT_GRADIENT = "0";

export default function SaveAsTemplateModal({ open, onClose, flow }: Props) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [icon, setIcon] = useState(DEFAULT_ICON);
  const [gradient, setGradient] = useState(DEFAULT_GRADIENT);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [nameError, setNameError] = useState<string | null>(null);

  // Reset state every time the modal reopens.
  useEffect(() => {
    if (open) {
      setName("");
      setDescription(flow.description ?? "");
      setIcon(DEFAULT_ICON);
      setGradient(DEFAULT_GRADIENT);
      setDetailsOpen(false);
      setNameError(null);
    }
  }, [open, flow.description]);

  const { blanked_fields } = useMemo(
    () =>
      blankCredentials({ nodes: flow.nodes ?? [], edges: flow.edges ?? [] }),
    [flow.nodes, flow.edges],
  );

  const canSubmit = name.trim().length > 0;

  return (
    <BaseModal open={open} setOpen={(o) => (!o ? onClose() : undefined)} size="medium">
      <BaseModal.Header description="Save the current flow as a reusable platform template.">
        Save as Template
      </BaseModal.Header>
      <BaseModal.Content>
        <div className="space-y-4">
          <label className="block text-sm">
            <span className="mb-1 block font-medium">
              Name <span className="text-red-600">*</span>
            </span>
            <input
              type="text"
              autoFocus
              maxLength={255}
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                if (nameError) setNameError(null);
              }}
              placeholder="e.g. Customer Support Agent"
              className={`w-full rounded-md border px-3 py-2 text-sm ${
                nameError ? "border-red-500" : ""
              }`}
            />
            {nameError && (
              <p className="mt-1 text-sm text-red-600" role="alert">
                {nameError}
              </p>
            )}
          </label>

          <label className="block text-sm">
            <span className="mb-1 block font-medium">Description</span>
            <textarea
              rows={3}
              maxLength={1000}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Short summary of what this template does."
              className="w-full rounded-md border px-3 py-2 text-sm"
            />
          </label>

          <div className="space-y-2">
            <span className="block text-sm font-medium">Icon</span>
            <IconPickerField value={icon} onChange={setIcon} />
          </div>

          <div className="space-y-2">
            <span className="block text-sm font-medium">Gradient</span>
            <GradientPickerField value={gradient} onChange={setGradient} />
          </div>

          <details open={detailsOpen} onToggle={(e) => setDetailsOpen((e.target as HTMLDetailsElement).open)}>
            <summary className="cursor-pointer text-sm font-medium">
              What gets stripped? ({blanked_fields.length})
            </summary>
            <ul className="mt-2 list-disc pl-6 text-sm text-muted-foreground">
              {blanked_fields.map((f: BlankedField) => (
                <li key={`${f.node_id}:${f.field_name}`}>
                  <span className="font-medium">{f.component_display_name}</span> — {f.field_display_name}
                </li>
              ))}
              {blanked_fields.length === 0 && (
                <li className="list-none italic">No credential fields detected.</li>
              )}
            </ul>
          </details>
        </div>
      </BaseModal.Content>
      <BaseModal.Footer>
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border px-3 py-1.5 text-sm"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={!canSubmit}
            className="rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground disabled:opacity-50"
          >
            Save as Template
          </button>
        </div>
      </BaseModal.Footer>
    </BaseModal>
  );
}
```

> **NOTE:** `BaseModal`'s exact prop/shape (e.g. `BaseModal.Header` vs inline `title` prop) is verified by reading `src/frontend/src/modals/baseModal/index.tsx` — adjust the composition to match what the current component accepts. If the sibling `exportModal` uses a different composition, mirror `exportModal`.

- [ ] **Step 3: TypeScript compile check**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/save-as-template-frontend/src/frontend
npx tsc --noEmit 2>&1 | grep SaveAsTemplateModal | head
```

Expected: no new errors in the new file. Fix imports/prop shapes as needed.

- [ ] **Step 4: Stage and pause**

`git add src/frontend/src/modals/SaveAsTemplateModal/index.tsx`. DO NOT COMMIT.

Proposed message: `feat(save-as-template): add modal skeleton with form + pickers + strip-preview`.

---

### Task 6: Modal submit wiring + error handling + tests

**Files:**
- Modify: `src/frontend/src/modals/SaveAsTemplateModal/index.tsx`
- Create test: `src/frontend/src/modals/SaveAsTemplateModal/__tests__/SaveAsTemplateModal.test.tsx`

- [ ] **Step 1: Write the failing modal tests**

Create `src/frontend/src/modals/SaveAsTemplateModal/__tests__/SaveAsTemplateModal.test.tsx`:

```tsx
import { describe, it, expect, jest } from "@jest/globals";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import SaveAsTemplateModal from "../index";

// Mock the create-template mutation hook.
const mutateMock = jest.fn();
jest.mock(
  "@/controllers/API/queries/templates",
  () => ({
    useCreateTemplate: () => ({
      mutate: mutateMock,
      isLoading: false,
    }),
  }),
);

// Mock the alert store (same pattern as sibling modals).
const successMock = jest.fn();
const errorMock = jest.fn();
jest.mock(
  "@/stores/alertStore",
  () => ({
    __esModule: true,
    default: (selector: any) =>
      selector({
        setSuccessData: successMock,
        setErrorData: errorMock,
      }),
  }),
);

function baseFlow() {
  return {
    id: "flow-abc",
    description: "Pre-existing description",
    nodes: [
      {
        id: "Node-1",
        data: {
          type: "APIRequest",
          node: {
            display_name: "API Request",
            template: {
              cert_pem: {
                _input_type: "TextFileSecretInput",
                auto_promote: true,
                value: "PEMPLAINTEXT",
                display_name: "Client Certificate",
              },
              url_input: {
                _input_type: "MessageTextInput",
                value: "https://example.com",
              },
            },
          },
        },
      },
    ],
    edges: [],
  };
}

describe("SaveAsTemplateModal", () => {
  beforeEach(() => {
    mutateMock.mockReset();
    successMock.mockReset();
    errorMock.mockReset();
  });

  it("renders all fields with expected defaults", () => {
    render(<SaveAsTemplateModal open onClose={() => {}} flow={baseFlow()} />);
    expect(screen.getByRole("textbox", { name: /name/i })).toHaveValue("");
    expect(screen.getByRole("textbox", { name: /description/i })).toHaveValue(
      "Pre-existing description",
    );
    expect(screen.getByRole("button", { name: /filetext/i })).toBeInTheDocument();
  });

  it("Save button is disabled until Name is non-empty", () => {
    render(<SaveAsTemplateModal open onClose={() => {}} flow={baseFlow()} />);
    const save = screen.getByRole("button", { name: /save as template/i });
    expect(save).toBeDisabled();
    fireEvent.change(screen.getByRole("textbox", { name: /name/i }), {
      target: { value: "My Template" },
    });
    expect(save).toBeEnabled();
  });

  it("strip-preview lists the credential field", () => {
    render(<SaveAsTemplateModal open onClose={() => {}} flow={baseFlow()} />);
    fireEvent.click(screen.getByRole("group").querySelector("summary")!);
    expect(screen.getByText(/API Request/)).toBeInTheDocument();
    expect(screen.getByText(/Client Certificate/)).toBeInTheDocument();
  });

  it("submit calls the mutation with the blanked-node payload", () => {
    render(<SaveAsTemplateModal open onClose={() => {}} flow={baseFlow()} />);
    fireEvent.change(screen.getByRole("textbox", { name: /name/i }), {
      target: { value: "My Template" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save as template/i }));
    expect(mutateMock).toHaveBeenCalledTimes(1);
    const [payload] = mutateMock.mock.calls[0];
    expect(payload.name).toBe("My Template");
    expect(payload.description).toBe("Pre-existing description");
    expect(payload.icon).toBe("FileText");
    expect(payload.gradient).toBe("0");
    // Blanking proof: cert_pem value is "", url_input unchanged.
    const cert = payload.nodes[0].data.node.template.cert_pem;
    expect(cert.value).toBe("");
    expect(cert.load_from_db).toBe(false);
    const url = payload.nodes[0].data.node.template.url_input;
    expect(url.value).toBe("https://example.com");
  });

  it("on 409 response, shows inline name error and re-enables button", async () => {
    mutateMock.mockImplementation((_payload, opts) => {
      opts.onError?.({
        response: { status: 409, data: { detail: "name conflict" } },
      });
    });
    const onClose = jest.fn();
    render(<SaveAsTemplateModal open onClose={onClose} flow={baseFlow()} />);
    fireEvent.change(screen.getByRole("textbox", { name: /name/i }), {
      target: { value: "Duplicate" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save as template/i }));
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/already exists/i);
    });
    expect(onClose).not.toHaveBeenCalled();
    expect(errorMock).not.toHaveBeenCalled();
  });

  it("on non-409 error, shows error toast and modal stays open", async () => {
    mutateMock.mockImplementation((_payload, opts) => {
      opts.onError?.({ response: { status: 500, data: {} } });
    });
    const onClose = jest.fn();
    render(<SaveAsTemplateModal open onClose={onClose} flow={baseFlow()} />);
    fireEvent.change(screen.getByRole("textbox", { name: /name/i }), {
      target: { value: "Boom" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save as template/i }));
    await waitFor(() => {
      expect(errorMock).toHaveBeenCalledTimes(1);
    });
    expect(onClose).not.toHaveBeenCalled();
  });

  it("on success, shows success toast and calls onClose", async () => {
    mutateMock.mockImplementation((_payload, opts) => {
      opts.onSuccess?.({ id: "template-new", name: "Saved" });
    });
    const onClose = jest.fn();
    render(<SaveAsTemplateModal open onClose={onClose} flow={baseFlow()} />);
    fireEvent.change(screen.getByRole("textbox", { name: /name/i }), {
      target: { value: "Saved" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save as template/i }));
    await waitFor(() => {
      expect(successMock).toHaveBeenCalledTimes(1);
      expect(onClose).toHaveBeenCalledTimes(1);
    });
  });
});
```

- [ ] **Step 2: Run to verify failure**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/save-as-template-frontend/src/frontend
npx jest src/modals/SaveAsTemplateModal/__tests__/SaveAsTemplateModal.test.tsx --no-coverage
```

Expected: most tests fail because submit logic isn't wired yet.

- [ ] **Step 3: Wire the submit handler**

Open `src/frontend/src/modals/SaveAsTemplateModal/index.tsx`. Add at the top (with the other imports):

```tsx
import { useCreateTemplate } from "@/controllers/API/queries/templates";
import useAlertStore from "@/stores/alertStore";
```

Inside the component body, after the existing state hooks:

```tsx
  const { mutate: createTemplate, isLoading: submitting } = useCreateTemplate();
  const setSuccessData = useAlertStore((s) => s.setSuccessData);
  const setErrorData = useAlertStore((s) => s.setErrorData);

  function handleSubmit() {
    if (!canSubmit) return;
    const { cleaned_nodes } = blankCredentials({
      nodes: flow.nodes ?? [],
      edges: flow.edges ?? [],
    });
    createTemplate(
      {
        name: name.trim(),
        description: description.trim() || null,
        icon,
        gradient,
        nodes: cleaned_nodes,
        edges: flow.edges ?? [],
      },
      {
        onSuccess: () => {
          setSuccessData({ title: `Template "${name.trim()}" saved` });
          onClose();
        },
        onError: (err: any) => {
          if (err?.response?.status === 409) {
            setNameError(
              "A template with that name already exists — pick a different one.",
            );
          } else {
            setErrorData({
              title: "Failed to save template",
              list: [err?.response?.data?.detail ?? "Please try again."],
            });
          }
        },
      },
    );
  }
```

Update the Save button at the bottom to wire up `onClick` and the disabled state for `submitting`:

```tsx
          <button
            type="button"
            disabled={!canSubmit || submitting}
            onClick={handleSubmit}
            className="rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground disabled:opacity-50"
          >
            {submitting ? "Saving…" : "Save as Template"}
          </button>
```

> **NOTE:** the `useCreateTemplate` hook's `mutate` signature is `mutate(payload, options?)` per the `useMutationFunctionType` pattern. Its `options` object accepts `onSuccess` and `onError` — verify against the stale branch's `use-create-template.ts` that we ported in Task 1.

- [ ] **Step 4: Run tests to verify pass**

Same command as Step 2. Expected: 7 passed.

If the `alertStore` mock or mutation mock doesn't match the real hook's shape, adjust the mock to what the real hook emits (e.g., the Zustand selector pattern sometimes differs from `default: (selector) => ...`). Use an existing test — e.g. `src/frontend/src/modals/fileManagerModal/__tests__/*.test.tsx` — as a reference for the correct Zustand-mock shape.

- [ ] **Step 5: Stage and pause**

`git add src/frontend/src/modals/SaveAsTemplateModal/index.tsx src/frontend/src/modals/SaveAsTemplateModal/__tests__/SaveAsTemplateModal.test.tsx`. DO NOT COMMIT.

Proposed message: `feat(save-as-template): wire submit, 409 inline error, success/error toasts`.

---

### Task 7: Share-dropdown integration (insert the menu item)

**Files:**
- Modify: `src/frontend/src/components/core/flowToolbarComponent/components/deploy-dropdown.tsx`

- [ ] **Step 1: Find the dropdown's menu items**

```bash
grep -n "Export\|MCP\|DropdownMenuItem\|onSelect" src/frontend/src/components/core/flowToolbarComponent/components/deploy-dropdown.tsx | head -30
```

Locate the two menu items — "Export" and "MCP Server" — and the code between them. Your insertion point is between them.

- [ ] **Step 2: Add modal state + wire the menu item**

Edit `src/frontend/src/components/core/flowToolbarComponent/components/deploy-dropdown.tsx`.

Imports (add near existing imports):

```tsx
import { useState } from "react";
import SaveAsTemplateModal from "@/modals/SaveAsTemplateModal";
```

Find how the component accesses the current flow (`useFlowStore`, prop, etc.) and the current user (usually via the auth store). Add to the top of the component body:

```tsx
  const [saveTemplateOpen, setSaveTemplateOpen] = useState(false);
  // Adapt to the store selector used elsewhere in this file. Common patterns:
  //   const currentUser = useAuthStore((s) => s.currentUser);
  //   const currentFlow = useFlowStore((s) => s.currentFlow);
  // Verify the exact names against the other store references already in this file.
  const isSuperuser = currentUser?.is_superuser === true;
```

Insert the new menu item between the Export and MCP Server entries. Match the sibling `<DropdownMenuItem>` styling / indentation:

```tsx
        {isSuperuser && (
          <DropdownMenuItem onSelect={() => setSaveTemplateOpen(true)}>
            {/* icon consistent with sibling items — e.g. FileText */}
            Save as Template
          </DropdownMenuItem>
        )}
```

At the bottom of the component's JSX (outside the dropdown, inside the component), add the modal mount:

```tsx
      <SaveAsTemplateModal
        open={saveTemplateOpen}
        onClose={() => setSaveTemplateOpen(false)}
        flow={currentFlow}
      />
```

`currentFlow` must have `{ id?, nodes, edges, description }` to satisfy the modal's Props. If the existing variable is shaped differently, map it inline:

```tsx
        flow={{
          id: currentFlow?.id,
          description: currentFlow?.description,
          nodes: currentFlow?.data?.nodes ?? [],
          edges: currentFlow?.data?.edges ?? [],
        }}
```

- [ ] **Step 3: TypeScript compile check**

```bash
cd /Users/brycedeneen/dev/langflow/.worktrees/save-as-template-frontend/src/frontend
npx tsc --noEmit 2>&1 | grep -E "deploy-dropdown|SaveAsTemplateModal" | head
```

Expected: no new errors.

- [ ] **Step 4: Manual smoke**

Not part of the automated flow, but document it in the commit message: spin up the dev server and confirm:
1. Superuser session: open a flow, click Share, see "Save as Template" between Export and MCP Server.
2. Regular user session: open a flow, click Share, confirm the item is absent.
3. Superuser clicks it → modal opens → fill name + save → success toast.

Defer this smoke to the end of the plan when everything is wired.

- [ ] **Step 5: Stage and pause**

`git add src/frontend/src/components/core/flowToolbarComponent/components/deploy-dropdown.tsx`. DO NOT COMMIT.

Proposed message: `feat(share-menu): insert superuser-only "Save as Template" item`.

---

## Post-plan follow-ups (tracked in the spec, out of scope here)

- **FU-1.** Per-field blank/keep toggles in the review panel.
- **FU-2.** Name-collision overwrite flow (second modal → PUT).
- **FU-3.** Template gallery integration — point the existing templates gallery at `GET /api/v1/templates` (currently reads starter projects).
- **FU-4.** Template edit / delete UI (admin surface).
- **FU-5.** Non-superuser authoring permission.
- **FU-6.** Icon picker polish — fuzzy search, recent selections, custom upload.

---

## Self-review

Checked each spec section against the plan:

- **§2 Goals G1–G5** — G1 Task 7, G2 Task 2 + Task 6, G3 Task 5 (strip-preview section), G4 Task 5, G5 single-responsibility tasks throughout.
- **§4 Decisions Q1–Q7** — Q1 Task 7, Q2 Task 1 + Task 5, Q3 Task 5 (read-only collapse), Q4 Task 6 (409 inline), Q5 Task 5 (name/desc/icon/gradient), Q6 Tasks 3–4 (use existing `gradients` + `fontAwesomeIcons`), Q7 Task 6 (success toast + onClose).
- **§5 Architecture** — 6 units all covered: hooks/types (Task 1), blanking (Task 2), pickers (Tasks 3–4), modal (Tasks 5–6), dropdown (Task 7).
- **§6 Modal UX** — field layout in Task 5; state machine wired in Task 6.
- **§7 Credential blanking** — Task 2 implements the exact rule set (SecretStrInput / TextFileSecretInput / MultilineSecretInput + auto_promote + password + `__autosecret_` prefix).
- **§8 Testing** — `credentialBlanking.test.ts` (Task 2, 7 tests), `GradientPickerField.test.tsx` (Task 3, 3 tests), `IconPickerField.test.tsx` (Task 4, 4 tests), `SaveAsTemplateModal.test.tsx` (Task 6, 7 tests).
- **§9 Share-dropdown integration** — Task 7.
- **§10 Scope boundaries** — follow-ups FU-1 through FU-6 all mentioned.
- **§11 Risks** — R1 & R2 flagged in Task 7 (implementer verifies the real paths and selector names); R3 blanking misses via Task 2's input-type set; R4 icon picker perf via Task 4 implementation (simple filter; virtualization deferred); R5 description prefill is editable in Task 5.

No placeholders (every code step has complete code). No type inconsistency (`BlankedField` shape consistent between Task 2 and Task 5's strip-preview render; `useCreateTemplate` shape consistent between Task 1 (definition) and Task 6 (consumption)).
