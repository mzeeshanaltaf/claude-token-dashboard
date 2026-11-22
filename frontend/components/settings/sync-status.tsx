"use client";

import { CheckCircle2Icon, CircleAlertIcon, LoaderIcon, TerminalIcon } from "lucide-react";

import { ErrorState } from "@/components/error-state";
import { TableSkeleton } from "@/components/loading";
import { SectionCard } from "@/components/section-card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { fmt } from "@/lib/format";
import { useApiQuery } from "@/lib/queries";

/** Status with an icon and a word, never colour alone. */
function RunStatus({ status }: { status: string }) {
  if (status === "ok")
    return (
      <span className="inline-flex items-center gap-1 text-success">
        <CheckCircle2Icon className="size-3.5" /> ok
      </span>
    );
  if (status === "running")
    return (
      <span className="inline-flex items-center gap-1 text-warning">
        <LoaderIcon className="size-3.5" /> running
      </span>
    );
  return (
    <span className="inline-flex items-center gap-1 text-destructive">
      <CircleAlertIcon className="size-3.5" /> {status}
    </span>
  );
}

function seconds(a: string, b: string | null | undefined): string {
  if (!b) return "—";
  return `${((new Date(b).getTime() - new Date(a).getTime()) / 1000).toFixed(1)}s`;
}

export function SyncStatusCard() {
  const q = useApiQuery("/api/sync-status");
  return (
    <SectionCard
      title="Sync status"
      description="The collector on each machine pushes new transcript lines to the database once a day (13:00, the “Claude Lens - Daily Sync” task)."
    >
      {q.isError ? (
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      ) : !q.data ? (
        <TableSkeleton rows={4} />
      ) : (
        <div className="flex flex-col gap-4">
          {q.data.machines.length === 0 ? (
            <p className="text-sm text-muted-foreground">No collector has run yet.</p>
          ) : (
            <ul className="grid gap-3 sm:grid-cols-2">
              {q.data.machines.map((m) => (
                <li key={m.machine} className="flex flex-col gap-1 rounded-lg border p-3">
                  <span className="flex items-center justify-between gap-2 text-sm font-medium">
                    <span className="truncate">{m.machine}</span>
                    <RunStatus status={m.last_run.status} />
                  </span>
                  <span className="text-xs text-muted-foreground">
                    Last run {fmt.ts(m.last_run.started_at)} ({fmt.relative(m.last_run.started_at)})
                  </span>
                  <span className="text-xs text-muted-foreground">Last success {m.last_ok_at ? fmt.ts(m.last_ok_at) : "never"}</span>
                  {m.last_run.error && <span className="font-mono text-xs wrap-break-word text-destructive">{m.last_run.error}</span>}
                </li>
              ))}
            </ul>
          )}

          <div className="flex items-start gap-2 rounded-lg bg-muted/50 p-3 text-xs text-muted-foreground">
            <TerminalIcon className="mt-0.5 size-3.5 shrink-0" />
            <span>
              To sync now, run <code className="rounded bg-background px-1 py-0.5 font-mono">uv run claude-lens scan</code> in{" "}
              <code className="rounded bg-background px-1 py-0.5 font-mono">backend/</code> on the machine with the transcripts.{" "}
              <code className="rounded bg-background px-1 py-0.5 font-mono">claude-lens status</code> lists recent runs.
            </span>
          </div>

          {q.data.runs.length > 0 && (
            <div className="overflow-hidden rounded-lg border">
              <Table>
                <TableHeader className="bg-muted/40">
                  <TableRow className="hover:bg-transparent">
                    <TableHead className="text-xs">Run</TableHead>
                    <TableHead className="text-xs">Machine</TableHead>
                    <TableHead className="text-xs">Started</TableHead>
                    <TableHead className="text-xs">Status</TableHead>
                    <TableHead className="text-right text-xs">Took</TableHead>
                    <TableHead className="text-right text-xs">Files</TableHead>
                    <TableHead className="text-right text-xs">Messages</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {q.data.runs.slice(0, 10).map((r) => (
                    <TableRow key={r.id} className="text-xs">
                      <TableCell className="font-mono">
                        <Badge variant="outline" className="font-mono font-normal">
                          #{r.id}
                        </Badge>
                      </TableCell>
                      <TableCell>{r.machine}</TableCell>
                      <TableCell className="font-mono whitespace-nowrap tabular">{fmt.ts(r.started_at)}</TableCell>
                      <TableCell>
                        <RunStatus status={r.status} />
                      </TableCell>
                      <TableCell className="text-right font-mono tabular">{seconds(r.started_at, r.finished_at)}</TableCell>
                      <TableCell className="text-right font-mono tabular">{r.files == null ? "—" : fmt.int(r.files)}</TableCell>
                      <TableCell className="text-right font-mono tabular">{r.messages == null ? "—" : fmt.int(r.messages)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </div>
      )}
    </SectionCard>
  );
}
