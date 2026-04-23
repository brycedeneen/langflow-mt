import { useState } from "react";
import { useGetOrgUsage } from "@/controllers/API/queries/usage/use-get-org-usage";

type Props = { orgId: string };

export default function UsageKpiCards({ orgId }: Props) {
  const [window, setWindow] = useState<"1d" | "7d" | "30d">("7d");
  const { data } = useGetOrgUsage({ orgId, window });

  return (
    <div className="flex flex-col gap-2">
      <div className="flex gap-2">
        {(["1d", "7d", "30d"] as const).map((w) => (
          <button
            key={w}
            onClick={() => setWindow(w)}
            className={`px-3 py-1 rounded text-sm ${window === w ? "bg-primary text-white" : "bg-muted"}`}
          >
            {w}
          </button>
        ))}
      </div>
      <div className="grid grid-cols-4 gap-3">
        <Card label="Runs" value={data?.runs ?? 0} />
        <Card label="Run-minutes" value={Math.round((data?.run_seconds ?? 0) / 60)} />
        <Card label="Tokens" value={data?.tokens ?? 0} />
        <Card label="Cost" value={formatCents(data?.cost_cents ?? 0)} />
      </div>
    </div>
  );
}

function Card({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded border p-4">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="text-2xl font-semibold">{value}</div>
    </div>
  );
}

function formatCents(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}
