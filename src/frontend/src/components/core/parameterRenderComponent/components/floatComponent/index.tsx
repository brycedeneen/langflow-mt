import { MinusIcon, PlusIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { cn } from "@/utils/utils";
import { handleKeyDown } from "../../../../../utils/reactflowUtils";
import type { FloatComponentType, InputProps } from "../../types";

export default function FloatComponent({
  value,
  handleOnNewValue,
  rangeSpec,
  disabled,
  editNode = false,
  id = "",
  showParameter = true,
}: InputProps<number, FloatComponentType>): JSX.Element | null {
  const step = rangeSpec?.step ?? 0.1;
  const min = rangeSpec?.min;
  const max = rangeSpec?.max;

  // Local state for input value
  const [localValue, setLocalValue] = useState<string>(value.toString());

  // Clear component state
  useEffect(() => {
    if (disabled && value !== 0) {
      handleOnNewValue({ value: 0 }, { skipSnapshot: true });
    }
  }, [disabled, handleOnNewValue]);

  // Update local value when prop changes
  useEffect(() => {
    setLocalValue(value.toString());
  }, [value]);

  const inputRef = useRef<HTMLInputElement>(null);

  const handleChangeInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    setLocalValue(e.target.value);
  };

  const handleBlur = () => {
    handleOnNewValue({ value: Number(localValue) });
  };

  const handleInputEvent = (event: React.FormEvent<HTMLInputElement>) => {
    const inputValue = Number((event.target as HTMLInputElement).value);
    if (min !== undefined && inputValue < min) {
      (event.target as HTMLInputElement).value = min.toString();
    } else if (max !== undefined && inputValue > max) {
      (event.target as HTMLInputElement).value = max.toString();
    }
  };

  const adjustValue = (delta: number) => {
    const current = Number(localValue);
    let next = (Number.isFinite(current) ? current : 0) + delta;
    if (min !== undefined && next < min) next = min;
    if (max !== undefined && next > max) next = max;
    setLocalValue(String(next));
  };

  const inputClassName = cn(
    editNode ? "input-edit-node" : "",
    "nopan nodelete nodrag noflow primary-input",
    "pr-7",
    disabled ? "cursor-not-allowed opacity-50" : "",
  );

  const iconClassName =
    "text-placeholder-foreground h-3 w-3 transition-colors";
  const stepperWrapperClassName =
    "absolute right-[1px] top-[1px] bottom-[1px] w-5 flex flex-col rounded-r-sm border-l-[1px] border-border overflow-hidden";
  const stepButtonClassName =
    "flex flex-1 items-center justify-center hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50";

  if (!showParameter) {
    return null;
  }

  return (
    <div className="relative w-full">
      <input
        id={id}
        type="number"
        step={step}
        min={min}
        max={max}
        value={localValue ?? ""}
        onChange={handleChangeInput}
        onBlur={handleBlur}
        onKeyDown={(event) => handleKeyDown(event, localValue, "")}
        onInput={handleInputEvent}
        disabled={disabled}
        placeholder={editNode ? "Float number" : "Type a float number"}
        data-testid={id}
        ref={inputRef}
        className={inputClassName}
      />
      <div className={stepperWrapperClassName}>
        <button
          type="button"
          tabIndex={-1}
          onClick={() => adjustValue(step)}
          disabled={disabled}
          className={cn(
            stepButtonClassName,
            "border-b-[1px] border-border hover:rounded-tr-[5px]",
          )}
          aria-label="Increment"
        >
          <PlusIcon className={iconClassName} />
        </button>
        <button
          type="button"
          tabIndex={-1}
          onClick={() => adjustValue(-step)}
          disabled={disabled}
          className={cn(
            stepButtonClassName,
            "hover:rounded-br-[5px]",
          )}
          aria-label="Decrement"
        >
          <MinusIcon className={iconClassName} />
        </button>
      </div>
    </div>
  );
}
