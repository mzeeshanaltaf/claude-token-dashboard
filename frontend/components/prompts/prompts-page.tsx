"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useMemo, useState } from "react";

import { DataTable } from "@/components/data-table";
import { ErrorState } from "@/components/error-state";
import { ExportButton } from "@/components/export-button";
import { FilterBar, ModelSelect, ProjectSelect, SearchBox } from "@/components/filters";
import { ModelBadge } from "@/components/model-badge";
import { Card, CardContent } from "@/components/ui/card";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { useClampPage, useServerTable } from "@/hooks/use-server-table";
import { useUrlState } from "@/hooks/use-url-state";
import type { Schema } from "@/lib/api";
import { fmt } from "@/lib/format";
import { GLOSSARY } from "@/lib/glossary";
import { useRangedQuery } from "@/lib/queries";

import { PromptSheet } from "./prompt-sheet";

type Prompt = Schema<"PromptRow">;

const SORTS = ["cost", "tokens", "recent", "cache_read", "chars"] as const;
const SORT_LABELS: Record<string, string> = { cost: "Cost", tokens: "Tokens", recent: "Recent" };

export function PromptsPage() {
  const { get } = useUrlState();
  const t = useServerTable(SORTS, "cost");
  const q = get("q") ?? undefined;
  const project = get("project") ?? undefined;
  const model = get("model") ?? undefined;

  const prompts = useRangedQuery("/api/prompts", { ...t.apiQuery, q, project, model });
  const projects = useRangedQuery("/api/projects");
  const [open, setOpen] = useState<Prompt | null>(null);

  useClampPage(t.page, prompts.data?.total, prompts.data?.items.length, t.set);

  const names = useMemo(
    () => new Map((projects.data ?? []).map((p) => [p.project_slug, p.project_name])),
    [projects.data],
  );
  const maxCost = Math.max(0, ...(prompts.data?.items ?? []).map((p) => p.estimated_cost_usd ?? 0));

  const columns = useMemo<ColumnDef<Prompt, unknown>[]>(
    () => [
      {
        id: "recent",
        header: "Time",
        sortDescFirst: true,
        cell: ({ row }) => <span className="font-mono text-xs whitespace-nowrap text-muted-foreground tabular">{fmt.ts(row.original.timestamp)}</span>,
      },
      {
        id: "project",
        header: "Project",
        enableSorting: false,
        cell: ({ row }) => (
          <span className="blur-sensitive block max-w-40 truncate text-xs" title={row.original.project_slug}>
            {names.get(row.original.project_slug) ?? row.original.project_slug}
          </span>
        ),
      },
      {
        id: "prompt",
        header: "Prompt",
        enableSorting: false,
        meta: { className: "w-full max-w-0 min-w-56" },
        cell: ({ row }) => (
          <span className="blur-sensitive block truncate text-sm">
            {row.original.prompt_text?.trim() || <span className="text-muted-foreground italic">(empty)</span>}
          </span>
        ),
      },
      {
        id: "model",
        header: "Model",
        enableSorting: false,
        cell: ({ row }) => <ModelBadge model={row.original.model} />,
      },
      {
        id: "tokens",
        header: "Core tokens",
        sortDescFirst: true,
        meta: { numeric: true, info: GLOSSARY.coreTokens },
        cell: ({ row }) => fmt.int(row.original.core_tokens),
      },
      {
        id: "cache_read",
        header: "Cache reads",
        sortDescFirst: true,
        meta: { numeric: true, info: GLOSSARY.cacheRead },
        cell: ({ row }) => fmt.int(row.original.cache_read_tokens),
      },
      {
        id: "cost",
        header: "Cost",
        sortDescFirst: true,
        meta: { numeric: true, info: "The full assistant turn that answered this prompt, at API rates (all five token types)." },
        cell: ({ row }) => <CostCell value={row.original.estimated_cost_usd} max={maxCost} />,
      },
    ],
    [names, maxCost],
  );

  return (
    <div className="flex flex-col gap-4">
      <FilterBar>
        <SearchBox placeholder="Search prompt text" />
        <ProjectSelect />
        <ModelSelect />
        <span className="flex-1" />
        <ToggleGroup
          type="single"
          size="sm"
          variant="outline"
          value={["cost", "tokens", "recent"].includes(t.sort) ? t.sort : ""}
          onValueChange={(v) => v && t.set({ sort: v, order: "desc", page: null })}
          aria-label="Sort by"
        >
          {Object.entries(SORT_LABELS).map(([k, label]) => (
            <ToggleGroupItem key={k} value={k}>
              {label}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
        <ExportButton table="prompts" query={{ q, project, model, sort: t.sort, order: t.order }} />
      </FilterBar>

      {prompts.isError ? (
        <ErrorState error={prompts.error} onRetry={() => prompts.refetch()} />
      ) : (
        <Card className="py-4">
          <CardContent className="px-4">
            <p className="mb-3 text-xs text-muted-foreground">
              Each prompt with the assistant turn that answered it. Click a row for the full prompt and its cost breakdown.
            </p>
            <DataTable
              columns={columns}
              data={prompts.data?.items}
              getRowId={(p) => p.user_uuid}
              server={t.table(prompts.data?.total ?? 0)}
              loading={!prompts.data}
              dim={prompts.isPlaceholderData}
              onRowClick={setOpen}
              empty={q || project || model ? "No prompts match these filters." : "No prompts in this range."}
            />
          </CardContent>
        </Card>
      )}

      <PromptSheet
        prompt={open}
        projectName={open ? (names.get(open.project_slug) ?? open.project_slug) : ""}
        onOpenChange={(o) => !o && setOpen(null)}
      />
    </div>
  );
}

/** "$0.1234" with a thin bar scaled to the page's most expensive prompt. */
function CostCell({ value, max }: { value: number | null | undefined; max: number }) {
  const pct = max > 0 && value ? (value / max) * 100 : 0;
  return (
    <span className="inline-flex items-center justify-end gap-2">
      <span className="hidden h-1.5 w-16 rounded-full bg-muted sm:block" aria-hidden>
        <span className="block h-full rounded-full bg-chart-output" style={{ width: `${pct}%`, minWidth: value ? 2 : 0 }} />
      </span>
      <span className="w-16 text-right">{fmt.usd4(value)}</span>
    </span>
  );
}
