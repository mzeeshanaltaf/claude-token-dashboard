"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { ClockIcon, GitBranchIcon } from "lucide-react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useCallback, useMemo, useState } from "react";

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

import { FilesCard, SubagentsCard } from "./insight-cards";
import { ToolTimeline } from "./tool-timeline";
import { ContextGrowthChart, TurnCostChart } from "./turn-charts";
import { TurnDialog, toolCallsOf } from "./turn-dialog";

type Turn = Schema<"TurnRow">;

/** Header chips: git branch(es), duration, models with their turn counts. */
function InsightChips({ data }: { data: Schema<"SessionInsights"> }) {
  return (
    <>
      {data.branches.map((b) => (
        <Badge key={b} variant="outline" className="blur-sensitive gap-1 font-mono text-[11px]" title="git branch">
          <GitBranchIcon />
          {b}
        </Badge>
      ))}
      {data.duration_s != null && (
        <Badge variant="outline" className="gap-1 text-[11px]" title="From the first to the last record">
          <ClockIcon />
          {fmt.duration(data.duration_s * 1000)}
        </Badge>
      )}
      {data.models.filter((m) => m.model !== "<synthetic>").map((m) => (
        <span key={m.model} className="inline-flex items-center gap-1" title={`${m.turns} turns · ${fmt.usd(m.cost)}`}>
          <ModelBadge model={m.model} />
          <span className="font-mono tabular">×{fmt.int(m.turns)}</span>
        </span>
      ))}
    </>
  );
}

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

const isTurn = (t: Turn) => t.type === "assistant" || (t.type === "user" && !!t.prompt_text);

export function SessionDetail() {
  const { id } = useParams<{ id: string }>();
  const sessionId = decodeURIComponent(id);
  const href = useRangedHref();
  const search = useSearchParams();
  const q = useApiQuery("/api/sessions/{session_id}", { params: { session_id: sessionId } });
  const insights = useApiQuery("/api/sessions/{session_id}/insights", { params: { session_id: sessionId } });
  const [open, setOpen] = useState<Turn | null>(null);
  const [show, setShow] = useState<"turns" | "all">("turns");
  const [focus, setFocus] = useState<{ id: string; nonce: number } | null>(null);

  const turns = useMemo(() => q.data ?? [], [q.data]);
  // "Turns": prompts and assistant replies. Tool-result and attachment records
  // (no tokens, no text of their own) are hidden until "All records".
  const shown = useMemo(() => (show === "all" ? turns : turns.filter(isTurn)), [turns, show]);
  const totals = useMemo(() => totalsOf(turns), [turns]);

  /** Show a record in the table: widen the filter if it hides it, then jump. */
  const focusTurn = useCallback(
    (uuid: string) => {
      const rec = turns.find((t) => t.uuid === uuid);
      if (!rec) return;
      if (!isTurn(rec)) setShow("all");
      setFocus((f) => ({ id: uuid, nonce: (f?.nonce ?? 0) + 1 }));
    },
    [turns],
  );

  // `?turn=<uuid>` (a search result): jump once the records have loaded.
  const turnParam = search.get("turn");
  const [handledTurn, setHandledTurn] = useState<string | null>(null);
  if (turnParam && q.data && handledTurn !== turnParam) {
    setHandledTurn(turnParam);
    const rec = q.data.find((t) => t.uuid === turnParam);
    if (rec) {
      if (!isTurn(rec)) setShow("all");
      setFocus({ id: turnParam, nonce: 1 });
    }
  }

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
            {insights.data && <InsightChips data={insights.data} />}
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

      {insights.isError ? (
        <ErrorState error={insights.error} onRetry={() => insights.refetch()} />
      ) : !insights.data ? (
        <>
          <ChartSkeleton className="h-80" />
          <ChartSkeleton className="h-48" />
        </>
      ) : (
        <>
          <ContextGrowthChart points={insights.data.context_growth} onTurn={focusTurn} />
          <TurnCostChart points={insights.data.context_growth} onTurn={focusTurn} />
          <ToolTimeline events={insights.data.tool_timeline} linked={insights.data.tool_calls_linked} onTurn={focusTurn} />
          <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
            <SubagentsCard
              agents={insights.data.subagents}
              invocations={insights.data.subagent_invocations}
              sessionCost={insights.data.cost_usd}
            />
            <FilesCard files={insights.data.files} total={insights.data.files_total} />
          </div>
        </>
      )}

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
          focusRow={focus}
          onRowClick={(t) => (t.prompt_text || toolCallsOf(t).length ? setOpen(t) : undefined)}
          rowClassName={(r) => (r.original.prompt_text || toolCallsOf(r.original).length ? undefined : "cursor-default")}
        />
      </SectionCard>

      <TurnDialog turn={open} onOpenChange={(o) => !o && setOpen(null)} />
    </div>
  );
}
