"use client";

import { useState } from "react";

import { InfoTip } from "@/components/info-tip";
import { SectionCard } from "@/components/section-card";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { fmt } from "@/lib/format";
import type { GlossaryTerm } from "@/lib/glossary";
import { cn } from "@/lib/utils";

export interface TokenTotals {
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cache_create_5m_tokens: number;
  cache_create_1h_tokens: number;
  cost_input_usd?: number | null;
  cost_output_usd?: number | null;
  cost_cache_read_usd?: number | null;
  cost_cache_create_5m_usd?: number | null;
  cost_cache_create_1h_usd?: number | null;
}

interface Part {
  key: string;
  label: string;
  term: GlossaryTerm;
  color: string;
  /** Label ink inside the block, by the fill's luminance. */
  ink: string;
  tokens: number;
  cost: number | null;
  detail?: React.ReactNode;
}

const sum = (...v: (number | null | undefined)[]) =>
  v.every((x) => x === null || x === undefined) ? null : v.reduce<number>((s, x) => s + (x ?? 0), 0);

function partsOf(t: TokenTotals): Part[] {
  const cacheCreate = t.cache_create_5m_tokens + t.cache_create_1h_tokens;
  return [
    { key: "input", label: "Input", term: "input", color: "var(--chart-input)", ink: "#0b1220", tokens: t.input_tokens, cost: t.cost_input_usd ?? null },
    { key: "output", label: "Output", term: "output", color: "var(--chart-output)", ink: "#ffffff", tokens: t.output_tokens, cost: t.cost_output_usd ?? null },
    { key: "cache_read", label: "Cache read", term: "cacheRead", color: "var(--chart-cache-read)", ink: "#0b1220", tokens: t.cache_read_tokens, cost: t.cost_cache_read_usd ?? null },
    {
      key: "cache_write",
      label: "Cache create",
      term: "cacheCreate",
      color: "var(--chart-cache-write)",
      ink: "#0b1220",
      tokens: cacheCreate,
      cost: sum(t.cost_cache_create_5m_usd, t.cost_cache_create_1h_usd),
      detail: (
        <span className="block text-muted-foreground">
          5m: {fmt.compact(t.cache_create_5m_tokens)} ({fmt.usd(t.cost_cache_create_5m_usd)}) · 1h: {fmt.compact(t.cache_create_1h_tokens)} (
          {fmt.usd(t.cost_cache_create_1h_usd)})
        </span>
      ),
    },
  ];
}

/**
 * One whole split into its parts: the tall segmented bar (28px, 2px gaps,
 * 4px corners, share printed inside when it fits). Switch between share of
 * tokens and share of cost; the legend always carries both numbers.
 */
export function TokenComposition({
  totals,
  title = "Token composition",
  dim,
}: {
  totals: TokenTotals;
  title?: string;
  dim?: boolean;
}) {
  const [by, setBy] = useState<"tokens" | "cost">("tokens");
  const parts = partsOf(totals);
  const value = (p: Part) => (by === "tokens" ? p.tokens : (p.cost ?? 0));
  const whole = parts.reduce((s, p) => s + value(p), 0);
  const totalTokens = parts.reduce((s, p) => s + p.tokens, 0);
  const totalCost = sum(...parts.map((p) => p.cost));

  return (
    <SectionCard
      title={
        <>
          {title}
          <InfoTip term="totalTokens" label="About total tokens" />
        </>
      }
      description={
        <>
          <span className="font-mono tabular">{fmt.int(totalTokens)}</span> tokens ·{" "}
          <span className="font-mono tabular">{fmt.usd(totalCost)}</span> est. cost
        </>
      }
      action={
        <ToggleGroup
          type="single"
          size="sm"
          variant="outline"
          value={by}
          onValueChange={(v) => v && setBy(v as "tokens" | "cost")}
          aria-label="Share of"
        >
          <ToggleGroupItem value="tokens">Tokens</ToggleGroupItem>
          <ToggleGroupItem value="cost">Cost</ToggleGroupItem>
        </ToggleGroup>
      }
      dim={dim}
    >
      <div
        className="flex h-7 w-full gap-0.5"
        role="img"
        aria-label={`Share of ${by}: ${parts.map((p) => `${p.label} ${fmt.pct(whole ? value(p) / whole : 0, 1)}`).join(", ")}`}
      >
        {parts.map((p) => {
          const share = whole ? value(p) / whole : 0;
          if (share <= 0) return null;
          return (
            <Tooltip key={p.key}>
              <TooltipTrigger asChild>
                <div
                  tabIndex={0}
                  className="flex h-full min-w-1 items-center overflow-hidden rounded-[4px] px-2 outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  style={{ flexGrow: share, flexBasis: 0, background: p.color }}
                >
                  {share >= 0.08 && (
                    <span className="font-mono text-xs font-medium tabular" style={{ color: p.ink }}>
                      {fmt.pct(share, share < 0.1 ? 1 : 0)}
                    </span>
                  )}
                </div>
              </TooltipTrigger>
              <TooltipContent>
                <span className="block font-medium">{p.label}</span>
                <span className="block font-mono tabular">
                  {fmt.int(p.tokens)} tokens · {fmt.usd(p.cost)} · {fmt.pct(share, 1)} of {by}
                </span>
                {p.detail}
              </TooltipContent>
            </Tooltip>
          );
        })}
      </div>
      <ul className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 lg:grid-cols-4">
        {parts.map((p) => (
          <li key={p.key} className="flex min-w-0 flex-col gap-0.5">
            <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <span aria-hidden className="size-2.5 shrink-0 rounded-[3px]" style={{ background: p.color }} />
              {p.label}
              <InfoTip term={p.term} label={`About ${p.label.toLowerCase()}`} />
            </span>
            <span className="font-mono text-sm font-medium" title={`${fmt.int(p.tokens)} tokens`}>
              {fmt.compact(p.tokens)}
            </span>
            <span className={cn("font-mono text-xs text-muted-foreground")}>{fmt.usd(p.cost)}</span>
            {p.key === "cache_write" && (
              <span className="font-mono text-[11px] text-muted-foreground">
                5m {fmt.compact(totals.cache_create_5m_tokens)} · 1h {fmt.compact(totals.cache_create_1h_tokens)}
              </span>
            )}
          </li>
        ))}
      </ul>
    </SectionCard>
  );
}
