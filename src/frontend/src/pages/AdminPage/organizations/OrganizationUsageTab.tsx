import PerFlowTable from "./components/PerFlowTable";
import UsageChart from "./components/UsageChart";
import UsageKpiCards from "./components/UsageKpiCards";

type Props = { orgId: string };

export default function OrganizationUsageTab({ orgId }: Props) {
  return (
    <div className="flex flex-col gap-6 p-4">
      <UsageKpiCards orgId={orgId} />
      <UsageChart orgId={orgId} />
      <PerFlowTable orgId={orgId} />
    </div>
  );
}
