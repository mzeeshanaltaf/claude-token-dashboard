"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useRouter } from "next/navigation";
import { useMemo } from "react";

import { DataTable } from "@/components/data-table";
import { ErrorState } from "@/components/error-state";
import { FilterBar, ModelSelect, ProjectSelect, SearchBox } from "@/components/filters";
import { Card, CardContent } from "@/components/ui/card";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useClampPage, useServerTable } from "@/hooks/use-server-table";
import { useRangedHref, useUrlState } from "@/hooks/use-url-state";
import type { Schema } from "@/lib/api";
import { fmt } from "@/lib/format";
import { GLOSSARY } from "@/lib/glossary";
import { useRangedQuery } from "@/lib/queries";

type Session = Schema<"SessionRow">;

const SORTS = [
  "started",
  "ended",
  "title",
  "turns",
  "tokens",
  "input_tokens",
  "output_tokens",
  "cache_read_tokens",
  "cache_write_tokens",
  "total_tokens",
  "cost",
] as const;

const num = (id: (typeof SORTS)[number], header: string, get: (s: Session) => number, info?: string): ColumnDef<Session, unknown> => ({
  id,
  header,
  sortDescFirst: true,
  meta: { numeric: true, info },
  cell: ({ row }) => fmt.int(get(row.original)),
});

export function SessionsPage() {
  const { get } = useUrlState();
  const t = useServerTable(SORTS, "started");
  const href = useRangedHref();
  const router = useRouter();
  const q = get("q") ?? undefined;
  const project = get("project") ?? undefined;
  const model = get("model") ?? undefined;

  const sessions = useRangedQuery("/api/sessions", { ...t.apiQuery, q, project, model });
  useClampPage(t.page, sessions.data?.total, sessions.data?.items.length, t.set);

  const columns = useMemo<ColumnDef<Session, unknown>[]>(
    () => [
      {
        id: "started",
        header: "Started",
        sortDescFirst: true,
        cell: ({ row }) => <span className="font-mono text-xs whitespace-nowrap text-muted-foreground tabular">{fmt.ts(row.original.started)}</span>,
      },
      {
        id: "project",
        header: "Project",
        enableSorting: false,
        cell: ({ row }) => (
          <span className="blur-sensitive block max-w-40 truncate text-xs" title={row.original.project_slug}>
            {row.original.project_name}
          </span>
        ),
      },
      {
        id: "title",
        header: "Title",
        sortDescFirst: false,
        meta: { className: "w-full max-w-0 min-w-48" },
        cell: ({ row }) => (
          <span className="blur-sensitive block truncate text-sm" title={row.original.title ?? undefined}>
            {row.original.title || <span className="font-mono text-xs text-muted-foreground">{row.original.session_id.slice(0, 8)}…</span>}
          </span>
        ),
      },
      num("turns", "Turns", (s) => s.turns, GLOSSARY.turn),
      num("input_tokens", "Input", (s) => s.input_tokens, GLOSSARY.input),
      num("output_tokens", "Output", (s) => s.output_tokens, GLOSSARY.output),
      num("cache_read_tokens", "Cache reads", (s) => s.cache_read_tokens, GLOSSARY.cacheRead),
      {
        id: "cache_write_tokens",
        header: "Cache writes",
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
      num("total_tokens", "Total tokens", (s) => s.total_tokens, GLOSSARY.totalTokens),
      {
        id: "cost",
        header: "Cost",
        sortDescFirst: true,
        meta: { numeric: true, info: "Estimated API-rate cost of the session's activity in this range." },
        cell: ({ row }) => fmt.usd(row.original.estimated_cost_usd),
      },
    ],
    [],
  );

  return (
    <div className="flex flex-col gap-4">
      <FilterBar>
        <SearchBox placeholder="Search title or session id" />
        <ProjectSelect />
        <ModelSelect />
      </FilterBar>
      {sessions.isError ? (
        <ErrorState error={sessions.error} onRetry={() => sessions.refetch()} />
      ) : (
        <Card className="py-4">
          <CardContent className="px-4">
            <DataTable
              columns={columns}
              data={sessions.data?.items}
              getRowId={(s) => s.session_id}
              server={t.table(sessions.data?.total ?? 0)}
              loading={!sessions.data}
              dim={sessions.isPlaceholderData}
              onRowClick={(s) => router.push(href(`/sessions/${encodeURIComponent(s.session_id)}`))}
              empty={q || project || model ? "No sessions match these filters." : "No sessions in this range."}
            />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
