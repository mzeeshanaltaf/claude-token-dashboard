"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { InfoIcon } from "lucide-react";
import { useMemo, useState } from "react";

import { BarList } from "@/components/bar-list";
import { DataTable } from "@/components/data-table";
import { ErrorState } from "@/components/error-state";
import { KpiCard } from "@/components/kpi-card";
import { ChartSkeleton, KpiGridSkeleton } from "@/components/loading";
import { SectionCard } from "@/components/section-card";
import { shortPath } from "@/components/sessions/insight-cards";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import type { Schema } from "@/lib/api";
import { fmt } from "@/lib/format";
import { useRangedQuery } from "@/lib/queries";

type Tool = Schema<"ToolStat">;
type FileStat = Schema<"FileStat">;
type Command = Schema<"CommandStat">;

const BARS = 12;

const num = <T,>(id: string, header: string, get: (r: T) => number, info?: string): ColumnDef<T, unknown> => ({
  id,
  header,
  accessorFn: get,
  sortDescFirst: true,
  meta: { numeric: true, info },
  cell: ({ getValue }) => fmt.int(getValue() as number),
});

const lastUsed = <T extends { last_used: string }>(): ColumnDef<T, unknown> => ({
  id: "last_used",
  header: "Last used",
  accessorFn: (r) => r.last_used,
  sortDescFirst: true,
  meta: { numeric: true },
  cell: ({ row }) => <span className="text-muted-foreground">{fmt.relative(row.original.last_used)}</span>,
});

/** Ranked bars, the top BARS rows with a "show all" toggle. */
function RankedTools({ items, value, display, color }: {
  items: readonly Tool[];
  value: (t: Tool) => number;
  display: (n: number) => string;
  color: string;
}) {
  const [all, setAll] = useState(false);
  const ranked = [...items].filter((t) => value(t) > 0).sort((a, b) => value(b) - value(a));
  const shown = all ? ranked : ranked.slice(0, BARS);
  const total = ranked.reduce((s, t) => s + value(t), 0);
  if (!ranked.length) return <p className="py-6 text-center text-sm text-muted-foreground">Nothing to show for this range.</p>;
  return (
    <div className="flex flex-col gap-2">
      <BarList
        color={color}
        items={shown.map((t) => ({
          key: t.tool_name,
          label: <span className="font-mono text-xs">{t.tool_name}</span>,
          value: value(t),
          display: display(value(t)),
          aside: fmt.pct(total ? value(t) / total : 0),
        }))}
      />
      {ranked.length > BARS && (
        <Button variant="ghost" size="xs" className="self-start text-muted-foreground" onClick={() => setAll((a) => !a)}>
          {all ? "Show top 12" : `Show all ${ranked.length}`}
        </Button>
      )}
    </div>
  );
}

export function ToolsPage() {
  const q = useRangedQuery("/api/tools/insights");
  const d = q.data;

  const toolCols = useMemo<ColumnDef<Tool, unknown>[]>(
    () => [
      {
        id: "tool",
        header: "Tool",
        accessorFn: (t) => t.tool_name.toLowerCase(),
        meta: { className: "w-full" },
        cell: ({ row }) => <span className="font-mono text-xs">{row.original.tool_name}</span>,
      },
      num<Tool>("calls", "Calls", (t) => t.calls),
      num<Tool>("linked", "Linked", (t) => t.linked, "Calls whose result can be matched by tool_use_id. Errors and result tokens are counted over these only."),
      num<Tool>("errors", "Errors", (t) => t.errors),
      {
        id: "rate",
        header: "Error rate",
        accessorFn: (t) => t.error_rate ?? -1,
        sortDescFirst: true,
        meta: { numeric: true },
        cell: ({ row }) => {
          const r = row.original.error_rate;
          if (r == null) return <span className="text-muted-foreground">—</span>;
          return <span className={r >= 0.1 ? "font-semibold text-destructive" : undefined}>{fmt.pct(r, 1)}</span>;
        },
      },
      num<Tool>("result", "Result tokens", (t) => t.result_tokens, "Estimated tokens in the tool's results (characters / 4), linked calls only."),
    ],
    [],
  );

  const fileCols = useMemo<ColumnDef<FileStat, unknown>[]>(
    () => [
      {
        id: "path",
        header: "File",
        accessorFn: (f) => f.path,
        meta: { className: "w-full max-w-0 min-w-48" },
        cell: ({ row }) => (
          <span className="blur-sensitive block truncate font-mono text-xs" title={row.original.path}>
            {shortPath(row.original.path, 4)}
          </span>
        ),
      },
      num<FileStat>("read", "Read", (f) => f.read),
      num<FileStat>("edit", "Edit", (f) => f.edit),
      num<FileStat>("write", "Write", (f) => f.write),
      num<FileStat>("total", "Total", (f) => f.total),
      num<FileStat>("sessions", "Sessions", (f) => f.sessions),
      lastUsed<FileStat>(),
    ],
    [],
  );

  const cmdCols = useMemo<ColumnDef<Command, unknown>[]>(
    () => [
      {
        id: "command",
        header: "Command",
        accessorFn: (c) => c.command,
        meta: { className: "w-full max-w-0 min-w-48" },
        cell: ({ row }) => (
          <code className="blur-sensitive block truncate text-xs" title={row.original.command}>
            {row.original.command.replace(/\s+/g, " ")}
          </code>
        ),
      },
      {
        id: "shell",
        header: "Shell",
        accessorFn: (c) => c.tool_name,
        cell: ({ row }) => <span className="text-xs text-muted-foreground">{row.original.tool_name}</span>,
      },
      num<Command>("calls", "Calls", (c) => c.calls),
      num<Command>("sessions", "Sessions", (c) => c.sessions),
      lastUsed<Command>(),
    ],
    [],
  );

  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!d) {
    return (
      <div className="flex flex-col gap-6">
        <KpiGridSkeleton count={4} />
        <ChartSkeleton />
      </div>
    );
  }

  const errors = d.tools.reduce((s, t) => s + t.errors, 0);
  const coverage = d.calls ? d.linked / d.calls : 0;
  const top = d.tools[0];

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard label="Tool calls" value={fmt.int(d.calls)} sub={`${fmt.int(d.tools.length)} distinct tools`} />
        <KpiCard label="Most used" value={top ? <span className="font-mono text-xl">{top.tool_name}</span> : "—"} sub={top ? `${fmt.int(top.calls)} calls (${fmt.pct(top.calls / d.calls)})` : undefined} />
        <KpiCard
          label="Error rate"
          value={d.linked ? fmt.pct(errors / d.linked, 1) : "—"}
          sub={d.linked ? `${fmt.int(errors)} failed of ${fmt.int(d.linked)} linked calls` : "no linked calls"}
          info={d.linked_note}
        />
        <KpiCard label="Linked calls" value={fmt.pct(coverage, coverage < 0.1 ? 1 : 0)} sub={`${fmt.int(d.linked)} of ${fmt.int(d.calls)}`} info={d.linked_note} />
      </div>

      {coverage < 0.5 && d.calls > 0 && (
        <Alert>
          <InfoIcon />
          <AlertTitle>Error rates and result tokens cover only {fmt.pct(coverage, 1)} of calls</AlertTitle>
          <AlertDescription>{d.linked_note}</AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <SectionCard title="Calls by tool" description="How often Claude reached for each tool." dim={q.isPlaceholderData}>
          <RankedTools items={d.tools} value={(t) => t.calls} display={fmt.int} color="var(--chart-input)" />
        </SectionCard>
        <SectionCard
          title="Result tokens by tool"
          description="Estimated tokens the tools' results put into context (characters / 4), over linked calls."
          dim={q.isPlaceholderData}
        >
          <RankedTools items={d.tools} value={(t) => t.result_tokens} display={fmt.compact} color="var(--chart-cache-write)" />
        </SectionCard>
      </div>

      <SectionCard title="Errors by tool" description="Failed results per tool. A rate of 10% or more is highlighted." dim={q.isPlaceholderData}>
        <DataTable columns={toolCols} data={d.tools} initialSort={[{ id: "calls", desc: true }]} clientPageSize={15} getRowId={(t) => t.tool_name} />
      </SectionCard>

      <div className="grid grid-cols-1 gap-6 2xl:grid-cols-2">
        <SectionCard title="Top files" description="The 20 files read, edited or written most often." dim={q.isPlaceholderData}>
          <DataTable columns={fileCols} data={d.files} initialSort={[{ id: "total", desc: true }]} getRowId={(f) => f.path} empty="No file reads or edits in this range." />
        </SectionCard>
        <SectionCard title="Top commands" description="The 20 most-run shell commands (Bash and PowerShell), exactly as typed." dim={q.isPlaceholderData}>
          <DataTable columns={cmdCols} data={d.commands} initialSort={[{ id: "calls", desc: true }]} getRowId={(c) => c.command} empty="No shell commands in this range." />
        </SectionCard>
      </div>

      <SectionCard title="WebFetch domains" description="Where Claude fetched pages from." dim={q.isPlaceholderData}>
        {d.domains.length ? (
          <BarList
            sensitiveLabels
            color="var(--chart-cache-read)"
            items={d.domains.map((x) => ({
              key: x.domain,
              label: <span className="font-mono text-xs">{x.domain}</span>,
              value: x.calls,
              display: fmt.int(x.calls),
              tooltip: `Last fetched ${fmt.ts(x.last_used)}`,
            }))}
          />
        ) : (
          <p className="py-6 text-center text-sm text-muted-foreground">No WebFetch calls in this range.</p>
        )}
      </SectionCard>
    </div>
  );
}
