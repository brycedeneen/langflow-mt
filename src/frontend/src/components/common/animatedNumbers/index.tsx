import { useEffect, useRef, useState } from "react";
import { cn } from "@/utils/utils";

type SpringOptions = {
  duration?: number;
  bounce?: number;
};

type AnimatedNumberProps = {
  value: number;
  humanizedValue?: string;
  className?: string;
  springOptions?: SpringOptions;
};

export function AnimatedNumber({
  value,
  humanizedValue,
  className,
  springOptions,
}: AnimatedNumberProps) {
  const [display, setDisplay] = useState(value);
  const currentRef = useRef(value);
  const rafRef = useRef<number | null>(null);
  const duration = springOptions?.duration ?? 300;

  useEffect(() => {
    const from = currentRef.current;
    const to = value;
    if (from === to) return;
    let startTime: number | null = null;
    const tick = (now: number) => {
      if (startTime === null) startTime = now;
      const elapsed = now - startTime;
      const t = Math.min(1, elapsed / duration);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - t, 3);
      const current = from + (to - from) * eased;
      currentRef.current = current;
      setDisplay(current);
      if (t < 1) {
        rafRef.current = requestAnimationFrame(tick);
      }
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    };
  }, [value, duration]);

  return (
    <span className={cn("tabular-nums", className)}>
      {humanizedValue ?? Math.round(display).toLocaleString()}
    </span>
  );
}

export function AnimatedNumberBasic() {
  const [value, setValue] = useState(0);

  useEffect(() => {
    setValue(2082);
  }, []);

  return (
    <div className="flex w-full items-center justify-center">
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 16 16"
        width="16"
        height="16"
        className="mr-3 h-3 w-3 fill-transparent stroke-foreground stroke-[1.3]"
      >
        <path d="M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.751.751 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25Z"></path>
      </svg>
      <AnimatedNumber
        className="inline-flex items-center font-mono text-2xl font-light text-foreground"
        springOptions={{
          bounce: 0,
          duration: 2000,
        }}
        value={value}
      />
    </div>
  );
}
