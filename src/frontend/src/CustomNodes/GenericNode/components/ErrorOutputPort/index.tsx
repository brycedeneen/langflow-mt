import { Handle, Position } from "@xyflow/react";
import { TriangleAlert } from "lucide-react";
import { memo } from "react";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { scapedJSONStringfy } from "@/utils/reactflowUtils";
import { cn } from "@/utils/utils";

const ERROR_PORT_TOOLTIP =
  "Error output — connects to an Error Handler or Agent.";

/**
 * Renders a dedicated error output port at the bottom of a node's output stack.
 * Shown when a node has an output named "error" with types=["ErrorPayload"].
 *
 * Styling uses --destructive Tailwind token (NOT the ADP brand red #ED1C2E).
 */
const ErrorOutputPort = memo(function ErrorOutputPort({
  nodeId,
  dataType,
  showNode,
}: {
  nodeId: string;
  dataType: string;
  showNode: boolean;
}) {
  const handleId = scapedJSONStringfy({
    output_types: ["ErrorPayload"],
    id: nodeId,
    dataType,
    name: "error",
  });

  if (!showNode) {
    // Collapsed node: render a bare handle with no row UI
    return (
      <Handle
        type="source"
        position={Position.Right}
        id={handleId}
        data-testid="output-port-error"
        className="z-50"
        style={{
          width: "32px",
          height: "32px",
          top: "50%",
          position: "absolute",
          background: "transparent",
          border: "none",
        }}
      />
    );
  }

  return (
    <div
      data-testid="output-port-error"
      className={cn(
        "relative flex h-11 w-full flex-wrap items-center justify-between",
        "rounded-b-[0.69rem] bg-muted px-5 py-2",
        "border-t border-destructive/30",
      )}
    >
      <div className="flex w-full items-center justify-end gap-2 truncate text-sm">
        <Tooltip delayDuration={500}>
          <TooltipTrigger asChild>
            <span className="flex cursor-default items-center gap-1.5 text-destructive">
              <TriangleAlert className="h-3.5 w-3.5 shrink-0" strokeWidth={2} />
              <span className="text-xs font-medium text-destructive">
                Error
              </span>
            </span>
          </TooltipTrigger>
          <TooltipContent
            className="z-[99] max-w-96 bg-tooltip text-xs text-tooltip-foreground"
            side="right"
            avoidCollisions={false}
            sticky="always"
          >
            {ERROR_PORT_TOOLTIP}
          </TooltipContent>
        </Tooltip>
      </div>

      <Handle
        type="source"
        position={Position.Right}
        id={handleId}
        className={cn("group/handle z-50 transition-all")}
        style={{
          width: "32px",
          height: "32px",
          top: "50%",
          position: "absolute",
          background: "transparent",
          border: "none",
          right: "-16px",
        }}
      >
        {/* Visible dot — styled with destructive token */}
        <div
          className={cn(
            "pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2",
            "h-2.5 w-2.5 rounded-full",
            "bg-destructive",
          )}
          style={{
            boxShadow: "0 0 0 3px hsl(var(--destructive))",
          }}
        />
      </Handle>
    </div>
  );
});

export default ErrorOutputPort;
