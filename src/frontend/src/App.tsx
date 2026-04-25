import "@xyflow/react/dist/style.css";
import { Suspense, useEffect } from "react";
import { RouterProvider } from "react-router-dom";
import ValidationErrorOverlay from "@/components/common/ValidationErrorOverlay";
import { configureReporter } from "@/lib/schema-errors";
import { initSentry, sentryReporter } from "@/lib/sentry";
import { LoadingPage } from "./pages/LoadingPage";
import router from "./routes";
import { useDarkStore } from "./stores/darkStore";

// Initialise Sentry at module load time (before any component renders).
// When VITE_SENTRY_DSN is absent the build is clean — initSentry() returns
// false and configureReporter is never called, so the default reporter
// (console + overlay store) stays in place unchanged.
const _sentryReady = initSentry();
if (_sentryReady) {
  // Compose: replicate the default reporter behaviour (console warn in
  // non-prod + overlay-store push) AND additionally forward to Sentry.
  configureReporter((payload) => {
    // Console warn in non-prod only (mirrors DEFAULT_REPORTER in schema-errors.ts).
    if (import.meta.env.MODE !== "production") {
      // eslint-disable-next-line no-console
      console.warn(
        `[ValidationError][${payload.boundary}][${payload.mode}] ${payload.id}`,
        payload.error.issues,
        { raw: payload.raw },
      );
    }
    // Push to overlay store (fire-and-forget, same as DEFAULT_REPORTER).
    void import("@/stores/validationErrorStore")
      .then(({ default: store }) => {
        store.getState().push({
          id: payload.id,
          boundary: payload.boundary,
          mode: payload.mode,
          error: payload.error,
          raw: payload.raw,
          at: Date.now(),
        });
      })
      .catch(() => {
        /* noop */
      });
    // Forward to Sentry.
    sentryReporter(payload);
  });
}

export default function App() {
  const dark = useDarkStore((state) => state.dark);
  useEffect(() => {
    if (!dark) {
      document.getElementById("body")!.classList.remove("dark");
    } else {
      document.getElementById("body")!.classList.add("dark");
    }
  }, [dark]);
  return (
    <>
      <ValidationErrorOverlay />
      <Suspense fallback={<LoadingPage />}>
        <RouterProvider router={router} />
      </Suspense>
    </>
  );
}
