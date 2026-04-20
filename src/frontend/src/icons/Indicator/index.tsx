import type React from "react";
import { forwardRef } from "react";
import { IndicatorComponent } from "./Indicator";

// `IndicatorComponent` is a JS component that accepts arbitrary props including
// `ref`; cast to any so TS doesn't object to the forwarded ref.
const IndicatorComponentAny = IndicatorComponent as any;

export const IndicatorIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{ className?: string }>
>((props, ref) => {
  return <IndicatorComponentAny ref={ref} {...props} />;
});
