/**
 * Pure helpers that shape API rows for the charts: the model family → version
 * tree (ported from the old Overview sunburst), gap-filled daily series and
 * per-family daily cost.
 */
import { addDays, format } from "date-fns";

import type { Schema } from "./api";
import { FAMILY_LABELS, MODEL_FAMILIES, parseClaudeModel, type ModelFamily } from "./models";
import { parseDay } from "./range";

type ModelRow = Schema<"ModelRow">;
type DailyRow = Schema<"DailyRow">;

interface TokenCounts {
  input_tokens?: number | null;
  output_tokens?: number | null;
  cache_read_tokens?: number | null;
  cache_create_5m_tokens?: number | null;
  cache_create_1h_tokens?: number | null;
}

/** Input + output + cache create (the old "core tokens"). */
export function coreTokens(m: TokenCounts): number {
  return (
    (m.input_tokens ?? 0) + (m.output_tokens ?? 0) + (m.cache_create_5m_tokens ?? 0) + (m.cache_create_1h_tokens ?? 0)
  );
}

/** cache_read / (cache_read + input + cache_create); null when there's nothing to divide. */
export function cacheHitRate(cacheRead: number, input: number, cacheCreate: number): number | null {
  const denom = cacheRead + input + cacheCreate;
  return denom > 0 ? cacheRead / denom : null;
}

// ---------------------------------------------------------------- model mix

export interface VersionNode {
  /** "Opus 4.7" */
  name: string;
  version: string;
  family: ModelFamily;
  /** Raw model ids folded into this version (dated variants). */
  ids: string[];
  tokens: number;
  cost: number;
  /** Share of all Claude core tokens. */
  share: number;
  /** Share of the family's core tokens. */
  familyShare: number;
}

export interface FamilyNode {
  family: ModelFamily;
  tokens: number;
  cost: number;
  share: number;
  versions: VersionNode[];
}

function cmpVersionDesc(a: string, b: string): number {
  const x = a.split(".").map(Number);
  const y = b.split(".").map(Number);
  for (let i = 0; i < Math.max(x.length, y.length); i++) {
    const d = (y[i] ?? 0) - (x[i] ?? 0);
    if (d) return d;
  }
  return 0;
}

/**
 * Family → version tree of core tokens (Claude models only; non-Claude ids and
 * "<synthetic>" are left out, as in the old sunburst). Families are ordered by
 * size, versions newest first.
 */
export function modelTree(rows: readonly ModelRow[]): { families: FamilyNode[]; total: number } {
  const fams = new Map<ModelFamily, { tokens: number; cost: number; versions: Map<string, Omit<VersionNode, "share" | "familyShare">> }>();
  for (const m of rows) {
    const p = parseClaudeModel(m.model);
    const tokens = coreTokens(m);
    if (!p || tokens <= 0) continue;
    const f = fams.get(p.family) ?? { tokens: 0, cost: 0, versions: new Map() };
    fams.set(p.family, f);
    const label = FAMILY_LABELS[p.family];
    const v = f.versions.get(p.version) ?? {
      name: p.version ? `${label} ${p.version}` : label,
      version: p.version,
      family: p.family,
      ids: [],
      tokens: 0,
      cost: 0,
    };
    f.versions.set(p.version, v);
    v.tokens += tokens;
    v.cost += m.cost_usd ?? 0;
    v.ids.push(m.model);
    f.tokens += tokens;
    f.cost += m.cost_usd ?? 0;
  }
  const total = [...fams.values()].reduce((s, f) => s + f.tokens, 0);
  const families = [...fams.entries()]
    .map(([family, f]) => ({
      family,
      tokens: f.tokens,
      cost: f.cost,
      share: total ? f.tokens / total : 0,
      versions: [...f.versions.values()]
        .sort((a, b) => cmpVersionDesc(a.version, b.version))
        .map((v) => ({ ...v, share: total ? v.tokens / total : 0, familyShare: f.tokens ? v.tokens / f.tokens : 0 })),
    }))
    .sort((a, b) => b.tokens - a.tokens);
  return { families, total };
}

// ---------------------------------------------------------------- daily series

/** Every day from `first` to `last` (YYYY-MM-DD, inclusive). */
export function dayList(first: string, last: string): string[] {
  const s = parseDay(first);
  const e = parseDay(last);
  if (!s || !e || s > e) return [];
  const out: string[] = [];
  for (let d = s; d <= e; d = addDays(d, 1)) out.push(format(d, "yyyy-MM-dd"));
  return out;
}

export type DailyPoint = DailyRow & {
  /** Cost per family key ("opus", …, "other"). */
  families: Record<string, number>;
};

const EMPTY_DAY: Omit<DailyRow, "day"> = {
  sessions: 0,
  turns: 0,
  input_tokens: 0,
  output_tokens: 0,
  cache_read_tokens: 0,
  cache_create_tokens: 0,
  cost_usd: 0,
  cost_by_model: {},
};

/**
 * Days from the first to the last active day with the quiet days filled in as
 * zeros (so the time axis is honest), each with its cost split by family.
 */
export function fillDaily(rows: readonly DailyRow[]): DailyPoint[] {
  if (!rows.length) return [];
  const byDay = new Map(rows.map((r) => [r.day, r]));
  return dayList(rows[0].day, rows[rows.length - 1].day).map((day) => {
    const r = byDay.get(day) ?? { ...EMPTY_DAY, day };
    const families: Record<string, number> = {};
    for (const [model, usd] of Object.entries(r.cost_by_model)) {
      const key = parseClaudeModel(model)?.family ?? "other";
      families[key] = (families[key] ?? 0) + usd;
    }
    return { ...r, families };
  });
}

/** Families (plus "other") that carry any cost in the series, in display order. */
export function familiesPresent(points: readonly DailyPoint[]): (ModelFamily | "other")[] {
  const seen = new Set<string>();
  for (const p of points) for (const [k, v] of Object.entries(p.families)) if (v > 0) seen.add(k);
  const out: (ModelFamily | "other")[] = MODEL_FAMILIES.filter((f) => seen.has(f));
  if (seen.has("other")) out.push("other");
  return out;
}
