"use client";

import { useMemo, useState } from "react";
import { Cell, Label, Pie, PieChart } from "recharts";

import { InfoTip } from "@/components/info-tip";
import { SectionCard } from "@/components/section-card";
import { Button } from "@/components/ui/button";
import { ChartContainer, ChartTooltip } from "@/components/ui/chart";
import type { Schema } from "@/lib/api";
import { familyChartConfig, familyColor } from "@/lib/chart-colors";
import { fmt } from "@/lib/format";
import { FAMILY_LABELS, type ModelFamily } from "@/lib/models";
import { cn } from "@/lib/utils";
import { modelTree, type FamilyNode } from "@/lib/usage";

const sharePct = (s: number) => fmt.pct(s, s >= 0.1 ? 0 : 1);

/**
 * Core tokens by Claude model: a donut of families beside the list of
 * versions (share bar, tokens, cost). Clicking a family, in the donut or the
 * chips, filters the list; colour always follows the family.
 */
export function ModelMix({ rows, dim }: { rows: readonly Schema<"ModelRow">[]; dim?: boolean }) {
  const { families, total } = useMemo(() => modelTree(rows), [rows]);
  const [picked, setPicked] = useState<ModelFamily | null>(null);
  const focus = picked && families.some((f) => f.family === picked) ? picked : null;
  const toggle = (f: ModelFamily) => setPicked((cur) => (cur === f ? null : f));

  const versions = families
    .filter((f) => !focus || f.family === focus)
    .flatMap((f) => f.versions)
    .sort((a, b) => b.tokens - a.tokens);
  const maxShare = Math.max(0, ...versions.map((v) => v.share));

  return (
    <SectionCard
      title={
        <>
          Model mix
          <InfoTip term="coreTokens" label="About core tokens" />
        </>
      }
      description="Share of core tokens across Claude models. Click a family to list only its versions."
      dim={dim}
    >
      {!families.length ? (
        <p className="py-10 text-center text-sm text-muted-foreground">No Claude model usage in this range.</p>
      ) : (
        <div className="grid items-center gap-6 md:grid-cols-[minmax(0,13rem)_minmax(0,1fr)]">
          <div className="flex flex-col items-center gap-3">
            <ChartContainer config={familyChartConfig} className="aspect-square w-full max-w-52">
              <PieChart>
                <ChartTooltip cursor={false} content={<FamilyTooltip />} />
                <Pie
                  data={families}
                  dataKey="tokens"
                  nameKey="family"
                  innerRadius="62%"
                  outerRadius="100%"
                  paddingAngle={families.length > 1 ? 1.5 : 0}
                  cornerRadius={4}
                  stroke="var(--card)"
                  strokeWidth={2}
                  isAnimationActive={false}
                  onClick={(d) => toggle((d as unknown as FamilyNode).family)}
                  className="cursor-pointer"
                >
                  {families.map((f) => (
                    <Cell
                      key={f.family}
                      fill={familyColor(f.family)}
                      opacity={!focus || focus === f.family ? 1 : 0.3}
                    />
                  ))}
                  <Label
                    content={({ viewBox }) => {
                      if (!viewBox || !("cx" in viewBox)) return null;
                      const { cx, cy } = viewBox as { cx: number; cy: number };
                      const f = families.find((x) => x.family === focus);
                      return (
                        <text x={cx} y={cy} textAnchor="middle" dominantBaseline="middle">
                          <tspan x={cx} y={cy - 6} className="fill-foreground font-mono text-lg font-semibold">
                            {fmt.compact(f ? f.tokens : total)}
                          </tspan>
                          <tspan x={cx} y={cy + 14} className="fill-muted-foreground text-[11px]">
                            {f ? `${FAMILY_LABELS[f.family]} tokens` : "core tokens"}
                          </tspan>
                        </text>
                      );
                    }}
                  />
                </Pie>
              </PieChart>
            </ChartContainer>
            <div className="flex flex-wrap justify-center gap-1.5" role="group" aria-label="Filter by family">
              {families.map((f) => (
                <Button
                  key={f.family}
                  size="xs"
                  variant={focus === f.family ? "secondary" : "ghost"}
                  aria-pressed={focus === f.family}
                  onClick={() => toggle(f.family)}
                  className="gap-1.5"
                >
                  <span aria-hidden className="size-2 rounded-full" style={{ background: familyColor(f.family) }} />
                  {FAMILY_LABELS[f.family]}
                  <span className="font-mono text-muted-foreground tabular">{sharePct(f.share)}</span>
                </Button>
              ))}
            </div>
          </div>

          <div className="min-w-0">
            <div className="mb-2 flex items-center justify-between text-xs text-muted-foreground">
              <span>{focus ? `${FAMILY_LABELS[focus]} versions` : "All versions"}</span>
              {focus && (
                <Button size="xs" variant="link" className="h-auto p-0" onClick={() => setPicked(null)}>
                  Show all
                </Button>
              )}
            </div>
            <ul className="flex flex-col gap-2">
              {versions.map((v) => (
                <li key={`${v.family}-${v.version}`} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1">
                  <span className="flex min-w-0 items-center gap-2 text-sm" title={v.ids.join(", ")}>
                    <span aria-hidden className="size-2 shrink-0 rounded-full" style={{ background: familyColor(v.family) }} />
                    <span className="truncate">{v.name}</span>
                  </span>
                  <span className="flex gap-3 font-mono text-xs tabular">
                    <span title={`${fmt.int(v.tokens)} core tokens`}>{fmt.compact(v.tokens)}</span>
                    <span className="w-20 text-right">{fmt.usd(v.cost)}</span>
                    <span className="w-10 text-right text-muted-foreground">{sharePct(focus ? v.familyShare : v.share)}</span>
                  </span>
                  <span className="col-span-2 h-1.5 rounded-full bg-muted" aria-hidden>
                    <span
                      className={cn("block h-full rounded-full")}
                      style={{
                        width: `${maxShare ? (v.share / maxShare) * 100 : 0}%`,
                        minWidth: 2,
                        background: familyColor(v.family),
                      }}
                    />
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </SectionCard>
  );
}

function FamilyTooltip({ active, payload }: { active?: boolean; payload?: { payload?: FamilyNode }[] }) {
  const f = payload?.[0]?.payload;
  if (!active || !f) return null;
  return (
    <div className="grid min-w-40 gap-1 rounded-lg border border-border/50 bg-background px-2.5 py-1.5 text-xs shadow-xl">
      <span className="flex items-center gap-1.5 font-medium">
        <span aria-hidden className="size-2 rounded-full" style={{ background: familyColor(f.family) }} />
        {FAMILY_LABELS[f.family]}
        <span className="font-normal text-muted-foreground">
          · {f.versions.length} model{f.versions.length === 1 ? "" : "s"}
        </span>
      </span>
      <span className="font-mono tabular">
        {fmt.compact(f.tokens)} core tokens · {sharePct(f.share)}
      </span>
      <span className="font-mono tabular">Est. cost {fmt.usd(f.cost)}</span>
    </div>
  );
}
