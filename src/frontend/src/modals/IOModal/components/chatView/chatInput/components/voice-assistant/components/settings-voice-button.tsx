import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Button } from "@/components/ui/button";

interface SettingsVoiceButtonProps {
  isRecording: boolean;
  setShowSettingsModal: (value: boolean) => void;
}

const SettingsVoiceButton = ({
  isRecording,
  setShowSettingsModal,
}: SettingsVoiceButtonProps) => {
  return (
    <>
      <Tooltip delayDuration={500}>
        <TooltipTrigger asChild>
          <div>
            <Button
              className={`btn-playground-actions cursor-pointer text-muted-foreground hover:text-primary`}
              unstyled
              disabled={isRecording}
              onClick={() => setShowSettingsModal(true)}
            >
              <ForwardedIconComponent
                className={`h-[18px] w-[18px]`}
                name={"Wrench"}
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
          Audio Settings
        </TooltipContent>
      </Tooltip>
    </>
  );
};

export default SettingsVoiceButton;
