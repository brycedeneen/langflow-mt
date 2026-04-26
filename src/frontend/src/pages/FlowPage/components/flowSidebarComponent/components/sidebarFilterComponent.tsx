import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Button } from "@/components/ui/button";

export function SidebarFilterComponent({
  name,
  description,
  resetFilters,
}: {
  name: string;
  description: string;
  resetFilters: () => void;
}) {
  const tooltips = description.split("\n");
  const plural = tooltips.length > 1 ? "s" : "";
  return (
    <div
      className={`mb-0.5 flex w-full items-center overflow-hidden justify-between rounded border p-2 text-sm text-foreground`}
    >
      <div className="flex flex-1 items-center gap-1.5 overflow-hidden">
        <ForwardedIconComponent
          name="ListFilter"
          className={`h-4 w-4 shrink-0 stroke-2`}
        />
        <div className="flex flex-1 overflow-hidden">
          {name}
          {plural}:{" "}
          <div className="flex-1 overflow-hidden truncate pl-1">
            {tooltips.join(", ")}
          </div>
        </div>
      </div>
      <Tooltip delayDuration={500}>
        <TooltipTrigger asChild>
          <Button
            unstyled
            className="shrink-0"
            onClick={resetFilters}
            data-testid="sidebar-filter-reset"
          >
            <ForwardedIconComponent
              name="X"
              className="h-4 w-4 stroke-2"
              aria-hidden="true"
            />
          </Button>
        </TooltipTrigger>
        <TooltipContent
          className="z-[99] max-w-96 bg-tooltip text-xs text-tooltip-foreground max-w-full"
          side="right"
          avoidCollisions={false}
          sticky="always"
        >
          Remove filter
        </TooltipContent>
      </Tooltip>
    </div>
  );
}
