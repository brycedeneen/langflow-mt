import type React from "react";
import { forwardRef } from "react";
import { AIMLComponent } from "./AI-ML";

// `AIMLComponent` is a JS component that accepts arbitrary props including
// `ref`; cast to any so TS doesn't object to the forwarded ref.
const AIMLComponentAny = AIMLComponent as any;

export const AIMLIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{ className?: string }>
>((props, ref) => {
  return <AIMLComponentAny ref={ref} {...props} />;
});
