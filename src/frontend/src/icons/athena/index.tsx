import type React from "react";
import { forwardRef } from "react";
//@ts-ignore
import { AthenaComponent } from "./athena";

// `AthenaComponent` is a JS component that accepts arbitrary props including
// `ref`; cast to any so TS doesn't object to the forwarded ref.
const AthenaComponentAny = AthenaComponent as any;

export const AthenaIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{ className?: string }>
>((props, ref) => {
  return <AthenaComponentAny ref={ref} {...props} />;
});
