# FU-2 — Name-collision Overwrite Flow — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Project commit policy:** This repo follows a strict "no git commits without explicit user approval" rule. Every Step labeled **Commit** in this plan REQUIRES the executing agent to pause and ask the user before running `git commit`. Do NOT auto-commit even if the plan says "commit".

**Goal:** When `POST /api/v1/templates` returns 409, open a confirm dialog showing the colliding template's name, description, and a relative last-updated timestamp; on Overwrite, issue `PUT /api/v1/templates/{id}` with the same payload; on Cancel, fall back to today's inline name-error behavior.

**Architecture:** A new stateless `ConfirmOverwriteDialog` (using the repo's existing Radix `Dialog` primitives, mirroring `DeleteConfirmationModal`'s pattern) renders on top of `SaveAsTemplateModal`. The parent modal eagerly fetches the templates list on open via `useListTemplates`, handles the 409 branch by looking up the matching row client-side, and fires `useUpdateTemplate` on confirm. A small local `formatRelativeTime` helper produces the relative date string; the repo ships no `date-fns`/`dayjs` so this is new code.

**Tech Stack:** React + TypeScript + Jest + React Testing Library, `@radix-ui/react-dialog` (existing), react-query (existing).

**Spec:** [`docs/superpowers/specs/2026-04-21-fu-2-name-collision-overwrite-flow-design.md`](../specs/2026-04-21-fu-2-name-collision-overwrite-flow-design.md)

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `src/frontend/src/modals/SaveAsTemplateModal/formatRelativeTime.ts` | create | Pure helper: ISO timestamp → "just now" / "N minutes ago" / "N hours ago" / "N days ago" / "on {date}" |
| `src/frontend/src/modals/SaveAsTemplateModal/ConfirmOverwriteDialog.tsx` | create | Stateless Radix-dialog confirm; shows name/description/relative-date; `[Cancel] [Overwrite]` footer |
| `src/frontend/src/modals/SaveAsTemplateModal/index.tsx` | modify | List-fetch on open, 409→confirm branch, Overwrite PUT, reset |
| `src/frontend/src/modals/SaveAsTemplateModal/__tests__/formatRelativeTime.test.ts` | create | Pure-function unit tests for the time helper |
| `src/frontend/src/modals/SaveAsTemplateModal/__tests__/ConfirmOverwriteDialog.test.tsx` | create | Component tests for the dialog |
| `src/frontend/src/modals/SaveAsTemplateModal/__tests__/SaveAsTemplateModal.test.tsx` | modify | Expand mocks for `useListTemplates` + `useUpdateTemplate`; add 4 integration tests |

---

## Task 1: `formatRelativeTime` helper + unit tests

**Files:**
- Create: `src/frontend/src/modals/SaveAsTemplateModal/formatRelativeTime.ts`
- Test: `src/frontend/src/modals/SaveAsTemplateModal/__tests__/formatRelativeTime.test.ts`

- [x] **Step 1: Write the failing test**

Create `src/frontend/src/modals/SaveAsTemplateModal/__tests__/formatRelativeTime.test.ts`:

```typescript
import { describe, expect, it } from "@jest/globals";
import { formatRelativeTime } from "../formatRelativeTime";

const NOW = new Date("2026-04-21T12:00:00Z");

function iso(offsetSeconds: number): string {
  return new Date(NOW.getTime() - offsetSeconds * 1000).toISOString();
}

describe("formatRelativeTime", () => {
  it("returns 'just now' for < 60 seconds", () => {
    expect(formatRelativeTime(iso(0), NOW)).toBe("just now");
    expect(formatRelativeTime(iso(59), NOW)).toBe("just now");
  });

  it("returns minutes for 60s to 59m59s, singular at 1 minute", () => {
    expect(formatRelativeTime(iso(60), NOW)).toBe("1 minute ago");
    expect(formatRelativeTime(iso(119), NOW)).toBe("1 minute ago");
    expect(formatRelativeTime(iso(120), NOW)).toBe("2 minutes ago");
    expect(formatRelativeTime(iso(3599), NOW)).toBe("59 minutes ago");
  });

  it("returns hours for 1h to 23h59m, singular at 1 hour", () => {
    expect(formatRelativeTime(iso(3600), NOW)).toBe("1 hour ago");
    expect(formatRelativeTime(iso(7199), NOW)).toBe("1 hour ago");
    expect(formatRelativeTime(iso(7200), NOW)).toBe("2 hours ago");
    expect(formatRelativeTime(iso(86399), NOW)).toBe("23 hours ago");
  });

  it("returns days for 1d to 29d, singular at 1 day", () => {
    expect(formatRelativeTime(iso(86400), NOW)).toBe("1 day ago");
    expect(formatRelativeTime(iso(86400 * 2), NOW)).toBe("2 days ago");
    expect(formatRelativeTime(iso(86400 * 29), NOW)).toBe("29 days ago");
  });

  it("returns 'on {date}' for >= 30 days", () => {
    const past = iso(86400 * 30);
    const result = formatRelativeTime(past, NOW);
    expect(result).toMatch(/^on /);
    // Verify the date string is the localized toLocaleDateString output
    expect(result).toBe(
      `on ${new Date(past).toLocaleDateString()}`,
    );
  });

  it("handles a future timestamp by treating it as 'just now'", () => {
    // Defensive: clock skew shouldn't produce negative-minutes nonsense.
    expect(formatRelativeTime(iso(-30), NOW)).toBe("just now");
  });
});
```

- [x] **Step 2: Run the test to verify it fails**

```bash
cd /Users/brycedeneen/dev/langflow/src/frontend && npx jest src/modals/SaveAsTemplateModal/__tests__/formatRelativeTime.test.ts
```

Expected: FAIL with `Cannot find module '../formatRelativeTime'`.

- [x] **Step 3: Implement `formatRelativeTime.ts`**

Create `src/frontend/src/modals/SaveAsTemplateModal/formatRelativeTime.ts`:

```typescript
/**
 * Format an ISO timestamp relative to a reference point (default: now).
 * Thresholds:
 *   < 60s          -> "just now"
 *   < 60m          -> "N minutes ago" (singular at 1)
 *   < 24h          -> "N hours ago"   (singular at 1)
 *   < 30d          -> "N days ago"    (singular at 1)
 *   >= 30d         -> "on {locale date}"
 * A future timestamp (ref < iso) is treated as "just now" to avoid negative-time
 * artifacts from clock skew.
 */
export function formatRelativeTime(
  iso: string,
  now: Date = new Date(),
): string {
  const then = new Date(iso);
  const elapsedSec = Math.floor((now.getTime() - then.getTime()) / 1000);

  if (elapsedSec < 60) return "just now";

  const minutes = Math.floor(elapsedSec / 60);
  if (minutes < 60) return minutes === 1 ? "1 minute ago" : `${minutes} minutes ago`;

  const hours = Math.floor(elapsedSec / 3600);
  if (hours < 24) return hours === 1 ? "1 hour ago" : `${hours} hours ago`;

  const days = Math.floor(elapsedSec / 86400);
  if (days < 30) return days === 1 ? "1 day ago" : `${days} days ago`;

  return `on ${then.toLocaleDateString()}`;
}
```

- [x] **Step 4: Run the test to verify it passes**

```bash
cd /Users/brycedeneen/dev/langflow/src/frontend && npx jest src/modals/SaveAsTemplateModal/__tests__/formatRelativeTime.test.ts
```

Expected: 6 tests pass.

- [x] **Step 5: Commit**

> **STOP — ask the user for explicit approval before running this commit.**

```bash
git add src/frontend/src/modals/SaveAsTemplateModal/formatRelativeTime.ts src/frontend/src/modals/SaveAsTemplateModal/__tests__/formatRelativeTime.test.ts
git commit -m "feat(save-as-template): add formatRelativeTime helper"
```

---

## Task 2: `ConfirmOverwriteDialog` component + unit tests

**Files:**
- Create: `src/frontend/src/modals/SaveAsTemplateModal/ConfirmOverwriteDialog.tsx`
- Test: `src/frontend/src/modals/SaveAsTemplateModal/__tests__/ConfirmOverwriteDialog.test.tsx`

- [x] **Step 1: Write the failing test**

Create `src/frontend/src/modals/SaveAsTemplateModal/__tests__/ConfirmOverwriteDialog.test.tsx`:

```tsx
import { describe, expect, it, jest } from "@jest/globals";
import { render, screen, fireEvent } from "@testing-library/react";
import ConfirmOverwriteDialog from "../ConfirmOverwriteDialog";

// Fix "now" so the relative-date assertion is stable.
const NOW = new Date("2026-04-21T12:00:00Z").toISOString();

function setup(overrides: Partial<Parameters<typeof ConfirmOverwriteDialog>[0]> = {}) {
  const onCancel = jest.fn();
  const onConfirm = jest.fn();
  const props = {
    open: true,
    templateName: "Customer Support",
    description: "Triage support tickets",
    updatedAt: NOW,
    submitting: false,
    onCancel,
    onConfirm,
    ...overrides,
  };
  render(<ConfirmOverwriteDialog {...props} />);
  return { onCancel, onConfirm };
}

describe("ConfirmOverwriteDialog", () => {
  it("renders the template name in the header", () => {
    setup();
    expect(screen.getByText(/Customer Support/)).toBeInTheDocument();
  });

  it("renders the description body text", () => {
    setup();
    expect(screen.getByText(/Triage support tickets/)).toBeInTheDocument();
  });

  it("renders italic '(no description)' when description is null", () => {
    setup({ description: null });
    expect(screen.getByText(/\(no description\)/i)).toBeInTheDocument();
  });

  it("renders italic '(no description)' when description is empty string", () => {
    setup({ description: "" });
    expect(screen.getByText(/\(no description\)/i)).toBeInTheDocument();
  });

  it("renders a relative-date line", () => {
    setup();
    // NOW is fixed, so "just now" is the expected relative string.
    expect(screen.getByText(/just now/i)).toBeInTheDocument();
  });

  it("clicking Cancel fires onCancel", () => {
    const { onCancel } = setup();
    fireEvent.click(screen.getByRole("button", { name: /^cancel$/i }));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("clicking Overwrite fires onConfirm", () => {
    const { onConfirm } = setup();
    fireEvent.click(screen.getByRole("button", { name: /^overwrite$/i }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("Overwrite disabled and Cancel enabled while submitting", () => {
    setup({ submitting: true });
    expect(screen.getByRole("button", { name: /^overwrite$/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /^cancel$/i })).toBeEnabled();
  });

  it("does not render dialog DOM when open=false", () => {
    setup({ open: false });
    expect(screen.queryByRole("button", { name: /^overwrite$/i })).not.toBeInTheDocument();
  });
});
```

- [x] **Step 2: Run the test to verify it fails**

```bash
cd /Users/brycedeneen/dev/langflow/src/frontend && npx jest src/modals/SaveAsTemplateModal/__tests__/ConfirmOverwriteDialog.test.tsx
```

Expected: FAIL with `Cannot find module '../ConfirmOverwriteDialog'`.

- [x] **Step 3: Implement `ConfirmOverwriteDialog.tsx`**

Create `src/frontend/src/modals/SaveAsTemplateModal/ConfirmOverwriteDialog.tsx`:

```tsx
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { formatRelativeTime } from "./formatRelativeTime";

type Props = {
  open: boolean;
  templateName: string;
  description: string | null;
  updatedAt: string; // ISO
  submitting: boolean;
  onCancel: () => void;
  onConfirm: () => void;
};

export default function ConfirmOverwriteDialog({
  open,
  templateName,
  description,
  updatedAt,
  submitting,
  onCancel,
  onConfirm,
}: Props) {
  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) onCancel();
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            <div className="flex items-center gap-2">
              <AlertTriangle
                className="h-5 w-5 text-yellow-600"
                strokeWidth={2}
              />
              <span>Template "{templateName}" already exists</span>
            </div>
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-2 text-sm">
          {description ? (
            <p className="line-clamp-3 text-muted-foreground">{description}</p>
          ) : (
            <p className="italic text-muted-foreground">(no description)</p>
          )}
          <p className="text-xs text-muted-foreground">
            Last updated {formatRelativeTime(updatedAt)}
          </p>
        </div>

        <DialogFooter>
          <Button
            autoFocus
            variant="outline"
            type="button"
            onClick={onCancel}
          >
            Cancel
          </Button>
          <Button
            variant="destructive"
            type="button"
            disabled={submitting}
            onClick={onConfirm}
          >
            {submitting ? "Overwriting…" : "Overwrite"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

- [x] **Step 4: Run the test to verify it passes**

```bash
cd /Users/brycedeneen/dev/langflow/src/frontend && npx jest src/modals/SaveAsTemplateModal/__tests__/ConfirmOverwriteDialog.test.tsx
```

Expected: 9 tests pass.

- [x] **Step 5: Commit**

> **STOP — ask the user for explicit approval before running this commit.**

```bash
git add src/frontend/src/modals/SaveAsTemplateModal/ConfirmOverwriteDialog.tsx src/frontend/src/modals/SaveAsTemplateModal/__tests__/ConfirmOverwriteDialog.test.tsx
git commit -m "feat(save-as-template): add ConfirmOverwriteDialog"
```

---

## Task 3: Wire the 409 → confirm → PUT flow into `SaveAsTemplateModal` + integration tests

**Files:**
- Modify: `src/frontend/src/modals/SaveAsTemplateModal/index.tsx`
- Modify: `src/frontend/src/modals/SaveAsTemplateModal/__tests__/SaveAsTemplateModal.test.tsx`

- [x] **Step 1: Expand test mocks and add the failing integration tests**

In `src/frontend/src/modals/SaveAsTemplateModal/__tests__/SaveAsTemplateModal.test.tsx`, replace the existing `jest.mock("@/controllers/API/queries/templates", …)` block (currently mocks only `useCreateTemplate`) with:

```ts
const mutateMock = jest.fn();
const listMock = jest.fn();
const updateMock = jest.fn();
jest.mock(
  "@/controllers/API/queries/templates",
  () => ({
    useCreateTemplate: () => ({
      mutate: mutateMock,
      isPending: false,
    }),
    useListTemplates: () => ({ data: listMock() }),
    useUpdateTemplate: () => ({
      mutate: updateMock,
      isPending: false,
    }),
  }),
);
```

Note: `mutateMock` is declared only once at the top of the mocks block (the existing file already declares it — keep that declaration, just add the two new mocks beneath it).

Update the existing `beforeEach` to reset the new mocks too:

```ts
beforeEach(() => {
  mutateMock.mockReset();
  successMock.mockReset();
  errorMock.mockReset();
  listMock.mockReset();
  updateMock.mockReset();
  listMock.mockReturnValue([]); // default: no templates
});
```

Now append the following 4 tests at the end of the existing `describe("SaveAsTemplateModal — submit wiring", …)` block, before its closing `});`:

```tsx
  it("409 + matching row in list opens the confirm dialog", async () => {
    listMock.mockReturnValue([
      {
        id: "T-1",
        name: "Duplicate",
        description: "Pre-existing description of the clashing template",
        icon: null,
        gradient: null,
        created_at: "2026-04-01T00:00:00Z",
        updated_at: "2026-04-01T00:00:00Z",
      },
    ]);
    mutateMock.mockImplementation((_payload: any, opts: any) => {
      opts.onError?.({ response: { status: 409 } });
    });
    renderWithProviders(<SaveAsTemplateModal open onClose={() => {}} flow={baseFlow()} />);
    fireEvent.change(screen.getByLabelText(/^name/i), {
      target: { value: "Duplicate" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save as template/i }));

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /^overwrite$/i }),
      ).toBeInTheDocument();
    });
    expect(
      screen.getByText(/Pre-existing description of the clashing template/),
    ).toBeInTheDocument();
  });

  it("409 with empty list falls back to inline name error and does not open the dialog", async () => {
    listMock.mockReturnValue(undefined);
    mutateMock.mockImplementation((_payload: any, opts: any) => {
      opts.onError?.({ response: { status: 409 } });
    });
    renderWithProviders(<SaveAsTemplateModal open onClose={() => {}} flow={baseFlow()} />);
    fireEvent.change(screen.getByLabelText(/^name/i), {
      target: { value: "Duplicate" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save as template/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/already exists/i);
    });
    expect(
      screen.queryByRole("button", { name: /^overwrite$/i }),
    ).not.toBeInTheDocument();
  });

  it("clicking Overwrite fires the update mutation with the correct payload", async () => {
    listMock.mockReturnValue([
      {
        id: "T-1",
        name: "Duplicate",
        description: "x",
        icon: null,
        gradient: null,
        created_at: "2026-04-01T00:00:00Z",
        updated_at: "2026-04-01T00:00:00Z",
      },
    ]);
    mutateMock.mockImplementation((_payload: any, opts: any) => {
      opts.onError?.({ response: { status: 409 } });
    });
    renderWithProviders(<SaveAsTemplateModal open onClose={() => {}} flow={baseFlow()} />);
    fireEvent.change(screen.getByLabelText(/^name/i), {
      target: { value: "Duplicate" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save as template/i }));
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /^overwrite$/i }),
      ).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /^overwrite$/i }));

    expect(updateMock).toHaveBeenCalledTimes(1);
    const [vars] = updateMock.mock.calls[0];
    expect(vars.templateId).toBe("T-1");
    expect(vars.body).toMatchObject({
      source_flow_id: "flow-abc",
      name: "Duplicate",
      icon: "FileText",
      gradient: "0",
    });
    expect(vars.body.blanked_fields).toEqual(
      expect.arrayContaining([
        { node_id: "Node-1", field_name: "cert_pem" },
        { node_id: "Node-1", field_name: "bearer_token" },
        { node_id: "Node-2", field_name: "api_key" },
      ]),
    );
  });

  it("clicking Cancel closes the dialog, shows inline error, and re-enables Save", async () => {
    listMock.mockReturnValue([
      {
        id: "T-1",
        name: "Duplicate",
        description: "x",
        icon: null,
        gradient: null,
        created_at: "2026-04-01T00:00:00Z",
        updated_at: "2026-04-01T00:00:00Z",
      },
    ]);
    mutateMock.mockImplementation((_payload: any, opts: any) => {
      opts.onError?.({ response: { status: 409 } });
    });
    renderWithProviders(<SaveAsTemplateModal open onClose={() => {}} flow={baseFlow()} />);
    fireEvent.change(screen.getByLabelText(/^name/i), {
      target: { value: "Duplicate" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save as template/i }));
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /^overwrite$/i }),
      ).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /^cancel$/i }));

    await waitFor(() => {
      expect(
        screen.queryByRole("button", { name: /^overwrite$/i }),
      ).not.toBeInTheDocument();
    });
    expect(screen.getByRole("alert")).toHaveTextContent(/already exists/i);
    expect(screen.getByRole("button", { name: /save as template/i })).toBeEnabled();
    expect(updateMock).not.toHaveBeenCalled();
  });
```

- [x] **Step 2: Run the tests to verify they fail**

```bash
cd /Users/brycedeneen/dev/langflow/src/frontend && npx jest src/modals/SaveAsTemplateModal/__tests__/SaveAsTemplateModal.test.tsx
```

Expected: the 4 new tests fail (modal has no list-fetch wiring, no confirm dialog, no update handler). Pre-existing tests still pass.

If any pre-existing test fails, STOP and report — the mock-block expansion may have broken something unintended.

- [x] **Step 3: Modify `SaveAsTemplateModal/index.tsx`**

Edit `src/frontend/src/modals/SaveAsTemplateModal/index.tsx` with four coordinated changes.

**Change A — imports.** Replace the existing imports at the top of the file with:

```tsx
import { useCallback, useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  useCreateTemplate,
  useListTemplates,
  useUpdateTemplate,
} from "@/controllers/API/queries/templates";
import BaseModal from "@/modals/baseModal";
import useAlertStore from "@/stores/alertStore";
import type { BlankedField, TemplateRead } from "@/types/template";
import ConfirmOverwriteDialog from "./ConfirmOverwriteDialog";
import GradientPickerField from "./GradientPickerField";
import IconPickerField from "./IconPickerField";
import StripPanel from "./StripPanel";
import {
  scanBlankableFields,
  type BlankableFieldInfo,
} from "./scanBlankableFields";
```

**Change B — state slots + payload builder.** Find the existing `useState`/`useEffect` block at the top of the component function body (currently lines ~30-50). Replace the state declarations with:

```tsx
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [icon, setIcon] = useState(DEFAULT_ICON);
  const [gradient, setGradient] = useState(DEFAULT_GRADIENT);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [nameError, setNameError] = useState<string | null>(null);
  const [keptFieldKeys, setKeptFieldKeys] = useState<Set<string>>(new Set());
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [conflict, setConflict] = useState<TemplateRead | null>(null);
```

Extend the reset effect's body to clear the new slots:

```tsx
  useEffect(() => {
    if (open) {
      setName("");
      setDescription(flow.description ?? "");
      setIcon(DEFAULT_ICON);
      setGradient(DEFAULT_GRADIENT);
      setDetailsOpen(false);
      setNameError(null);
      setKeptFieldKeys(new Set());
      setConfirmOpen(false);
      setConflict(null);
    }
  }, [open, flow.description]);
```

**Change C — hooks and payload helper.** After the existing `blankableFields` memo + `toggleField` callback, add:

```tsx
  const { data: templatesList } = useListTemplates();
  const updateTemplate = useUpdateTemplate();

  const buildPayload = useCallback(() => {
    const blanked_fields: BlankedField[] = blankableFields
      .filter((f) => !keptFieldKeys.has(`${f.node_id}:${f.field_name}`))
      .map((f) => ({
        node_id: f.node_id,
        field_name: f.field_name,
      }));
    return {
      source_flow_id: flow.id!,
      name: name.trim(),
      description: description.trim() || null,
      icon,
      gradient,
      blanked_fields,
    };
  }, [
    blankableFields,
    keptFieldKeys,
    flow.id,
    name,
    description,
    icon,
    gradient,
  ]);
```

Update `submitting` to cover both mutations:

```tsx
  const submitting = createTemplate.isPending || updateTemplate.isPending;
```

**Change D — replace `handleSubmit`'s error branch + add overwrite handlers.** Replace the existing `handleSubmit` function (from `function handleSubmit()` through its closing `}`) with:

```tsx
  function handleSubmit() {
    if (!canSubmit) return;
    if (!flow.id) return;

    createTemplate.mutate(buildPayload(), {
      onSuccess: () => {
        setSuccessData({ title: `Template "${name.trim()}" saved` });
        onClose();
      },
      onError: (err: any) => {
        if (err?.response?.status !== 409) {
          setErrorData({
            title: "Failed to save template",
            list: [err?.response?.data?.detail ?? "Please try again."],
          });
          return;
        }
        const match = templatesList?.find(
          (t) => t.name.trim() === name.trim(),
        );
        if (match) {
          setConflict(match);
          setConfirmOpen(true);
          return;
        }
        // Fallback: list not ready yet.
        setNameError(
          "A template with that name already exists — pick a different one.",
        );
      },
    });
  }

  function handleOverwriteConfirm() {
    if (!conflict) return;
    updateTemplate.mutate(
      { templateId: conflict.id, body: buildPayload() },
      {
        onSuccess: () => {
          setSuccessData({ title: `Template "${name.trim()}" updated` });
          setConfirmOpen(false);
          setConflict(null);
          onClose();
        },
        onError: (err: any) => {
          setConfirmOpen(false);
          setConflict(null);
          setErrorData({
            title: "Failed to overwrite template",
            list: [err?.response?.data?.detail ?? "Please try again."],
          });
        },
      },
    );
  }

  function handleOverwriteCancel() {
    setConfirmOpen(false);
    setConflict(null);
    setNameError(
      "A template with that name already exists — pick a different one.",
    );
  }
```

**Change E — render the confirm dialog.** At the end of the JSX return, **just before the closing `</BaseModal>`**, add:

```tsx
      <ConfirmOverwriteDialog
        open={confirmOpen}
        templateName={conflict?.name ?? ""}
        description={conflict?.description ?? null}
        updatedAt={conflict?.updated_at ?? new Date().toISOString()}
        submitting={updateTemplate.isPending}
        onCancel={handleOverwriteCancel}
        onConfirm={handleOverwriteConfirm}
      />
```

The fallback `conflict?.name ?? ""` / `updated_at ?? new Date().toISOString()` only renders when `confirmOpen=false`, so the fallback values are never user-visible — they exist to satisfy the always-mounted Radix Dialog's prop requirements.

- [x] **Step 4: Run the integration tests to verify they pass**

```bash
cd /Users/brycedeneen/dev/langflow/src/frontend && npx jest src/modals/SaveAsTemplateModal/__tests__/SaveAsTemplateModal.test.tsx
```

Expected: all tests pass (5 pre-existing + 4 new = 9 in this file).

- [x] **Step 5: Run the full SaveAsTemplateModal directory**

```bash
cd /Users/brycedeneen/dev/langflow/src/frontend && npx jest src/modals/SaveAsTemplateModal
```

Expected: all suites pass with no regressions. Full count should be roughly 76 (previous 61 + 6 formatRelativeTime + 9 ConfirmOverwriteDialog + 4 new SaveAsTemplateModal = 80; minor variance if jest counts differently — the number to watch is "no failures").

- [x] **Step 6: Type-check the changed files**

```bash
cd /Users/brycedeneen/dev/langflow/src/frontend && npx tsc --noEmit -p tsconfig.json 2>&1 | grep -E "(SaveAsTemplateModal/index|ConfirmOverwriteDialog|formatRelativeTime)" | head -20
```

Expected: no new errors in the changed files. Pre-existing `toBeInTheDocument`/`toBeChecked` errors in `__tests__/` are out of scope.

- [x] **Step 7: Manual smoke test**

DO NOT do this yourself — the controller will run the manual smoke test before approving the commit. Skip.

- [x] **Step 8: Commit**

> **STOP — ask the user for explicit approval before running this commit.**

```bash
git add src/frontend/src/modals/SaveAsTemplateModal/index.tsx src/frontend/src/modals/SaveAsTemplateModal/__tests__/SaveAsTemplateModal.test.tsx
git commit -m "feat(save-as-template): wire 409 collision into overwrite confirm flow"
```

---

## Self-Review Notes

- **Spec coverage:** G1 (open dialog on 409) → Task 3 Change D. G2 (name + description + relative date) → Task 2 component + Task 1 helper. G3 (PUT with same payload) → Task 3 Change D's `handleOverwriteConfirm` via `buildPayload()`. G4 (fallback to inline error when list not ready + on cancel) → Task 3's error branch and `handleOverwriteCancel`. G5 (distinct updated toast) → `handleOverwriteConfirm`'s `setSuccessData({title: "...updated"})`.
- **Risks coverage:** R1 double-fire → Save button disabled via `submitting = createTemplate.isPending || updateTemplate.isPending`. R2 stale list race → lookup fall-through to inline error. R3 help copy drift → the collision copy lives in two places (fallback inline error and the dialog body text), both written in Task 3.
- **Type consistency:** `TemplateRead` (from `@/types/template`) used for `conflict`. `BlankedField` unchanged. `useListTemplates`, `useUpdateTemplate`, `useCreateTemplate` exports all present in `@/controllers/API/queries/templates/index.ts` (verified during planning).
- **Edge cases from spec §8:** Rename between 409 and Overwrite — handled because `buildPayload()` always reads current `name` state at call time. Whitespace — handled by `.trim()` on both sides of the `.find()`. Soft-delete race — caught by 404 in the update's error branch (generic toast). Stale updated_at — cosmetic; fixed if the PUT hits a real mismatch.
