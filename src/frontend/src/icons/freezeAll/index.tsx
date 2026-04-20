import type React from "react";
import { forwardRef } from "react";
import SvgFreezeAll from "./freezeAll";

// `SvgFreezeAll` is a JS component that accepts arbitrary props including
// `ref`; cast to any so TS doesn't object to the forwarded ref.
const SvgFreezeAllAny = SvgFreezeAll as any;

export const freezeAllIcon = forwardRef<
  SVGSVGElement,
  React.PropsWithChildren<{ className?: string }>
>((props, ref) => {
  return <SvgFreezeAllAny ref={ref} {...props} />;
});
