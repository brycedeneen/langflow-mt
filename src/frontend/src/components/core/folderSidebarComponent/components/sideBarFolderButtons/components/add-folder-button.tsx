import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/utils/utils";

export const AddFolderButton = ({
  onClick,
  disabled,
  loading,
}: {
  onClick: () => void;
  disabled: boolean;
  loading: boolean;
}) => (
  <Tooltip delayDuration={500}>
    <TooltipTrigger asChild>
      <Button
        variant="ghost"
        size="icon"
        className="h-7 w-7 border-0 text-muted-foreground hover:bg-muted"
        onClick={onClick}
        data-testid="add-project-button"
        disabled={disabled}
        loading={loading}
      >
        <IconComponent name="Plus" className="h-4 w-4" />
      </Button>
    </TooltipTrigger>
    <TooltipContent
      className={cn("z-[99] max-w-96 bg-tooltip text-xs text-tooltip-foreground", "z-50")}
      avoidCollisions={false}
      sticky="always"
    >
      Create new project
    </TooltipContent>
  </Tooltip>
);
