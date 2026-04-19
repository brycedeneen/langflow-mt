import { useState } from "react";

type Props = {
  value: unknown;
};

export function RawOutput({ value }: Props) {
  const [open, setOpen] = useState(false);
  const rendered =
    typeof value === "string" ? value : JSON.stringify(value, null, 2);
  return (
    <div>
      <button
        type="button"
        aria-expanded={open}
        className="text-xs text-muted-foreground underline-offset-2 hover:underline"
        onClick={() => setOpen((o) => !o)}
      >
        {open ? "Hide full output" : "View full output →"}
      </button>
      {open && (
        <pre className="mt-2 max-h-60 overflow-auto rounded bg-muted p-2 text-xs">
          {rendered}
        </pre>
      )}
    </div>
  );
}
