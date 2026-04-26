import { beforeEach, describe, expect, it, jest } from "@jest/globals";
import "@testing-library/jest-dom/jest-globals";
import { fireEvent, render, screen } from "@testing-library/react";
import type { ProServiceSettings } from "@/types/pro-service-quote";

const getMock = jest.fn();
const updateMock = jest.fn();
const testWebhookMock = jest.fn();

jest.mock("@/controllers/API/queries/admin/professional-services", () => ({
  useGetProServiceSettings: () => getMock(),
  useUpdateProServiceSettings: () => ({
    mutate: updateMock,
    isPending: false,
  }),
  useTestProServiceWebhook: () => ({
    mutate: testWebhookMock,
    isPending: false,
  }),
}));

const setSuccessDataMock = jest.fn();
const setErrorDataMock = jest.fn();
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (
    selector: (state: {
      setSuccessData: typeof setSuccessDataMock;
      setErrorData: typeof setErrorDataMock;
    }) => unknown,
  ) =>
    selector({
      setSuccessData: setSuccessDataMock,
      setErrorData: setErrorDataMock,
    }),
}));

import ProfessionalServicesPage from "../index";

function settings(overrides: Partial<ProServiceSettings> = {}): ProServiceSettings {
  return {
    default_hourly_rate_low: "200.00",
    default_hourly_rate_high: "300.00",
    webhook_url: "https://example.com/hook",
    has_webhook_secret: true,
    ...overrides,
  };
}

describe("ProfessionalServicesPage", () => {
  beforeEach(() => {
    getMock.mockReset();
    updateMock.mockReset();
    testWebhookMock.mockReset();
    setSuccessDataMock.mockReset();
    setErrorDataMock.mockReset();
  });

  it("seeds the form from server settings", () => {
    getMock.mockReturnValue({ data: settings(), isLoading: false });
    render(<ProfessionalServicesPage />);
    expect(screen.getByTestId("ps-settings-rate-low")).toHaveValue(200);
    expect(screen.getByTestId("ps-settings-rate-high")).toHaveValue(300);
    expect(screen.getByTestId("ps-settings-webhook-url")).toHaveValue(
      "https://example.com/hook",
    );
    // Secret is write-only — placeholder reflects has_webhook_secret only.
    const secret = screen.getByTestId(
      "ps-settings-webhook-secret",
    ) as HTMLInputElement;
    expect(secret.value).toBe("");
    expect(secret.placeholder).toBe("••••••");
  });

  it("disables Test webhook when there is no URL or no secret", () => {
    getMock.mockReturnValue({
      data: settings({ webhook_url: null, has_webhook_secret: false }),
      isLoading: false,
    });
    render(<ProfessionalServicesPage />);
    expect(screen.getByTestId("ps-settings-test-webhook")).toBeDisabled();
  });

  it("enables Test webhook when both URL and secret are configured", () => {
    getMock.mockReturnValue({ data: settings(), isLoading: false });
    render(<ProfessionalServicesPage />);
    expect(screen.getByTestId("ps-settings-test-webhook")).not.toBeDisabled();
  });

  it("submits the rotated secret as a non-empty body field on Save", () => {
    getMock.mockReturnValue({ data: settings(), isLoading: false });
    render(<ProfessionalServicesPage />);
    fireEvent.change(screen.getByTestId("ps-settings-webhook-secret"), {
      target: { value: "new-secret" },
    });
    fireEvent.click(screen.getByTestId("ps-settings-save"));
    expect(updateMock).toHaveBeenCalledTimes(1);
    const [payload] = updateMock.mock.calls[0] as [any, ...unknown[]];
    expect(payload).toMatchObject({
      default_hourly_rate_low: "200.00",
      default_hourly_rate_high: "300.00",
      webhook_url: "https://example.com/hook",
      webhook_secret: "new-secret",
    });
  });

  it("omits webhook_secret from the body when the field is empty", () => {
    getMock.mockReturnValue({ data: settings(), isLoading: false });
    render(<ProfessionalServicesPage />);
    fireEvent.click(screen.getByTestId("ps-settings-save"));
    expect(updateMock).toHaveBeenCalledTimes(1);
    const [payload] = updateMock.mock.calls[0] as [any, ...unknown[]];
    expect(payload).not.toHaveProperty("webhook_secret");
  });
});
