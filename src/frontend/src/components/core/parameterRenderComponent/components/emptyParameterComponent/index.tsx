import { memo } from "react";
import { areInputPropsEqual } from "@/components/core/parameterRenderComponent/areInputPropsEqual";
import type { InputProps } from "../../types";

function EmptyParameterComponentInner({
  id,
  value,
  editNode,
  handleOnNewValue,
  disabled,
  showParameter = true,
}: InputProps): JSX.Element | null {
  if (!showParameter) {
    return null;
  }
  return <div id={id}></div>;
}

export const EmptyParameterComponent = memo(EmptyParameterComponentInner, areInputPropsEqual);
