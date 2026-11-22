"use client";

import { format } from "date-fns";
import Link from "next/link";

import { ErrorState } from "@/components/error-state";
import { KpiCard } from "@/components/kpi-card";
import { ChartSkeleton, KpiGridSkeleton } from "@/components/loading";
import { useRangedHref } from "@/hooks/use-url-state";
import type { Schema } from "@/lib/api";
import { fmt } from "@/lib/format";
import { useRangedQuery } from "@/lib/queries";
import { parseDay } from "@/lib/range";

import { CalendarHeatmap, dayHref } from "./calendar-heatmap";
import { HourHeatmap } from "./hour-heatmap";

const longDay = (d: string) => {
  const p = parseDay(d);
  return p ? format(p, "EEE, MMM d yyyy") : d;
};
const pad = (h: number) => String(h).padStart(2, "0");
const plural = (n: number, one: string) => `${fmt.int(n)} ${one}${n === 1 ? "" : "s"}`;

function SummaryCards({ s }: { s: Schema<"ActivitySummary"> }) {
  const href = useRangedHref();
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
      <KpiCard
        label="Active days"
        value={fmt.int(s.active_days)}
        sub={s.days_in_range ? `of ${plural(s.days_in_range, "day")} (${fmt.pct(s.active_days / s.days_in_range)})` : "no activity"}
      />
      <KpiCard
        label="Current streak"
        value={plural(s.current_streak, "day")}
        sub={`Longest: ${plural(s.longest_streak, "day")}`}
        info="Consecutive days with any activity. The current streak ends today (or yesterday, so an idle morning doesn't break it)."
      />
      <KpiCard
        label="Busiest day"
        value={
          s.busiest_day ? (
            <Link href={dayHref(s.busiest_day.day)} className="text-lg hover:underline">
              {longDay(s.busiest_day.day)}
            </Link>
          ) : (
            "—"
          )
        }
        sub={s.busiest_day ? `${fmt.usd(s.busiest_day.cost_usd)} · ${fmt.compact(s.busiest_day.tokens)} tokens` : undefined}
        info="The day with the highest estimated cost."
      />
      <KpiCard
        label="Per active day"
        value={fmt.usd(s.avg_cost_per_active_day)}
        sub={`${fmt.compact(s.avg_tokens_per_active_day)} tokens on average`}
        info="Estimated cost and tokens (input, output and cache writes) averaged over the days you were active, not every calendar day."
      />
      <KpiCard
        label="Top project"
        sensitive
        value={
          s.top_project ? (
            <Link href={href(`/projects/${encodeURIComponent(s.top_project.project_slug)}`)} className="block truncate text-lg hover:underline">
              {s.top_project.project_name}
            </Link>
          ) : (
            "—"
          )
        }
        sub={s.top_project ? `${fmt.int(s.top_project.turns)} turns · ${fmt.usd(s.top_project.cost_usd)}` : undefined}
        info="The project with the most turns in this range."
      />
      <KpiCard
        label="Peak hour"
        value={s.peak_hour ? `${pad(s.peak_hour.hour)}:00` : "—"}
        sub={s.peak_hour ? `${fmt.int(s.peak_hour.turns)} turns at ${pad(s.peak_hour.hour)}:00–${pad((s.peak_hour.hour + 1) % 24)}:00` : undefined}
        info={`The hour of the day with the most turns, in ${s.timezone}.`}
      />
    </div>
  );
}

export function ActivityPage() {
  const summary = useRangedQuery("/api/activity/summary");
  const hourly = useRangedQuery("/api/activity/hourly");
  const tz = summary.data?.timezone ?? hourly.data?.timezone;

  return (
    <div className="flex flex-col gap-6">
      {summary.isError ? (
        <ErrorState error={summary.error} onRetry={() => summary.refetch()} />
      ) : summary.data ? (
        <div className={summary.isPlaceholderData ? "opacity-60 transition-opacity" : undefined}>
          <SummaryCards s={summary.data} />
        </div>
      ) : (
        <KpiGridSkeleton count={6} />
      )}

      <CalendarHeatmap />

      {hourly.isError ? (
        <ErrorState error={hourly.error} onRetry={() => hourly.refetch()} />
      ) : hourly.data ? (
        <HourHeatmap data={hourly.data} dim={hourly.isPlaceholderData} />
      ) : (
        <ChartSkeleton className="h-56" />
      )}

      {tz && (
        <p className="text-xs text-muted-foreground">
          Days and hours are in <span className="font-mono">{tz}</span>, the timezone set in{" "}
          <Link href="/settings" className="underline hover:text-foreground">
            Settings
          </Link>
          . The calendar always shows the last 12 months; the cards and the hour grid follow the date range.
        </p>
      )}
    </div>
  );
}
