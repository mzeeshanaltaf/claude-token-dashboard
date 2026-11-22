/**
 * The dashboard date range.
 *
 * URL forms (shareable):  ?range=7d|30d|90d|all   or   ?since=YYYY-MM-DD&until=YYYY-MM-DD
 * (custom dates are local calendar days, `until` inclusive).
 *
 * Query keys use `rangeKey(spec)`, a deterministic string. The actual
 * `since`/`until` sent to the API are computed at fetch time by
 * `rangeToApi()`, from the browser's local day boundaries, as ISO strings with
 * an explicit offset (the backend reads naive values as UTC).
 */
import { addDays, format, isValid, parse, startOfDay } from "date-fns";

export const RANGE_PRESETS = ["7d", "30d", "90d", "all"] as const;
export type RangePreset = (typeof RANGE_PRESETS)[number];

export type RangeSpec =
  | { kind: "preset"; preset: RangePreset }
  | { kind: "custom"; since: string; until: string };

/** Matches the old dashboard, which showed all-time data until narrowed. */
export const DEFAULT_RANGE: RangeSpec = { kind: "preset", preset: "all" };

export const PRESET_LABELS: Record<RangePreset, string> = {
  "7d": "7d",
  "30d": "30d",
  "90d": "90d",
  all: "All",
};

const PRESET_DAYS: Record<Exclude<RangePreset, "all">, number> = { "7d": 7, "30d": 30, "90d": 90 };
const DAY_RE = /^\d{4}-\d{2}-\d{2}$/;

export const RANGE_PARAM_NAMES = ["range", "since", "until"] as const;

function isPreset(v: string | null): v is RangePreset {
  return v !== null && (RANGE_PRESETS as readonly string[]).includes(v);
}

export function parseDay(s: string | null | undefined): Date | null {
  if (!s || !DAY_RE.test(s)) return null;
  const d = parse(s, "yyyy-MM-dd", new Date(2000, 0, 1));
  return isValid(d) ? d : null;
}

export function formatDay(d: Date): string {
  return format(d, "yyyy-MM-dd");
}

/** Parses a range from URL params; null when the URL doesn't carry one. */
export function parseRange(params: { get(name: string): string | null }): RangeSpec | null {
  const since = params.get("since");
  const until = params.get("until");
  const s = parseDay(since);
  const u = parseDay(until);
  if (s && u && since && until) {
    return s <= u ? { kind: "custom", since, until } : { kind: "custom", since: until, until: since };
  }
  const preset = params.get("range");
  return isPreset(preset) ? { kind: "preset", preset } : null;
}

/** Serialises for storage and query keys: "30d" or "2026-11-01..2026-11-20". */
export function rangeKey(spec: RangeSpec): string {
  return spec.kind === "preset" ? spec.preset : `${spec.since}..${spec.until}`;
}

export function rangeFromKey(key: string | null | undefined): RangeSpec | null {
  if (!key) return null;
  if (isPreset(key)) return { kind: "preset", preset: key };
  const [since, until] = key.split("..");
  return parseRange(new URLSearchParams({ since: since ?? "", until: until ?? "" }));
}

/** URL params for a range, merged into `current` (other params kept). */
export function withRange(current: URLSearchParams, spec: RangeSpec): URLSearchParams {
  const next = new URLSearchParams(current);
  RANGE_PARAM_NAMES.forEach((n) => next.delete(n));
  if (spec.kind === "preset") next.set("range", spec.preset);
  else {
    next.set("since", spec.since);
    next.set("until", spec.until);
  }
  return next;
}

/** `since` (inclusive) / `until` (exclusive) for the API, at local midnight. */
export function rangeToApi(spec: RangeSpec, now: Date = new Date()): { since?: string; until?: string } {
  if (spec.kind === "preset") {
    if (spec.preset === "all") return {};
    // "7d" = today plus the 6 days before it.
    const since = startOfDay(addDays(now, -(PRESET_DAYS[spec.preset] - 1)));
    return { since: since.toISOString() };
  }
  const s = parseDay(spec.since);
  const u = parseDay(spec.until);
  if (!s || !u) return {};
  return { since: startOfDay(s).toISOString(), until: startOfDay(addDays(u, 1)).toISOString() };
}

export function rangeLabel(spec: RangeSpec): string {
  if (spec.kind === "preset") {
    return spec.preset === "all" ? "All time" : `Last ${PRESET_DAYS[spec.preset]} days`;
  }
  const s = parseDay(spec.since);
  const u = parseDay(spec.until);
  if (!s || !u) return "Custom range";
  const sameYear = s.getFullYear() === u.getFullYear();
  return `${format(s, sameYear ? "MMM d" : "MMM d, yyyy")} – ${format(u, "MMM d, yyyy")}`;
}
