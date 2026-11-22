"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useMemo } from "react";

import { BarList } from "@/components/bar-list";
import { DataTable } from "@/components/data-table";
import { ErrorState } from "@/components/error-state";
import { KpiCard } from "@/components/kpi-card";
import { ChartSkeleton, KpiGridSkeleton } from "@/components/loading";
import { SectionCard } from "@/components/section-card";
import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { Schema } from "@/lib/api";
import { fmt } from "@/lib/format";
import { useRangedQuery } from "@/lib/queries";

type Skill = Schema<"SkillRow">;

/** docs/KNOWN_LIMITATIONS.md § "Skills token counts are partial". */
const NOT_SCANNED =
  "Not installed in a scanned root. Tokens per call are known only for skills whose SKILL.md lives under ~/.claude/skills/, ~/.claude/scheduled-tasks/ or ~/.claude/plugins/. Project-local skills and skills dispatched through a subagent show invocation counts only.";

export function SkillsPage() {
  const q = useRangedQuery("/api/skills");

  const columns = useMemo<ColumnDef<Skill, unknown>[]>(
    () => [
      {
        id: "skill",
        header: "Skill",
        accessorFn: (s) => s.skill.toLowerCase(),
        sortDescFirst: false,
        meta: { className: "w-full" },
        cell: ({ row }) => (
          <Badge variant="secondary" className="max-w-[24rem] truncate font-mono font-normal" title={row.original.skill}>
            {row.original.skill}
          </Badge>
        ),
      },
      {
        id: "invocations",
        header: "Invocations",
        accessorFn: (s) => s.invocations,
        sortDescFirst: true,
        meta: { numeric: true },
        cell: ({ row }) => fmt.int(row.original.invocations),
      },
      {
        id: "sessions",
        header: "Sessions",
        accessorFn: (s) => s.sessions,
        sortDescFirst: true,
        meta: { numeric: true },
        cell: ({ row }) => fmt.int(row.original.sessions),
      },
      {
        id: "last_used",
        header: "Last used",
        accessorFn: (s) => s.last_used ?? "",
        sortDescFirst: true,
        cell: ({ row }) => <span className="font-mono text-xs whitespace-nowrap text-muted-foreground tabular">{fmt.ts(row.original.last_used)}</span>,
      },
      {
        id: "tokens_per_call",
        header: "Tokens per call",
        accessorFn: (s) => s.tokens_per_call ?? -1,
        sortDescFirst: true,
        meta: {
          numeric: true,
          info: "The size of the skill's SKILL.md: what Claude Code loads into context each time the skill is invoked.",
        },
        cell: ({ row }) =>
          row.original.tokens_per_call == null ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <span tabIndex={0} className="cursor-help font-sans text-muted-foreground underline decoration-dotted underline-offset-4">
                  not scanned
                </span>
              </TooltipTrigger>
              <TooltipContent className="max-w-72 text-pretty">{NOT_SCANNED}</TooltipContent>
            </Tooltip>
          ) : (
            fmt.int(row.original.tokens_per_call)
          ),
      },
    ],
    [],
  );

  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data) {
    return (
      <div className="flex flex-col gap-6">
        <KpiGridSkeleton count={3} />
        <ChartSkeleton className="h-80" />
      </div>
    );
  }

  const skills = q.data;
  const invocations = skills.reduce((s, k) => s + k.invocations, 0);
  const known = skills.filter((s) => s.tokens_per_call != null);
  const loaded = known.reduce((s, k) => s + (k.tokens_per_call ?? 0) * k.invocations, 0);
  const top = [...skills].sort((a, b) => b.invocations - a.invocations).slice(0, 12);

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <KpiCard label="Unique skills used" value={fmt.int(skills.length)} />
        <KpiCard label="Total invocations" value={fmt.int(invocations)} />
        <KpiCard
          label="SKILL.md tokens loaded"
          value={fmt.compact(loaded)}
          sub={`${fmt.int(known.length)} of ${fmt.int(skills.length)} skills have a known size`}
          info="Tokens per call × invocations, for the skills with a known SKILL.md size."
        />
      </div>

      <SectionCard title="Top skills" description="By invocations (top 12)." dim={q.isPlaceholderData}>
        {top.length ? (
          <BarList
            color="var(--chart-cache-read)"
            ariaLabel="Skills by invocations"
            items={top.map((s) => ({
              key: s.skill,
              label: <span className="font-mono text-xs">{s.skill}</span>,
              value: s.invocations,
              display: fmt.int(s.invocations),
              tooltip: (
                <span className="font-mono tabular">
                  {s.skill}: {fmt.int(s.invocations)} invocations · {fmt.int(s.sessions)} sessions
                </span>
              ),
            }))}
          />
        ) : (
          <p className="py-10 text-center text-sm text-muted-foreground">No skills invoked in this range.</p>
        )}
      </SectionCard>

      <SectionCard title="All skills" description="Click a column header to sort.">
        <DataTable
          columns={columns}
          data={skills}
          getRowId={(s) => s.skill}
          initialSort={[{ id: "invocations", desc: true }]}
          clientPageSize={50}
          dim={q.isPlaceholderData}
          empty="No skills invoked in this range."
        />
      </SectionCard>
    </div>
  );
}
