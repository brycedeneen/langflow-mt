import * as Sentry from "@sentry/react";
import type { ParseFailurePayload, Reporter } from "./schema-errors";

const DSN = import.meta.env.VITE_SENTRY_DSN as string | undefined;
const ENV =
  (import.meta.env.VITE_SENTRY_ENV as string | undefined) ??
  (import.meta.env.MODE as string | undefined) ??
  "development";

/**
 * Initialise Sentry. Returns `true` if a DSN was found and Sentry was
 * initialised, `false` otherwise (build stays clean without a DSN).
 */
export function initSentry(): boolean {
  if (!DSN) return false;
  Sentry.init({
    dsn: DSN,
    environment: ENV,
    tracesSampleRate: 0.1,
    // Don't send PII by default; validation payloads may contain user data.
    sendDefaultPii: false,
  });
  return true;
}

/**
 * Sentry reporter for schema-validation failures.
 * No-ops silently when DSN is not configured.
 */
export const sentryReporter: Reporter = (payload: ParseFailurePayload) => {
  if (!DSN) return;
  const topPath = payload.error.issues[0]?.path?.[0] ?? "<root>";
  Sentry.withScope((scope) => {
    scope.setTag("schema_id", payload.id);
    scope.setTag("boundary", payload.boundary);
    scope.setTag("mode", payload.mode);
    scope.setFingerprint([payload.id, String(topPath)]);
    // Truncate raw payload to ≤10 KB before sending.
    const rawStr = safeStringify(payload.raw, 10_000);
    scope.addBreadcrumb({
      category: "validation.raw",
      level: "info",
      data: { raw: rawStr },
    });
    Sentry.captureMessage(
      `ValidationError [${payload.boundary}/${payload.mode}] ${payload.id}`,
      "warning",
    );
  });
};

function safeStringify(value: unknown, maxLen: number): string {
  try {
    const s = JSON.stringify(value);
    return s.length > maxLen ? s.slice(0, maxLen) + "…(truncated)" : s;
  } catch {
    return "<unserializable>";
  }
}
