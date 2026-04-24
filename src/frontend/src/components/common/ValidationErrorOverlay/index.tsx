import { useState } from "react";
import useAuthStore from "@/stores/authStore";
import useValidationErrorStore from "@/stores/validationErrorStore";

export default function ValidationErrorOverlay() {
  const isAdmin = useAuthStore((s) => s.isAdmin);
  const isPlatformAdmin = useAuthStore((s) => s.isPlatformAdmin);
  const visible = isAdmin || isPlatformAdmin;

  // Subscribe AFTER the visibility gate so non-admins pay zero cost.
  if (!visible) return null;
  return <OverlayInner />;
}

function OverlayInner() {
  const errors = useValidationErrorStore((s) => s.errors);
  const mute = useValidationErrorStore((s) => s.mute);
  const clear = useValidationErrorStore((s) => s.clear);
  const [open, setOpen] = useState(false);
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);

  const selected = selectedIdx !== null ? errors[selectedIdx] : null;
  return (
    <>
      <button
        data-testid="validation-error-overlay-toggle"
        onClick={() => setOpen((o) => !o)}
        className="fixed bottom-2 right-2 z-[9999] rounded bg-red-600 px-2 py-1 text-xs text-white shadow"
        aria-label="Validation errors"
      >
        ⚠︎ {errors.length}
      </button>
      {open && (
        <div className="fixed bottom-12 right-2 z-[9999] flex max-h-[70vh] w-[600px] flex-col overflow-hidden rounded border bg-background shadow-lg">
          <div className="flex items-center justify-between border-b px-3 py-2">
            <div className="text-sm font-semibold">Validation errors ({errors.length})</div>
            <div className="flex gap-2 text-xs">
              <button onClick={clear} className="underline">Clear</button>
              <button onClick={() => setOpen(false)} className="underline">Close</button>
            </div>
          </div>
          <div className="flex flex-1 overflow-hidden">
            <ul className="w-1/2 overflow-y-auto border-r text-xs">
              {errors.map((e, i) => (
                <li
                  key={`${e.id}-${e.at}-${i}`}
                  className="cursor-pointer border-b px-2 py-1 hover:bg-muted"
                  onClick={() => setSelectedIdx(i)}
                >
                  <div className="font-mono">{e.id}</div>
                  <div className="opacity-60">{e.boundary} · {e.mode}</div>
                </li>
              ))}
            </ul>
            <div className="w-1/2 overflow-y-auto p-2 text-xs">
              {selected ? (
                <>
                  <div className="mb-2 flex items-center justify-between">
                    <span className="font-mono">{selected.id}</span>
                    <div className="flex gap-2">
                      <button
                        onClick={() => navigator.clipboard.writeText(JSON.stringify(selected.raw, null, 2))}
                        className="underline"
                      >
                        Copy payload
                      </button>
                      <button onClick={() => mute(selected.id)} className="underline">Mute</button>
                    </div>
                  </div>
                  <pre className="whitespace-pre-wrap break-all rounded bg-muted p-2">
{JSON.stringify(selected.error.issues, null, 2)}
                  </pre>
                  <pre className="mt-2 whitespace-pre-wrap break-all rounded bg-muted p-2">
{JSON.stringify(selected.raw, null, 2)}
                  </pre>
                </>
              ) : (
                <div className="opacity-60">Select an error on the left.</div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
