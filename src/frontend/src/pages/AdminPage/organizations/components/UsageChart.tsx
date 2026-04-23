import { useState } from "react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useGetOrgUsageCharts } from "@/controllers/API/queries/usage/use-get-org-usage-charts";

type Metric = "runs" | "run_seconds" | "tokens" | "cost_cents";
type Props = { orgId: string };

export default function UsageChart({ orgId }: Props) {
  const [metric, setMetric] = useState<Metric>("runs");
  const { data } = useGetOrgUsageCharts({ orgId, metric, window: "30d" });
  const rows = (data?.series ?? []).map((p) => ({ date: p.date, value: p.value }));

  return (
    <div className="flex flex-col gap-2">
      <div className="flex gap-2">
        {(["runs", "run_seconds", "tokens", "cost_cents"] as const).map((m) => (
          <button
            key={m}
            onClick={() => setMetric(m)}
            className={`px-2 py-1 rounded text-sm ${metric === m ? "bg-primary text-white" : "bg-muted"}`}
          >
            {m}
          </button>
        ))}
      </div>
      <div style={{ width: "100%", height: 260 }}>
        <ResponsiveContainer>
          <LineChart data={rows}>
            <XAxis dataKey="date" tickFormatter={(s: string) => s.slice(5)} />
            <YAxis />
            <Tooltip />
            <Line dataKey="value" type="monotone" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
