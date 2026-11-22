"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useRouter } from "next/navigation";
import { useMemo } from "react";

import { DataTable } from "@/components/data-table";
import { ErrorState } from "@/components/error-state";
import { ExportButton } from "@/components/export-button";
import { FilterBar, SearchBox } from "@/components/filters";
import { Sparkline } from "@/components/sparkline";
import { Card, CardContent } from "@/components/ui/card";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useRangedHref, useUrlState } from "@/hooks/use-url-state";
import type { Schema } from "@/lib/api";
import { fmt } from "@/lib/format";
import { GLOSSARY } from "@/lib/glossary";
import { useRangedQuery } from "@/lib/queries";
import { dayList } from "@/lib/usage";

type Project = Schema<"ProjectRow"> & { spark: number[] };

const num = (id: keyof Schema<"ProjectRow">, header: string, info?: string): ColumnDef<Project, unknown> => ({
  id,
  header,
  accessorFn: (p) => p[id] ?? -1,
  sortDescFirst: true,
  meta: { numeric: true, info },
  cell: ({ row }) => fmt.int(row.original[id] as number),
});

export function ProjectsPage() {
  const { get } = useUrlState();
  const q = (get("q") ?? "").toLowerCase();
  const href = useRangedHref();
  const router = useRouter();
  const projects = useRangedQuery("/api/projects");
  const daily = useRangedQuery("/api/projects/daily");

  const rows = useMemo<Project[]>(() => {
    const list = projects.data ?? [];
    const d = daily.data ?? [];
    // One shared day axis for every sparkline, so their shapes compare.
    const days = d.length ? dayList(d.reduce((a, r) => (r.day < a ? r.day : a), d[0].day), d.reduce((a, r) => (r.day > a ? r.day : a), d[0].day)) : [];
    const index = new Map(days.map((day, i) => [day, i]));
    const series = new Map<string, number[]>();
    for (const r of d) {
      const s = series.get(r.project_slug) ?? new Array<number>(days.length).fill(0);
      s[index.get(r.day) ?? 0] += r.cost_usd;
      series.set(r.project_slug, s);
    }
    return list
      .filter((p) => !q || p.project_name.toLowerCase().includes(q) || p.project_slug.toLowerCase().includes(q))
      .map((p) => ({ ...p, spark: series.get(p.project_slug) ?? [] }));
  }, [projects.data, daily.data, q]);

  const columns = useMemo<ColumnDef<Project, unknown>[]>(
    () => [
      {
        id: "project_name",
        header: "Project",
        accessorFn: (p) => p.project_name.toLowerCase(),
        sortDescFirst: false,
        meta: { className: "min-w-44" },
        cell: ({ row }) => (
          <span className="blur-sensitive block max-w-64 truncate font-medium" title={row.original.project_slug}>
            {row.original.project_name}
          </span>
        ),
      },
      {
        id: "trend",
        header: "Daily cost",
        enableSorting: false,
        cell: ({ row }) => <Sparkline values={row.original.spark} color="var(--chart-output)" />,
      },
      {
        id: "estimated_cost_usd",
        header: "Cost",
        accessorFn: (p) => p.estimated_cost_usd ?? -1,
        sortDescFirst: true,
        meta: { numeric: true, info: GLOSSARY.estCost },
        cell: ({ row }) => fmt.usd(row.original.estimated_cost_usd),
      },
      num("sessions", "Sessions", GLOSSARY.session),
      num("turns", "Turns", GLOSSARY.turn),
      num("input_tokens", "Input", GLOSSARY.input),
      num("output_tokens", "Output", GLOSSARY.output),
      num("cache_read_tokens", "Cache reads", GLOSSARY.cacheRead),
      {
        id: "cache_write_tokens",
        header: "Cache writes",
        accessorFn: (p) => p.cache_write_tokens,
        sortDescFirst: true,
        meta: { numeric: true, info: GLOSSARY.cacheCreate },
        cell: ({ row }) => (
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="cursor-default underline decoration-dotted decoration-muted-foreground/50 underline-offset-4">
                {fmt.int(row.original.cache_write_tokens)}
              </span>
            </TooltipTrigger>
            <TooltipContent className="font-mono tabular">
              5m: {fmt.int(row.original.cache_create_5m_tokens)} · 1h: {fmt.int(row.original.cache_create_1h_tokens)}
            </TooltipContent>
          </Tooltip>
        ),
      },
      num("total_tokens", "Total tokens", GLOSSARY.totalTokens),
      {
        id: "last_active",
        header: "Last active",
        accessorFn: (p) => p.last_active ?? "",
        sortDescFirst: true,
        cell: ({ row }) => <span className="font-mono text-xs whitespace-nowrap text-muted-foreground tabular">{fmt.ts(row.original.last_active)}</span>,
      },
    ],
    [],
  );

  if (projects.isError) return <ErrorState error={projects.error} onRetry={() => projects.refetch()} />;

  return (
    <div className="flex flex-col gap-4">
      <FilterBar>
        <SearchBox placeholder="Filter projects" />
        <span className="text-xs text-muted-foreground tabular">
          {projects.data ? `${fmt.int(rows.length)} of ${fmt.int(projects.data.length)} projects` : null}
        </span>
        <ExportButton table="projects" query={{ q: get("q") }} />
      </FilterBar>
      <Card className="py-4">
        <CardContent className="px-4">
          <p className="mb-3 text-xs text-muted-foreground">Click a project to see its costs, models and sessions. Click a column header to sort.</p>
          <DataTable
            columns={columns}
            data={projects.data ? rows : undefined}
            getRowId={(p) => p.project_slug}
            initialSort={[{ id: "estimated_cost_usd", desc: true }]}
            loading={!projects.data}
            dim={projects.isPlaceholderData}
            onRowClick={(p) => router.push(href(`/projects/${encodeURIComponent(p.project_slug)}`))}
            empty={q ? "No projects match this filter." : "No projects in this range."}
          />
        </CardContent>
      </Card>
    </div>
  );
}
