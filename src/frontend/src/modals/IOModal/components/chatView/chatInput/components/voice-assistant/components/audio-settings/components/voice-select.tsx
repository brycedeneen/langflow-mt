import { OPENAI_VOICES } from "@/constants/constants";
import { Info } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "../../../../../../../../../../components/ui/tooltip";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../../../../../../../../../../components/ui/select";
import { toTitleCase } from "../../../../../../../../../../utils/utils";

interface VoiceSelectProps {
  voice: string;
  handleSetVoice: (value: string) => void;
  allVoices: { value: string; name: string }[];
}

const VoiceSelect = ({
  voice,
  handleSetVoice,
  allVoices,
}: VoiceSelectProps) => {
  allVoices = allVoices?.length === 0 || !allVoices ? OPENAI_VOICES : allVoices;

  return (
    <div className="grid w-full items-center gap-2">
      <span className="flex w-full items-center text-sm">
        Voice
        <Tooltip delayDuration={500}>
          <TooltipTrigger asChild>
            <div>
              <Info
                strokeWidth={2}
                className="relative -top-[3px] left-1 h-[14px] w-[14px] text-placeholder"
              />
            </div>
          </TooltipTrigger>
          <TooltipContent
            className="z-[99] max-w-96 bg-tooltip text-xs text-tooltip-foreground"
            avoidCollisions={false}
            sticky="always"
          >
            You can select ElevenLabs voices if you have an ElevenLabs API key. Otherwise, you can only select OpenAI voices.
          </TooltipContent>
        </Tooltip>
      </span>

      <Select value={voice} onValueChange={handleSetVoice}>
        <SelectTrigger className="h-9 w-full">
          <SelectValue placeholder="Select" />
        </SelectTrigger>
        <SelectContent className="max-h-[200px]">
          <SelectGroup>
            {allVoices?.map((voice, index) => (
              <SelectItem value={voice?.value} key={voice?.value}>
                <div className="max-w-[220px] truncate text-left">
                  {toTitleCase(voice?.name)}
                </div>
              </SelectItem>
            ))}
          </SelectGroup>
        </SelectContent>
      </Select>
    </div>
  );
};

export default VoiceSelect;
