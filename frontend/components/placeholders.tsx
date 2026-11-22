"use client";

/**
 * Placeholders for the pages phase 06 builds (Activity, Tools): each shows a
 * couple of real numbers for the range. Phase 05 replaced the others.
 */
import { ConstructionIcon } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { KpiCard } from "@/components/kpi-card";
import { KpiGridSkeleton } from "@/components/loading";
import { useRange } from "@/hooks/use-range";
import { fmt } from "@/lib/format";
import { useRangedQuery } from "@/lib/queries";
import { rangeLabel } from "@/lib/range";

function Grid({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">{children}</div>;
}

function ComingSoon({ page }: { page: string }) {
  return (
    <EmptyState
      className="flex-none py-10"
      icon={ConstructionIcon}
      title={`The full ${page} page is on its way`}
      description="This preview shows live numbers from your data; charts and tables come next."
    />
  );
}

function RangeNote() {
  const { range } = useRange();
  return <span>{rangeLabel(range)}</span>;
}

export function ActivityPlaceholder() {
  const daily = useRangedQuery("/api/daily");
  if (daily.isError) return <ErrorState error={daily.error} onRetry={() => daily.refetch()} />;
  if (!daily.data) return <KpiGridSkeleton count={2} />;
  const days = daily.data;
  const busiest = days.reduce<(typeof days)[number] | null>((a, d) => (!a || d.output_tokens > a.output_tokens ? d : a), null);
  return (
    <>
      <Grid>
        <KpiCard
          label="Active days"
          value={fmt.int(days.length)}
          sub={<RangeNote />}
          sparkline={days.map((d) => d.output_tokens)}
          sparkColor="var(--chart-input)"
        />
        <KpiCard
          label="Busiest day"
          value={busiest ? busiest.day : "—"}
          sub={busiest ? `${fmt.compact(busiest.output_tokens)} output tokens` : undefined}
        />
      </Grid>
      <ComingSoon page="Activity" />
    </>
  );
}

export function ToolsPlaceholder() {
  const tools = useRangedQuery("/api/tools");
  if (tools.isError) return <ErrorState error={tools.error} onRetry={() => tools.refetch()} />;
  if (!tools.data) return <KpiGridSkeleton count={2} />;
  const calls = tools.data.reduce((s, t) => s + t.calls, 0);
  const top = [...tools.data].sort((a, b) => b.calls - a.calls)[0];
  return (
    <>
      <Grid>
        <KpiCard label="Tool calls" value={fmt.int(calls)} sub={<RangeNote />} />
        <KpiCard label="Distinct tools" value={fmt.int(tools.data.length)} sub={top ? `Most used: ${top.tool_name}` : undefined} />
      </Grid>
      <ComingSoon page="Tools" />
    </>
  );
}
