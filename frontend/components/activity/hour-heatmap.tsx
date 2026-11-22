"use client";

import { useMemo, useState } from "react";

import { heatColor, quantizer } from "@/components/charts/heat-scale";
import { HoverTip, useHoverTip } from "@/components/charts/hover-tip";
import { SectionCard } from "@/components/section-card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { Schema } from "@/lib/api";
import { fmt } from "@/lib/format";

import { HeatLegend } from "./heat-legend";

type Metric = "turns" | "tokens" | "cost";
type Cell = Schema<"HourCell">;

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const HOURS = Array.from({ length: 24 }, (_, h) => h);
const pad = (h: number) => String(h).padStart(2, "0");

const valueOf = (c: Cell, m: Metric) => (m === "turns" ? c.turns : m === "tokens" ? c.tokens : c.cost_usd);
const formatter = (m: Metric) => (m === "turns" ? fmt.int : m === "tokens" ? fmt.compact : fmt.usd);

function cellTip(c: Cell) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="font-medium">
        {DAYS[c.dow - 1]} {pad(c.hour)}:00–{pad((c.hour + 1) % 24)}:00
      </span>
      <span className="font-mono tabular text-muted-foreground">
        {fmt.int(c.turns)} turns · {fmt.compact(c.tokens)} tokens · {fmt.usd(c.cost_usd)}
      </span>
    </div>
  );
}

/** When you work: ISO weekday rows × local hour columns, one-hue quantised scale. */
export function HourHeatmap({ data, dim }: { data: Schema<"ActivityHourly">; dim?: boolean }) {
  const [metric, setMetric] = useState<Metric>("turns");
  const [view, setView] = useState<"chart" | "table">("chart");
  const { ref: tipRef, tip, show: showTip, hide: hideTip } = useHoverTip();

  const grid = useMemo(() => {
    const byKey = new Map(data.cells.map((c) => [`${c.dow}-${c.hour}`, c]));
    return DAYS.map((_, i) => HOURS.map((h) => byKey.get(`${i + 1}-${h}`) ?? { dow: i + 1, hour: h, turns: 0, tokens: 0, cost_usd: 0 }));
  }, [data]);
  const { level, thresholds } = useMemo(() => quantizer(data.cells.map((c) => valueOf(c, metric))), [data, metric]);
  const f = formatter(metric);
  const empty = data.cells.every((c) => !c.turns && !c.tokens);

  return (
    <SectionCard
      title="Hour × weekday"
      description={`When you work, in ${data.timezone}. "Turns" counts every user record (prompts and tool results), as on the Overview.`}
      dim={dim}
      action={
        <div className="flex flex-wrap items-center gap-2">
          <ToggleGroup type="single" size="sm" variant="outline" value={metric} onValueChange={(v) => v && setMetric(v as Metric)} aria-label="Measure">
            <ToggleGroupItem value="turns">Turns</ToggleGroupItem>
            <ToggleGroupItem value="tokens">Tokens</ToggleGroupItem>
            <ToggleGroupItem value="cost">Cost</ToggleGroupItem>
          </ToggleGroup>
          <ToggleGroup type="single" size="sm" variant="outline" value={view} onValueChange={(v) => v && setView(v as "chart" | "table")} aria-label="View">
            <ToggleGroupItem value="chart">Chart</ToggleGroupItem>
            <ToggleGroupItem value="table">Table</ToggleGroupItem>
          </ToggleGroup>
        </div>
      }
    >
      {empty ? (
        <p className="py-8 text-center text-sm text-muted-foreground">No activity in this range.</p>
      ) : view === "table" ? (
        <div className="overflow-auto rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead />
                {HOURS.map((h) => (
                  <TableHead key={h} className="px-1.5 text-right font-mono text-[10px]">
                    {pad(h)}
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {grid.map((row, i) => (
                <TableRow key={i} className="font-mono text-[11px] tabular">
                  <TableCell className="font-sans text-xs">{DAYS[i].slice(0, 3)}</TableCell>
                  {row.map((c) => (
                    <TableCell key={c.hour} className="px-1.5 text-right">
                      {valueOf(c, metric) ? f(valueOf(c, metric)) : "·"}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          <div ref={tipRef} className="relative overflow-x-auto pb-1" onMouseLeave={hideTip}>
            <div className="grid min-w-140 gap-0.75" style={{ gridTemplateColumns: "2.25rem repeat(24, minmax(0, 1fr))" }}>
              <span />
              {HOURS.map((h) => (
                <span key={h} className="text-center text-[10px] leading-4 text-muted-foreground">
                  {h % 3 === 0 ? pad(h) : ""}
                </span>
              ))}
              {grid.map((row, i) => [
                <span key={`l${i}`} className="self-center text-[10px] text-muted-foreground">
                  {DAYS[i].slice(0, 3)}
                </span>,
                ...row.map((c) => (
                  <span
                    key={`${i}-${c.hour}`}
                    role="img"
                    tabIndex={0}
                    aria-label={`${DAYS[i]} ${pad(c.hour)}:00: ${fmt.int(c.turns)} turns, ${fmt.int(c.tokens)} tokens, ${fmt.usd(c.cost_usd)}`}
                    className="h-5 rounded-[2px] outline-none focus-visible:ring-2 focus-visible:ring-ring sm:h-6"
                    style={{ background: heatColor(level(valueOf(c, metric))) }}
                    onMouseEnter={(e) => showTip(e.currentTarget, cellTip(c))}
                    onFocus={(e) => showTip(e.currentTarget, cellTip(c))}
                    onBlur={hideTip}
                  />
                )),
              ])}
            </div>
            <HoverTip tip={tip} />
          </div>
          <HeatLegend thresholds={thresholds} format={f} />
        </div>
      )}
    </SectionCard>
  );
}
