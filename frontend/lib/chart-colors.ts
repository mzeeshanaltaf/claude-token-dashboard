/**
 * How charts get their colours: never hex values in components. Spread one of
 * these configs into a shadcn `ChartConfig`; each `color` points at a CSS
 * variable defined in app/globals.css, so light/dark and any future palette
 * change stay in one place. Inside a ChartContainer, series read
 * `var(--color-<key>)`.
 */
import type { ChartConfig } from "@/components/ui/chart";

import { FAMILY_LABELS, MODEL_FAMILIES, type ModelFamily } from "./models";

export const TOKEN_TYPES = ["input", "output", "cache_write", "cache_read"] as const;
export type TokenType = (typeof TOKEN_TYPES)[number];

export const tokenChartConfig = {
  input: { label: "Input", color: "var(--chart-input)" },
  output: { label: "Output", color: "var(--chart-output)" },
  cache_write: { label: "Cache write", color: "var(--chart-cache-write)" },
  cache_read: { label: "Cache read", color: "var(--chart-cache-read)" },
} satisfies ChartConfig;

export const familyChartConfig = Object.fromEntries(
  MODEL_FAMILIES.map((f) => [f, { label: FAMILY_LABELS[f], color: `var(--family-${f})` }]),
) as Record<ModelFamily, { label: string; color: string }> satisfies ChartConfig;

export function familyColor(family: ModelFamily | null): string {
  return family ? `var(--family-${family})` : "var(--muted-foreground)";
}
