import { fireEvent, render, screen } from "@testing-library/react";
import TextFileSecretComponent from "../index";

// Mock InputGlobalComponent to avoid heavy store/API dependencies
jest.mock("../../inputGlobalComponent", () => ({
  __esModule: true,
  default: (props: any) => (
    <input
      data-testid="mock-global-input"
      value={props.value}
      onChange={(e) => props.handleOnNewValue({ value: e.target.value })}
      onBlur={props.onBlur}
    />
  ),
}));

const defaultProps = {
  id: "test-secret",
  value: "",
  handleOnNewValue: jest.fn(),
  disabled: false,
  editNode: false,
};

describe("TextFileSecretComponent", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("Tab defaults", () => {
    it("defaults to Upload tab when value is empty", () => {
      render(<TextFileSecretComponent {...defaultProps} value="" />);

      const uploadTrigger = screen.getByRole("tab", { name: /upload file/i });
      const pasteTrigger = screen.getByRole("tab", { name: /paste/i });

      expect(uploadTrigger).toHaveAttribute("data-state", "active");
      expect(pasteTrigger).toHaveAttribute("data-state", "inactive");
    });

    it("defaults to Paste tab when value is set", () => {
      render(
        <TextFileSecretComponent
          {...defaultProps}
          value="-----BEGIN CERTIFICATE-----\nAAA\n-----END CERTIFICATE-----\n"
        />,
      );

      const pasteTrigger = screen.getByRole("tab", { name: /paste/i });
      const uploadTrigger = screen.getByRole("tab", { name: /upload file/i });

      expect(pasteTrigger).toHaveAttribute("data-state", "active");
      expect(uploadTrigger).toHaveAttribute("data-state", "inactive");
    });
  });

  describe("File upload", () => {
    it("reads file text and calls handleOnNewValue", async () => {
      const handleOnNewValue = jest.fn();
      render(
        <TextFileSecretComponent
          {...defaultProps}
          handleOnNewValue={handleOnNewValue}
        />,
      );

      const fileContents =
        "-----BEGIN CERTIFICATE-----\nAAA\n-----END CERTIFICATE-----\n";
      const file = new File([fileContents], "cert.pem", { type: "text/plain" });

      // Mock file.text() to return the contents
      Object.defineProperty(file, "text", {
        value: () => Promise.resolve(fileContents),
      });

      const fileInput = document.querySelector(
        'input[type="file"]',
      ) as HTMLInputElement;
      expect(fileInput).toBeInTheDocument();

      fireEvent.change(fileInput, { target: { files: [file] } });

      // Wait for async file read
      await screen.findByRole("tab", { name: /upload file/i });

      expect(handleOnNewValue).toHaveBeenCalledWith({ value: fileContents });
    });

    it("rejects oversize files with a warning and does not call handleOnNewValue", async () => {
      const handleOnNewValue = jest.fn();
      render(
        <TextFileSecretComponent
          {...defaultProps}
          handleOnNewValue={handleOnNewValue}
        />,
      );

      const bigContent = "x".repeat(1_200_000);
      const file = new File([bigContent], "big.pem", { type: "text/plain" });

      const fileInput = document.querySelector(
        'input[type="file"]',
      ) as HTMLInputElement;
      expect(fileInput).toBeInTheDocument();

      fireEvent.change(fileInput, { target: { files: [file] } });

      // Warning should appear synchronously (no async read on oversize)
      const alert = await screen.findByRole("alert");
      expect(alert).toHaveTextContent(/max is/i);

      expect(handleOnNewValue).not.toHaveBeenCalled();
    });
  });
});
