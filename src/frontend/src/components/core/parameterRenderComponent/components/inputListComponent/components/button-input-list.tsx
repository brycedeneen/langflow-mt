import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { ICON_STROKE_WIDTH } from "@/constants/constants";
import { cn } from "@/utils/utils";
import { getButtonClassName } from "../helpers/get-class-name";
import { getTestId } from "../helpers/get-test-id";

export const ButtonInputList = ({
  index,
  addNewInput,
  disabled,
  editNode,
  componentName,
  listAddLabel,
}: {
  index: number;
  addNewInput: (e) => void;
  disabled: boolean;
  editNode: boolean;
  componentName: string;
  listAddLabel: string;
}) => {
  return (
    <>
      <Tooltip delayDuration={500}>
        <TooltipTrigger asChild>
        <div
          onClick={addNewInput}
          className={cn(
            "hit-area-icon group absolute -top-8 right-0 flex items-center justify-center bg-background text-center hover:bg-muted",
            disabled
              ? "pointer-events-none bg-background hover:bg-background"
              : "",
          )}
        >
          <Button
            unstyled
            size="icon"
            className={cn(
              "hit-area-icon flex items-center justify-center",
              getButtonClassName(disabled),
            )}
            data-testid={getTestId("plus", index, editNode, componentName)}
            disabled={disabled}
          >
            <Plus
              className={cn(
                "icon-size justify-self-center text-muted-foreground",
                !disabled && "hover:cursor-pointer hover:text-foreground",
                "group-hover:text-foreground",
              )}
              strokeWidth={ICON_STROKE_WIDTH}
            />
          </Button>
        </div>
        </TooltipTrigger>
        <TooltipContent
          className="z-[99] max-w-96 bg-tooltip text-xs text-tooltip-foreground"
          side="top"
          avoidCollisions={false}
          sticky="always"
        >
          {listAddLabel}
        </TooltipContent>
      </Tooltip>
    </>
  );
};
