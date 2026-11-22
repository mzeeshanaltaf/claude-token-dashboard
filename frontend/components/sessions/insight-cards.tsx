"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useMemo } from "react";

import { DataTable } from "@/components/data-table";
import { SectionCard } from "@/components/section-card";
import { Badge } from "@/components/ui/badge";
import type { Schema } from "@/lib/api";
import { fmt } from "@/lib/format";

type Agent = Schema<"Subagent">;
type FileRow = Schema<"FileTouch">;

const FILES_SHOWN = 15;

/** "C:\a\b\c\d.ts" → "…/c/d.ts" (the full path is in the title). */
export function shortPath(p: string, keep = 3): string {
  const parts = p.replace(/\\/g, "/").split("/").filter(Boolean);
  return parts.length > keep ? `…/${parts.slice(-keep).join("/")}` : p;
}

function ShareBar({ share }: { share: number | null }) {
  if (share == null) return <span className="text-muted-foreground">—</span>;
  return (
    <span className="flex items-center justify-end gap-2">
      <span className="h-2 w-10 overflow-hidden rounded-full bg-muted" aria-hidden>
        <span className="block h-full rounded-r-[4px] bg-(--family-mythos)" style={{ width: `${Math.min(100, share * 100)}%` }} />
      </span>
      <span className="w-10 text-right">{fmt.pct(share, share < 0.1 ? 1 : 0)}</span>
    </span>
  );
}

/** Subagent runs (sidechain turns grouped by agent id) and their share of the session's cost. */
export function SubagentsCard({
  agents,
  invocations,
  sessionCost,
}: {
  agents: readonly Agent[];
  invocations: readonly Schema<"SubagentInvocation">[];
  sessionCost: number;
}) {
  const types = useMemo(() => {
    const m = new Map<string, number>();
    for (const i of invocations) m.set(i.subagent_type ?? "not recorded", (m.get(i.subagent_type ?? "not recorded") ?? 0) + 1);
    return [...m.entries()].sort((a, b) => b[1] - a[1]);
  }, [invocations]);
  const total = agents.reduce((s, a) => s + (a.cost ?? 0), 0);

  const columns = useMemo<ColumnDef<Agent, unknown>[]>(
    () => [
      {
        id: "agent",
        header: "Agent",
        accessorFn: (a) => a.first_ts,
        // id, start time and how long it ran, in one cell so the table fits a half-width card
        cell: ({ row }) => {
          const a = row.original;
          const ran = new Date(a.last_ts).getTime() - new Date(a.first_ts).getTime();
          return (
            <span className="flex flex-col font-mono text-xs" title={a.agent_id}>
              {a.agent_id.slice(0, 8)}
              <span className="text-[11px] text-muted-foreground">
                {fmt.tsTime(a.first_ts)} · {fmt.duration(ran)}
              </span>
            </span>
          );
        },
      },
      { id: "turns", header: "Turns", accessorFn: (a) => a.turns, sortDescFirst: true, meta: { numeric: true }, cell: ({ getValue }) => fmt.int(getValue() as number) },
      {
        id: "tokens",
        header: "Tokens",
        accessorFn: (a) => a.tokens,
        sortDescFirst: true,
        meta: { numeric: true, info: "Input, output and cache writes (cache reads left out)." },
        cell: ({ getValue }) => fmt.compact(getValue() as number),
      },
      { id: "cost", header: "Cost", accessorFn: (a) => a.cost ?? -1, sortDescFirst: true, meta: { numeric: true }, cell: ({ row }) => fmt.usd(row.original.cost) },
      {
        id: "share",
        header: "Share",
        accessorFn: (a) => a.cost ?? -1,
        sortDescFirst: true,
        meta: { numeric: true, info: "Share of the whole session's estimated cost." },
        cell: ({ row }) => <ShareBar share={sessionCost > 0 && row.original.cost != null ? row.original.cost / sessionCost : null} />,
      },
    ],
    [sessionCost],
  );

  return (
    <SectionCard
      title="Subagents"
      description={
        agents.length
          ? `${agents.length} subagent run${agents.length === 1 ? "" : "s"} cost ${fmt.usd(total)}, ${fmt.pct(sessionCost ? total / sessionCost : 0)} of this session.`
          : "No subagents ran in this session."
      }
    >
      {(agents.length > 0 || invocations.length > 0) && (
        <div className="flex flex-col gap-3">
          {invocations.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
              <span>{fmt.int(invocations.length)} Agent/Task calls:</span>
              {types.map(([t, n]) => (
                <Badge key={t} variant="secondary" className="font-mono text-[11px]" title={t === "not recorded" ? "Default agent, or a call ingested before the subagent type was recorded" : undefined}>
                  {t} ×{n}
                </Badge>
              ))}
            </div>
          )}
          {agents.length > 0 && <DataTable columns={columns} data={agents} clientPageSize={8} getRowId={(a) => a.agent_id} />}
        </div>
      )}
    </SectionCard>
  );
}

/** The most-touched files with their Read / Edit / Write counts. */
export function FilesCard({ files, total }: { files: readonly FileRow[]; total: number }) {
  const shown = files.slice(0, FILES_SHOWN);
  const max = Math.max(1, ...shown.map((f) => f.total));
  return (
    <SectionCard
      title="Files touched"
      description={total ? `Read, Edit and Write calls per file. Top ${shown.length} of ${fmt.int(total)}.` : "No file reads or edits in this session."}
    >
      {shown.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full table-fixed text-sm">
            <thead>
              <tr className="text-xs text-muted-foreground">
                <th className="pb-2 text-left font-medium">File</th>
                <th className="w-12 pb-2 pl-2 text-right font-medium">Read</th>
                <th className="w-12 pb-2 pl-2 text-right font-medium">Edit</th>
                <th className="w-12 pb-2 pl-2 text-right font-medium">Write</th>
                <th className="w-24 pb-2 pl-3 text-left font-medium">Total</th>
              </tr>
            </thead>
            <tbody className="font-mono text-xs tabular">
              {shown.map((f) => (
                <tr key={f.path} className="border-t">
                  <td className="py-1.5 pr-2">
                    <span className="blur-sensitive block truncate" title={f.path}>
                      {shortPath(f.path)}
                    </span>
                  </td>
                  <td className="py-1.5 pl-2 text-right">{f.read || "·"}</td>
                  <td className="py-1.5 pl-2 text-right">{f.edit || "·"}</td>
                  <td className="py-1.5 pl-2 text-right">{f.write || "·"}</td>
                  <td className="py-1.5 pl-3">
                    <span className="flex items-center gap-2">
                      <span className="h-2 rounded-r-[4px] bg-(--chart-input)" style={{ width: `${(f.total / max) * 3.5}rem` }} aria-hidden />
                      {f.total}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </SectionCard>
  );
}
