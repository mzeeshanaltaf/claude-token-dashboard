"use client";

/**
 * Phase 04 placeholders: each route renders one or two real numbers from its
 * endpoint to prove the proxy → backend → Postgres path and the range wiring.
 * Phase 05/06 replace these with the real pages.
 */
import { ConstructionIcon } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { KpiCard } from "@/components/kpi-card";
import { KpiGridSkeleton } from "@/components/loading";
import { useRange } from "@/hooks/use-range";
import { fmt } from "@/lib/format";
import { useApiQuery, useRangedQuery } from "@/lib/queries";
import { rangeLabel } from "@/lib/range";

function Grid({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">{children}</div>;
}

function ComingSoon({ page }: { page: string }) {
  return (
    <EmptyState
      className="flex-none py-10"
      icon={ConstructionIcon}
      title={`The full ${page} page is on its way`}
      description="This preview shows live numbers from your data; charts and tables come next."
    />
  );
}

function RangeNote() {
  const { range } = useRange();
  return <span>{rangeLabel(range)}</span>;
}

export function OverviewPlaceholder() {
  const overview = useRangedQuery("/api/overview");
  const daily = useRangedQuery("/api/daily");
  if (overview.isError) return <ErrorState error={overview.error} onRetry={() => overview.refetch()} />;
  if (!overview.data) return <KpiGridSkeleton />;
  const o = overview.data;
  const days = daily.data ?? [];
  return (
    <>
      <Grid>
        <KpiCard
          label="Est. cost"
          value={fmt.usd(o.cost_usd)}
          sub={<RangeNote />}
          info="API-rate cost of every assistant turn in range, from pricing.json."
        />
        <KpiCard label="Sessions" value={fmt.int(o.sessions)} sub={`${fmt.int(o.projects)} projects`} />
        <KpiCard
          label="Output tokens"
          value={fmt.compact(o.output_tokens)}
          sub={`${fmt.int(o.turns)} turns`}
          sparkline={days.map((d) => d.output_tokens)}
          sparkColor="var(--chart-output)"
        />
        <KpiCard
          label="Cache read"
          value={fmt.compact(o.cache_read_tokens)}
          sub={`${fmt.compact(o.input_tokens)} fresh input`}
          sparkline={days.map((d) => d.cache_read_tokens)}
          sparkColor="var(--chart-cache-read)"
        />
      </Grid>
      <ComingSoon page="Overview" />
    </>
  );
}

export function ActivityPlaceholder() {
  const daily = useRangedQuery("/api/daily");
  if (daily.isError) return <ErrorState error={daily.error} onRetry={() => daily.refetch()} />;
  if (!daily.data) return <KpiGridSkeleton count={2} />;
  const days = daily.data;
  const busiest = days.reduce<(typeof days)[number] | null>((a, d) => (!a || d.output_tokens > a.output_tokens ? d : a), null);
  return (
    <>
      <Grid>
        <KpiCard
          label="Active days"
          value={fmt.int(days.length)}
          sub={<RangeNote />}
          sparkline={days.map((d) => d.output_tokens)}
          sparkColor="var(--chart-input)"
        />
        <KpiCard
          label="Busiest day"
          value={busiest ? busiest.day : "—"}
          sub={busiest ? `${fmt.compact(busiest.output_tokens)} output tokens` : undefined}
        />
      </Grid>
      <ComingSoon page="Activity" />
    </>
  );
}

export function PromptsPlaceholder() {
  const prompts = useRangedQuery("/api/prompts", { page_size: 1, sort: "cost" });
  if (prompts.isError) return <ErrorState error={prompts.error} onRetry={() => prompts.refetch()} />;
  if (!prompts.data) return <KpiGridSkeleton count={2} />;
  const top = prompts.data.items[0];
  return (
    <>
      <Grid>
        <KpiCard label="Prompts" value={fmt.int(prompts.data.total)} sub={<RangeNote />} />
        <KpiCard
          className="sm:col-span-1 xl:col-span-3"
          label="Most expensive prompt"
          value={top ? fmt.usd(top.estimated_cost_usd) : "—"}
          sub={top ? <span className="blur-sensitive">{fmt.short(top.prompt_text, 140)}</span> : "No prompts in range"}
        />
      </Grid>
      <ComingSoon page="Prompts" />
    </>
  );
}

export function SessionsPlaceholder() {
  const sessions = useRangedQuery("/api/sessions", { page_size: 1 });
  if (sessions.isError) return <ErrorState error={sessions.error} onRetry={() => sessions.refetch()} />;
  if (!sessions.data) return <KpiGridSkeleton count={2} />;
  const latest = sessions.data.items[0];
  return (
    <>
      <Grid>
        <KpiCard label="Sessions" value={fmt.int(sessions.data.total)} sub={<RangeNote />} />
        <KpiCard
          className="xl:col-span-3"
          label="Latest session"
          value={latest ? fmt.ts(latest.ended) : "—"}
          sub={
            latest ? (
              <span className="blur-sensitive">
                {latest.project_name} · {fmt.short(latest.title ?? latest.session_id, 100)}
              </span>
            ) : (
              "No sessions in range"
            )
          }
        />
      </Grid>
      <ComingSoon page="Sessions" />
    </>
  );
}

export function ProjectsPlaceholder() {
  const projects = useRangedQuery("/api/projects");
  if (projects.isError) return <ErrorState error={projects.error} onRetry={() => projects.refetch()} />;
  if (!projects.data) return <KpiGridSkeleton count={2} />;
  const top = [...projects.data].sort((a, b) => (b.estimated_cost_usd ?? 0) - (a.estimated_cost_usd ?? 0))[0];
  return (
    <>
      <Grid>
        <KpiCard label="Projects" value={fmt.int(projects.data.length)} sub={<RangeNote />} />
        <KpiCard
          label="Top project by cost"
          value={top ? fmt.usd(top.estimated_cost_usd) : "—"}
          sub={top ? <span className="blur-sensitive">{top.project_name}</span> : undefined}
        />
      </Grid>
      <ComingSoon page="Projects" />
    </>
  );
}

export function ToolsPlaceholder() {
  const tools = useRangedQuery("/api/tools");
  if (tools.isError) return <ErrorState error={tools.error} onRetry={() => tools.refetch()} />;
  if (!tools.data) return <KpiGridSkeleton count={2} />;
  const calls = tools.data.reduce((s, t) => s + t.calls, 0);
  const top = [...tools.data].sort((a, b) => b.calls - a.calls)[0];
  return (
    <>
      <Grid>
        <KpiCard label="Tool calls" value={fmt.int(calls)} sub={<RangeNote />} />
        <KpiCard label="Distinct tools" value={fmt.int(tools.data.length)} sub={top ? `Most used: ${top.tool_name}` : undefined} />
      </Grid>
      <ComingSoon page="Tools" />
    </>
  );
}

export function SkillsPlaceholder() {
  const skills = useRangedQuery("/api/skills");
  if (skills.isError) return <ErrorState error={skills.error} onRetry={() => skills.refetch()} />;
  if (!skills.data) return <KpiGridSkeleton count={2} />;
  const invocations = skills.data.reduce((s, k) => s + k.invocations, 0);
  return (
    <>
      <Grid>
        <KpiCard label="Skills used" value={fmt.int(skills.data.length)} sub={<RangeNote />} />
        <KpiCard label="Invocations" value={fmt.int(invocations)} />
      </Grid>
      <ComingSoon page="Skills" />
    </>
  );
}

export function TipsPlaceholder() {
  const tips = useApiQuery("/api/tips");
  if (tips.isError) return <ErrorState error={tips.error} onRetry={() => tips.refetch()} />;
  if (!tips.data) return <KpiGridSkeleton count={1} />;
  return (
    <>
      <Grid>
        <KpiCard label="Open tips" value={fmt.int(tips.data.length)} sub={tips.data[0]?.title} />
      </Grid>
      <ComingSoon page="Tips" />
    </>
  );
}

export function SettingsPlaceholder() {
  const settings = useApiQuery("/api/settings");
  const plan = useApiQuery("/api/plan");
  if (settings.isError) return <ErrorState error={settings.error} onRetry={() => settings.refetch()} />;
  if (!settings.data) return <KpiGridSkeleton count={2} />;
  const plans = (plan.data?.pricing?.plans ?? {}) as Record<string, { label?: string }>;
  const key = settings.data.plan;
  return (
    <>
      <Grid>
        <KpiCard label="Plan" value={key ? (plans[key]?.label ?? key) : "Not set"} />
        <KpiCard label="Timezone" value={settings.data.timezone} sub="Used for daily buckets" />
      </Grid>
      <div id="password">
        <ComingSoon page="Settings" />
      </div>
    </>
  );
}
