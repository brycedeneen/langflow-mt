import { useNavigate } from "react-router-dom";
import { useGetOrgUsageFlows } from "@/controllers/API/queries/usage/use-get-org-usage-flows";

type Props = { orgId: string };

export default function PerFlowTable({ orgId }: Props) {
  const navigate = useNavigate();
  const { data } = useGetOrgUsageFlows({ orgId, window: "30d" });
  const items = data?.items ?? [];

  if (items.length === 0) {
    return <div className="text-muted-foreground text-sm">No flow usage data yet.</div>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-muted-foreground">
            <th className="pb-2 pr-4">Flow</th>
            <th className="pb-2 pr-4 text-right">Runs</th>
            <th className="pb-2 pr-4 text-right">Run-min</th>
            <th className="pb-2 pr-4 text-right">Tokens</th>
            <th className="pb-2 text-right">Cost</th>
          </tr>
        </thead>
        <tbody>
          {items.map((row) => (
            <tr
              key={row.flow_id}
              className="border-b cursor-pointer hover:bg-muted/50"
              onClick={() => navigate(`/flow/${row.flow_id}`)}
            >
              <td className="py-2 pr-4">{row.name}</td>
              <td className="py-2 pr-4 text-right">{row.runs}</td>
              <td className="py-2 pr-4 text-right">{Math.round(row.run_seconds / 60)}</td>
              <td className="py-2 pr-4 text-right">{row.tokens.toLocaleString()}</td>
              <td className="py-2 text-right">${(row.cost_cents / 100).toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
