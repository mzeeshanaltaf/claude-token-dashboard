/**
 * Display formatters, ported from the old web/app.js `fmt`.
 *
 * `ts`/`tsTime`/`relative` depend on the browser's timezone or clock, so only
 * call them in client-only trees or on client-fetched data (never in markup
 * that is server-rendered and then hydrated).
 */
import { FAMILY_LABELS, parseClaudeModel, type ModelFamily } from "./models";

const INT = new Intl.NumberFormat("en-US");
const COMPACT = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 });
const USD = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 2 });
const USD4 = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 4, maximumFractionDigits: 4 });

const pad = (n: number) => String(n).padStart(2, "0");

function toDate(t: string | number | Date | null | undefined): Date | null {
  if (t === null || t === undefined || t === "") return null;
  const d = t instanceof Date ? t : new Date(t);
  return Number.isNaN(d.getTime()) ? null : d;
}

export const fmt = {
  /** 1234567 → "1,234,567" */
  int: (n: number | null | undefined) => INT.format(n ?? 0),
  /** 1234567 → "1.2M" */
  compact: (n: number | null | undefined) => COMPACT.format(n ?? 0),
  /** 12.345 → "$12.35"; null → "—" */
  usd: (n: number | null | undefined) => (n === null || n === undefined ? "—" : USD.format(n)),
  /** 0.01234 → "$0.0123"; null → "—" */
  usd4: (n: number | null | undefined) => (n === null || n === undefined ? "—" : USD4.format(n)),
  /** 0.4567 → "46%"; null → "—" */
  pct: (n: number | null | undefined, digits = 0) =>
    n === null || n === undefined || Number.isNaN(n) ? "—" : `${(n * 100).toFixed(digits)}%`,
  /** Truncate with an ellipsis. */
  short: (s: string | null | undefined, n = 80) => (s == null ? "" : s.length > n ? `${s.slice(0, n - 1)}…` : s),
  /** ISO → "2026-11-22 14:05" in local time. */
  ts: (t: string | null | undefined) => {
    const d = toDate(t);
    if (!d) return t ? t.slice(0, 16).replace("T", " ") : "";
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  },
  /** ISO → "14:05:09" in local time. */
  tsTime: (t: string | null | undefined) => {
    const d = toDate(t);
    if (!d) return t ? t.slice(11, 19) : "";
    return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  },
  /** "claude-opus-5-5" → "opus-5-5" */
  modelShort: (m: string | null | undefined) => (m ?? "").replace(/^claude-/, ""),
  /** "claude-opus-5-5" → "Opus 5.5"; other ids unchanged. */
  modelLabel: (m: string | null | undefined) => {
    const p = parseClaudeModel(m);
    if (!p) return m ?? "";
    return p.version ? `${FAMILY_LABELS[p.family]} ${p.version}` : FAMILY_LABELS[p.family];
  },
  /** The model's family, or null for non-Claude ids. */
  modelFamily: (m: string | null | undefined): ModelFamily | null => parseClaudeModel(m)?.family ?? null,
  /** "5h ago", "3d ago", "just now". `now` is injectable for tests. */
  relative: (t: string | Date | null | undefined, now: number = Date.now()) => {
    const d = toDate(t);
    if (!d) return "never";
    const s = Math.round((now - d.getTime()) / 1000);
    if (s < 45) return "just now";
    const m = Math.round(s / 60);
    if (m < 60) return `${m}m ago`;
    const h = Math.round(m / 60);
    if (h < 48) return `${h}h ago`;
    return `${Math.round(h / 24)}d ago`;
  },
};
