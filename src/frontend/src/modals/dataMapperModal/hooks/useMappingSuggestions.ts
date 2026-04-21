import { useCallback, useRef, useState } from "react";
import type React from "react";
import {
  useDataMapperAutoMapMutation,
  DataMapperAutoMapInput,
} from "../../../controllers/API/queries/assistant/use-data-mapper-auto-map";
import type { MapperConfig, MappingEntry, TransformType } from "../types";
import { filterEligibleSuggestions } from "../util/filterEligibleSuggestions";

export type MappingSuggestionsState = "idle" | "fetching" | "pending" | "empty" | "error";

export interface UseMappingSuggestionsArgs {
  config: MapperConfig;
}

export interface UseMappingSuggestionsResult {
  state: MappingSuggestionsState;
  entries: MappingEntry[];
  error: string | null;
  run: () => Promise<void>;
  cancel: () => void;
  reset: () => void;
  setEntries: React.Dispatch<React.SetStateAction<MappingEntry[]>>;
  setState: React.Dispatch<React.SetStateAction<MappingSuggestionsState>>;
}

const ALLOWED_TRANSFORMS: readonly TransformType[] = ["direct", "static", "variable", "template", "array"];

function extractJsonArray(raw: string): unknown {
  const stripped = raw.trim();
  const start = stripped.indexOf("[");
  const end = stripped.lastIndexOf("]");
  if (start < 0 || end <= start) throw new Error("no JSON array found");
  return JSON.parse(stripped.slice(start, end + 1));
}

function coerceEntries(parsed: unknown, knownInputs: Set<string>): MappingEntry[] {
  if (!Array.isArray(parsed)) throw new Error("expected array");
  const out: MappingEntry[] = [];
  for (const raw of parsed) {
    if (!raw || typeof raw !== "object") continue;
    const e = raw as Record<string, unknown>;
    if (typeof e.destination !== "string") continue;
    if (typeof e.transform !== "string") continue;
    if (!ALLOWED_TRANSFORMS.includes(e.transform as TransformType)) continue;
    const sources = Array.isArray(e.sources)
      ? e.sources.filter((s: unknown) => {
          const r = s as Record<string, unknown>;
          return r && typeof r.input === "string" && typeof r.field === "string" && knownInputs.has(r.input as string);
        })
      : [];
    const config =
      e.config && typeof e.config === "object" ? (e.config as Record<string, unknown>) : {};
    out.push({
      destination: e.destination,
      transform: e.transform as TransformType,
      sources: sources as MappingEntry["sources"],
      config,
    });
  }
  return out;
}

function extractMessageText(response: unknown): string {
  const r = response as {
    data?: {
      outputs?: Array<{
        outputs?: Array<{ outputs?: { message?: { message?: string } } }>;
      }>;
    };
  };
  const msg = r?.data?.outputs?.[0]?.outputs?.[0]?.outputs?.message?.message;
  if (typeof msg !== "string") throw new Error("no message in response");
  return msg;
}

export function useMappingSuggestions({ config }: UseMappingSuggestionsArgs): UseMappingSuggestionsResult {
  const [state, setState] = useState<MappingSuggestionsState>("idle");
  const [entries, setEntries] = useState<MappingEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const mutation = useDataMapperAutoMapMutation();

  const reset = useCallback(() => {
    setState("idle");
    setEntries([]);
    setError(null);
  }, []);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    reset();
  }, [reset]);

  const run = useCallback(async () => {
    abortRef.current?.abort();   // abort any prior in-flight request

    setState("fetching");
    setError(null);
    setEntries([]);

    const controller = new AbortController();
    abortRef.current = controller;

    const inputPayload: DataMapperAutoMapInput = {
      driver: {
        alias: config.inputs[config.driver_index]?.alias ?? "driver",
        fields: config.inputs[config.driver_index]?.schema.fields ?? [],
        sample: config.inputs[config.driver_index]?.sample ?? undefined,
      },
      destinations: config.destination_schema,
      lookups: config.inputs
        .filter((_, idx) => idx !== config.driver_index)
        .map((inp) => ({
          alias: inp.alias,
          fields: inp.schema.fields,
          sample: inp.sample ?? undefined,
          join_fields: inp.join?.on ?? [],
        })),
    };

    try {
      const response = await mutation.mutateAsync({ inputPayload, signal: controller.signal });
      if (controller.signal.aborted) return;

      const text = extractMessageText(response);
      const parsed = extractJsonArray(text);
      const knownInputs = new Set(config.inputs.map((i) => i.alias));
      const coerced = coerceEntries(parsed, knownInputs);
      const filtered = filterEligibleSuggestions(config, coerced);

      if (controller.signal.aborted) return;
      setEntries(filtered);
      setState(filtered.length > 0 ? "pending" : "empty");
    } catch (err) {
      if (controller.signal.aborted) return;
      const anyErr = err as { response?: { status?: number }; message?: string };
      if (anyErr?.response?.status === 404) {
        setError(
          "Auto-mapping isn't available in this environment. Ask your admin to update Langflow.",
        );
      } else if (
        anyErr?.response?.status === 401 ||
        anyErr?.response?.status === 403
      ) {
        setError("Not authorized. Sign in and try again.");
      } else if (
        anyErr?.message?.match(/no JSON array|expected array|no message/)
      ) {
        setError("Could not parse assistant output. Retry?");
      } else {
        setError(anyErr?.message || "Auto-mapping failed. Retry?");
      }
      setState("error");
    } finally {
      if (abortRef.current === controller) abortRef.current = null;
    }
  }, [config, mutation]);

  return { state, entries, error, run, cancel, reset, setEntries, setState };
}
