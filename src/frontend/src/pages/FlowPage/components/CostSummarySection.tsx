import { Line, LineChart, ResponsiveContainer } from "recharts";
import { useGetFlowCostSummary } from "@/controllers/API/queries/usage/use-get-flow-cost-summary";

type Props = { flowId: string };

export default function CostSummarySection({ flowId }: Props) {
  const { data } = useGetFlowCostSummary({ flowId });
  if (!data) return null;
  const sparkline = (data.sparkline ?? []).map((p) => ({
    date: p.date,
    cost: p.cost_cents,
  }));
  return (
    <div className="rounded border p-3 flex items-center gap-4">
      <div>
        <div className="text-xs text-muted-foreground">30d cost</div>
        <div className="text-lg font-semibold">
          ${(data.total_cost_cents / 100).toFixed(2)}
        </div>
      </div>
      <div style={{ width: 200, height: 40 }}>
        <ResponsiveContainer>
          <LineChart data={sparkline}>
            <Line dataKey="cost" type="monotone" strokeWidth={1.5} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
