"use client";

import { useCallback, useRef, useState } from "react";

import { cn } from "@/lib/utils";

interface Tip {
  x: number;
  y: number;
  content: React.ReactNode;
}

/**
 * One floating tooltip for a whole grid of marks (a heatmap's cells, a
 * timeline's ticks) instead of one Radix tooltip per mark. Put `ref` on a
 * `relative` container and call `show(el, content)` on hover/focus.
 */
export function useHoverTip<T extends HTMLElement = HTMLDivElement>() {
  const ref = useRef<T>(null);
  const [tip, setTip] = useState<Tip | null>(null);

  const showAt = useCallback((clientX: number, clientY: number, content: React.ReactNode) => {
    const box = ref.current?.getBoundingClientRect();
    if (!box) return;
    setTip({ x: clientX - box.left, y: clientY - box.top, content });
  }, []);

  /** Above the element's centre. */
  const show = useCallback(
    (el: Element, content: React.ReactNode) => {
      const r = el.getBoundingClientRect();
      showAt(r.left + r.width / 2, r.top, content);
    },
    [showAt],
  );

  const hide = useCallback(() => setTip(null), []);
  return { ref, tip, show, showAt, hide } as const;
}

export function HoverTip({ tip, className }: { tip: Tip | null; className?: string }) {
  if (!tip) return null;
  return (
    <div
      role="tooltip"
      className={cn(
        "pointer-events-none absolute z-20 w-max max-w-72 -translate-x-1/2 -translate-y-full rounded-md border bg-popover px-2.5 py-1.5 text-xs text-popover-foreground shadow-md",
        className,
      )}
      style={{ left: tip.x, top: tip.y - 6 }}
    >
      {tip.content}
    </div>
  );
}
