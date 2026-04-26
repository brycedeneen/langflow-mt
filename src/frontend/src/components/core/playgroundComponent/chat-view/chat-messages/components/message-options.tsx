import { type ButtonHTMLAttributes, useState } from "react";
import { Pen } from "lucide-react";
import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/utils/utils";

export function EditMessageButton({
  onEdit,
  onCopy,
  onEvaluate,
  isBotMessage,
  evaluation,
  isAudioMessage,
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  onEdit?: () => void;
  onCopy: () => void;
  onEvaluate?: (value: boolean | null) => void;
  isBotMessage?: boolean;
  evaluation?: boolean | null;
  isAudioMessage?: boolean;
}) {
  const [isCopied, setIsCopied] = useState(false);

  const handleCopy = () => {
    onCopy();
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  const handleEvaluate = (value: boolean) => {
    onEvaluate?.(evaluation === value ? null : value);
  };

  return (
    <div className="flex items-center rounded-md border border-border bg-background">
      {!isAudioMessage && onEdit && (
        <Tooltip delayDuration={500}>
          <TooltipTrigger asChild>
            <div className="p-1">
              <Button
                variant="ghost"
                size="icon"
                onClick={onEdit}
                className="h-8 w-8"
              >
                <Pen className="h-4 w-4" />
              </Button>
            </div>
          </TooltipTrigger>
          <TooltipContent
            className="z-[99] max-w-96 bg-tooltip text-xs text-tooltip-foreground z-50"
            side="top"
            avoidCollisions={false}
            sticky="always"
          >
            Edit message
          </TooltipContent>
        </Tooltip>
      )}

      <Tooltip delayDuration={500}>
        <TooltipTrigger asChild>
          <div className="p-1">
            <Button
              variant="ghost"
              size="icon"
              onClick={handleCopy}
              className="h-8 w-8"
            >
              <IconComponent
                name={isCopied ? "Check" : "Copy"}
                className="h-4 w-4"
              />
            </Button>
          </div>
        </TooltipTrigger>
        <TooltipContent
          className="z-[99] max-w-96 bg-tooltip text-xs text-tooltip-foreground z-50"
          side="top"
          avoidCollisions={false}
          sticky="always"
        >
          {isCopied ? "Copied!" : "Copy message"}
        </TooltipContent>
      </Tooltip>

      {isBotMessage && (
        <div className="flex">
          <Tooltip delayDuration={500}>
            <TooltipTrigger asChild>
              <div className="p-1">
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => handleEvaluate(true)}
                  className="h-8 w-8"
                  data-testid="helpful-button"
                >
                  <IconComponent
                    name={evaluation === true ? "ThumbUpIconCustom" : "ThumbsUp"}
                    className={cn("h-4 w-4")}
                  />
                </Button>
              </div>
            </TooltipTrigger>
            <TooltipContent
              className="z-[99] max-w-96 bg-tooltip text-xs text-tooltip-foreground z-50"
              side="top"
              avoidCollisions={false}
              sticky="always"
            >
              Helpful
            </TooltipContent>
          </Tooltip>

          <Tooltip delayDuration={500}>
            <TooltipTrigger asChild>
              <div className="p-1">
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => handleEvaluate(false)}
                  className="h-8 w-8"
                  data-testid="not-helpful-button"
                >
                  <IconComponent
                    name={
                      evaluation === false ? "ThumbDownIconCustom" : "ThumbsDown"
                    }
                    className={cn("h-4 w-4")}
                  />
                </Button>
              </div>
            </TooltipTrigger>
            <TooltipContent
              className="z-[99] max-w-96 bg-tooltip text-xs text-tooltip-foreground z-50"
              side="top"
              avoidCollisions={false}
              sticky="always"
            >
              Not helpful
            </TooltipContent>
          </Tooltip>
        </div>
      )}
    </div>
  );
}
