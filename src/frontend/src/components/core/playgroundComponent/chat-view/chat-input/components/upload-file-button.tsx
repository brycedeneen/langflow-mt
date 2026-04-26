import { Image } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Button } from "@/components/ui/button";

interface UploadFileButtonProps {
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  handleFileChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  handleButtonClick: () => void;
  isBuilding: boolean;
}

const UploadFileButton = ({
  fileInputRef,
  handleFileChange,
  handleButtonClick,
  isBuilding,
}: UploadFileButtonProps) => {
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
            accept=".png,.jpg,.jpeg,image/png,image/jpeg"
          />
          <Button
            disabled={isBuilding}
            className={`h-7 w-7 px-0 flex items-center justify-center ${
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
