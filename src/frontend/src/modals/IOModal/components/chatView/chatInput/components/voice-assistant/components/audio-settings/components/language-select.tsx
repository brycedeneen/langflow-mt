import { ALL_LANGUAGES } from "@/constants/constants";
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

interface LanguageSelectProps {
  language: string;
  handleSetLanguage: (value: string) => void;
}

const LanguageSelect = ({
  language,
  handleSetLanguage,
}: LanguageSelectProps) => {
  return (
    <div className="grid w-full items-center gap-2">
      <span className="flex w-full items-center text-sm">
        Preferred Language
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
            Select the language for speech recognition
          </TooltipContent>
        </Tooltip>
      </span>

      <Select value={language} onValueChange={handleSetLanguage}>
        <SelectTrigger className="h-9 w-full">
          <SelectValue placeholder="Select language" />
        </SelectTrigger>
        <SelectContent className="max-h-[200px]">
          <SelectGroup>
            {ALL_LANGUAGES?.map((lang) => (
              <SelectItem key={lang?.value} value={lang?.value}>
                <div className="max-w-[220px] truncate text-left">
                  {lang?.name}
                </div>
              </SelectItem>
            ))}
          </SelectGroup>
        </SelectContent>
      </Select>
    </div>
  );
};

export default LanguageSelect;
