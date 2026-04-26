import { Check, Loader2, X } from "lucide-react";

export type TestStatus = "not_tested" | "testing" | "passed" | "failed";

type Props = {
  status: TestStatus;
  errorMessage?: string;
};

export function StatusBadge({ status, errorMessage }: Props) {
  if (status === "not_tested") {
    return (
      <span className="flex items-center gap-1 text-xs text-muted-foreground">
        <span className="h-2 w-2 rounded-full bg-muted-foreground/40" />
        Not tested
      </span>
    );
  }
  if (status === "testing") {
    return (
      <span className="flex items-center gap-1 text-xs text-amber-600">
        <Loader2 className="h-3 w-3 animate-spin" />
        Testing…
      </span>
    );
  }
  if (status === "passed") {
    return (
      <span className="flex items-center gap-1 text-xs text-emerald-600">
        <Check className="h-3 w-3" />
        Passed
      </span>
    );
  }
  // failed
  const label = errorMessage ? errorMessage.split("\n")[0] : "Failed";
  return (
    <span
      className="flex items-center gap-1 text-xs text-red-600"
      title={errorMessage}
    >
      <X className="h-3 w-3 shrink-0" />
      <span className="truncate">{label}</span>
    </span>
  );
}
