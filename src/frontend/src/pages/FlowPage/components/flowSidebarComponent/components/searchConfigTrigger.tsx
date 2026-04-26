import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Button } from "@/components/ui/button";

interface SearchConfigTriggerProps {
  showConfig: boolean;
  setShowConfig: (show: boolean) => void;
}

export const SearchConfigTrigger = ({
  showConfig,
  setShowConfig,
}: SearchConfigTriggerProps) => {
  return (
    <div className="flex items-center justify-center">
      <Tooltip delayDuration={500}>
        <TooltipTrigger asChild>
          <Button
            variant={showConfig ? "ghostActive" : "ghost"}
            size="iconMd"
            data-testid="sidebar-options-trigger"
            onClick={() => setShowConfig(!showConfig)}
            className="hover:text-primary text-muted-foreground"
            style={{ padding: "0px" }}
          >
            <ForwardedIconComponent name="Settings2" className="h-4 w-4" />
          </Button>
        </TooltipTrigger>
        <TooltipContent
          className="z-[99] max-w-96 bg-tooltip text-xs text-tooltip-foreground z-50"
          avoidCollisions={false}
          sticky="always"
        >
          Component settings
        </TooltipContent>
      </Tooltip>
    </div>
  );
};
