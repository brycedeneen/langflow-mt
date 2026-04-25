import { MinusIcon, PlusIcon } from "lucide-react";
import { useEffect, useRef } from "react";
import { ICON_STROKE_WIDTH } from "@/constants/constants";
import { cn } from "@/utils/utils";
import { handleKeyDown } from "../../../../../utils/reactflowUtils";
import type { InputProps, IntComponentType } from "../../types";

export default function IntComponent({
  value,
  handleOnNewValue,
  rangeSpec,
  name,
  disabled,
  editNode = false,
  id = "",
  readonly,
  showParameter = true,
}: InputProps<number, IntComponentType>): JSX.Element | null {
  const min = -Infinity;
  // Clear component state when disabled
  useEffect(() => {
    if (disabled && value !== 0) {
      handleOnNewValue({ value: 0 }, { skipSnapshot: true });
    }
  }, [disabled, handleOnNewValue]);

  const inputRef = useRef<HTMLInputElement>(null);

  const parseAndValidate = (raw: string): number | null => {
    const trimmed = raw.trim();
    if (trimmed === "") return null;
    const num = Number(trimmed);
    if (!Number.isFinite(num) || !Number.isInteger(num)) return null;
    const minVal = getMinValue();
    const maxVal = getMaxValue();
    if (num < minVal) return minVal;
    if (maxVal !== undefined && num > maxVal) return maxVal;
    return num;
  };

  const handleChangeInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value;
    const parsed = parseAndValidate(raw);
    handleOnNewValue({
      value: parsed !== null ? parsed : (null as unknown as number),
    });
  };

  const getStepValue = () => {
    return (Number.isInteger(rangeSpec?.step) ? rangeSpec?.step : 1) ?? 1;
  };

  const getMinValue = () => {
    // max_tokens must be at least 1; enforce even when rangeSpec is missing (e.g. saved flows)
    if (name === "max_tokens") {
      return rangeSpec?.min ?? 1;
    }
    return rangeSpec?.min ?? min;
  };

  const getMaxValue = () => {
    return rangeSpec?.max ?? undefined;
  };

  const minVal = getMinValue();
  const isAtOrBelowMin =
    typeof minVal === "number" &&
    Number.isFinite(minVal) &&
    (value == null || value <= minVal);

  // Clamp existing out-of-range values to min on load (e.g. max_tokens -14 -> 1).
  // For max_tokens, 0 means "empty/no limit" — do not clamp 0 to 1.
  useEffect(() => {
    if (
      typeof minVal === "number" &&
      Number.isFinite(minVal) &&
      typeof value === "number" &&
      value < minVal &&
      !(name === "max_tokens" && value === 0)
    ) {
      handleOnNewValue({ value: minVal }, { skipSnapshot: true });
    }
  }, [minVal, value, handleOnNewValue, name]);

  const handleNumberChange = (newValue: string | number) => {
    if (newValue === "" || newValue === undefined) {
      handleOnNewValue({ value: null as unknown as number });
      return;
    }
    const num = Number(newValue);
    if (!Number.isFinite(num)) {
      handleOnNewValue({ value: null as unknown as number });
      return;
    }
    const minLocal = getMinValue();
    const maxLocal = getMaxValue();
    let clamped = Math.round(num);
    if (clamped < minLocal) clamped = minLocal;
    if (maxLocal !== undefined && clamped > maxLocal) clamped = maxLocal;
    handleOnNewValue({ value: clamped });
  };

  const handleInputEvent = (event: React.FormEvent<HTMLInputElement>) => {
    const inputValue = Number((event.target as HTMLInputElement).value);
    if (Number.isFinite(inputValue) && inputValue < getMinValue()) {
      (event.target as HTMLInputElement).value = getMinValue().toString();
    }
  };

  const adjustValue = (delta: number) => {
    const current = typeof value === "number" && Number.isFinite(value) ? value : 0;
    handleNumberChange(current + delta);
  };

  const baseInputClassName = cn(
    editNode ? "input-edit-node" : "",
    "nopan nodelete nodrag noflow primary-input pr-7",
  );
  const DISABLED_INPUT_CLASS =
    "cursor-default bg-secondary border-border border rounded-md py-2 px-3 text-sm text-input placeholder:text-input pr-7";

  const iconClassName =
    "text-placeholder-foreground h-3 w-3 transition-colors";
  const stepperWrapperClassName =
    "absolute right-[1px] top-[1px] bottom-[1px] w-5 flex flex-col rounded-r-sm border-l-[1px] border-border overflow-hidden";
  const stepButtonClassName =
    "flex flex-1 items-center justify-center hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50";

  if (!showParameter) {
    return null;
  }

  const isDisabled = Boolean(disabled || readonly);
  const step = getStepValue();
  const displayValue =
    name === "max_tokens" && (value === 0 || value === null)
      ? ""
      : (value ?? "");

  return (
    <div className="relative w-full">
      <input
        id={id}
        type="number"
        step={step}
        min={getMinValue()}
        max={getMaxValue()}
        value={displayValue}
        onChange={handleChangeInput}
        onKeyDown={(event) => handleKeyDown(event, value, "")}
        onInput={handleInputEvent}
        disabled={isDisabled}
        placeholder={editNode ? "Integer number" : "Type an integer number"}
        data-testid={id}
        ref={inputRef}
        className={isDisabled ? DISABLED_INPUT_CLASS : baseInputClassName}
      />
      <div className={stepperWrapperClassName}>
        <button
          type="button"
          tabIndex={-1}
          onClick={() => adjustValue(step)}
          disabled={isDisabled}
          className={cn(
            stepButtonClassName,
            "border-b-[1px] border-border hover:rounded-tr-[5px]",
          )}
          aria-label="Increment"
        >
          <PlusIcon
            className={iconClassName}
            strokeWidth={ICON_STROKE_WIDTH}
          />
        </button>
        <button
          type="button"
          tabIndex={-1}
          onClick={() => adjustValue(-step)}
          disabled={isDisabled || isAtOrBelowMin}
          aria-disabled={isAtOrBelowMin || undefined}
          data-disabled={isAtOrBelowMin ? "" : undefined}
          className={cn(
            stepButtonClassName,
            "hover:rounded-br-[5px]",
            isAtOrBelowMin && "pointer-events-none opacity-50",
          )}
          aria-label="Decrement"
        >
          <MinusIcon
            className={iconClassName}
            strokeWidth={ICON_STROKE_WIDTH}
          />
        </button>
      </div>
    </div>
  );
}
