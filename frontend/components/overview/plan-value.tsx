"use client";

import { BarList } from "@/components/bar-list";
import { ErrorState } from "@/components/error-state";
import { ChartSkeleton } from "@/components/loading";
import { SectionCard } from "@/components/section-card";
import { fmt } from "@/lib/format";
import { useApiQuery } from "@/lib/queries";

/** How many months the bar list shows (newest first). */
const MONTHS_SHOWN = 12;

interface PlanInfo {
  label?: string;
  monthly?: number | null;
}

export interface PaidPlan {
  key: string;
  label: string;
  monthly: number;
}

/** The chosen subscription plan, or null for API pricing / no plan / no price. */
export function usePaidPlan(): PaidPlan | null {
  const plan = useApiQuery("/api/plan");
  const key = plan.data?.plan;
  if (!key || key === "api") return null;
  const p = (plan.data?.pricing?.plans as Record<string, PlanInfo> | undefined)?.[key];
  if (!p?.monthly) return null;
  return { key, label: p.label ?? key, monthly: p.monthly };
}

interface MonthRow {
  month: string; // YYYY-MM
  cost: number;
  activeDays: number;
}

const MONTH_LABEL = new Intl.DateTimeFormat(undefined, { month: "short", year: "numeric", timeZone: "UTC" });

function monthLabel(month: string): string {
  return MONTH_LABEL.format(new Date(`${month}-01T00:00:00Z`));
}

function nextMonth(month: string): string {
  const [y, m] = month.split("-").map(Number);
  return m === 12 ? `${y + 1}-01` : `${y}-${String(m + 1).padStart(2, "0")}`;
}

/** "37×", "4.2×", "0.6×": the API-equivalent cost as a multiple of the plan price. */
function multiple(cost: number, price: number): string {
  const x = cost / price;
  return `${x >= 10 ? Math.round(x).toLocaleString() : x.toFixed(1)}×`;
}

/**
 * Every calendar month from the first active one to `current`, zero-filled.
 * Days are already bucketed in the timezone setting by /api/daily.
 */
function toMonths(days: readonly { day: string; cost_usd?: number | null }[], current: string): MonthRow[] {
  const byMonth = new Map<string, MonthRow>();
  for (const d of days) {
    const month = d.day.slice(0, 7);
    const row = byMonth.get(month) ?? { month, cost: 0, activeDays: 0 };
    row.cost += d.cost_usd ?? 0;
    row.activeDays += 1;
    byMonth.set(month, row);
  }
  const first = [...byMonth.keys()].sort()[0];
  if (!first) return [];
  const last = current > first ? current : first;
  const out: MonthRow[] = [];
  for (let m = first; m <= last; m = nextMonth(m)) out.push(byMonth.get(m) ?? { month: m, cost: 0, activeDays: 0 });
  return out;
}

/**
 * Plan value: what the usage would have cost at API rates, against the flat
 * monthly price of the chosen plan. Range-independent (whole calendar months),
 * like the Activity calendar. Hidden on API pricing, where cost is what you pay.
 */
export function PlanValueCard() {
  const plan = usePaidPlan();
  // All-time daily rows: ~one per active day, so this stays small.
  const daily = useApiQuery("/api/daily", { enabled: plan !== null });

  if (!plan) return null;
  if (daily.isError) return <ErrorState error={daily.error} onRetry={() => daily.refetch()} />;
  if (!daily.data) return <ChartSkeleton className="h-64" />;

  // Only runs in the browser: the dashboard pages fetch their data client-side.
  const now = new Date();
  const current = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  const months = toMonths(daily.data, current);
  if (!months.length) return null;

  const thisMonth = months[months.length - 1];
  const total = months.reduce((s, m) => s + m.cost, 0);
  const paid = months.length * plan.monthly;
  const shown = months.slice(-MONTHS_SHOWN).reverse();
  // Plan prices are whole dollars: "$20", "$200", not "$20.00".
  const dollars = (n: number) => `$${n.toLocaleString()}`;
  const price = dollars(plan.monthly);

  return (
    <SectionCard
      title="Plan value"
      description={`Your usage priced at API rates, per calendar month, against the ${price}/mo you pay on ${plan.label}. Ignores the range picker, and counts every month at your current plan's price.`}
    >
      <div className="grid grid-cols-1 gap-6 md:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <dl className="grid grid-cols-2 content-start gap-x-4 gap-y-5 md:grid-cols-1">
          <div className="grid gap-1">
            <dt className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
              {monthLabel(thisMonth.month)} so far
            </dt>
            <dd className="font-mono text-3xl font-semibold tracking-tight tabular">
              {multiple(thisMonth.cost, plan.monthly)}
            </dd>
            <dd className="text-xs text-muted-foreground tabular">
              {fmt.usd(thisMonth.cost)} of API-equivalent usage for {price}
            </dd>
          </div>
          <div className="grid gap-1">
            <dt className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
              Since {monthLabel(months[0].month)}
            </dt>
            <dd className="font-mono text-3xl font-semibold tracking-tight tabular">{multiple(total, plan.monthly * months.length)}</dd>
            <dd className="text-xs text-muted-foreground tabular">
              {fmt.usd(total)} for {dollars(paid)} over {months.length} {months.length === 1 ? "month" : "months"}
            </dd>
          </div>
        </dl>
        <BarList
          color="var(--chart-output)"
          ariaLabel={`API-equivalent cost per month, as a multiple of the ${plan.label} plan price`}
          items={shown.map((m) => ({
            key: m.month,
            label: m === thisMonth ? `${monthLabel(m.month)} (so far)` : monthLabel(m.month),
            value: m.cost,
            display: fmt.usd(m.cost),
            aside: multiple(m.cost, plan.monthly),
            tooltip: (
              <span className="grid gap-0.5 font-mono tabular">
                <span className="font-sans font-medium">{monthLabel(m.month)}</span>
                <span>
                  API-equivalent {fmt.usd(m.cost)} · {multiple(m.cost, plan.monthly)} the {price} plan
                </span>
                <span className="text-muted-foreground">{fmt.int(m.activeDays)} active days</span>
              </span>
            ),
          }))}
        />
      </div>
    </SectionCard>
  );
}
