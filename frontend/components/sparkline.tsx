import { cn } from "@/lib/utils";

/**
 * A tiny inline SVG trend line (no axes, no hover) for table rows, where a
 * Recharts instance per row would be heavy. 2px line, a 10% area wash, and an
 * end dot. The row's own numbers carry the values, so it's aria-hidden.
 */
export function Sparkline({
  values,
  color = "var(--chart-input)",
  width = 96,
  height = 24,
  className,
}: {
  values: readonly number[];
  color?: string;
  width?: number;
  height?: number;
  className?: string;
}) {
  if (values.length < 2) {
    return <span className={cn("inline-block text-xs text-muted-foreground", className)} style={{ width }}>—</span>;
  }
  const max = Math.max(...values, 0);
  const pad = 3;
  const x = (i: number) => (i / (values.length - 1)) * (width - pad * 2) + pad;
  const y = (v: number) => height - pad - (max > 0 ? (v / max) * (height - pad * 2) : 0);
  const line = values.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join("");
  const area = `${line}L${x(values.length - 1).toFixed(1)},${height - pad}L${x(0).toFixed(1)},${height - pad}Z`;
  const last = values.length - 1;
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className={cn("block", className)} aria-hidden>
      <path d={area} fill={color} opacity={0.1} />
      <path d={line} fill="none" stroke={color} strokeWidth={1.5} strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={x(last)} cy={y(values[last])} r={2.5} fill={color} />
    </svg>
  );
}
