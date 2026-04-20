import { useEffect, useRef, useState } from "react";

type AnimatedNumberProps = {
  value: number;
  durationMs?: number;
  className?: string;
  format?: (n: number) => string;
};

export function AnimatedNumber({
  value,
  durationMs = 900,
  className,
  format,
}: AnimatedNumberProps) {
  const [display, setDisplay] = useState(0);
  const startVal = useRef(0);

  useEffect(() => {
    const from = startVal.current;
    const to = value;
    const start = performance.now();
    let raf = 0;

    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / durationMs);
      // easeOutCubic — strong start, gentle settle
      const eased = 1 - Math.pow(1 - t, 3);
      setDisplay(Math.round(from + (to - from) * eased));
      if (t < 1) raf = requestAnimationFrame(tick);
      else startVal.current = to;
    };

    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, durationMs]);

  return (
    <span className={className}>{format ? format(display) : display}</span>
  );
}
