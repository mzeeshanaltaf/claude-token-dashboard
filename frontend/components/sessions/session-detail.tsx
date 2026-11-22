"use client";

import type { ColumnDef } from "@tanstack/react-table";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMemo, useState } from "react";

import { TokenComposition, type TokenTotals } from "@/components/charts/token-composition";
import { DataTable } from "@/components/data-table";
import { CopyId, DetailHeader } from "@/components/detail-header";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { KpiCard } from "@/components/kpi-card";
import { ChartSkeleton, KpiGridSkeleton, TableSkeleton } from "@/components/loading";
import { ModelBadge } from "@/components/model-badge";
import { SectionCard } from "@/components/section-card";
import { Badge } from "@/components/ui/badge";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { useRangedHref } from "@/hooks/use-url-state";
import type { Schema } from "@/lib/api";
import { fmt } from "@/lib/format";
import { GLOSSARY } from "@/lib/glossary";
import { useApiQuery } from "@/lib/queries";

import { TurnDialog, toolCallsOf } from "./turn-dialog";

type Turn = Schema<"TurnRow">;

/** The project label the old page used: the cwd's last folder, else the slug. */
function projectLabel(turns: Turn[]): string {
  const cwd = turns.find((t) => t.cwd)?.cwd ?? "";
  const base = cwd.replace(/\\/g, "/").replace(/\/+$/, "").split("/").pop();
  return base || turns[0]?.project_slug || "";
}

function totalsOf(turns: Turn[]): TokenTotals & { cost: number } {
  const t = {
    input_tokens: 0,
    output_tokens: 0,
    cache_read_tokens: 0,
    cache_create_5m_tokens: 0,
    cache_create_1h_tokens: 0,
    cost_input_usd: 0,
    cost_output_usd: 0,
    cost_cache_read_usd: 0,
    cost_cache_create_5m_usd: 0,
    cost_cache_create_1h_usd: 0,
    cost: 0,
  };
  for (const r of turns) {
    if (r.type !== "assistant") continue;
    t.input_tokens += r.input_tokens;
    t.output_tokens += r.output_tokens;
    t.cache_read_tokens += r.cache_read_tokens;
    t.cache_create_5m_tokens += r.cache_create_5m_tokens;
    t.cache_create_1h_tokens += r.cache_create_1h_tokens;
    t.cost_input_usd += r.cost_input_usd ?? 0;
    t.cost_output_usd += r.cost_output_usd ?? 0;
    t.cost_cache_read_usd += r.cost_cache_read_usd ?? 0;
    t.cost_cache_create_5m_usd += r.cost_cache_create_5m_usd ?? 0;
    t.cost_cache_create_1h_usd += r.cost_cache_create_1h_usd ?? 0;
    t.cost += r.estimated_cost_usd ?? 0;
  }
  return t;
}

/** One-line summary: the prompt, else the tool names. */
function summaryOf(t: Turn): string {
  if (t.prompt_text) return t.prompt_text.replace(/\s+/g, " ").trim();
  return toolCallsOf(t)
    .map((c) => c.name)
    .join(" · ");
}

const n = (id: string, header: string, get: (t: Turn) => number, info?: string): ColumnDef<Turn, unknown> => ({
  id,
  header,
  accessorFn: get,
  sortDescFirst: true,
  meta: { numeric: true, info },
  cell: ({ getValue }) => fmt.int(getValue() as number),
});

export function SessionDetail() {
  const { id } = useParams<{ id: string }>();
  const sessionId = decodeURIComponent(id);
  const href = useRangedHref();
  const q = useApiQuery("/api/sessions/{session_id}", { params: { session_id: sessionId } });
  const [open, setOpen] = useState<Turn | null>(null);
  const [show, setShow] = useState<"turns" | "all">("turns");

  const turns = useMemo(() => q.data ?? [], [q.data]);
  // "Turns": prompts and assistant replies. Tool-result and attachment records
  // (no tokens, no text of their own) are hidden until "All records".
  const shown = useMemo(
    () => (show === "all" ? turns : turns.filter((t) => t.type === "assistant" || (t.type === "user" && !!t.prompt_text))),
    [turns, show],
  );
  const totals = useMemo(() => totalsOf(turns), [turns]);

  const columns = useMemo<ColumnDef<Turn, unknown>[]>(
    () => [
      {
        id: "time",
        header: "Time",
        accessorFn: (t) => t.timestamp,
        cell: ({ row }) => <span className="font-mono text-xs text-muted-foreground tabular">{fmt.tsTime(row.original.timestamp)}</span>,
      },
      {
        id: "type",
        header: "Type",
        accessorFn: (t) => t.type,
        cell: ({ row }) => (
          <span className="flex items-center gap-1.5 text-xs">
            {row.original.type}
            {row.original.is_sidechain && (
              <Badge variant="secondary" className="h-4 px-1.5 text-[10px]" title="Sidechain (subagent) record">
                side
              </Badge>
            )}
          </span>
        ),
      },
      {
        id: "model",
        header: "Model",
        enableSorting: false,
        cell: ({ row }) => (row.original.model ? <ModelBadge model={row.original.model} /> : null),
      },
      {
        id: "summary",
        header: "Prompt / tools",
        enableSorting: false,
        meta: { className: "w-full max-w-0 min-w-56" },
        cell: ({ row }) => {
          const s = summaryOf(row.original);
          return <span className="blur-sensitive block truncate text-sm">{s || <span className="text-muted-foreground">—</span>}</span>;
        },
      },
      n("in", "In", (t) => t.input_tokens, GLOSSARY.input),
      n("out", "Out", (t) => t.output_tokens, GLOSSARY.output),
      n("cache_rd", "Cache rd", (t) => t.cache_read_tokens, GLOSSARY.cacheRead),
      n("cache_5m", "Cache wr 5m", (t) => t.cache_create_5m_tokens, "Cache write, 5-minute TTL."),
      n("cache_1h", "Cache wr 1h", (t) => t.cache_create_1h_tokens, "Cache write, 1-hour TTL."),
      {
        id: "cost",
        header: "Cost",
        accessorFn: (t) => t.estimated_cost_usd ?? -1,
        sortDescFirst: true,
        meta: { numeric: true },
        cell: ({ row }) => (row.original.estimated_cost_usd == null ? "" : fmt.usd4(row.original.estimated_cost_usd)),
      },
    ],
    [],
  );

  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data) {
    return (
      <div className="flex flex-col gap-6">
        <ChartSkeleton className="h-16" />
        <KpiGridSkeleton count={5} />
        <TableSkeleton />
      </div>
    );
  }
  if (!turns.length) {
    return (
      <EmptyState title="Session not found" description={`No records for session ${sessionId}.`}>
        <Link href={href("/sessions")} className="text-sm underline">
          Back to sessions
        </Link>
      </EmptyState>
    );
  }

  const title = turns.find((t) => t.title)?.title;
  const started = turns[0].timestamp;
  const ended = turns[turns.length - 1].timestamp;
  const slug = turns[0].project_slug;

  return (
    <div className="flex flex-col gap-6">
      <DetailHeader
        backHref={href("/sessions")}
        backLabel="All sessions"
        title={title || `Session ${sessionId.slice(0, 8)}…`}
        meta={
          <>
            <Link href={href(`/projects/${encodeURIComponent(slug)}`)} className="blur-sensitive hover:text-foreground hover:underline">
              {projectLabel(turns)}
            </Link>
            <CopyId id={sessionId} label="session id" />
          </>
        }
      />

      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5">
        <KpiCard label="Started" value={<span className="text-lg">{fmt.ts(started)}</span>} />
        <KpiCard label="Ended" value={<span className="text-lg">{fmt.ts(ended)}</span>} />
        <KpiCard label="Duration" value={fmt.duration(new Date(ended).getTime() - new Date(started).getTime())} />
        <KpiCard label="Records" value={fmt.int(turns.length)} sub={`${fmt.int(turns.filter((t) => t.type === "user" && t.prompt_text).length)} prompts`} />
        <KpiCard label="Est. cost" value={fmt.usd(totals.cost)} info={GLOSSARY.estCost} className="col-span-2 md:col-span-1" />
      </div>

      <TokenComposition totals={totals} title="Tokens in this session" />

      <SectionCard
        title="Turn by turn"
        description="In time order. Click a row with a prompt or tool calls to read it in full."
        action={
          <ToggleGroup type="single" size="sm" variant="outline" value={show} onValueChange={(v) => v && setShow(v as "turns" | "all")} aria-label="Records shown">
            <ToggleGroupItem value="turns">Turns</ToggleGroupItem>
            <ToggleGroupItem value="all">All records ({fmt.int(turns.length)})</ToggleGroupItem>
          </ToggleGroup>
        }
      >
        <DataTable
          columns={columns}
          data={shown}
          getRowId={(t) => t.uuid}
          clientPageSize={100}
          onRowClick={(t) => (t.prompt_text || toolCallsOf(t).length ? setOpen(t) : undefined)}
          rowClassName={(r) => (r.original.prompt_text || toolCallsOf(r.original).length ? undefined : "cursor-default")}
        />
      </SectionCard>

      <TurnDialog turn={open} onOpenChange={(o) => !o && setOpen(null)} />
    </div>
  );
}
