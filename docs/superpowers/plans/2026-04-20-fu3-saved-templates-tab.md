# FU-3: Saved Templates Tab — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **User memory rule:** Never run `git commit` without explicit user approval. "Commit" steps in this plan mean: stage the intended files and present the commit message to the user; wait for "go ahead" before running `git commit`.

**Goal:** Wire `GET /api/v1/templates` into the New Flow modal so saved templates appear in a dedicated "Saved Templates" tab and can be used to create flows.

**Architecture:** Add a new nav item to the existing `TemplatesModal` that renders a `SavedTemplatesContent` component. Templates are adapted into the shape `TemplateCardComponent` already expects (it reads `icon` + `gradient`), so no new card component is needed. On selection (id prefix `tpl:<uuid>`), `handleCreateFromSelection` fetches `TemplateReadDetail` imperatively and hands a `FlowType`-shaped object to `useAddFlow`.

**Tech Stack:** React + TypeScript, Jest + React Testing Library, `@tanstack/react-query` (via `UseRequestProcessor` wrapper), existing `api` axios client, existing `useListTemplates()` hook.

**Spec reference:** `docs/superpowers/specs/2026-04-20-fu3-saved-templates-tab-design.md`

---

## File Structure

### New files

- `src/frontend/src/modals/templatesModal/components/SavedTemplatesContent/index.tsx`
  Responsibility: fetch templates via `useListTemplates`; manage loading / empty / error UI; adapt each `TemplateRead` into a minimal `FlowType`-shaped object (so the existing `TemplateCardComponent` renders it); surface selection to the parent modal.

- `src/frontend/src/modals/templatesModal/components/SavedTemplatesContent/__tests__/SavedTemplatesContent.test.tsx`
  Unit coverage for the component's four states (loading / empty / error / populated) and adapter correctness.

- `src/frontend/src/modals/templatesModal/__tests__/TemplatesModal.saved-tab.test.tsx`
  Integration coverage that the modal shows the new nav item, switches tab on click, and that selecting a card then clicking "Start building" drives `addFlow` with the data from `/templates/{id}`.

### Modified files

- `src/frontend/src/modals/templatesModal/index.tsx`
  - Append `{ title: "Saved Templates", icon: "Bookmark", id: "saved" }` to the first nav category.
  - Render `<SavedTemplatesContent />` when `currentTab === "saved"`.
  - Extend `handleCreateFromSelection` to resolve `tpl:<uuid>` selections by fetching detail and building a flow payload.

### Non-goals (explicit)

- No new card component — reuse `TemplateCardComponent`.
- No new type file — `TemplateRead` / `TemplateReadDetail` already exist in `@/types/template`.
- No changes to backend, query hooks, or existing starter-flow rendering.

---

## Task 1: `SavedTemplatesContent` component (TDD)

**Files:**
- Create: `src/frontend/src/modals/templatesModal/components/SavedTemplatesContent/index.tsx`
- Test: `src/frontend/src/modals/templatesModal/components/SavedTemplatesContent/__tests__/SavedTemplatesContent.test.tsx`

### Component contract

```ts
type Props = {
  selectedTemplate: string | null;
  onSelectTemplate: (id: string | null) => void;
  loading: boolean; // true while the parent modal is creating a flow
};
```

Behavior:
- Calls `useListTemplates()`. The hook returns `{ data, isPending, isError, refetch }` (react-query v5 shape — per `project_frontend_test_stack` memory, this project uses `isPending`, NOT `isLoading`).
- Converts each `TemplateRead` into the minimum shape `TemplateCardComponent` needs: `{ id: "tpl:" + t.id, name, description, icon, gradient }` (cast `as unknown as FlowType` — we only touch fields the card actually reads).
- Delegates to `TemplateCategoryComponent` for rendering the card grid to stay visually consistent.
- Handles three non-populated states:
  - `isPending` → 3 skeleton cards, `data-testid="saved-templates-loading"`.
  - `isError` → centered message + "Retry" button that calls `refetch()`, `data-testid="saved-templates-error"`.
  - `data.length === 0` → centered empty-state message, `data-testid="saved-templates-empty"`.

### Steps

- [x] **Step 1: Write the failing test file**

Create `src/frontend/src/modals/templatesModal/components/SavedTemplatesContent/__tests__/SavedTemplatesContent.test.tsx`:

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import SavedTemplatesContent from "../index";

// Mock the list-templates hook. Each test overrides the return value.
const mockUseListTemplates = jest.fn();
jest.mock("@/controllers/API/queries/templates/use-list-templates", () => ({
  __esModule: true,
  useListTemplates: () => mockUseListTemplates(),
  TEMPLATES_QUERY_KEY: ["templates"],
}));

// genericIconComponent renders <svg>s that pull from lucide dynamic imports;
// stub it out so tests are deterministic.
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: (props: { name?: string }) => <span data-testid={`icon-${props.name}`} />,
  ForwardedIconComponent: (props: { name?: string }) => (
    <span data-testid={`icon-${props.name}`} />
  ),
}));

describe("SavedTemplatesContent", () => {
  beforeEach(() => {
    mockUseListTemplates.mockReset();
  });

  it("shows a loading skeleton while fetching", () => {
    mockUseListTemplates.mockReturnValue({
      data: undefined,
      isPending: true,
      isError: false,
      refetch: jest.fn(),
    });
    render(
      <SavedTemplatesContent
        selectedTemplate={null}
        onSelectTemplate={jest.fn()}
        loading={false}
      />,
    );
    expect(screen.getByTestId("saved-templates-loading")).toBeInTheDocument();
  });

  it("renders an empty state when the list is empty", () => {
    mockUseListTemplates.mockReturnValue({
      data: [],
      isPending: false,
      isError: false,
      refetch: jest.fn(),
    });
    render(
      <SavedTemplatesContent
        selectedTemplate={null}
        onSelectTemplate={jest.fn()}
        loading={false}
      />,
    );
    expect(screen.getByTestId("saved-templates-empty")).toBeInTheDocument();
    expect(screen.getByText(/no saved templates yet/i)).toBeInTheDocument();
  });

  it("renders an error state with a retry button", () => {
    const refetch = jest.fn();
    mockUseListTemplates.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      refetch,
    });
    render(
      <SavedTemplatesContent
        selectedTemplate={null}
        onSelectTemplate={jest.fn()}
        loading={false}
      />,
    );
    expect(screen.getByTestId("saved-templates-error")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it("renders a card per template and maps ids with the tpl: prefix", () => {
    mockUseListTemplates.mockReturnValue({
      data: [
        {
          id: "11111111-1111-1111-1111-111111111111",
          name: "Support Agent",
          description: "Frontline triage",
          icon: "Bot",
          gradient: "2",
          created_at: "2026-04-20T00:00:00Z",
          updated_at: "2026-04-20T00:00:00Z",
        },
        {
          id: "22222222-2222-2222-2222-222222222222",
          name: "Billing Q&A",
          description: null,
          icon: null,
          gradient: null,
          created_at: "2026-04-20T00:00:00Z",
          updated_at: "2026-04-20T00:00:00Z",
        },
      ],
      isPending: false,
      isError: false,
      refetch: jest.fn(),
    });
    const onSelect = jest.fn();
    render(
      <SavedTemplatesContent
        selectedTemplate={null}
        onSelectTemplate={onSelect}
        loading={false}
      />,
    );
    expect(screen.getByText("Support Agent")).toBeInTheDocument();
    expect(screen.getByText("Billing Q&A")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Support Agent"));
    expect(onSelect).toHaveBeenCalledWith(
      "tpl:11111111-1111-1111-1111-111111111111",
    );
  });

  it("marks the matching card as selected", () => {
    mockUseListTemplates.mockReturnValue({
      data: [
        {
          id: "11111111-1111-1111-1111-111111111111",
          name: "Support Agent",
          description: "Frontline triage",
          icon: "Bot",
          gradient: "2",
          created_at: "2026-04-20T00:00:00Z",
          updated_at: "2026-04-20T00:00:00Z",
        },
      ],
      isPending: false,
      isError: false,
      refetch: jest.fn(),
    });
    const { container } = render(
      <SavedTemplatesContent
        selectedTemplate="tpl:11111111-1111-1111-1111-111111111111"
        onSelectTemplate={jest.fn()}
        loading={false}
      />,
    );
    // TemplateCardComponent applies border-primary on the outer wrapper when selected.
    expect(container.querySelector(".border-primary")).toBeInTheDocument();
  });
});
```

- [x] **Step 2: Run the test and confirm it fails (file not yet created)**

Run: `cd src/frontend && npx jest src/modals/templatesModal/components/SavedTemplatesContent -c test.config.js`
Expected: FAIL — `Cannot find module '../index'`.

(If the above config path is not the project's jest config, use whatever the existing tests use. Check `src/frontend/package.json` scripts for the `test` entry, and the existing `src/frontend/src/modals/templatesModal/__tests__/action-bar.test.tsx` passes via `npm test` or `npx jest` at the `src/frontend` root. Prefer the same invocation.)

- [x] **Step 3: Implement `SavedTemplatesContent`**

Create `src/frontend/src/modals/templatesModal/components/SavedTemplatesContent/index.tsx`:

```tsx
import { useMemo } from "react";
import { Button } from "@/components/ui/button";
import { useListTemplates } from "@/controllers/API/queries/templates/use-list-templates";
import type { FlowType } from "@/types/flow";
import type { TemplateRead } from "@/types/template";
import { TemplateCategoryComponent } from "../TemplateCategoryComponent";

type Props = {
  selectedTemplate: string | null;
  onSelectTemplate: (id: string | null) => void;
  loading: boolean;
};

function adaptTemplateToFlowLike(template: TemplateRead): FlowType {
  return {
    id: `tpl:${template.id}`,
    name: template.name,
    description: template.description ?? "",
    icon: template.icon ?? undefined,
    gradient: template.gradient ?? undefined,
    data: null,
  } as FlowType;
}

export default function SavedTemplatesContent({
  selectedTemplate,
  onSelectTemplate,
  loading,
}: Props) {
  const { data, isPending, isError, refetch } = useListTemplates();

  const adapted = useMemo(
    () => (data ?? []).map(adaptTemplateToFlowLike),
    [data],
  );

  if (isPending) {
    return (
      <div
        data-testid="saved-templates-loading"
        className="grid grid-cols-1 gap-6 lg:grid-cols-2"
      >
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="h-24 animate-pulse rounded-md bg-muted"
            aria-hidden
          />
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <div
        data-testid="saved-templates-error"
        className="flex flex-col items-center justify-center gap-3 px-4 py-12 text-center"
      >
        <p className="text-sm text-secondary-foreground">
          Couldn't load saved templates.
        </p>
        <Button variant="outline" onClick={() => refetch()}>
          Retry
        </Button>
      </div>
    );
  }

  if (adapted.length === 0) {
    return (
      <div
        data-testid="saved-templates-empty"
        className="flex flex-col items-center justify-center px-4 py-12 text-center"
      >
        <p className="text-sm text-secondary-foreground">
          No saved templates yet. Save a flow as a template from the flow
          toolbar to see it here.
        </p>
      </div>
    );
  }

  return (
    <TemplateCategoryComponent
      examples={adapted}
      onCardClick={() => {}}
      loading={loading}
      selectedTemplate={selectedTemplate}
      onSelectTemplate={onSelectTemplate}
    />
  );
}
```

- [x] **Step 4: Run the test and confirm it passes**

Run: the same jest invocation as Step 2.
Expected: PASS — all five tests green.

- [x] **Step 5: Type-check the new file**

Run: `cd src/frontend && npx tsc --noEmit`
Expected: no new errors in `SavedTemplatesContent/index.tsx`. (Pre-existing errors in unrelated files are acceptable — only new ones matter.)

- [x] **Step 6: Stage and ask user before committing**

```bash
git add src/frontend/src/modals/templatesModal/components/SavedTemplatesContent
```

Proposed message:
`feat(templates-modal): add SavedTemplatesContent backed by /api/v1/templates`

**Do not run `git commit` until the user approves.**

---

## Task 2: Add "Saved Templates" nav item and render branch

**Files:**
- Modify: `src/frontend/src/modals/templatesModal/index.tsx`
- Test: `src/frontend/src/modals/templatesModal/__tests__/TemplatesModal.saved-tab.test.tsx`

### Steps

- [x] **Step 1: Write the failing nav + rendering test**

Create `src/frontend/src/modals/templatesModal/__tests__/TemplatesModal.saved-tab.test.tsx`:

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import TemplatesModal from "../index";

// Mocks — keep tight, only what the modal traverses.
jest.mock("@/controllers/API/queries/templates/use-list-templates", () => ({
  __esModule: true,
  useListTemplates: () => ({
    data: [],
    isPending: false,
    isError: false,
    refetch: jest.fn(),
  }),
  TEMPLATES_QUERY_KEY: ["templates"],
}));

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector: any) =>
    selector({ examples: [], setExamples: jest.fn() }),
}));

jest.mock("@/hooks/flows/use-add-flow", () => ({
  __esModule: true,
  default: () => jest.fn(),
}));

jest.mock("@/customization/hooks/use-custom-navigate", () => ({
  __esModule: true,
  useCustomNavigate: () => jest.fn(),
}));

jest.mock("@/customization/utils/analytics", () => ({
  __esModule: true,
  track: jest.fn(),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: (props: { name?: string }) => <span data-testid={`icon-${props.name}`} />,
  ForwardedIconComponent: (props: { name?: string }) => (
    <span data-testid={`icon-${props.name}`} />
  ),
}));

describe("TemplatesModal — Saved Templates tab", () => {
  it("shows the Saved Templates nav item and switches to it on click", () => {
    render(
      <MemoryRouter>
        <TemplatesModal open={true} setOpen={jest.fn()} />
      </MemoryRouter>,
    );
    const navItem = screen.getByTestId("side_nav_options_saved-templates");
    expect(navItem).toBeInTheDocument();

    fireEvent.click(navItem);
    // Empty-state copy from SavedTemplatesContent confirms the tab rendered.
    expect(screen.getByTestId("saved-templates-empty")).toBeInTheDocument();
  });
});
```

- [x] **Step 2: Run the test and confirm it fails**

Run: jest targeting `TemplatesModal.saved-tab.test.tsx`.
Expected: FAIL — `Unable to find element by: [data-testid="side_nav_options_saved-templates"]`.

- [x] **Step 3: Add the nav item and render branch**

In `src/frontend/src/modals/templatesModal/index.tsx`:

(a) Add an import at the top:

```tsx
import SavedTemplatesContent from "./components/SavedTemplatesContent";
```

(b) Append the nav item to the first category. Replace the existing first category block:

```ts
    {
      title: "Templates",
      items: [
        { title: "Get started", icon: "SquarePlay", id: "get-started" },
        { title: "All templates", icon: "LayoutPanelTop", id: "all-templates" },
      ],
    },
```

with:

```ts
    {
      title: "Templates",
      items: [
        { title: "Get started", icon: "SquarePlay", id: "get-started" },
        { title: "All templates", icon: "LayoutPanelTop", id: "all-templates" },
        { title: "Saved Templates", icon: "Bookmark", id: "saved" },
      ],
    },
```

(c) Add the render branch. Replace the existing `main` body:

```tsx
            <main className="flex flex-1 flex-col gap-4 overflow-auto p-6 md:gap-8">
              {currentTab === "get-started" ? (
                <GetStartedComponent
                  loading={loading}
                  onFlowCreating={handleFlowCreating}
                  selectedTemplate={selectedTemplate}
                  onSelectTemplate={setSelectedTemplate}
                />
              ) : (
                <TemplateContentComponent
                  currentTab={currentTab}
                  categories={categories.flatMap((category) => category.items)}
                  loading={loading}
                  onFlowCreating={handleFlowCreating}
                  selectedTemplate={selectedTemplate}
                  onSelectTemplate={setSelectedTemplate}
                />
              )}
            </main>
```

with:

```tsx
            <main className="flex flex-1 flex-col gap-4 overflow-auto p-6 md:gap-8">
              {currentTab === "get-started" && (
                <GetStartedComponent
                  loading={loading}
                  onFlowCreating={handleFlowCreating}
                  selectedTemplate={selectedTemplate}
                  onSelectTemplate={setSelectedTemplate}
                />
              )}
              {currentTab === "saved" && (
                <SavedTemplatesContent
                  loading={loading}
                  selectedTemplate={selectedTemplate}
                  onSelectTemplate={setSelectedTemplate}
                />
              )}
              {currentTab !== "get-started" && currentTab !== "saved" && (
                <TemplateContentComponent
                  currentTab={currentTab}
                  categories={categories.flatMap((category) => category.items)}
                  loading={loading}
                  onFlowCreating={handleFlowCreating}
                  selectedTemplate={selectedTemplate}
                  onSelectTemplate={setSelectedTemplate}
                />
              )}
            </main>
```

- [x] **Step 4: Run the test and confirm it passes**

Run: jest targeting `TemplatesModal.saved-tab.test.tsx`.
Expected: PASS.

- [x] **Step 5: Stage and ask user before committing**

```bash
git add src/frontend/src/modals/templatesModal/index.tsx src/frontend/src/modals/templatesModal/__tests__/TemplatesModal.saved-tab.test.tsx
```

Proposed message:
`feat(templates-modal): add Saved Templates tab entry + render branch`

**Do not run `git commit` until the user approves.**

---

## Task 3: Resolve `tpl:` selection to a flow via detail fetch

**Files:**
- Modify: `src/frontend/src/modals/templatesModal/index.tsx` (only the `handleCreateFromSelection` handler)
- Test: extend `src/frontend/src/modals/templatesModal/__tests__/TemplatesModal.saved-tab.test.tsx`

### Steps

- [x] **Step 1: Extend the test to cover template-driven flow creation**

Append this test suite to `TemplatesModal.saved-tab.test.tsx` (inside the same `describe`, or a new sibling `describe`):

Before: at the top of the file, replace the current `use-list-templates` mock with one that returns a single template, and add an `api` mock and an `addFlow` mock we can inspect. The full mocks block should look like:

```tsx
const mockAddFlow = jest.fn().mockResolvedValue("new-flow-id");
const mockApiGet = jest.fn();

jest.mock("@/controllers/API/queries/templates/use-list-templates", () => ({
  __esModule: true,
  useListTemplates: () => ({
    data: [
      {
        id: "11111111-1111-1111-1111-111111111111",
        name: "Support Agent",
        description: "Frontline triage",
        icon: "Bot",
        gradient: "2",
        created_at: "2026-04-20T00:00:00Z",
        updated_at: "2026-04-20T00:00:00Z",
      },
    ],
    isPending: false,
    isError: false,
    refetch: jest.fn(),
  }),
  TEMPLATES_QUERY_KEY: ["templates"],
}));

jest.mock("@/controllers/API/api", () => ({
  __esModule: true,
  api: { get: (...args: unknown[]) => mockApiGet(...args) },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  __esModule: true,
  getURL: (key: string) => `/api/v1/${key.toLowerCase()}`,
}));

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector: any) =>
    selector({ examples: [], setExamples: jest.fn() }),
}));

jest.mock("@/hooks/flows/use-add-flow", () => ({
  __esModule: true,
  default: () => mockAddFlow,
}));

jest.mock("@/customization/hooks/use-custom-navigate", () => ({
  __esModule: true,
  useCustomNavigate: () => jest.fn(),
}));

jest.mock("@/customization/utils/analytics", () => ({
  __esModule: true,
  track: jest.fn(),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: (props: { name?: string }) => <span data-testid={`icon-${props.name}`} />,
  ForwardedIconComponent: (props: { name?: string }) => (
    <span data-testid={`icon-${props.name}`} />
  ),
}));

jest.mock("@/utils/reactflowUtils", () => ({
  __esModule: true,
  updateIds: jest.fn(),
}));
```

And the first `it` block that was asserting the empty state should be kept as-is (it does not depend on the mock returning rows — it simply confirms the nav item is wired). Replace the empty-state assertion with a cards-visible assertion, since the list is no longer empty:

```tsx
describe("TemplatesModal — Saved Templates tab", () => {
  beforeEach(() => {
    mockAddFlow.mockClear();
    mockApiGet.mockReset();
  });

  it("shows the Saved Templates nav item and switches to it on click", () => {
    render(
      <MemoryRouter>
        <TemplatesModal open={true} setOpen={jest.fn()} />
      </MemoryRouter>,
    );
    const navItem = screen.getByTestId("side_nav_options_saved-templates");
    expect(navItem).toBeInTheDocument();

    fireEvent.click(navItem);
    expect(screen.getByText("Support Agent")).toBeInTheDocument();
  });

  it("creates a flow from a saved template on Start building", async () => {
    mockApiGet.mockResolvedValue({
      data: {
        id: "11111111-1111-1111-1111-111111111111",
        name: "Support Agent",
        description: "Frontline triage",
        icon: "Bot",
        gradient: "2",
        nodes: [{ id: "node-a" }],
        edges: [{ id: "edge-a" }],
        created_at: "2026-04-20T00:00:00Z",
        updated_at: "2026-04-20T00:00:00Z",
      },
    });

    render(
      <MemoryRouter>
        <TemplatesModal open={true} setOpen={jest.fn()} />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByTestId("side_nav_options_saved-templates"));
    fireEvent.click(screen.getByText("Support Agent"));
    fireEvent.click(screen.getByRole("button", { name: /start building/i }));

    // Wait for the async handler to resolve.
    await screen.findByText("Support Agent");

    expect(mockApiGet).toHaveBeenCalledWith(
      "/api/v1/templates/11111111-1111-1111-1111-111111111111",
    );
    expect(mockAddFlow).toHaveBeenCalledTimes(1);
    const callArg = mockAddFlow.mock.calls[0][0];
    expect(callArg.flow.name).toBe("Support Agent");
    expect(callArg.flow.data.nodes).toEqual([{ id: "node-a" }]);
    expect(callArg.flow.data.edges).toEqual([{ id: "edge-a" }]);
    expect(callArg.built_with_assist).toBe(false);
  });
});
```

- [x] **Step 2: Run the test and confirm it fails**

Run: jest targeting `TemplatesModal.saved-tab.test.tsx`.
Expected: the new `"creates a flow from a saved template"` case FAILS — `mockAddFlow` was not called, because the modal does not yet know about `tpl:` prefixed ids.

- [x] **Step 3: Update `handleCreateFromSelection` to resolve `tpl:` selections**

In `src/frontend/src/modals/templatesModal/index.tsx`:

(a) Add imports at the top:

```tsx
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import type { TemplateReadDetail } from "@/types/template";
```

(b) Replace the body of `handleCreateFromSelection` with:

```tsx
  const handleCreateFromSelection = async (withAssist: boolean) => {
    if (!selectedTemplate || loading) return;
    handleFlowCreating(true);
    try {
      let id: string;
      let templateAnalyticsName = selectedTemplate;

      if (selectedTemplate === "blank") {
        id = await addFlow({ new_blank: true, built_with_assist: withAssist });
        templateAnalyticsName = "Blank Flow";
      } else if (selectedTemplate.startsWith("tpl:")) {
        const templateId = selectedTemplate.slice("tpl:".length);
        const { data: detail } = await api.get<TemplateReadDetail>(
          `${getURL("TEMPLATES")}/${templateId}`,
        );
        const flowPayload = {
          id: detail.id,
          name: detail.name,
          description: detail.description ?? "",
          data: {
            nodes: detail.nodes,
            edges: detail.edges,
            viewport: { x: 0, y: 0, zoom: 1 },
          },
        } as unknown as Parameters<typeof addFlow>[0] extends infer P
          ? P extends { flow?: infer F }
            ? F
            : never
          : never;
        updateIds(flowPayload!.data!);
        id = await addFlow({
          flow: flowPayload,
          built_with_assist: withAssist,
        });
        templateAnalyticsName = detail.name;
      } else {
        const example = examples.find((e) => e.id === selectedTemplate);
        if (!example) return;
        updateIds(example.data!);
        id = await addFlow({ flow: example, built_with_assist: withAssist });
      }

      track("New Flow Created", {
        template: templateAnalyticsName,
        entry: withAssist ? "build-with-assist" : "start-building",
      });
      setOpen(false);
      if (withAssist) {
        openFlowInFullscreenAssist(id, navigate);
      } else {
        navigate(`/flow/${id}${folderId ? `/folder/${folderId}` : ""}`);
      }
    } finally {
      handleFlowCreating(false);
    }
  };
```

Note: the conditional-type dance around `Parameters<typeof addFlow>[0]` is noisy. Simpler alternative that keeps the intent obvious — use a direct import and cast:

```tsx
import type { FlowType } from "@/types/flow";
// ...
        const flowPayload = {
          id: detail.id,
          name: detail.name,
          description: detail.description ?? "",
          data: {
            nodes: detail.nodes,
            edges: detail.edges,
            viewport: { x: 0, y: 0, zoom: 1 },
          },
        } as unknown as FlowType;
        updateIds(flowPayload.data!);
        id = await addFlow({
          flow: flowPayload,
          built_with_assist: withAssist,
        });
```

Use the simpler `FlowType` cast version. (Replace the import block and payload construction accordingly.)

- [x] **Step 4: Run the test and confirm it passes**

Run: jest targeting `TemplatesModal.saved-tab.test.tsx`.
Expected: both test cases PASS.

- [x] **Step 5: Sanity-check the existing starter-flow path still works**

Confirm no regression in the non-`tpl:` branches by grep-inspecting the diff:

Run: `git diff src/frontend/src/modals/templatesModal/index.tsx`
Expected: the `"blank"` branch still calls `addFlow({ new_blank: true, ... })`; the `examples.find(...)` branch is unchanged; only the new `tpl:` branch and analytics renaming are added.

- [x] **Step 6: Type-check the modal**

Run: `cd src/frontend && npx tsc --noEmit`
Expected: no new errors.

- [x] **Step 7: Stage and ask user before committing**

```bash
git add src/frontend/src/modals/templatesModal/index.tsx src/frontend/src/modals/templatesModal/__tests__/TemplatesModal.saved-tab.test.tsx
```

Proposed message:
`feat(templates-modal): create flow from saved template via detail fetch`

**Do not run `git commit` until the user approves.**

---

## Task 4: Manual verification in the dev environment

UI changes require a browser check (per AGENTS.md / project standard).

- [x] **Step 1: Start the dev stack**

Run whatever the repo uses locally (per AGENTS.md — typically `make run` or similar). If the frontend dev server alone is enough, `cd src/frontend && npm run dev` against a backend that's already up.

- [x] **Step 2: Save a template**

In the UI:
1. Log in as a superuser (create-template requires superuser).
2. Open any flow.
3. From the flow toolbar's deploy dropdown, pick "Save as Template" and save with a distinctive name, icon, and gradient.

- [x] **Step 3: Verify it shows up in the New Flow modal**

1. Return to the flows list / main page.
2. Open "New Flow".
3. Click the new **Saved Templates** nav item.
4. Confirm the template you saved appears, with the icon and gradient chosen in Save-as-Template.

- [x] **Step 4: Verify flow creation from the saved template**

1. Select the card.
2. Click **Start building**.
3. Confirm you're navigated to a new flow at `/flow/<id>` (or `/folder/...`).
4. Open the flow and confirm nodes + edges match the template source (password-flagged fields should be blank — that's expected per Save-as-Template blanking).

- [x] **Step 5: Spot-check the empty state**

As a separate user (or by deleting the single template you created), confirm the "No saved templates yet." copy appears.

- [x] **Step 6: Spot-check existing tabs**

Click "Get started" and "All templates" — the starter flows should render exactly as before.

- [x] **Step 7: If anything fails, return to the relevant task; do not skip verification.**

---

## Post-implementation

- [x] **Final: Report what changed, what was verified, and any deferred items.** (Memory follow-up — after user approval — may update `project_template_management_state.md` to reflect FU-3 as done.)

---

## Plan self-review notes

- **Spec coverage:** Tab added ✓, `useListTemplates` wired ✓, empty/error/loading handled ✓, selection scheme `tpl:` ✓, detail fetch imperative ✓, Get Started untouched ✓, out-of-scope items explicitly deferred ✓.
- **Placeholder scan:** all code blocks are complete; commit commands and test invocations are spelled out; no "TBD" or "similar to Task N" dangling references.
- **Type consistency:** `TemplateRead` / `TemplateReadDetail` shape matches the backend model (checked `model.py` and `@/types/template`); `FlowType` has `name`, `id`, `data`, `description` as required fields, all present in the constructed payload.
- **Deviation from spec:** Spec proposed a new `SavedTemplateCardComponent`. Reading the code showed `TemplateCardComponent` already renders `icon` + `gradient` with the exact visual we want, so we reuse it via adapter and skip the new card. Spec's testing section for that card becomes the adapter test inside `SavedTemplatesContent.test.tsx`.
