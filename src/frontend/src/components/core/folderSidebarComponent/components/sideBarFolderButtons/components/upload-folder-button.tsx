import { Upload } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Button } from "@/components/ui/button";

export const UploadFolderButton = ({ onClick, disabled }) => (
  <Tooltip delayDuration={500}>
    <TooltipTrigger asChild>
      <Button
        variant="ghost"
        size="icon"
        className="h-7 w-7 border-0 text-muted-foreground hover:bg-muted"
        onClick={onClick}
        data-testid="upload-project-button"
        disabled={disabled}
      >
        <Upload className="h-4 w-4" />
      </Button>
    </TooltipTrigger>
    <TooltipContent
      className="z-[99] max-w-96 bg-tooltip text-xs text-tooltip-foreground z-50"
      avoidCollisions={false}
      sticky="always"
    >
      Upload a flow
    </TooltipContent>
  </Tooltip>
);
