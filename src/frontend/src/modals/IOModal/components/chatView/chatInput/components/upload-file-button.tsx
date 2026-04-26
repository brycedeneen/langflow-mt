import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Image } from "lucide-react";
import { Button } from "../../../../../../components/ui/button";

const UploadFileButton = ({
  fileInputRef,
  handleFileChange,
  handleButtonClick,
  isBuilding,
}) => {
  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    handleButtonClick();
  };

  return (
    <Tooltip delayDuration={500}>
      <TooltipTrigger asChild>
        <div>
          <input
            disabled={isBuilding}
            type="file"
            ref={fileInputRef}
            style={{ display: "none" }}
            onChange={handleFileChange}
          />
          <Button
            disabled={isBuilding}
            className={`btn-playground-actions ${
              isBuilding
                ? "cursor-not-allowed"
                : "text-muted-foreground hover:text-primary"
            }`}
            onClick={handleClick}
            unstyled
          >
            <Image className="h-[18px] w-[18px]" />
          </Button>
        </div>
      </TooltipTrigger>
      <TooltipContent
        className="z-[99] max-w-96 bg-tooltip text-xs text-tooltip-foreground z-50"
        side="right"
        avoidCollisions={false}
        sticky="always"
      >
        Attach image (png, jpg, jpeg)
      </TooltipContent>
    </Tooltip>
  );
};

export default UploadFileButton;
