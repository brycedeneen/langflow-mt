import _ from "lodash";
import { memo, useCallback, useEffect, useRef, useState } from "react";
import { areInputPropsEqual } from "@/components/core/parameterRenderComponent/areInputPropsEqual";

import { Button } from "@/components/ui/button";
import { cn } from "../../../../../utils/utils";
import { getPlaceholder } from "../../helpers/get-placeholder-disabled";
import type { InputListComponentType, InputProps } from "../../types";
import { ButtonInputList } from "./components/button-input-list";
import { CursorInput } from "./components/cursor-input";
import { DeleteButtonInputList } from "./components/delete-button-input-list";

function InputListComponent({
  value = [""],
  handleOnNewValue,
  disabled,
  editNode = false,
  componentName,
  id,
  placeholder,
  listAddLabel,
  showParameter = true,
}: InputProps<string[], InputListComponentType>): JSX.Element | null {
  const [_dropdownOpen, setDropdownOpen] = useState<number | null>(null);
  const [focusedIndex, setFocusedIndex] = useState<number | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (disabled && value.length > 0 && value[0] !== "") {
      handleOnNewValue({ value: [""] }, { skipSnapshot: true });
    }
  }, [disabled, handleOnNewValue, value]);

  if (typeof value === "string") {
    value = [value];
  }
  if (!value?.length) value = [""];

  // Stable per-row React keys so removing a middle row doesn't shift focus
  // onto an unrelated input. We can't add an _id field to the wire format
  // (it's a `string[]` boundary), so we maintain a parallel ids ref that
  // stays in lockstep with `value` via the explicit add/remove handlers
  // below; on external value-length changes we best-effort grow/truncate.
  const idsRef = useRef<string[]>([]);
  while (idsRef.current.length < value.length) {
    idsRef.current.push(crypto.randomUUID());
  }
  if (idsRef.current.length > value.length) {
    idsRef.current = idsRef.current.slice(0, value.length);
  }

  if (!showParameter) {
    return null;
  }

  const handleInputChange = useCallback(
    (index: number, newValue: string) => {
      const newInputList = _.cloneDeep(value);
      newInputList[index] = newValue;
      handleOnNewValue({ value: newInputList });
    },
    [value, handleOnNewValue],
  );

  const addNewInput = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      const newInputList = _.cloneDeep(value);
      newInputList.push("");
      idsRef.current = [...idsRef.current, crypto.randomUUID()];
      handleOnNewValue({ value: newInputList });
    },
    [value, handleOnNewValue],
  );

  const removeInput = useCallback(
    (index: number, e: React.MouseEvent | KeyboardEvent) => {
      e.preventDefault();
      const newInputList = _.cloneDeep(value);
      newInputList.splice(index, 1);
      idsRef.current = idsRef.current.filter((_, i) => i !== index);
      handleOnNewValue({ value: newInputList });
      setDropdownOpen(null);
    },
    [value, handleOnNewValue],
  );

  // const handleDuplicateInput = useCallback(
  //   (index: number, e: React.MouseEvent | KeyboardEvent) => {
  //     e.preventDefault();
  //     const newInputList = _.cloneDeep(value);
  //     newInputList.splice(index, 0, newInputList[index]);
  //     handleOnNewValue({ value: newInputList });
  //     setDropdownOpen(null);
  //   },
  //   [value, handleOnNewValue],
  // );

  return (
    <div className={cn("relative w-full", editNode && "max-h-52")}>
      {!editNode && !disabled && (
        <ButtonInputList
          index={0}
          addNewInput={addNewInput}
          disabled={disabled}
          editNode={editNode}
          componentName={componentName || ""}
          listAddLabel={listAddLabel || "Add More"}
        />
      )}

      <div className="flex w-full flex-col gap-2">
        {value.map((singleValue, index) => (
          <div
            key={idsRef.current[index] ?? `input-list-fallback-${index}`}
            className="flex w-full items-center"
          >
            <div className="group relative flex-1">
              <CursorInput
                ref={index === 0 ? inputRef : null}
                disabled={disabled}
                value={singleValue}
                className={cn(value.length > 1 && "pr-10")}
                placeholder={getPlaceholder(disabled, placeholder)}
                onChange={(newValue) => handleInputChange(index, newValue)}
                dataTestId={`${id}_${index}`}
                editNode={editNode}
                onFocus={() => setFocusedIndex(index)}
                onBlur={() => setFocusedIndex(null)}
              />

              {value.length > 1 && (
                <div className="absolute right-2 top-1/2 -translate-y-1/2">
                  <DeleteButtonInputList
                    index={index}
                    removeInput={(e) => removeInput(index, e)}
                    disabled={disabled}
                    editNode={editNode}
                    componentName={componentName || ""}
                  />
                </div>
              )}
              {focusedIndex !== index && !disabled && (
                <div className="pointer-events-none absolute top-1/2 flex w-full -translate-y-1/2">
                  <div
                    className={cn(
                      "flex-1 cursor-text select-text text-nowrap pl-3 text-sm text-muted-foreground truncate-background",
                      value.length > 1 ? "mr-10" : "mr-3",
                    )}
                  >
                    <span className="opacity-0">{singleValue}</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
        {editNode && !disabled && (
          <Button
            unstyled
            onClick={addNewInput}
            className="flex h-6 w-full items-center justify-center rounded-md p-2 text-sm hover:bg-muted"
            data-testid={`input-list-add-more-${editNode ? "edit" : "view"}`}
          >
            <span className="mr-2 text-lg">+</span> {listAddLabel || "Add More"}
          </Button>
        )}
      </div>
    </div>
  );
}

export default memo(InputListComponent, areInputPropsEqual);
