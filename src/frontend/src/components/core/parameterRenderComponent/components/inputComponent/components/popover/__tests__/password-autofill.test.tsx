/**
 * Tests for the password-manager autofill suppression on SecretStrInput
 * fields rendered via CustomInputPopover (the active path — InputComponent's
 * `isForm` defaults to false).
 *
 * The bug: Chrome / 1Password / LastPass / Bitwarden autofill the saved-login
 * username slot into any password-typed input whose name/id contains "id" or
 * "username". A field literally called `client_id` gets clobbered with a
 * stock dummy like `P@ssword1!`. That fired React onChange → autosave →
 * `auto_secrets.py::promote_plaintext_secrets_to_variables` Branch 5 wrote
 * the autofilled garbage into Vault, overwriting the real autosecret.
 *
 * The fix: when `password={true}`, render the underlying <input> with
 *   - autoComplete="new-password"   (Chrome respects this on password inputs
 *                                    even when it ignores "off")
 *   - data-1p-ignore                (1Password)
 *   - data-lpignore                 (LastPass)
 *   - data-bwignore                 (Bitwarden)
 * Non-password inputs MUST NOT get those data-* attrs.
 */

import { render, screen } from "@testing-library/react";
import React from "react";
import CustomInputPopover from "../index";

// --- Mocks --------------------------------------------------------------

// Radix popover anchor renders children inline.
jest.mock("@radix-ui/react-popover", () => ({
  PopoverAnchor: ({ children }: React.PropsWithChildren) => <>{children}</>,
}));

// lucide icons → trivial spans
jest.mock("lucide-react", () => ({
  Check: () => <span />,
  X: () => <span />,
}));

// UI primitives → render children, drop styling.
jest.mock("@/components/ui/tooltip", () => ({
  Tooltip: ({ children }: React.PropsWithChildren) => <>{children}</>,
  TooltipTrigger: ({ children }: React.PropsWithChildren) => <>{children}</>,
  TooltipContent: ({ children }: React.PropsWithChildren) => <>{children}</>,
}));

jest.mock("@/components/ui/badge", () => ({
  Badge: ({ children }: React.PropsWithChildren) => <span>{children}</span>,
}));

jest.mock("@/components/ui/command", () => ({
  Command: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  CommandGroup: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  CommandInput: () => <input />,
  CommandItem: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  CommandList: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
}));

jest.mock("@/components/ui/popover", () => ({
  Popover: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  PopoverContent: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  PopoverContentWithoutPortal: ({ children }: React.PropsWithChildren) => (
    <div>{children}</div>
  ),
}));

jest.mock("@/utils/utils", () => ({
  cn: (...classes: (string | undefined | false | null)[]) =>
    classes.filter(Boolean).join(" "),
}));

// --- Helpers ------------------------------------------------------------

const baseProps = {
  id: "client_id",
  refInput: { current: null },
  onInputLostFocus: undefined,
  selectedOption: "",
  setSelectedOption: undefined,
  selectedOptions: [],
  setSelectedOptions: undefined,
  value: "",
  disabled: false,
  setShowOptions: () => {},
  required: false,
  pwdVisible: false,
  editNode: false,
  placeholder: "secret",
  onChange: () => {},
  blurOnEnter: false,
  options: [],
  optionsPlaceholder: "Search options...",
  optionsButton: undefined,
  handleKeyDown: undefined,
  showOptions: false,
  nodeStyle: undefined,
  optionButton: undefined,
  autoFocus: false,
  popoverWidth: undefined,
  commandWidth: undefined,
  blockAddNewGlobalVariable: false,
  hasRefreshButton: false,
  inspectionPanel: false,
} as const;

// --- Tests --------------------------------------------------------------

describe("CustomInputPopover password autofill suppression", () => {
  it("renders new-password autocomplete + 1P/LP/BW ignore attrs when password={true}", () => {
    render(
      <CustomInputPopover {...(baseProps as any)} password={true} />,
    );

    const input = screen.getByTestId("client_id");
    // The <input> we're targeting carries the testid passed in via `id`.
    // It's the only input rendered when value/selection are empty.
    expect(input.tagName).toBe("INPUT");
    expect(input.getAttribute("type")).toBe("password");
    expect(input.getAttribute("autocomplete")).toBe("new-password");
    expect(input.getAttribute("data-1p-ignore")).toBe("true");
    expect(input.getAttribute("data-lpignore")).toBe("true");
    expect(input.getAttribute("data-bwignore")).toBe("true");
  });

  it("does NOT render data-1p-ignore / data-lpignore / data-bwignore on non-password inputs", () => {
    render(
      <CustomInputPopover {...(baseProps as any)} password={false} />,
    );

    const input = screen.getByTestId("client_id");
    expect(input.tagName).toBe("INPUT");
    expect(input.getAttribute("type")).toBe("text");
    // Non-password inputs keep the existing autoComplete="off" — they must
    // not opt in to "new-password" (which would suppress legitimate autofill
    // for non-secret fields like name/title), and must not carry the
    // ignore attrs.
    expect(input.getAttribute("autocomplete")).toBe("off");
    expect(input.hasAttribute("data-1p-ignore")).toBe(false);
    expect(input.hasAttribute("data-lpignore")).toBe(false);
    expect(input.hasAttribute("data-bwignore")).toBe(false);
  });
});
