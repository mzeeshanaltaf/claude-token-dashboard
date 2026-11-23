"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { BarList } from "@/components/bar-list";
import { DailyChart } from "@/components/charts/daily-chart";
import { ModelMix } from "@/components/charts/model-mix";
import { TokenComposition } from "@/components/charts/token-composition";
import { ErrorState } from "@/components/error-state";
import { InfoTip } from "@/components/info-tip";
import { KpiCard } from "@/components/kpi-card";
import { ChartSkeleton, KpiGridSkeleton, TableSkeleton } from "@/components/loading";
import { PlanValueCard, usePaidPlan } from "@/components/overview/plan-value";
import { SectionCard } from "@/components/section-card";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useRangedHref } from "@/hooks/use-url-state";
import { fmt } from "@/lib/format";
import { GLOSSARY } from "@/lib/glossary";
import { useRangedQuery } from "@/lib/queries";
import { cacheHitRate } from "@/lib/usage";

/** "You pay $100/mo on Max" (the old planSubtitle); nothing for API pricing. */
function usePlanNote(): string | undefined {
  const plan = usePaidPlan();
  return plan ? `You pay $${plan.monthly}/mo on ${plan.label}` : undefined;
}

export function OverviewPage() {
  const overview = useRangedQuery("/api/overview");
  const daily = useRangedQuery("/api/daily");
  const planNote = usePlanNote();

  if (overview.isError) return <ErrorState error={overview.error} onRetry={() => overview.refetch()} />;

  const o = overview.data;
  const days = daily.data ?? [];
  const dim = overview.isPlaceholderData;

  return (
    <div className="flex flex-col gap-6">
      {!o ? (
        <KpiGridSkeleton />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <KpiCard
            label="Est. cost"
            value={fmt.usd(o.cost_usd)}
            sub={planNote ?? `${fmt.usd(o.turns ? o.cost_usd / o.turns : 0)} per prompt`}
            info={GLOSSARY.estCost}
            sparkline={days.map((d) => d.cost_usd)}
            sparkColor="var(--chart-output)"
          />
          <KpiCard
            label="Sessions"
            value={fmt.int(o.sessions)}
            sub={`${fmt.int(o.projects)} projects`}
            info={GLOSSARY.session}
            sparkline={days.map((d) => d.sessions)}
            sparkColor="var(--chart-input)"
          />
          <KpiCard
            label="Prompts"
            value={fmt.int(o.turns)}
            sub={`${fmt.compact(o.sessions ? o.turns / o.sessions : 0)} per session`}
            info={GLOSSARY.turn}
            sparkline={days.map((d) => d.turns)}
            sparkColor="var(--chart-input)"
          />
          <KpiCard
            label="Cache hit rate"
            value={fmt.pct(
              cacheHitRate(o.cache_read_tokens, o.input_tokens, o.cache_create_5m_tokens + o.cache_create_1h_tokens),
              1,
            )}
            sub={`${fmt.compact(o.cache_read_tokens)} tokens read from cache`}
            info={GLOSSARY.cacheHitRate}
            sparkline={days.map((d) => (cacheHitRate(d.cache_read_tokens, d.input_tokens, d.cache_create_tokens) ?? 0) * 100)}
            sparkColor="var(--chart-cache-read)"
          />
        </div>
      )}

      {o ? <TokenComposition totals={o} dim={dim} /> : <ChartSkeleton className="h-36" />}

      <PlanValueCard />

      {daily.isError ? (
        <ErrorState error={daily.error} onRetry={() => daily.refetch()} />
      ) : daily.data ? (
        <DailyChart rows={daily.data} dim={daily.isPlaceholderData} />
      ) : (
        <ChartSkeleton className="h-96" />
      )}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <ModelMixCard />
        <TopProjects />
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <TopTools />
        <RecentSessions />
      </div>
    </div>
  );
}

function ModelMixCard() {
  const q = useRangedQuery("/api/by-model");
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data) return <ChartSkeleton className="h-80" />;
  return <ModelMix rows={q.data} dim={q.isPlaceholderData} />;
}

function TopProjects() {
  const q = useRangedQuery("/api/projects");
  const href = useRangedHref();
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data) return <ChartSkeleton className="h-80" />;
  const total = q.data.reduce((s, p) => s + (p.estimated_cost_usd ?? 0), 0);
  const top = q.data
    .filter((p) => (p.estimated_cost_usd ?? 0) > 0)
    .sort((a, b) => (b.estimated_cost_usd ?? 0) - (a.estimated_cost_usd ?? 0))
    .slice(0, 10);
  return (
    <SectionCard
      title="Top projects by cost"
      description="Top 10 projects by estimated API cost, with their share of spend. Click one to open it."
      dim={q.isPlaceholderData}
      action={
        <Button asChild variant="ghost" size="xs">
          <Link href={href("/projects")}>All projects</Link>
        </Button>
      }
    >
      {top.length ? (
        <BarList
          sensitiveLabels
          color="var(--chart-input)"
          ariaLabel="Projects by estimated cost"
          items={top.map((p) => ({
            key: p.project_slug,
            label: p.project_name,
            value: p.estimated_cost_usd ?? 0,
            display: fmt.usd(p.estimated_cost_usd),
            aside: total ? fmt.pct((p.estimated_cost_usd ?? 0) / total, (p.estimated_cost_usd ?? 0) / total < 0.1 ? 1 : 0) : undefined,
            href: href(`/projects/${encodeURIComponent(p.project_slug)}`),
            tooltip: (
              <span className="grid gap-0.5">
                <span className="blur-sensitive font-medium">{p.project_name}</span>
                <span className="font-mono tabular">
                  Est. cost {fmt.usd(p.estimated_cost_usd)}
                  {total ? ` · ${fmt.pct((p.estimated_cost_usd ?? 0) / total, 1)} of spend` : ""}
                </span>
                <span className="font-mono tabular">
                  {fmt.int(p.sessions)} sessions · {fmt.int(p.turns)} turns
                </span>
                <span className="font-mono tabular text-muted-foreground">
                  in {fmt.compact(p.input_tokens)} · out {fmt.compact(p.output_tokens)} · cache rd {fmt.compact(p.cache_read_tokens)}
                </span>
              </span>
            ),
          }))}
        />
      ) : (
        <p className="py-10 text-center text-sm text-muted-foreground">No project costs in this range.</p>
      )}
    </SectionCard>
  );
}

function TopTools() {
  const q = useRangedQuery("/api/tools");
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data) return <ChartSkeleton className="h-80" />;
  const top = [...q.data].sort((a, b) => b.calls - a.calls).slice(0, 8);
  return (
    <SectionCard title="Top tools" description="Calls per tool (top 8)." dim={q.isPlaceholderData}>
      {top.length ? (
        <BarList
          color="var(--chart-output)"
          ariaLabel="Tools by call count"
          items={top.map((t) => ({
            key: t.tool_name,
            label: t.tool_name,
            value: t.calls,
            display: fmt.int(t.calls),
            tooltip: (
              <span className="font-mono tabular">
                {t.tool_name}: {fmt.int(t.calls)} calls · {fmt.compact(t.result_tokens)} result tokens
              </span>
            ),
          }))}
        />
      ) : (
        <p className="py-10 text-center text-sm text-muted-foreground">No tool calls in this range.</p>
      )}
    </SectionCard>
  );
}

function RecentSessions() {
  const q = useRangedQuery("/api/sessions", { page_size: 10, sort: "ended" });
  const href = useRangedHref();
  const router = useRouter();
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  return (
    <SectionCard
      title="Recent sessions"
      dim={q.isPlaceholderData}
      action={
        <Button asChild variant="ghost" size="xs">
          <Link href={href("/sessions")}>All sessions</Link>
        </Button>
      }
    >
      {!q.data ? (
        <TableSkeleton rows={10} />
      ) : !q.data.items.length ? (
        <p className="py-10 text-center text-sm text-muted-foreground">No sessions in this range.</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead className="text-xs">Started</TableHead>
              <TableHead className="text-xs">Project / title</TableHead>
              <TableHead className="text-right text-xs">
                <span className="inline-flex items-center gap-1">
                  Tokens <InfoTip label="About tokens">Input + output tokens.</InfoTip>
                </span>
              </TableHead>
              <TableHead className="text-right text-xs">Cost</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {q.data.items.map((s) => {
              const to = href(`/sessions/${encodeURIComponent(s.session_id)}`);
              return (
                <TableRow key={s.session_id} className="cursor-pointer" onClick={() => router.push(to)}>
                  <TableCell className="font-mono text-xs whitespace-nowrap text-muted-foreground tabular">{fmt.ts(s.started)}</TableCell>
                  <TableCell className="max-w-0 w-full">
                    <Link href={to} className="block truncate text-sm hover:underline" onClick={(e) => e.stopPropagation()}>
                      <span className="blur-sensitive">{s.title || s.project_name}</span>
                    </Link>
                    {s.title && <span className="blur-sensitive block truncate text-xs text-muted-foreground">{s.project_name}</span>}
                  </TableCell>
                  <TableCell className="text-right font-mono text-xs tabular">{fmt.compact(s.tokens)}</TableCell>
                  <TableCell className="text-right font-mono text-xs tabular">{fmt.usd(s.estimated_cost_usd)}</TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      )}
    </SectionCard>
  );
}
