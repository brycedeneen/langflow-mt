import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Check, Copy } from "lucide-react";

export const ContentRenderKey = ({
  inputLabel,
  inputRef,
  apiKeyValue,
  handleCopyClick,
  textCopied,
  renderKey,
}: {
  inputLabel: string;
  inputRef: React.RefObject<HTMLInputElement | null>;
  apiKeyValue: string;
  handleCopyClick: () => void;
  textCopied: boolean;
  renderKey: boolean;
}) => {
  return (
    <>
      <div className="flex items-center gap-3">
        <div className="w-full">
          {inputLabel && !renderKey && (
            <div className="relative bottom-1">
              {inputLabel as React.ReactNode}
            </div>
          )}

          <Input
            data-testid="api-key-input"
            ref={inputRef}
            readOnly={true}
            value={apiKeyValue}
          />
        </div>

        <Button
          onClick={(e) => {
            handleCopyClick();
            e.stopPropagation();
          }}
          data-testid="btn-copy-api-key"
          unstyled
        >
          {textCopied ? (
            <Copy className="h-4 w-4" />
          ) : (
            <Check className="h-4 w-4" />
          )}
        </Button>
      </div>
    </>
  );
};
