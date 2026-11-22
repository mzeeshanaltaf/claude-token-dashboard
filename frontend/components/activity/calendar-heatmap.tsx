"use client";

import { addDays, differenceInCalendarDays, format, getISODay } from "date-fns";
import Link from "next/link";
import { useMemo, useState } from "react";

import { heatColor, quantizer } from "@/components/charts/heat-scale";
import { HoverTip, useHoverTip } from "@/components/charts/hover-tip";
import { SectionCard } from "@/components/section-card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { Schema } from "@/lib/api";
import { fmt } from "@/lib/format";
import { useApiQuery } from "@/lib/queries";
import { formatDay, parseDay } from "@/lib/range";

import { HeatLegend } from "./heat-legend";

type Metric = "cost" | "tokens";
type Day = Schema<"CalendarDay">;

const WEEKDAY_LABELS = ["Mon", "", "Wed", "", "Fri", "", ""];

/** A day's sessions: the custom range is an inclusive local day on both ends. */
export function dayHref(day: string) {
  return `/sessions?since=${day}&until=${day}`;
}

function dayTip(day: string, d: Day | undefined) {
  const date = parseDay(day);
  return (
    <div className="flex flex-col gap-0.5">
      <span className="font-medium">{date ? format(date, "EEE, MMM d yyyy") : day}</span>
      {d ? (
        <span className="font-mono tabular text-muted-foreground">
          {fmt.usd(d.cost_usd)} · {fmt.compact(d.tokens)} tokens · {fmt.int(d.sessions)} session{d.sessions === 1 ? "" : "s"}
        </span>
      ) : (
        <span className="text-muted-foreground">No activity</span>
      )}
    </div>
  );
}

/**
 * A GitHub-style year: one column per week (Monday first), one square per
 * day, a quantised one-hue scale. A day with activity links to its sessions.
 * Always the last 365 days, whatever the page's range.
 */
export function CalendarHeatmap() {
  const [metric, setMetric] = useState<Metric>("cost");
  const [view, setView] = useState<"chart" | "table">("chart");
  const q = useApiQuery("/api/activity/calendar", { query: { metric, days: 365 } });

  return (
    <SectionCard
      title="Daily activity, last 12 months"
      description={
        q.data
          ? `Each square is one day in ${q.data.timezone}; darker means more ${metric === "cost" ? "estimated cost" : "tokens (input, output and cache writes)"}. Click a day to see its sessions.`
          : "Each square is one day."
      }
      dim={q.isPlaceholderData}
      action={
        <div className="flex flex-wrap items-center gap-2">
          <ToggleGroup type="single" size="sm" variant="outline" value={metric} onValueChange={(v) => v && setMetric(v as Metric)} aria-label="Measure">
            <ToggleGroupItem value="cost">Cost</ToggleGroupItem>
            <ToggleGroupItem value="tokens">Tokens</ToggleGroupItem>
          </ToggleGroup>
          <ToggleGroup type="single" size="sm" variant="outline" value={view} onValueChange={(v) => v && setView(v as "chart" | "table")} aria-label="View">
            <ToggleGroupItem value="chart">Chart</ToggleGroupItem>
            <ToggleGroupItem value="table">Table</ToggleGroupItem>
          </ToggleGroup>
        </div>
      }
    >
      {q.isError ? (
        <p className="py-8 text-center text-sm text-destructive">Couldn&apos;t load the calendar: {q.error.message}</p>
      ) : !q.data ? (
        <div className="h-40 animate-pulse rounded-lg bg-muted" />
      ) : view === "table" ? (
        <CalendarTable days={q.data.days} />
      ) : (
        <CalendarGrid data={q.data} metric={metric} />
      )}
    </SectionCard>
  );
}

function CalendarGrid({ data, metric }: { data: Schema<"ActivityCalendar">; metric: Metric }) {
  const { ref: tipRef, tip, show: showTip, hide: hideTip } = useHoverTip();
  const layout = useMemo(() => {
    const start = parseDay(data.start)!;
    const end = parseDay(data.end)!;
    const gridStart = addDays(start, -(getISODay(start) - 1)); // the Monday on/before start
    const weeks = Math.floor(differenceInCalendarDays(end, gridStart) / 7) + 1;
    const byDay = new Map(data.days.map((d) => [d.day, d]));
    const { level, thresholds } = quantizer(data.days.map((d) => d.value));
    const months: { col: number; label: string }[] = [];
    let lastMonth = -1;
    for (let w = 0; w < weeks; w++) {
      // label a column by the first in-range day of its week
      const first = [0, 1, 2, 3, 4, 5, 6].map((i) => addDays(gridStart, w * 7 + i)).find((d) => d >= start && d <= end);
      if (first && first.getMonth() !== lastMonth) {
        if (first.getDate() <= 7 || w === 0) months.push({ col: w, label: format(first, "MMM") });
        lastMonth = first.getMonth();
      }
    }
    // A partial first month would collide with the next label.
    if (months.length > 1 && months[1].col - months[0].col < 3) months.shift();
    return { start, end, gridStart, weeks, byDay, level, thresholds, months };
  }, [data]);

  const cells: React.ReactNode[] = [];
  for (let w = 0; w < layout.weeks; w++) {
    for (let i = 0; i < 7; i++) {
      const date = addDays(layout.gridStart, w * 7 + i);
      const style = { gridColumn: w + 2, gridRow: i + 2 };
      if (date < layout.start || date > layout.end) {
        cells.push(<span key={`${w}-${i}`} style={style} aria-hidden />);
        continue;
      }
      const day = formatDay(date);
      const d = layout.byDay.get(day);
      const lvl = d ? layout.level(d.value) : 0;
      const common = {
        style: { ...style, background: heatColor(lvl) },
        className: "aspect-square w-full rounded-[2px] outline-none focus-visible:ring-2 focus-visible:ring-ring",
        onMouseEnter: (e: React.MouseEvent) => showTip(e.currentTarget, dayTip(day, d)),
        onFocus: (e: React.FocusEvent) => showTip(e.currentTarget, dayTip(day, d)),
        onMouseLeave: hideTip,
        onBlur: hideTip,
      };
      const label = d
        ? `${day}: ${fmt.usd(d.cost_usd)}, ${fmt.int(d.tokens)} tokens, ${d.sessions} sessions`
        : `${day}: no activity`;
      cells.push(
        d ? (
          <Link key={day} href={dayHref(day)} aria-label={label} {...common} />
        ) : (
          <span key={day} role="img" aria-label={label} {...common} />
        ),
      );
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div ref={tipRef} className="relative overflow-x-auto pb-1" onMouseLeave={hideTip}>
        <div
          className="grid min-w-160 gap-0.75"
          style={{ gridTemplateColumns: `1.75rem repeat(${layout.weeks}, minmax(0, 1fr))` }}
        >
          {layout.months.map((m) => (
            <span key={m.col} className="text-[10px] leading-4 text-muted-foreground" style={{ gridColumn: `${m.col + 2} / span 4`, gridRow: 1 }}>
              {m.label}
            </span>
          ))}
          {WEEKDAY_LABELS.map((l, i) => (
            <span key={i} className="self-center text-[10px] leading-none text-muted-foreground" style={{ gridColumn: 1, gridRow: i + 2 }}>
              {l}
            </span>
          ))}
          {cells}
        </div>
        <HoverTip tip={tip} />
      </div>
      <HeatLegend
        thresholds={layout.thresholds}
        format={metric === "cost" ? fmt.usd : fmt.compact}
        note={`${fmt.int(data.days.length)} active days`}
      />
    </div>
  );
}

function CalendarTable({ days }: { days: readonly Day[] }) {
  const rows = [...days].reverse();
  if (!rows.length) return <p className="py-8 text-center text-sm text-muted-foreground">No activity in the last 12 months.</p>;
  return (
    <div className="max-h-80 overflow-auto rounded-lg border">
      <Table>
        <TableHeader className="sticky top-0 bg-card">
          <TableRow>
            <TableHead>Day</TableHead>
            <TableHead className="text-right">Cost</TableHead>
            <TableHead className="text-right">Tokens</TableHead>
            <TableHead className="text-right">Sessions</TableHead>
            <TableHead className="text-right">Turns</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((d) => (
            <TableRow key={d.day} className="font-mono text-xs tabular">
              <TableCell>
                <Link href={dayHref(d.day)} className="hover:underline">
                  {d.day}
                </Link>
              </TableCell>
              <TableCell className="text-right">{fmt.usd(d.cost_usd)}</TableCell>
              <TableCell className="text-right">{fmt.int(d.tokens)}</TableCell>
              <TableCell className="text-right">{fmt.int(d.sessions)}</TableCell>
              <TableCell className="text-right">{fmt.int(d.turns)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
