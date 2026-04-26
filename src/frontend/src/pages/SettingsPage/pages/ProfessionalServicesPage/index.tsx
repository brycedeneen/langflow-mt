import { useEffect, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  useGetProServiceSettings,
  useTestProServiceWebhook,
  useUpdateProServiceSettings,
} from "@/controllers/API/queries/admin/professional-services";
import useAlertStore from "@/stores/alertStore";
import type {
  ProServiceSettingsWrite,
  ProServiceWebhookTestResult,
} from "@/types/pro-service-quote";

export default function ProfessionalServicesPage() {
  const { data, isLoading } = useGetProServiceSettings();
  const update = useUpdateProServiceSettings();
  const testWebhook = useTestProServiceWebhook();

  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const [rateLow, setRateLow] = useState("");
  const [rateHigh, setRateHigh] = useState("");
  const [webhookUrl, setWebhookUrl] = useState("");
  const [webhookSecret, setWebhookSecret] = useState("");
  const [testResult, setTestResult] =
    useState<ProServiceWebhookTestResult | null>(null);

  // Seed inputs from server response. Webhook secret is intentionally never
  // populated — it's write-only and the backend reports presence via
  // ``has_webhook_secret`` only.
  useEffect(() => {
    if (data) {
      setRateLow(data.default_hourly_rate_low ?? "");
      setRateHigh(data.default_hourly_rate_high ?? "");
      setWebhookUrl(data.webhook_url ?? "");
    }
  }, [data]);

  const handleSave = () => {
    const body: ProServiceSettingsWrite = {};
    if (rateLow.trim() !== "") body.default_hourly_rate_low = rateLow.trim();
    if (rateHigh.trim() !== "") body.default_hourly_rate_high = rateHigh.trim();
    body.webhook_url = webhookUrl.trim();
    if (webhookSecret.trim() !== "") {
      body.webhook_secret = webhookSecret.trim();
    }
    update.mutate(body, {
      onSuccess: () => {
        setSuccessData({ title: "Professional services settings saved." });
        setWebhookSecret(""); // Clear write-only field after save
      },
      onError: (err: any) => {
        setErrorData({
          title: "Failed to save settings",
          list: [err?.message ?? "Unknown error"],
        });
      },
    });
  };

  const canTestWebhook =
    !!data?.webhook_url && data.has_webhook_secret && !testWebhook.isPending;

  const handleTestWebhook = () => {
    setTestResult(null);
    testWebhook.mutate(undefined as void, {
      onSuccess: (result: ProServiceWebhookTestResult) => {
        setTestResult(result);
      },
      onError: (err: any) => {
        setTestResult({
          status: "failed",
          detail: err?.message ?? "Unknown error",
        });
      },
    });
  };

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <ForwardedIconComponent
          name="Loader2"
          className="h-6 w-6 animate-spin text-muted-foreground"
        />
      </div>
    );
  }

  return (
    <div
      className="flex flex-col gap-6 p-6"
      data-testid="professional-services-settings-page"
    >
      <div>
        <h2 className="text-lg font-semibold">Professional Services</h2>
        <p className="text-sm text-muted-foreground">
          Configure default hourly rates, the inbound webhook, and the
          shared signing secret used to deliver new quote requests.
        </p>
      </div>

      <div className="flex max-w-md flex-col gap-4">
        <div className="flex flex-col gap-2">
          <Label htmlFor="rate-low">Default rate (low) — $/hour</Label>
          <Input
            id="rate-low"
            type="number"
            step="0.01"
            value={rateLow}
            onChange={(e) => setRateLow(e.target.value)}
            placeholder="200.00"
            data-testid="ps-settings-rate-low"
          />
        </div>

        <div className="flex flex-col gap-2">
          <Label htmlFor="rate-high">Default rate (high) — $/hour</Label>
          <Input
            id="rate-high"
            type="number"
            step="0.01"
            value={rateHigh}
            onChange={(e) => setRateHigh(e.target.value)}
            placeholder="300.00"
            data-testid="ps-settings-rate-high"
          />
        </div>

        <div className="flex flex-col gap-2">
          <Label htmlFor="webhook-url">Webhook URL</Label>
          <Input
            id="webhook-url"
            type="url"
            value={webhookUrl}
            onChange={(e) => setWebhookUrl(e.target.value)}
            placeholder="https://example.com/hooks/pro-services"
            data-testid="ps-settings-webhook-url"
          />
        </div>

        <div className="flex flex-col gap-2">
          <Label htmlFor="webhook-secret">Webhook signing secret</Label>
          <Input
            id="webhook-secret"
            type="password"
            value={webhookSecret}
            onChange={(e) => setWebhookSecret(e.target.value)}
            placeholder={data?.has_webhook_secret ? "••••••" : "(none set)"}
            data-testid="ps-settings-webhook-secret"
          />
          <p className="text-xs text-muted-foreground">
            Leave empty to keep the existing secret. Enter a new value to
            rotate it. The secret is never returned by the API.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            onClick={handleSave}
            loading={update.isPending}
            data-testid="ps-settings-save"
          >
            Save settings
          </Button>
          <Button
            variant="outline"
            onClick={handleTestWebhook}
            disabled={!canTestWebhook}
            loading={testWebhook.isPending}
            data-testid="ps-settings-test-webhook"
          >
            Test webhook
          </Button>
        </div>

        {testResult && (
          <div
            className={
              testResult.status === "ok"
                ? "rounded border border-accent-emerald-foreground/40 bg-accent-emerald/40 p-3 text-sm"
                : "rounded border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive"
            }
            data-testid="ps-settings-test-result"
          >
            {testResult.status === "ok"
              ? `status: ok${testResult.status_code ? ` (${testResult.status_code})` : ""}`
              : `status: failed${testResult.detail ? `: ${testResult.detail}` : ""}`}
          </div>
        )}
      </div>
    </div>
  );
}
