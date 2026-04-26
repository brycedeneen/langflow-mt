import { useEffect, useState } from "react";
import { Loader2, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  getAssistantSettings,
  putAssistantSettings,
} from "@/controllers/API/queries/assistant/assistant-api";
import useAlertStore from "@/stores/alertStore";

const PROVIDER_OPTIONS = ["openai", "anthropic"] as const;
type Provider = (typeof PROVIDER_OPTIONS)[number];

const MODEL_MAP: Record<Provider, string[]> = {
  openai: ["gpt-4o", "gpt-4o-mini"],
  anthropic: ["claude-sonnet-4-20250514", "claude-opus-4-20250514"],
};

export default function AssistantSettingsPage() {
  const [provider, setProvider] = useState<Provider>("openai");
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [loading, setLoading] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);

  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setErrorData = useAlertStore((state) => state.setErrorData);

  useEffect(() => {
    async function load() {
      try {
        const data = await getAssistantSettings();
        if (data?.provider) {
          setProvider(data.provider as Provider);
        }
        if (data?.model) {
          setModel(data.model);
        }
        // API key is not returned for security
      } catch {
        // Settings may not exist yet
      } finally {
        setInitialLoading(false);
      }
    }
    load();
  }, []);

  // When provider changes, reset model to first option if current model is invalid
  useEffect(() => {
    const models = MODEL_MAP[provider];
    if (!models.includes(model)) {
      setModel(models[0]);
    }
  }, [provider]);

  const handleSave = async () => {
    setLoading(true);
    try {
      const body: { provider: string; model: string; api_key?: string } = {
        provider,
        model,
      };
      if (apiKey) {
        body.api_key = apiKey;
      }
      await putAssistantSettings(body);
      setSuccessData({ title: "Assistant settings saved." });
      setApiKey("");
    } catch (err: any) {
      setErrorData({
        title: "Failed to save assistant settings",
        list: [err?.message ?? "Unknown error"],
      });
    } finally {
      setLoading(false);
    }
  };

  if (initialLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2
          className="h-6 w-6 animate-spin text-muted-foreground"
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      <div>
        <h2 className="text-lg font-semibold">Flow Assistant</h2>
        <p className="text-sm text-muted-foreground">
          Configure the LLM provider for the flow builder assistant.
        </p>
      </div>

      <div className="flex max-w-md flex-col gap-4">
        <div className="flex flex-col gap-2">
          <Label htmlFor="provider">Provider</Label>
          <select
            id="provider"
            value={provider}
            onChange={(e) => setProvider(e.target.value as Provider)}
            className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-xs transition-colors focus-visible:outline-hidden focus-visible:ring-1 focus-visible:ring-ring"
          >
            {PROVIDER_OPTIONS.map((p) => (
              <option key={p} value={p}>
                {p === "openai" ? "OpenAI" : "Anthropic"}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-2">
          <Label htmlFor="model">Model</Label>
          <select
            id="model"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-xs transition-colors focus-visible:outline-hidden focus-visible:ring-1 focus-visible:ring-ring"
          >
            {MODEL_MAP[provider].map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-2">
          <Label htmlFor="api-key">API Key</Label>
          <Input
            id="api-key"
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="Enter API key (leave empty to keep existing)"
          />
          <p className="text-xs text-muted-foreground">
            The key is encrypted at rest and never displayed after saving.
          </p>
        </div>

        <Button onClick={handleSave} disabled={loading} className="w-fit">
          {loading ? (
            <Loader2
              className="mr-2 h-4 w-4 animate-spin"
            />
          ) : (
            <Save className="mr-2 h-4 w-4" />
          )}
          Save Settings
        </Button>
      </div>
    </div>
  );
}
