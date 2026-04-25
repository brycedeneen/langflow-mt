import { memo } from "react";
import { areInputPropsEqual } from "@/components/core/parameterRenderComponent/areInputPropsEqual";
import CodeAreaModal from "@/modals/codeAreaModal";
import { useCustomComponentsAllowed } from "@/utils/customComponentGuards";
import { cn } from "../../../../../utils/utils";
import IconComponent from "../../../../common/genericIconComponent";
import { Button } from "../../../../ui/button";
import { getPlaceholder } from "../../helpers/get-placeholder-disabled";
import type { InputProps } from "../../types";

const codeContentClasses = {
  base: "overflow-hidden text-clip whitespace-nowrap",
  editNode: "input-edit-node input-dialog",
  normal: "primary-input text-muted-foreground",
  disabled: "disabled-state",
};

const externalLinkIconClasses = {
  background: ({
    disabled,
    editNode,
  }: {
    disabled: boolean;
    editNode: boolean;
  }) =>
    disabled
      ? ""
      : editNode
        ? "background-fade-input-edit-node"
        : "background-fade-input",
  icon: "icons-parameters-comp absolute right-3 h-4 w-4 shrink-0",
  editNodeTop: "top-[6px]",
  normalTop: "top-2.5",
};

function CodeAreaComponent({
  value,
  handleOnNewValue,
  disabled,
  editNode = false,
  nodeClass,
  handleNodeClass,
  id = "",
  placeholder,
  showParameter = true,
}: InputProps<string>): JSX.Element | null {
  // Force read-only editing for gated tenants (Task 10).
  const customAllowed = useCustomComponentsAllowed();

  const renderCodeText = () => (
    <span
      id={id}
      data-testid={id}
      className={cn(
        codeContentClasses.base,
        editNode ? codeContentClasses.editNode : codeContentClasses.normal,
        disabled && !editNode && codeContentClasses.disabled,
      )}
    >
      {value !== "" ? value : getPlaceholder(disabled, placeholder)}
    </span>
  );

  const renderExternalLinkIcon = () => (
    <>
      <div
        className={cn(
          externalLinkIconClasses.background({ disabled, editNode }),
          editNode
            ? externalLinkIconClasses.editNodeTop
            : externalLinkIconClasses.normalTop,
          disabled && "bg-border",
        )}
        aria-hidden="true"
      />
      <IconComponent
        name={disabled ? "lock" : "Scan"}
        className={cn(
          externalLinkIconClasses.icon,
          editNode
            ? externalLinkIconClasses.editNodeTop
            : externalLinkIconClasses.normalTop,
          disabled ? "text-placeholder-foreground" : "text-foreground",
        )}
      />
    </>
  );

  if (!showParameter) {
    return null;
  }

  return (
    <div className={cn("w-full", disabled && "pointer-events-none")}>
      <CodeAreaModal
        dynamic={false}
        value={value}
        nodeClass={nodeClass}
        setNodeClass={handleNodeClass!}
        setValue={(newValue) => handleOnNewValue({ value: newValue })}
        readonly={!customAllowed}
      >
        <Button unstyled className="w-full">
          <div className="relative w-full">
            {renderCodeText()}
            {renderExternalLinkIcon()}
          </div>
        </Button>
      </CodeAreaModal>
    </div>
  );
}

export default memo(CodeAreaComponent, areInputPropsEqual);
