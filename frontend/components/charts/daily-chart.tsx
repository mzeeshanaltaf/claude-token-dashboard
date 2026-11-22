"use client";

import { format } from "date-fns";
import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";

import { SectionCard } from "@/components/section-card";
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { Schema } from "@/lib/api";
import { familyChartConfig, tokenChartConfig } from "@/lib/chart-colors";
import { fmt } from "@/lib/format";
import { FAMILY_LABELS, type ModelFamily } from "@/lib/models";
import { parseDay } from "@/lib/range";
import { familiesPresent, fillDaily, type DailyPoint } from "@/lib/usage";

type Mode = "tokens" | "cost";
type View = "chart" | "table";

const dayTick = (d: string) => {
  const p = parseDay(d);
  return p ? format(p, "MMM d") : d;
};
const dayLong = (d: unknown) => {
  const p = typeof d === "string" ? parseDay(d) : null;
  return p ? format(p, "EEE, MMM d yyyy") : String(d ?? "");
};

const TOKEN_STACK = ["input", "output", "cache_write"] as const;

/** Bars are capped at 24px and get a 2px surface gap only when wide enough. */
function barProps(n: number) {
  return { maxBarSize: 24, stroke: n <= 60 ? "var(--card)" : undefined, strokeWidth: n <= 60 ? 1 : 0 };
}

/**
 * Daily activity as stacked columns. Tokens mode stacks input, output and
 * cache create, with cache reads in their own small chart (they're ~100×
 * larger); Cost mode stacks estimated cost by model family. A table view
 * carries every value.
 */
export function DailyChart({
  rows,
  dim,
  title = "Daily activity",
  defaultMode = "tokens",
}: {
  rows: readonly Schema<"DailyRow">[];
  dim?: boolean;
  title?: string;
  defaultMode?: Mode;
}) {
  const [mode, setMode] = useState<Mode>(defaultMode);
  const [view, setView] = useState<View>("chart");
  const points = useMemo(() => fillDaily(rows), [rows]);
  const families = useMemo(() => familiesPresent(points), [points]);

  const data = useMemo(
    () =>
      points.map((p) => ({
        day: p.day,
        input: p.input_tokens,
        output: p.output_tokens,
        cache_write: p.cache_create_tokens,
        cache_read: p.cache_read_tokens,
        cost: p.cost_usd,
        ...Object.fromEntries(families.map((f) => [f, p.families[f] ?? 0])),
      })),
    [points, families],
  );

  const costConfig = useMemo(
    () =>
      Object.fromEntries(
        families.map((f) => [
          f,
          f === "other" ? { label: "Other", color: "var(--muted-foreground)" } : familyChartConfig[f as ModelFamily],
        ]),
      ) satisfies ChartConfig,
    [families],
  );

  const description =
    mode === "tokens"
      ? "Tokens you paid full price for: what you sent (input), what Claude wrote (output), and what got stored for re-use (cache create)."
      : "Estimated API-rate cost per day, by model family.";

  return (
    <SectionCard
      title={title}
      description={description}
      dim={dim}
      action={
        <div className="flex flex-wrap items-center gap-2">
          <ToggleGroup type="single" size="sm" variant="outline" value={mode} onValueChange={(v) => v && setMode(v as Mode)} aria-label="Measure">
            <ToggleGroupItem value="tokens">Tokens</ToggleGroupItem>
            <ToggleGroupItem value="cost">Cost</ToggleGroupItem>
          </ToggleGroup>
          <ToggleGroup type="single" size="sm" variant="outline" value={view} onValueChange={(v) => v && setView(v as View)} aria-label="View">
            <ToggleGroupItem value="chart">Chart</ToggleGroupItem>
            <ToggleGroupItem value="table">Table</ToggleGroupItem>
          </ToggleGroup>
        </div>
      }
    >
      {!data.length ? (
        <p className="py-10 text-center text-sm text-muted-foreground">No activity in this range.</p>
      ) : view === "table" ? (
        <DailyTable points={points} mode={mode} families={families} />
      ) : mode === "tokens" ? (
        <div className="flex flex-col gap-4">
          <ChartContainer config={tokenChartConfig} className="aspect-auto h-64 w-full">
            <BarChart data={data} margin={{ left: 4, right: 4, top: 8 }} barCategoryGap="20%">
              <CartesianGrid vertical={false} />
              <XAxis dataKey="day" tickLine={false} axisLine={false} tickMargin={8} minTickGap={28} tickFormatter={dayTick} />
              <YAxis tickLine={false} axisLine={false} width={48} tickFormatter={(v: number) => fmt.compact(v)} />
              <ChartTooltip
                cursor={{ fillOpacity: 0.4 }}
                content={<ChartTooltipContent labelFormatter={(_, p) => dayLong(p?.[0]?.payload?.day)} valueFormatter={fmt.int} />}
              />
              <ChartLegend itemSorter={null} content={<ChartLegendContent />} />
              {TOKEN_STACK.map((k, i) => (
                <Bar
                  key={k}
                  dataKey={k}
                  stackId="t"
                  fill={`var(--color-${k})`}
                  radius={i === TOKEN_STACK.length - 1 ? [4, 4, 0, 0] : 0}
                  {...barProps(data.length)}
                />
              ))}
            </BarChart>
          </ChartContainer>
          <div>
            <p className="mb-1 text-xs text-muted-foreground">
              Cache reads, on their own scale: cheap re-uses of things Claude already saw (like your CLAUDE.md). High numbers here are a good thing.
            </p>
            <ChartContainer config={{ cache_read: tokenChartConfig.cache_read }} className="aspect-auto h-32 w-full">
              <BarChart data={data} margin={{ left: 4, right: 4, top: 4 }} barCategoryGap="20%">
                <CartesianGrid vertical={false} />
                <XAxis dataKey="day" tickLine={false} axisLine={false} tickMargin={8} minTickGap={28} tickFormatter={dayTick} />
                <YAxis tickLine={false} axisLine={false} width={48} tickFormatter={(v: number) => fmt.compact(v)} />
                <ChartTooltip
                  cursor={{ fillOpacity: 0.4 }}
                  content={<ChartTooltipContent labelFormatter={(_, p) => dayLong(p?.[0]?.payload?.day)} valueFormatter={fmt.int} />}
                />
                <Bar dataKey="cache_read" fill="var(--color-cache_read)" radius={[4, 4, 0, 0]} {...barProps(data.length)} />
              </BarChart>
            </ChartContainer>
          </div>
        </div>
      ) : (
        <ChartContainer config={costConfig} className="aspect-auto h-72 w-full">
          <BarChart data={data} margin={{ left: 4, right: 4, top: 8 }} barCategoryGap="20%">
            <CartesianGrid vertical={false} />
            <XAxis dataKey="day" tickLine={false} axisLine={false} tickMargin={8} minTickGap={28} tickFormatter={dayTick} />
            <YAxis tickLine={false} axisLine={false} width={48} tickFormatter={(v: number) => `$${fmt.compact(v)}`} />
            <ChartTooltip
              cursor={{ fillOpacity: 0.4 }}
              content={
                <ChartTooltipContent
                  labelFormatter={(_, p) => {
                    const row = p?.[0]?.payload as { day?: string; cost?: number } | undefined;
                    return `${dayLong(row?.day)} · ${fmt.usd(row?.cost)}`;
                  }}
                  valueFormatter={fmt.usd}
                />
              }
            />
            <ChartLegend itemSorter={null} content={<ChartLegendContent />} />
            {families.map((f, i) => (
              <Bar
                key={f}
                dataKey={f}
                stackId="c"
                fill={`var(--color-${f})`}
                radius={i === families.length - 1 ? [4, 4, 0, 0] : 0}
                {...barProps(data.length)}
              />
            ))}
          </BarChart>
        </ChartContainer>
      )}
    </SectionCard>
  );
}

function DailyTable({ points, mode, families }: { points: DailyPoint[]; mode: Mode; families: (ModelFamily | "other")[] }) {
  const rows = [...points].reverse().filter((p) => p.turns || p.cost_usd || p.output_tokens);
  return (
    <div className="max-h-80 overflow-auto rounded-lg border">
      <Table>
        <TableHeader className="sticky top-0 bg-card">
          <TableRow>
            <TableHead>Day</TableHead>
            {mode === "tokens" ? (
              <>
                <TableHead className="text-right">Input</TableHead>
                <TableHead className="text-right">Output</TableHead>
                <TableHead className="text-right">Cache create</TableHead>
                <TableHead className="text-right">Cache read</TableHead>
              </>
            ) : (
              <>
                {families.map((f) => (
                  <TableHead key={f} className="text-right">
                    {f === "other" ? "Other" : FAMILY_LABELS[f]}
                  </TableHead>
                ))}
                <TableHead className="text-right">Total</TableHead>
              </>
            )}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((p) => (
            <TableRow key={p.day} className="font-mono text-xs tabular">
              <TableCell>{p.day}</TableCell>
              {mode === "tokens" ? (
                <>
                  <TableCell className="text-right">{fmt.int(p.input_tokens)}</TableCell>
                  <TableCell className="text-right">{fmt.int(p.output_tokens)}</TableCell>
                  <TableCell className="text-right">{fmt.int(p.cache_create_tokens)}</TableCell>
                  <TableCell className="text-right">{fmt.int(p.cache_read_tokens)}</TableCell>
                </>
              ) : (
                <>
                  {families.map((f) => (
                    <TableCell key={f} className="text-right">
                      {fmt.usd(p.families[f] ?? 0)}
                    </TableCell>
                  ))}
                  <TableCell className="text-right">{fmt.usd(p.cost_usd)}</TableCell>
                </>
              )}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
