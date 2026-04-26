import { useEffect, useState } from "react";
import IconComponent from "@/components/common/genericIconComponent";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Button } from "@/components/ui/button";
import type { TableOptionsTypeAPI } from "@/types/api";
import { cn } from "@/utils/utils";

export default function TableOptions({
  resetGrid,
  duplicateRow,
  deleteRow,
  hasSelection,
  stateChange,
  paginationInfo,
  addRow,
  tableOptions,
}: {
  resetGrid: () => void;
  duplicateRow?: () => void;
  deleteRow?: () => void;
  addRow?: () => void;
  hasSelection: boolean;
  stateChange: boolean;
  tableOptions?: TableOptionsTypeAPI;
  paginationInfo?: string;
}): JSX.Element {
  const [tabIndex, setTabIndex] = useState(-1);

  useEffect(() => {
    setTimeout(() => {
      setTabIndex(0);
    }, 10);
  }, []);

  return (
    <div className={cn("absolute bottom-3 left-6")}>
      <div className="flex items-center gap-3">
        {addRow && !tableOptions?.block_add && (
          <div>
            <Tooltip delayDuration={500}>
              <TooltipTrigger asChild>
                <Button
                  data-testid="add-row-button"
                  unstyled
                  onClick={addRow}
                  tabIndex={tabIndex}
                >
                  <IconComponent
                    name="Plus"
                    className={cn("h-5 w-5 text-primary transition-all")}
                  />
                </Button>
              </TooltipTrigger>
              <TooltipContent
                className="z-[99] max-w-96 bg-tooltip text-xs text-tooltip-foreground"
                avoidCollisions={false}
                sticky="always"
              >
                Add a new row
              </TooltipContent>
            </Tooltip>
          </div>
        )}
        {duplicateRow && (
          <div>
            <Tooltip delayDuration={500}>
              <TooltipTrigger asChild>
                <Button
                  data-testid="duplicate-row-button"
                  unstyled
                  onClick={duplicateRow}
                  disabled={!hasSelection}
                  tabIndex={tabIndex}
                >
                  <IconComponent
                    name="Copy"
                    className={cn(
                      "h-5 w-5 transition-all",
                      hasSelection
                        ? "text-primary"
                        : "cursor-not-allowed text-placeholder-foreground",
                    )}
                  />
                </Button>
              </TooltipTrigger>
              <TooltipContent
                className="z-[99] max-w-96 bg-tooltip text-xs text-tooltip-foreground"
                avoidCollisions={false}
                sticky="always"
              >
                {!hasSelection ? (
                  <span>Select items to duplicate</span>
                ) : (
                  <span>Duplicate selected items</span>
                )}
              </TooltipContent>
            </Tooltip>
          </div>
        )}
        {deleteRow && (
          <div>
            <Tooltip delayDuration={500}>
              <TooltipTrigger asChild>
                <Button
                  data-testid="delete-row-button"
                  unstyled
                  onClick={deleteRow}
                  disabled={!hasSelection}
                  tabIndex={tabIndex}
                >
                  <IconComponent
                    name="Trash2"
                    className={cn(
                      "h-5 w-5 transition-all",
                      !hasSelection
                        ? "cursor-not-allowed text-placeholder-foreground"
                        : "text-primary hover:text-status-red",
                    )}
                  />
                </Button>
              </TooltipTrigger>
              <TooltipContent
                className="z-[99] max-w-96 bg-tooltip text-xs text-tooltip-foreground"
                avoidCollisions={false}
                sticky="always"
              >
                {!hasSelection ? (
                  <span>Select items to delete</span>
                ) : (
                  <span>Delete selected items</span>
                )}
              </TooltipContent>
            </Tooltip>
          </div>
        )}{" "}
        <div>
          <Tooltip delayDuration={500}>
            <TooltipTrigger asChild>
              <Button
                data-testid="reset-columns-button"
                unstyled
                onClick={() => {
                  resetGrid();
                }}
                disabled={!stateChange}
                tabIndex={tabIndex}
              >
                <IconComponent
                  name="RotateCcw"
                  strokeWidth={2}
                  className={cn(
                    "h-5 w-5 transition-all",
                    !stateChange
                      ? "cursor-not-allowed text-placeholder-foreground"
                      : "text-primary",
                  )}
                />
              </Button>
            </TooltipTrigger>
            <TooltipContent
              className="z-[99] max-w-96 bg-tooltip text-xs text-tooltip-foreground"
              avoidCollisions={false}
              sticky="always"
            >
              Reset Columns
            </TooltipContent>
          </Tooltip>
        </div>
        {paginationInfo && (
          <div className="ml-2 text-xs text-muted-foreground">
            <Tooltip delayDuration={500}>
              <TooltipTrigger asChild>
                <span>{paginationInfo}</span>
              </TooltipTrigger>
              <TooltipContent
                className="z-[99] max-w-96 bg-tooltip text-xs text-tooltip-foreground"
                avoidCollisions={false}
                sticky="always"
              >
                Pagination Info
              </TooltipContent>
            </Tooltip>
          </div>
        )}
      </div>
    </div>
  );
}
