"use client";

import { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ReferenceLine, XAxis, YAxis } from "recharts";

import { SectionCard } from "@/components/section-card";
import { ChartContainer, ChartLegend, ChartLegendContent, ChartTooltip, type ChartConfig } from "@/components/ui/chart";
import type { Schema } from "@/lib/api";
import { fmt } from "@/lib/format";

type Point = Schema<"ContextPoint">;

interface Row {
  i: number;
  uuid: string;
  ts: string;
  model: string | null;
  sidechain: boolean;
  context: number;
  output: number;
  cost: number | null;
  main: number | null;
  side: number | null;
  main_cost: number | null;
  side_cost: number | null;
}

const config = {
  main: { label: "Main thread", color: "var(--chart-input)" },
  side: { label: "Subagents (sidechain)", color: "var(--family-mythos)" },
  output: { label: "Output tokens", color: "var(--chart-output)" },
  main_cost: { label: "Main thread", color: "var(--chart-input)" },
  side_cost: { label: "Subagents (sidechain)", color: "var(--family-mythos)" },
} satisfies ChartConfig;

/**
 * A main-chain turn whose context fell below half the previous one (from > 40k): a compaction or /clear.
 * Turns with no usage at all (`<synthetic>` records: API errors, interruptions) are skipped.
 */
function compactions(rows: Row[]): number[] {
  const out: number[] = [];
  let prev: number | null = null;
  for (const r of rows) {
    if (r.sidechain || r.context === 0) continue;
    if (prev !== null && prev > 40_000 && r.context < prev * 0.5) out.push(r.i);
    prev = r.context;
  }
  return out;
}

function useRows(points: readonly Point[]): Row[] {
  return useMemo(
    () =>
      points.map((p, k) => ({
        i: k + 1,
        uuid: p.uuid,
        ts: p.ts,
        model: p.model,
        sidechain: p.is_sidechain,
        context: p.context_tokens,
        output: p.output_tokens,
        cost: p.cost,
        // A turn with no usage (a `<synthetic>` record) is a gap, not a dive to zero.
        main: p.is_sidechain || !p.context_tokens ? null : p.context_tokens,
        side: p.is_sidechain && p.context_tokens ? p.context_tokens : null,
        main_cost: p.is_sidechain ? null : p.cost,
        side_cost: p.is_sidechain ? p.cost : null,
      })),
    [points],
  );
}

function TurnTip({ active, payload }: { active?: boolean; payload?: readonly { payload?: Row }[] }) {
  const r = payload?.[0]?.payload;
  if (!active || !r) return null;
  return (
    <div className="grid min-w-44 gap-1 rounded-lg border bg-background px-2.5 py-1.5 text-xs shadow-xl">
      <div className="flex items-center justify-between gap-3 font-medium">
        <span>Turn #{r.i}</span>
        <span className="font-mono text-muted-foreground tabular">{fmt.tsTime(r.ts)}</span>
      </div>
      <div className="text-muted-foreground">
        {fmt.modelLabel(r.model) || "unknown model"}
        {r.sidechain && " · subagent"}
      </div>
      <dl className="grid grid-cols-[auto_auto] gap-x-3 font-mono tabular">
        <dt className="font-sans text-muted-foreground">Context</dt>
        <dd className="text-right">{fmt.int(r.context)}</dd>
        <dt className="font-sans text-muted-foreground">Output</dt>
        <dd className="text-right">{fmt.int(r.output)}</dd>
        <dt className="font-sans text-muted-foreground">Cost</dt>
        <dd className="text-right">{fmt.usd4(r.cost)}</dd>
      </dl>
      <div className="text-[10px] text-muted-foreground">Click to show this turn in the table</div>
    </div>
  );
}

type ClickState = { activeTooltipIndex?: number | string | null } | null | undefined;

function clickHandler(rows: Row[], onTurn: (uuid: string) => void) {
  return (state: ClickState) => {
    const idx = Number(state?.activeTooltipIndex);
    if (Number.isInteger(idx) && rows[idx]) onTurn(rows[idx].uuid);
  };
}

const xAxisProps = {
  dataKey: "i",
  tickLine: false,
  axisLine: false,
  tickMargin: 6,
  minTickGap: 32,
} as const;

/**
 * What the model saw on each assistant turn (input + cache reads + cache
 * writes): the main thread as a line, subagent turns as dots (they have their
 * own, smaller contexts). Sharp drops are marked: compaction or /clear.
 * Output tokens sit in a second chart on the same turn axis (one y-axis per
 * chart; never a dual axis).
 */
export function ContextGrowthChart({ points, onTurn }: { points: readonly Point[]; onTurn: (uuid: string) => void }) {
  const rows = useRows(points);
  const drops = useMemo(() => compactions(rows), [rows]);
  const hasSide = rows.some((r) => r.sidechain);
  const onClick = clickHandler(rows, onTurn);
  const peak = rows.reduce((m, r) => (r.sidechain ? m : Math.max(m, r.context)), 0);

  return (
    <SectionCard
      title="Context growth"
      description={
        <>
          Context size per assistant turn: how full the window was. Peak {fmt.compact(peak)} tokens on the main thread
          {drops.length ? `; ${drops.length} sharp drop${drops.length === 1 ? "" : "s"} (compaction or /clear) marked` : ""}.
        </>
      }
    >
      {!rows.length ? (
        <p className="py-8 text-center text-sm text-muted-foreground">No assistant turns.</p>
      ) : (
        <div className="flex flex-col gap-3">
          <ChartContainer config={config} className="aspect-auto h-60 w-full cursor-pointer">
            <LineChart data={rows} syncId="session-turns" margin={{ left: 4, right: 8, top: 8 }} onClick={onClick}>
              <CartesianGrid vertical={false} />
              <XAxis {...xAxisProps} hide />
              <YAxis tickLine={false} axisLine={false} width={48} tickFormatter={(v: number) => fmt.compact(v)} />
              <ChartTooltip cursor={{ strokeOpacity: 0.4 }} content={<TurnTip />} />
              {drops.map((x) => (
                <ReferenceLine
                  key={x}
                  x={x}
                  stroke="var(--muted-foreground)"
                  strokeDasharray="3 3"
                  strokeOpacity={0.6}
                  label={{ value: "compacted", position: "insideTopRight", fontSize: 10, fill: "var(--muted-foreground)" }}
                />
              ))}
              <Line dataKey="main" type="linear" stroke="var(--color-main)" strokeWidth={2} dot={false} connectNulls isAnimationActive={false} />
              {hasSide && (
                <Line
                  dataKey="side"
                  // dots only: the stroke is the legend swatch's colour, drawn at width 0
                  stroke="var(--color-side)"
                  strokeWidth={0}
                  dot={{ r: 2, fill: "var(--color-side)", strokeWidth: 0 }}
                  activeDot={{ r: 4, fill: "var(--color-side)", stroke: "var(--card)", strokeWidth: 2 }}
                  isAnimationActive={false}
                  legendType="circle"
                />
              )}
              <ChartLegend itemSorter={null} content={<ChartLegendContent />} />
            </LineChart>
          </ChartContainer>
          <div>
            <p className="mb-1 text-xs text-muted-foreground">Output tokens per turn, on their own scale.</p>
            <ChartContainer config={{ output: config.output }} className="aspect-auto h-24 w-full cursor-pointer">
              <BarChart data={rows} syncId="session-turns" margin={{ left: 4, right: 8, top: 4 }} barCategoryGap={1} onClick={onClick}>
                <CartesianGrid vertical={false} />
                <XAxis {...xAxisProps} />
                <YAxis tickLine={false} axisLine={false} width={48} tickFormatter={(v: number) => fmt.compact(v)} />
                <ChartTooltip cursor={{ fillOpacity: 0.3 }} content={<TurnTip />} />
                <Bar dataKey="output" fill="var(--color-output)" radius={[2, 2, 0, 0]} maxBarSize={24} isAnimationActive={false} />
              </BarChart>
            </ChartContainer>
          </div>
        </div>
      )}
    </SectionCard>
  );
}

/** Estimated cost of each assistant turn; click a bar to find the turn in the table. */
export function TurnCostChart({ points, onTurn }: { points: readonly Point[]; onTurn: (uuid: string) => void }) {
  const rows = useRows(points);
  const hasSide = rows.some((r) => r.sidechain);
  const top = useMemo(
    () => [...rows].filter((r) => r.cost != null).sort((a, b) => (b.cost ?? 0) - (a.cost ?? 0)).slice(0, 3),
    [rows],
  );

  return (
    <SectionCard
      title="Cost per turn"
      description={
        top.length ? (
          <>
            The expensive turns stand out. Most expensive:{" "}
            {top.map((r, k) => (
              <span key={r.uuid}>
                {k > 0 && ", "}
                <button type="button" className="font-mono underline-offset-2 hover:underline" onClick={() => onTurn(r.uuid)}>
                  #{r.i} {fmt.usd(r.cost)}
                </button>
              </span>
            ))}
            .
          </>
        ) : (
          "No priced turns."
        )
      }
    >
      {rows.length > 0 && (
        <ChartContainer config={config} className="aspect-auto h-44 w-full cursor-pointer">
          <BarChart data={rows} syncId="session-turns" margin={{ left: 4, right: 8, top: 8 }} barCategoryGap={1} onClick={clickHandler(rows, onTurn)}>
            <CartesianGrid vertical={false} />
            <XAxis {...xAxisProps} />
            <YAxis tickLine={false} axisLine={false} width={48} tickFormatter={(v: number) => `$${fmt.compact(v)}`} />
            <ChartTooltip cursor={{ fillOpacity: 0.3 }} content={<TurnTip />} />
            <Bar dataKey="main_cost" stackId="c" fill="var(--color-main_cost)" radius={[2, 2, 0, 0]} maxBarSize={24} isAnimationActive={false} />
            {hasSide && (
              <Bar dataKey="side_cost" stackId="c" fill="var(--color-side_cost)" radius={[2, 2, 0, 0]} maxBarSize={24} isAnimationActive={false} />
            )}
            {hasSide && <ChartLegend itemSorter={null} content={<ChartLegendContent />} />}
          </BarChart>
        </ChartContainer>
      )}
    </SectionCard>
  );
}
