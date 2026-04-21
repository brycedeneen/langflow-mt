# FU-1 — Per-field Blank/Keep Toggles — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Project commit policy:** This repo follows a strict "no git commits without explicit user approval" rule. Every Step labeled **Commit** in this plan REQUIRES the executing agent to pause and ask the user before running `git commit`. Do NOT auto-commit even if the plan says "commit".

**Goal:** Replace the read-only "What gets stripped?" list inside `SaveAsTemplateModal` with per-field interactive checkboxes grouped by component, defaulting to "blank everything", and surface a persistent inline warning whenever the user has opted to keep ≥1 credential.

**Architecture:** Extract a stateless `StripPanel` component owning the rendering of the panel's summary line, optional warning, grouped checkbox list, and empty state. The parent `SaveAsTemplateModal` adds one new state slot (`keptFieldKeys: Set<string>`), wires a `toggleField` callback, and filters the submit payload's `blanked_fields` against the kept set.

**Tech Stack:** React + TypeScript + Jest + React Testing Library, lucide-react (existing).

**Spec:** [`docs/superpowers/specs/2026-04-20-fu-1-per-field-blank-toggles-design.md`](../specs/2026-04-20-fu-1-per-field-blank-toggles-design.md)

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `src/frontend/src/modals/SaveAsTemplateModal/StripPanel.tsx` | create | Stateless `<details>`-based panel: summary line with count + warning, grouped checkbox list, empty state |
| `src/frontend/src/modals/SaveAsTemplateModal/index.tsx` | modify | Add `keptFieldKeys` state + reset + `toggleField` callback + filtered submit; replace the inline `<details>` body with `<StripPanel>` |
| `src/frontend/src/modals/SaveAsTemplateModal/__tests__/StripPanel.test.tsx` | create | Unit-level component tests (rendering, grouping, summary, warning, toggle wiring) |
| `src/frontend/src/modals/SaveAsTemplateModal/__tests__/SaveAsTemplateModal.test.tsx` | modify | Add 3 integrated tests: submit-with-kept-field, kept-then-rechecked-on-submit, reset-on-reopen |

---

## Task 1: `StripPanel` component + unit tests

**Files:**
- Create: `src/frontend/src/modals/SaveAsTemplateModal/StripPanel.tsx`
- Test: `src/frontend/src/modals/SaveAsTemplateModal/__tests__/StripPanel.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `src/frontend/src/modals/SaveAsTemplateModal/__tests__/StripPanel.test.tsx`:

```tsx
import { describe, expect, it, jest } from "@jest/globals";
import { render, screen, fireEvent, within } from "@testing-library/react";
import StripPanel from "../StripPanel";
import type { BlankableFieldInfo } from "../scanBlankableFields";

const fields: BlankableFieldInfo[] = [
  {
    node_id: "n1",
    field_name: "api_key",
    component_display_name: "OpenAI",
    field_display_name: "API Key",
  },
  {
    node_id: "n1",
    field_name: "org_id",
    component_display_name: "OpenAI",
    field_display_name: "Org ID",
  },
  {
    node_id: "n2",
    field_name: "index_key",
    component_display_name: "Pinecone",
    field_display_name: "Index API Key",
  },
];

function noop() {}

describe("StripPanel", () => {
  it("renders the empty state when fields is empty", () => {
    render(
      <StripPanel
        fields={[]}
        keptKeys={new Set()}
        onToggle={noop}
        open={true}
        onOpenChange={noop}
      />,
    );
    expect(screen.getByText(/no credential fields detected/i)).toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("summary reads 'What gets stripped (N)' when no fields are kept", () => {
    render(
      <StripPanel
        fields={fields}
        keptKeys={new Set()}
        onToggle={noop}
        open={false}
        onOpenChange={noop}
      />,
    );
    const summary = screen.getByText(/what gets stripped/i);
    expect(summary).toHaveTextContent("What gets stripped (3)");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("summary reads 'What gets stripped (B of N)' when 1 ≤ K < N fields are kept", () => {
    render(
      <StripPanel
        fields={fields}
        keptKeys={new Set(["n1:org_id"])}
        onToggle={noop}
        open={false}
        onOpenChange={noop}
      />,
    );
    expect(screen.getByText(/what gets stripped \(2 of 3\)/i)).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(/1 credential will be saved/i);
  });

  it("summary reads only the warning when all N fields are kept (K = N)", () => {
    render(
      <StripPanel
        fields={fields}
        keptKeys={new Set(["n1:api_key", "n1:org_id", "n2:index_key"])}
        onToggle={noop}
        open={false}
        onOpenChange={noop}
      />,
    );
    expect(screen.queryByText(/what gets stripped/i)).not.toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(/3 credentials will be saved/i);
  });

  it("groups field rows by component_display_name, alphabetically", () => {
    render(
      <StripPanel
        fields={fields}
        keptKeys={new Set()}
        onToggle={noop}
        open={true}
        onOpenChange={noop}
      />,
    );
    const headers = screen.getAllByRole("heading", { level: 4 });
    expect(headers.map((h) => h.textContent)).toEqual(["OpenAI", "Pinecone"]);
  });

  it("renders one checked checkbox per field by default; key in keptKeys renders unchecked", () => {
    render(
      <StripPanel
        fields={fields}
        keptKeys={new Set(["n2:index_key"])}
        onToggle={noop}
        open={true}
        onOpenChange={noop}
      />,
    );
    const apiKey = screen.getByRole("checkbox", { name: /api key/i });
    const orgId = screen.getByRole("checkbox", { name: /org id/i });
    const indexKey = screen.getByRole("checkbox", { name: /index api key/i });
    expect(apiKey).toBeChecked();
    expect(orgId).toBeChecked();
    expect(indexKey).not.toBeChecked();
  });

  it("clicking a checkbox calls onToggle(node_id, field_name) exactly once", () => {
    const onToggle = jest.fn();
    render(
      <StripPanel
        fields={fields}
        keptKeys={new Set()}
        onToggle={onToggle}
        open={true}
        onOpenChange={noop}
      />,
    );
    fireEvent.click(screen.getByRole("checkbox", { name: /index api key/i }));
    expect(onToggle).toHaveBeenCalledTimes(1);
    expect(onToggle).toHaveBeenCalledWith("n2", "index_key");
  });

  it("open={false} keeps the body collapsed; open={true} reveals it", () => {
    const { rerender } = render(
      <StripPanel
        fields={fields}
        keptKeys={new Set()}
        onToggle={noop}
        open={false}
        onOpenChange={noop}
      />,
    );
    // Closed: no checkboxes in DOM (details hides children)
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    rerender(
      <StripPanel
        fields={fields}
        keptKeys={new Set()}
        onToggle={noop}
        open={true}
        onOpenChange={noop}
      />,
    );
    expect(screen.getAllByRole("checkbox")).toHaveLength(3);
  });

  it("toggling the <details> element fires onOpenChange with the new state", () => {
    const onOpenChange = jest.fn();
    const { container } = render(
      <StripPanel
        fields={fields}
        keptKeys={new Set()}
        onToggle={noop}
        open={false}
        onOpenChange={onOpenChange}
      />,
    );
    const details = container.querySelector("details") as HTMLDetailsElement;
    expect(details).not.toBeNull();
    // Simulate the browser toggling the details element open
    details.open = true;
    fireEvent.toggle(details);
    expect(onOpenChange).toHaveBeenCalledWith(true);
  });

  it("warning row is also visible inside the open body when ≥1 field is kept", () => {
    render(
      <StripPanel
        fields={fields}
        keptKeys={new Set(["n1:api_key"])}
        onToggle={noop}
        open={true}
        onOpenChange={noop}
      />,
    );
    // Both the summary and inside-body alert should be present.
    const alerts = screen.getAllByRole("alert");
    expect(alerts.length).toBe(2);
    alerts.forEach((a) =>
      expect(a).toHaveTextContent(/1 credential will be saved/i),
    );
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd /Users/brycedeneen/dev/langflow/src/frontend && npx jest src/modals/SaveAsTemplateModal/__tests__/StripPanel.test.tsx
```

Expected: FAIL with `Cannot find module '../StripPanel'`.

- [ ] **Step 3: Implement `StripPanel.tsx`**

Create `src/frontend/src/modals/SaveAsTemplateModal/StripPanel.tsx`:

```tsx
import { AlertTriangle } from "lucide-react";
import { useMemo } from "react";
import { cn } from "@/utils/utils";
import type { BlankableFieldInfo } from "./scanBlankableFields";

type Props = {
  fields: BlankableFieldInfo[];
  keptKeys: Set<string>;
  onToggle: (node_id: string, field_name: string) => void;
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

function fieldKey(f: { node_id: string; field_name: string }): string {
  return `${f.node_id}:${f.field_name}`;
}

function groupByComponent(
  fields: BlankableFieldInfo[],
): { component: string; items: BlankableFieldInfo[] }[] {
  const groups = new Map<string, BlankableFieldInfo[]>();
  for (const f of fields) {
    const list = groups.get(f.component_display_name) ?? [];
    list.push(f);
    groups.set(f.component_display_name, list);
  }
  return [...groups.entries()]
    .sort(([a], [b]) => a.toLowerCase().localeCompare(b.toLowerCase()))
    .map(([component, items]) => ({ component, items }));
}

function warningCopy(keptCount: number): string {
  return keptCount === 1
    ? "1 credential will be saved with this template"
    : `${keptCount} credentials will be saved with this template`;
}

export default function StripPanel({
  fields,
  keptKeys,
  onToggle,
  open,
  onOpenChange,
}: Props) {
  const groups = useMemo(() => groupByComponent(fields), [fields]);
  const total = fields.length;
  const keptCount = useMemo(
    () => fields.filter((f) => keptKeys.has(fieldKey(f))).length,
    [fields, keptKeys],
  );
  const blankedCount = total - keptCount;

  const showCount = !(total > 0 && keptCount === total); // hide count when K = N
  const showWarning = keptCount > 0;

  let countCopy = "";
  if (showCount) {
    countCopy =
      keptCount === 0
        ? `What gets stripped (${total})`
        : `What gets stripped (${blankedCount} of ${total})`;
  }

  return (
    <details
      open={open}
      onToggle={(e) =>
        onOpenChange((e.target as HTMLDetailsElement).open)
      }
    >
      <summary className="cursor-pointer text-sm font-medium">
        <span className="inline-flex items-center gap-2">
          {showCount && <span>{countCopy}</span>}
          {showWarning && (
            <span
              role="alert"
              className="inline-flex items-center gap-1 text-yellow-600"
            >
              <AlertTriangle className="h-4 w-4" />
              {warningCopy(keptCount)}
            </span>
          )}
        </span>
      </summary>
      <div className="mt-2 space-y-3">
        {showWarning && (
          <div
            role="alert"
            className="flex items-center gap-2 rounded-sm border border-yellow-300 bg-yellow-50 px-2 py-1 text-sm text-yellow-700"
          >
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span>{warningCopy(keptCount)}</span>
          </div>
        )}
        {fields.length === 0 ? (
          <p className="text-sm italic text-muted-foreground">
            No credential fields detected.
          </p>
        ) : (
          <div className="space-y-2">
            {groups.map(({ component, items }) => (
              <div key={component} className="space-y-1">
                <h4 className="text-sm font-medium">{component}</h4>
                <ul className="space-y-1 pl-4">
                  {items.map((f) => {
                    const k = fieldKey(f);
                    const checked = !keptKeys.has(k);
                    return (
                      <li key={k}>
                        <label
                          className={cn(
                            "flex cursor-pointer items-center gap-2 text-sm",
                            !checked && "text-yellow-700",
                          )}
                        >
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => onToggle(f.node_id, f.field_name)}
                          />
                          {f.field_display_name}
                        </label>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
          </div>
        )}
      </div>
    </details>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd /Users/brycedeneen/dev/langflow/src/frontend && npx jest src/modals/SaveAsTemplateModal/__tests__/StripPanel.test.tsx
```

Expected: 10 tests pass.

- [ ] **Step 5: Commit**

> **STOP — ask the user for explicit approval before running this commit.**

```bash
git add src/frontend/src/modals/SaveAsTemplateModal/StripPanel.tsx src/frontend/src/modals/SaveAsTemplateModal/__tests__/StripPanel.test.tsx
git commit -m "feat(save-as-template): add StripPanel with per-field blank/keep checkboxes"
```

---

## Task 2: Wire `StripPanel` into `SaveAsTemplateModal` + integration tests

**Files:**
- Modify: `src/frontend/src/modals/SaveAsTemplateModal/index.tsx`
- Modify: `src/frontend/src/modals/SaveAsTemplateModal/__tests__/SaveAsTemplateModal.test.tsx`

- [ ] **Step 1: Add the failing integration tests**

Append the following 3 tests to the existing `describe("SaveAsTemplateModal — submit wiring", …)` block in `src/frontend/src/modals/SaveAsTemplateModal/__tests__/SaveAsTemplateModal.test.tsx`. First, replace the `baseFlow()` fixture's single-credential body with a multi-credential, multi-component flow so the tests have something to toggle. Find the existing `baseFlow` definition (lines ~42-73) and replace it with:

```tsx
function baseFlow() {
  return {
    id: "flow-abc",
    description: "Pre-existing description",
    data: {
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
                bearer_token: {
                  _input_type: "SecretStrInput",
                  auto_promote: true,
                  value: "tok",
                  display_name: "Bearer Token",
                },
                url_input: {
                  _input_type: "MessageTextInput",
                  value: "https://example.com",
                },
              },
            },
          },
        },
        {
          id: "Node-2",
          data: {
            type: "OpenAI",
            node: {
              display_name: "OpenAI",
              template: {
                api_key: {
                  _input_type: "SecretStrInput",
                  auto_promote: true,
                  value: "sk-xxx",
                  display_name: "API Key",
                },
              },
            },
          },
        },
      ],
      edges: [],
    },
  };
}
```

Then update the existing `"submit calls mutation with correct payload shape"` test's blanked_fields assertion (around line 117-120). The fixture now produces 3 blankable fields, so replace:

```tsx
    // blanked_fields carries the credential field only.
    expect(payload.blanked_fields).toEqual([
      { node_id: "Node-1", field_name: "cert_pem" },
    ]);
```

with:

```tsx
    // All 3 detected credentials are blanked by default.
    expect(payload.blanked_fields).toEqual(
      expect.arrayContaining([
        { node_id: "Node-1", field_name: "cert_pem" },
        { node_id: "Node-1", field_name: "bearer_token" },
        { node_id: "Node-2", field_name: "api_key" },
      ]),
    );
    expect(payload.blanked_fields).toHaveLength(3);
```

Now append the 3 new tests at the end of the `describe` block, before its closing `});`:

```tsx
  it("unchecking a field excludes it from blanked_fields on submit", async () => {
    renderWithProviders(<SaveAsTemplateModal open onClose={() => {}} flow={baseFlow()} />);
    fireEvent.change(screen.getByLabelText(/^name/i), {
      target: { value: "T" },
    });
    // Open the strip panel
    const summary = screen.getByText(/what gets stripped/i);
    fireEvent.click(summary);
    // Uncheck "Bearer Token"
    fireEvent.click(screen.getByRole("checkbox", { name: /bearer token/i }));
    fireEvent.click(screen.getByRole("button", { name: /save as template/i }));

    expect(mutateMock).toHaveBeenCalledTimes(1);
    const [payload] = mutateMock.mock.calls[0];
    expect(payload.blanked_fields).toHaveLength(2);
    expect(payload.blanked_fields).toEqual(
      expect.arrayContaining([
        { node_id: "Node-1", field_name: "cert_pem" },
        { node_id: "Node-2", field_name: "api_key" },
      ]),
    );
    expect(payload.blanked_fields).not.toContainEqual({
      node_id: "Node-1",
      field_name: "bearer_token",
    });
  });

  it("re-checking a field re-includes it in blanked_fields on submit", () => {
    renderWithProviders(<SaveAsTemplateModal open onClose={() => {}} flow={baseFlow()} />);
    fireEvent.change(screen.getByLabelText(/^name/i), {
      target: { value: "T" },
    });
    fireEvent.click(screen.getByText(/what gets stripped/i));
    const bearer = screen.getByRole("checkbox", { name: /bearer token/i });
    fireEvent.click(bearer); // uncheck
    fireEvent.click(bearer); // re-check
    fireEvent.click(screen.getByRole("button", { name: /save as template/i }));

    const [payload] = mutateMock.mock.calls[0];
    expect(payload.blanked_fields).toHaveLength(3);
    expect(payload.blanked_fields).toContainEqual({
      node_id: "Node-1",
      field_name: "bearer_token",
    });
  });

  it("closing and re-opening the modal resets keptFieldKeys to empty", () => {
    const flow = baseFlow();
    const { rerender } = renderWithProviders(
      <SaveAsTemplateModal open={true} onClose={() => {}} flow={flow} />,
    );
    // Uncheck a field
    fireEvent.click(screen.getByText(/what gets stripped/i));
    fireEvent.click(screen.getByRole("checkbox", { name: /bearer token/i }));

    // Close
    rerender(<SaveAsTemplateModal open={false} onClose={() => {}} flow={flow} />);
    // Re-open
    rerender(<SaveAsTemplateModal open={true} onClose={() => {}} flow={flow} />);

    // Submit immediately — every field should be blanked again
    fireEvent.change(screen.getByLabelText(/^name/i), {
      target: { value: "T" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save as template/i }));
    const [payload] = mutateMock.mock.calls[0];
    expect(payload.blanked_fields).toHaveLength(3);
  });
```

- [ ] **Step 2: Run the integration tests to verify they fail**

```bash
cd /Users/brycedeneen/dev/langflow/src/frontend && npx jest src/modals/SaveAsTemplateModal/__tests__/SaveAsTemplateModal.test.tsx
```

Expected: the 3 new tests fail because `IconPickerField`'s parent modal hasn't been wired to the new `StripPanel` yet — checkboxes don't exist in DOM. The pre-existing `"submit calls mutation with correct payload shape"` test also needs the fixture rewrite to match (it now expects 3 blanked fields). The 4 unchanged tests (defaults, save-disabled, no-id no-op, 409) should still pass.

If any of the unchanged tests fail, STOP and report — that means the fixture change broke something other than what we intended.

- [ ] **Step 3: Modify `SaveAsTemplateModal/index.tsx`**

Edit `src/frontend/src/modals/SaveAsTemplateModal/index.tsx` with three coordinated changes.

**Change A — imports.** Replace the existing import block at the top of the file (lines 1-12) with:

```tsx
import { useCallback, useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { useCreateTemplate } from "@/controllers/API/queries/templates";
import BaseModal from "@/modals/baseModal";
import useAlertStore from "@/stores/alertStore";
import type { BlankedField } from "@/types/template";
import GradientPickerField from "./GradientPickerField";
import IconPickerField from "./IconPickerField";
import StripPanel from "./StripPanel";
import {
  scanBlankableFields,
  type BlankableFieldInfo,
} from "./scanBlankableFields";
```

**Change B — state, reset, toggle, filtered submit.** Find the block that declares `useState`/`useEffect` for the modal's local state plus `handleSubmit` (currently lines ~30-99). Replace it with:

```tsx
export default function SaveAsTemplateModal({ open, onClose, flow }: Props) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [icon, setIcon] = useState(DEFAULT_ICON);
  const [gradient, setGradient] = useState(DEFAULT_GRADIENT);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [nameError, setNameError] = useState<string | null>(null);
  const [keptFieldKeys, setKeptFieldKeys] = useState<Set<string>>(new Set());

  // Reset state whenever the modal opens.
  useEffect(() => {
    if (open) {
      setName("");
      setDescription(flow.description ?? "");
      setIcon(DEFAULT_ICON);
      setGradient(DEFAULT_GRADIENT);
      setDetailsOpen(false);
      setNameError(null);
      setKeptFieldKeys(new Set());
    }
  }, [open, flow.description]);

  const blankableFields: BlankableFieldInfo[] = useMemo(() => {
    const nodes = Array.isArray(flow.data?.nodes) ? flow.data!.nodes : [];
    return scanBlankableFields({ nodes });
  }, [flow.data?.nodes]);

  const canSubmit = name.trim().length > 0;

  const createTemplate = useCreateTemplate();
  const submitting = createTemplate.isPending;
  const setSuccessData = useAlertStore((s) => s.setSuccessData);
  const setErrorData = useAlertStore((s) => s.setErrorData);

  const toggleField = useCallback((node_id: string, field_name: string) => {
    setKeptFieldKeys((prev) => {
      const next = new Set(prev);
      const key = `${node_id}:${field_name}`;
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  function handleSubmit() {
    if (!canSubmit) return;
    if (!flow.id) return;

    const blanked_fields: BlankedField[] = blankableFields
      .filter((f) => !keptFieldKeys.has(`${f.node_id}:${f.field_name}`))
      .map((f) => ({
        node_id: f.node_id,
        field_name: f.field_name,
      }));

    createTemplate.mutate(
      {
        source_flow_id: flow.id,
        name: name.trim(),
        description: description.trim() || null,
        icon,
        gradient,
        blanked_fields,
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

**Change C — replace the inline `<details>` body with `<StripPanel>`.** Find the existing `<details>…</details>` block in the JSX (currently lines ~161-184) and replace it with:

```tsx
          <StripPanel
            fields={blankableFields}
            keptKeys={keptFieldKeys}
            onToggle={toggleField}
            open={detailsOpen}
            onOpenChange={setDetailsOpen}
          />
```

- [ ] **Step 4: Run the integration tests to verify they pass**

```bash
cd /Users/brycedeneen/dev/langflow/src/frontend && npx jest src/modals/SaveAsTemplateModal/__tests__/SaveAsTemplateModal.test.tsx
```

Expected: all tests pass (4 pre-existing + 1 modified payload assertion + 3 new = 8 total in this file should pass; full SaveAsTemplateModal directory should be 50+ tests across 8 suites with no failures).

- [ ] **Step 5: Run the full SaveAsTemplateModal directory**

```bash
cd /Users/brycedeneen/dev/langflow/src/frontend && npx jest src/modals/SaveAsTemplateModal
```

Expected: all suites pass — `lucideIconNames`, `useRecentIcons`, `filterIconNames`, `IconPickerField`, `GradientPickerField`, `scanBlankableFields`, `StripPanel`, `SaveAsTemplateModal`. No regressions.

- [ ] **Step 6: Type-check the project (changed files only)**

```bash
cd /Users/brycedeneen/dev/langflow/src/frontend && npx tsc --noEmit -p tsconfig.json 2>&1 | grep -E "(SaveAsTemplateModal|StripPanel)" | head -20
```

Expected: no new errors involving the changed files. (Pre-existing repo-wide errors involving `toBeInTheDocument` etc. in `__tests__/` are out of scope.)

- [ ] **Step 7: Manual smoke test**

DO NOT do this yourself — the controller will run the manual smoke test before approving the commit. Skip Step 7 in your work; report back after Step 6 passes.

- [ ] **Step 8: Commit**

> **STOP — ask the user for explicit approval before running this commit.**

```bash
git add src/frontend/src/modals/SaveAsTemplateModal/index.tsx src/frontend/src/modals/SaveAsTemplateModal/__tests__/SaveAsTemplateModal.test.tsx
git commit -m "feat(save-as-template): wire per-field blank toggles into submit"
```

---

## Self-Review Notes

- **Spec coverage:** G1–G5 all map to Task 1 (`StripPanel`) for rendering + Task 2 (`SaveAsTemplateModal/index.tsx` rewiring) for state + submit. The grouping/alphabetical/empty-state rules from §5 land in Task 1 Step 3. The K=N special case from §5.1 lands in `StripPanel`'s `showCount` derivation.
- **Risks coverage:** R1 (warning visual hierarchy) handled by the distinct `text-yellow-600` + `<AlertTriangle>` treatment in Task 1 Step 3. R2 (cancel-loses-selections) handled by Task 2 Change B's reset effect. R3 (stale keys) handled by Task 2 Change B's `.filter` step at submit time.
- **Type consistency:** `BlankableFieldInfo` (from `scanBlankableFields`), `BlankedField` (from `@/types/template`), `Set<string>` keyed `${node_id}:${field_name}` — used consistently across both tasks.
- **Test scope:** Task 1 covers `StripPanel` in isolation (10 tests). Task 2 covers the integration through the modal (3 new + 1 modified). Together they verify rendering, toggling, submit-payload filtering, and reset-on-reopen.
