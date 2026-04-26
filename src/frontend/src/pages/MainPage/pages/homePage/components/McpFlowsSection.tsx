import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import ToolsComponent from "@/components/core/parameterRenderComponent/components/ToolsComponent";
import type { InputFieldType } from "@/types/api";
import type { ToolFlow } from "../utils/mcpServerUtils";

interface McpFlowsSectionProps {
  flowsMCPData: ToolFlow[];
  handleOnNewValue: (changes: Partial<InputFieldType>) => void;
}

export const McpFlowsSection = ({
  flowsMCPData,
  handleOnNewValue,
}: McpFlowsSectionProps) => (
  <div className="w-full xl:w-2/5">
    <div className="flex flex-row justify-between pt-1">
      <Tooltip delayDuration={500}>
        <TooltipTrigger asChild>
          <div className="flex items-center text-sm font-medium hover:cursor-help">
            Flows/Tools
            <ForwardedIconComponent
              name="info"
              className="ml-1.5 h-4 w-4 text-muted-foreground"
              aria-hidden="true"
            />
          </div>
        </TooltipTrigger>
        <TooltipContent
          className="z-[99] max-w-96 bg-tooltip text-xs text-tooltip-foreground"
          side="right"
          avoidCollisions={false}
          sticky="always"
        >
          Flows in this project can be exposed as callable MCP tools.
        </TooltipContent>
      </Tooltip>
    </div>
    <div className="flex flex-row flex-wrap gap-2 pt-2">
      <ToolsComponent
        value={flowsMCPData}
        title="MCP Server Tools"
        description="Select tools to add to this server"
        handleOnNewValue={handleOnNewValue}
        id="mcp-server-tools"
        button_description="Edit Tools"
        editNode={false}
        isAction
        disabled={false}
      />
    </div>
  </div>
);
