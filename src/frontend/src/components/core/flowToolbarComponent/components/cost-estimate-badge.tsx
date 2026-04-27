import { useState } from "react";
import { DollarSign } from "lucide-react";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useEstimateFlowCost } from "@/controllers/API/queries/usage/use-estimate-flow-cost";
import useFlowsManagerStore from "@/stores/flowsManagerStore";

const formatCents = (cents: number) => {
  const dollars = cents / 100;
  if (dollars > 0 && dollars < 0.01) return "<$0.01";
  return `$${dollars.toFixed(2)}`;
};

export default function CostEstimateBadge() {
  const flowId = useFlowsManagerStore((s) => s.currentFlow?.id) || "";
  const { mutate, data, isPending } = useEstimateFlowCost();
  const [open, setOpen] = useState(false);

  const onOpen = (o: boolean) => {
    setOpen(o);
    if (o && flowId && !data) mutate({ flowId });
  };

  const estimate = data?.estimate;
  const expectedDollars = estimate ? estimate.expected_cost_cents / 100 : 0;
  const label =
    !estimate
      ? isPending ? "…" : "Estimate"
      : estimate.confidence === "none"
      ? "?"
      : expectedDollars > 0 && expectedDollars < 0.01
      ? "<$0.01/run"
      : `~$${expectedDollars.toFixed(2)}/run`;

  const pillClass =
    !estimate
      ? "border"
      : estimate.confidence === "low"
      ? "border border-dashed"
      : "border";

  return (
    <Popover open={open} onOpenChange={onOpen}>
      <PopoverTrigger asChild>
        <button
          className={`rounded px-2 py-1 text-sm ${pillClass}`}
          data-testid="cost-estimate-badge"
        >
          <DollarSign className="inline h-4 w-4 mr-1" />
          {label}
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-80">
        <div className="text-xs text-muted-foreground mb-2">
          Estimate — actual cost varies based on inputs and agent loops.
        </div>
        {data?.per_component?.length ? (
          <ul className="flex flex-col gap-1 text-sm">
            {data.per_component.map((c, i) => (
              <li key={i} className="flex justify-between">
                <span>{c.kind} · {c.model || "?"}</span>
                <span>{c.unknown ? "?" : formatCents(c.cost_cents)}</span>
              </li>
            ))}
          </ul>
        ) : null}
      </PopoverContent>
    </Popover>
  );
}
