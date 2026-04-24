import type { z } from "zod";
import type { SchemaMode } from "./schema-registry";

export type Boundary = "http" | "storage" | "stream";

export class ValidationError extends Error {
  readonly id: string;
  readonly zodError: z.ZodError;
  readonly boundary: Boundary;

  constructor(id: string, zodError: z.ZodError, boundary: Boundary) {
    const preview = zodError.issues.slice(0, 3).map(formatIssue).join("; ");
    super(`ValidationError [${id}] ${preview}`);
    this.name = "ValidationError";
    this.id = id;
    this.zodError = zodError;
    this.boundary = boundary;
  }
}

function formatIssue(issue: z.ZodIssue): string {
  const path = issue.path.length
    ? issue.path.map((p) => (typeof p === "number" ? `[${p}]` : p)).join(".").replace(/\.\[/g, "[")
    : "<root>";
  return `at ${path}: ${issue.message}`;
}

export interface ParseFailurePayload {
  id: string;
  mode: SchemaMode;
  error: z.ZodError;
  raw: unknown;
  boundary: Boundary;
}

export type Reporter = (payload: ParseFailurePayload) => void;

const DEFAULT_REPORTER: Reporter = (payload) => {
  if (process.env.NODE_ENV !== "production") {
    // eslint-disable-next-line no-console
    console.warn(`[ValidationError][${payload.boundary}][${payload.mode}] ${payload.id}`, payload.error.issues, { raw: payload.raw });
  }
  // Fire-and-forget push to the in-app store; keeps app path untouched if the store isn't present (e.g. unit tests that reset reporter).
  void import("@/stores/validationErrorStore").then(({ default: store }) => {
    store.getState().push({
      id: payload.id, boundary: payload.boundary, mode: payload.mode,
      error: payload.error, raw: payload.raw, at: Date.now(),
    });
  }).catch(() => { /* noop */ });
};

let reporter: Reporter = DEFAULT_REPORTER;
const DEDUP_WINDOW_MS = 60_000;
const recentKeys = new Map<string, number>();

export function configureReporter(next: Reporter): void {
  reporter = next;
}

export function reportParseFailure(payload: ParseFailurePayload): void {
  const topPath = payload.error.issues[0]?.path?.[0] ?? "<root>";
  const key = `${payload.id}::${String(topPath)}`;
  const now = Date.now();
  const last = recentKeys.get(key);
  if (last !== undefined && now - last < DEDUP_WINDOW_MS) return;
  recentKeys.set(key, now);
  try {
    reporter(payload);
  } catch {
    // never let a bad reporter break the app path
  }
}

/** Test-only reset of reporter config + dedup cache. */
export function _resetReporterForTest(): void {
  reporter = DEFAULT_REPORTER;
  recentKeys.clear();
}
