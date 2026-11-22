"use client";

import Link from "next/link";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

export interface BarListItem {
  key: string;
  label: React.ReactNode;
  value: number;
  /** The formatted value printed at the bar's end. */
  display: React.ReactNode;
  /** A muted second figure after the value ("23%"). */
  aside?: React.ReactNode;
  href?: string;
  /** Hover / focus detail. */
  tooltip?: React.ReactNode;
}

/**
 * Ranked horizontal bars as HTML: label, bar, value in each row. One series,
 * one colour (never a value ramp). Bars are 10px with a 4px rounded end and
 * grow from a shared baseline; the value is always printed, so the tooltip
 * only adds detail. Labels can be `.blur-sensitive` (`sensitiveLabels`).
 */
export function BarList({
  items,
  color = "var(--chart-input)",
  sensitiveLabels,
  max,
  className,
  ariaLabel,
}: {
  items: readonly BarListItem[];
  color?: string;
  sensitiveLabels?: boolean;
  /** Scale maximum; defaults to the largest value. */
  max?: number;
  className?: string;
  ariaLabel?: string;
}) {
  const top = max ?? Math.max(0, ...items.map((i) => i.value));
  return (
    <ul className={cn("flex flex-col gap-1", className)} aria-label={ariaLabel}>
      {items.map((item) => {
        const pct = top > 0 ? Math.max(0, (item.value / top) * 100) : 0;
        const row = (
          <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 rounded-md px-2 py-1.5 sm:grid-cols-[minmax(7rem,11rem)_minmax(0,1fr)_auto]">
            <span className={cn("truncate text-sm", sensitiveLabels && "blur-sensitive")}>{item.label}</span>
            <span className="col-span-2 row-start-2 h-2.5 min-w-0 sm:col-span-1 sm:row-start-auto" aria-hidden>
              <span
                className="block h-full rounded-r-[4px]"
                style={{ width: `${pct}%`, minWidth: item.value > 0 ? 2 : 0, background: color }}
              />
            </span>
            <span className="flex items-baseline gap-2 justify-self-end font-mono text-xs tabular">
              {item.display}
              {item.aside !== undefined && <span className="w-9 text-right text-muted-foreground">{item.aside}</span>}
            </span>
          </div>
        );
        const interactive = item.href ? (
          <Link
            href={item.href}
            className="block rounded-md outline-none hover:bg-muted/60 focus-visible:ring-2 focus-visible:ring-ring"
          >
            {row}
          </Link>
        ) : (
          <div tabIndex={item.tooltip ? 0 : undefined} className="rounded-md outline-none hover:bg-muted/40 focus-visible:ring-2 focus-visible:ring-ring">
            {row}
          </div>
        );
        return (
          <li key={item.key}>
            {item.tooltip ? (
              <Tooltip>
                <TooltipTrigger asChild>{interactive}</TooltipTrigger>
                <TooltipContent side="top" align="start" className="max-w-80">
                  {item.tooltip}
                </TooltipContent>
              </Tooltip>
            ) : (
              interactive
            )}
          </li>
        );
      })}
    </ul>
  );
}
