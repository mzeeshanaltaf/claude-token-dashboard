"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useParams, useRouter } from "next/navigation";
import { useMemo } from "react";

import { DailyChart } from "@/components/charts/daily-chart";
import { ModelMix } from "@/components/charts/model-mix";
import { TokenComposition } from "@/components/charts/token-composition";
import { DataTable } from "@/components/data-table";
import { DetailHeader } from "@/components/detail-header";
import { ErrorState } from "@/components/error-state";
import { KpiCard } from "@/components/kpi-card";
import { ChartSkeleton, KpiGridSkeleton } from "@/components/loading";
import { SectionCard } from "@/components/section-card";
import { useRange } from "@/hooks/use-range";
import { useRangedHref } from "@/hooks/use-url-state";
import type { Schema } from "@/lib/api";
import { fmt } from "@/lib/format";
import { GLOSSARY } from "@/lib/glossary";
import { useRangedQuery } from "@/lib/queries";
import { rangeLabel } from "@/lib/range";

type ProjectSession = Schema<"ProjectSessionRow">;

export function ProjectDetail() {
  const { slug: raw } = useParams<{ slug: string }>();
  const slug = decodeURIComponent(raw);
  const href = useRangedHref();
  const router = useRouter();
  const { range } = useRange();

  const overview = useRangedQuery("/api/overview", { project: slug });
  const daily = useRangedQuery("/api/daily", { project: slug });
  const models = useRangedQuery("/api/by-model", { project: slug });
  const projects = useRangedQuery("/api/projects");
  const sessions = useRangedQuery("/api/projects/{slug}/sessions", undefined, { params: { slug } });

  const name =
    projects.data?.find((p) => p.project_slug === slug)?.project_name ?? sessions.data?.[0]?.project_name ?? slug;

  const columns = useMemo<ColumnDef<ProjectSession, unknown>[]>(
    () => [
      {
        id: "started",
        header: "Started",
        accessorFn: (s) => s.started,
        sortDescFirst: true,
        cell: ({ row }) => <span className="font-mono text-xs whitespace-nowrap text-muted-foreground tabular">{fmt.ts(row.original.started)}</span>,
      },
      {
        id: "ended",
        header: "Ended",
        accessorFn: (s) => s.ended,
        sortDescFirst: true,
        cell: ({ row }) => <span className="font-mono text-xs whitespace-nowrap text-muted-foreground tabular">{fmt.ts(row.original.ended)}</span>,
      },
      {
        id: "title",
        header: "Title",
        accessorFn: (s) => (s.title ?? "").toLowerCase(),
        meta: { className: "w-full max-w-0 min-w-48" },
        cell: ({ row }) => (
          <span className="blur-sensitive block truncate text-sm" title={row.original.title ?? undefined}>
            {row.original.title || <span className="font-mono text-xs text-muted-foreground">{row.original.session_id.slice(0, 8)}…</span>}
          </span>
        ),
      },
      {
        id: "turns",
        header: "Turns",
        accessorFn: (s) => s.turns,
        sortDescFirst: true,
        meta: { numeric: true, info: GLOSSARY.turn },
        cell: ({ row }) => fmt.int(row.original.turns),
      },
      {
        id: "tokens",
        header: "Tokens",
        accessorFn: (s) => s.tokens,
        sortDescFirst: true,
        meta: { numeric: true, info: "Input + output tokens." },
        cell: ({ row }) => fmt.int(row.original.tokens),
      },
      {
        id: "cost",
        header: "Cost",
        accessorFn: (s) => s.estimated_cost_usd ?? -1,
        sortDescFirst: true,
        meta: { numeric: true },
        cell: ({ row }) => fmt.usd(row.original.estimated_cost_usd),
      },
    ],
    [],
  );

  const o = overview.data;
  const totalTokens = o
    ? o.input_tokens + o.output_tokens + o.cache_read_tokens + o.cache_create_5m_tokens + o.cache_create_1h_tokens
    : 0;

  return (
    <div className="flex flex-col gap-6">
      <DetailHeader
        backHref={href("/projects")}
        backLabel="All projects"
        title={name}
        meta={
          <>
            <span className="blur-sensitive font-mono" title="project slug">
              {slug}
            </span>
            <span>{rangeLabel(range)}</span>
          </>
        }
      />

      {overview.isError ? (
        <ErrorState error={overview.error} onRetry={() => overview.refetch()} />
      ) : !o ? (
        <KpiGridSkeleton />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <KpiCard label="Est. cost" value={fmt.usd(o.cost_usd)} info={GLOSSARY.estCost} sparkline={(daily.data ?? []).map((d) => d.cost_usd)} sparkColor="var(--chart-output)" />
          <KpiCard label="Sessions" value={fmt.int(o.sessions)} info={GLOSSARY.session} sparkline={(daily.data ?? []).map((d) => d.sessions)} />
          <KpiCard label="Turns" value={fmt.int(o.turns)} info={GLOSSARY.turn} sparkline={(daily.data ?? []).map((d) => d.turns)} />
          <KpiCard label="Total tokens" value={fmt.compact(totalTokens)} sub={`${fmt.int(totalTokens)} tokens`} info={GLOSSARY.totalTokens} />
        </div>
      )}

      {o && o.sessions === 0 ? (
        <p className="text-sm text-muted-foreground">No activity for this project in this range. Try a wider range.</p>
      ) : (
        <>
          {o ? <TokenComposition totals={o} title="Cost breakdown" dim={overview.isPlaceholderData} /> : <ChartSkeleton className="h-36" />}
          <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
            {daily.data ? (
              <DailyChart rows={daily.data} title="Daily cost" defaultMode="cost" dim={daily.isPlaceholderData} />
            ) : (
              <ChartSkeleton className="h-96" />
            )}
            {models.data ? <ModelMix rows={models.data} dim={models.isPlaceholderData} /> : <ChartSkeleton className="h-96" />}
          </div>
        </>
      )}

      <SectionCard title="Sessions" description="Sessions of this project with activity in the range; tokens and cost cover that activity.">
        {sessions.isError ? (
          <ErrorState error={sessions.error} onRetry={() => sessions.refetch()} />
        ) : (
          <DataTable
            columns={columns}
            data={sessions.data}
            getRowId={(s) => s.session_id}
            initialSort={[{ id: "ended", desc: true }]}
            clientPageSize={50}
            loading={!sessions.data}
            dim={sessions.isPlaceholderData}
            onRowClick={(s) => router.push(href(`/sessions/${encodeURIComponent(s.session_id)}`))}
            empty="No sessions for this project in this range."
          />
        )}
      </SectionCard>
    </div>
  );
}
