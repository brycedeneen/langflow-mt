import type { ReactNode } from "react";
import { cn } from "@/utils/utils";

// NOTE: The `../../../components/ui/border-beams` module does not exist in
// this codebase and `EnhancedBeamEffect` is currently not referenced
// anywhere in production. The local `BorderBeam` stub below keeps this file
// type-clean until the real component is restored.
function BorderBeam(_props: {
  duration?: number;
  size?: number;
  className?: string;
  colorFrom?: string;
  colorTo?: string;
  anchor?: number;
  borderWidth?: number;
}) {
  return null;
}

interface EnhancedBeamEffectProps {
  children: ReactNode;
  className?: string;
  primaryColor?: string;
  secondaryColor?: string;
  size?: number;
}

export const EnhancedBeamEffect = ({
  children,
  className,
  primaryColor = "#C661B8",
  secondaryColor = "#61C6B8",
  size = 200,
}: EnhancedBeamEffectProps) => {
  return (
    <div
      className={cn(
        "relative flex items-center justify-center overflow-hidden rounded-xl",
        className,
      )}
    >
      {children}

      {/* Primary beam - larger, slower rotation */}
      <BorderBeam
        duration={12}
        size={size}
        className="opacity-80"
        colorFrom={primaryColor}
        colorTo={secondaryColor}
        anchor={20}
        borderWidth={1.5}
      />
    </div>
  );
};

export default EnhancedBeamEffect;
