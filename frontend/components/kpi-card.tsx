"use client";

import { InfoIcon } from "lucide-react";
import { Area, AreaChart } from "recharts";

import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ChartContainer, type ChartConfig } from "@/components/ui/chart";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

export interface KpiCardProps {
  label: string;
  value: React.ReactNode;
  /** A secondary line under the value ("of $6,438 all time"). */
  sub?: React.ReactNode;
  /** Explains how the number is computed. */
  info?: React.ReactNode;
  /** Values in time order; drawn as a small area chart. */
  sparkline?: number[];
  /** A CSS colour, normally a token: "var(--chart-output)". */
  sparkColor?: string;
  /** Blur the value under the privacy toggle. */
  sensitive?: boolean;
  loading?: boolean;
  className?: string;
}

export function KpiCard({
  label,
  value,
  sub,
  info,
  sparkline,
  sparkColor = "var(--chart-input)",
  sensitive,
  loading,
  className,
}: KpiCardProps) {
  const config = { v: { label, color: sparkColor } } satisfies ChartConfig;
  return (
    <Card size="sm" className={cn("gap-2 overflow-hidden", className)}>
      <CardHeader>
        <CardDescription className="text-xs font-medium tracking-wide uppercase">{label}</CardDescription>
        {info && (
          <CardAction>
            <Tooltip>
              <TooltipTrigger asChild>
                <button type="button" className="text-muted-foreground hover:text-foreground" aria-label={`About ${label}`}>
                  <InfoIcon className="size-3.5" />
                </button>
              </TooltipTrigger>
              <TooltipContent className="max-w-64">{info}</TooltipContent>
            </Tooltip>
          </CardAction>
        )}
        <CardTitle className={cn("font-mono text-2xl font-semibold tracking-tight tabular", sensitive && "blur-sensitive")}>
          {loading ? <Skeleton className="h-8 w-28" /> : value}
        </CardTitle>
      </CardHeader>
      {(sub || sparkline) && (
        <CardContent className="flex flex-col gap-2">
          {sub && (
            <div className="text-xs text-muted-foreground tabular">
              {loading ? <Skeleton className="h-3.5 w-24" /> : sub}
            </div>
          )}
          {sparkline && sparkline.length > 1 && !loading && (
            <ChartContainer config={config} className="aspect-auto h-10 w-full" aria-hidden>
              <AreaChart data={sparkline.map((v, i) => ({ i, v }))} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
                <defs>
                  <linearGradient id={`spark-${label.replace(/\W/g, "")}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--color-v)" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="var(--color-v)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <Area
                  dataKey="v"
                  type="monotone"
                  stroke="var(--color-v)"
                  strokeWidth={1.5}
                  fill={`url(#spark-${label.replace(/\W/g, "")})`}
                  isAnimationActive={false}
                />
              </AreaChart>
            </ChartContainer>
          )}
        </CardContent>
      )}
    </Card>
  );
}
