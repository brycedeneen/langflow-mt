import { render } from "@testing-library/react";
import type React from "react";
import { TooltipProvider } from "@/components/ui/tooltip";
import InputGlobalComponent from "../index";

type TestProps = Record<string, unknown>;

function renderWithTooltip(ui: React.ReactElement) {
  return render(<TooltipProvider>{ui}</TooltipProvider>);
}

// The backend filters autosecret variables out of /api/v1/variables, so the
// marker we render with WILL NOT be present in this list. Reproducing that.
const mockUseGetGlobalVariables = jest.fn();
jest.mock("@/controllers/API/queries/variables", () => ({
  useGetGlobalVariables: () => mockUseGetGlobalVariables(),
}));

jest.mock("@/stores/globalVariablesStore/globalVariables", () => ({
  useGlobalVariablesStore: (
    selector: (state: { unavailableFields: Record<string, string> }) => unknown,
  ) => selector({ unavailableFields: {} }),
}));

jest.mock("@/components/core/GlobalVariableModal/GlobalVariableModal", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

jest.mock("@/shared/components/delete-confirmation-modal", () => ({
  __esModule: true,
  default: () => null,
}));

const AUTOSECRET_VALUE =
  "__autosecret|11111111-1111-1111-1111-111111111111|node-1|client_id";

function baseProps(overrides: TestProps = {}): TestProps {
  return {
    id: "field-client_id",
    value: AUTOSECRET_VALUE,
    editNode: false,
    handleOnNewValue: jest.fn(),
    disabled: false,
    load_from_db: true,
    password: true,
    display_name: "Client ID",
    placeholder: "Type something",
    ...overrides,
  };
}

// InputGlobalComponent is a memoized component with a complex InputProps type
// pulled from the wider parameter renderer. The test only needs to drive the
// orphan-cleanup branch, so cast through unknown rather than reconstructing
// every nested prop type just to satisfy the spread.
const InputGlobalAsAny = InputGlobalComponent as unknown as React.ComponentType<
  Record<string, unknown>
>;

async function flushEffects() {
  // Two microtask flushes are enough for any post-render useEffect to run.
  await Promise.resolve();
  await Promise.resolve();
}

describe("InputGlobalComponent — autosecret marker round-trip", () => {
  beforeEach(() => {
    mockUseGetGlobalVariables.mockReset();
    mockUseGetGlobalVariables.mockReturnValue({ data: [] });
  });

  it("does NOT clear the field via the orphaned-variable cleanup when the value is an autosecret marker", async () => {
    const handleOnNewValue = jest.fn();
    renderWithTooltip(
      <InputGlobalAsAny {...baseProps({ handleOnNewValue })} />,
    );
    await flushEffects();

    // Bug: orphaned-variable cleanup useEffect calls
    // `handleOnNewValue({ value: "", load_from_db: false })` on mount because
    // the marker isn't in the visible variables list. After the fix this MUST
    // NOT happen.
    const clearedCalls = handleOnNewValue.mock.calls.filter(
      ([change]) =>
        change && change.value === "" && change.load_from_db === false,
    );
    expect(clearedCalls).toHaveLength(0);
  });

  it("does not leak the raw marker text into the rendered DOM", async () => {
    renderWithTooltip(<InputGlobalAsAny {...baseProps()} />);
    await flushEffects();

    // Marker shouldn't appear anywhere in the visible input — neither in input
    // .value nor as plain text inside the dropdown badge.
    const inputs = document.querySelectorAll("input");
    inputs.forEach((input) => {
      expect(input.value).not.toContain("__autosecret|");
    });
    expect(document.body.textContent ?? "").not.toContain("__autosecret|");
  });
});
