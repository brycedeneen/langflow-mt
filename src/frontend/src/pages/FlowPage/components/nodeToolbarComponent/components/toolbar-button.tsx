import { memo } from "react";
import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/utils";
import ShortcutDisplay from "../shortcutDisplay";

export const ToolbarButton = memo(
  ({
    onClick,
    icon,
    label,
    shortcut,
    className,
    dataTestId,
  }: {
    onClick: () => void;
    icon: string;
    label?: string;
    shortcut?: any;
    className?: string;
    dataTestId?: string;
  }) => (
    <Tooltip delayDuration={500}>
      <TooltipTrigger asChild>
        <Button
          className={cn("node-toolbar-buttons", className)}
          variant="ghost"
          onClick={onClick}
          size="node-toolbar"
          data-testid={dataTestId}
        >
          <ForwardedIconComponent name={icon} className="h-4 w-4" />
          {label && <span className="text-mmd font-medium">{label}</span>}
        </Button>
      </TooltipTrigger>
      <TooltipContent
        className="z-[99] max-w-96 bg-tooltip text-xs text-tooltip-foreground"
        side="top"
        avoidCollisions={true}
        sticky="always"
      >
        <ShortcutDisplay {...shortcut} />
      </TooltipContent>
    </Tooltip>
  ),
);
