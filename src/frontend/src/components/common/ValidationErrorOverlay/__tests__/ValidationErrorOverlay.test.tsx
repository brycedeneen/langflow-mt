import { describe, it, expect, beforeEach } from "@jest/globals";
import { render, screen } from "@testing-library/react";
import { z } from "zod";
import ValidationErrorOverlay from "..";
import useAuthStore from "@/stores/authStore";
import useValidationErrorStore from "@/stores/validationErrorStore";

describe("<ValidationErrorOverlay />", () => {
  beforeEach(() => {
    useAuthStore.setState({ isAdmin: false, isPlatformAdmin: false });
    useValidationErrorStore.setState({ errors: [], mutedIds: new Set() });
  });

  it("renders nothing for non-admin users", () => {
    useValidationErrorStore.getState().push({
      id: "x", boundary: "http", mode: "permissive",
      error: new z.ZodError([]), raw: null, at: Date.now(),
    });
    const { container } = render(<ValidationErrorOverlay />);
    expect(container.firstChild).toBeNull();
  });

  it("renders the toggle for super admin", () => {
    useAuthStore.setState({ isAdmin: true });
    render(<ValidationErrorOverlay />);
    expect(screen.getByTestId("validation-error-overlay-toggle")).toBeInTheDocument();
  });

  it("renders the toggle for platform admin", () => {
    useAuthStore.setState({ isPlatformAdmin: true });
    render(<ValidationErrorOverlay />);
    expect(screen.getByTestId("validation-error-overlay-toggle")).toBeInTheDocument();
  });
});
