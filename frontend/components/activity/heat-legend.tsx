import { HEAT_LEVELS, heatColor } from "@/components/charts/heat-scale";

/**
 * "Less ■■■■■ More" with the step boundaries spelled out, so the colour
 * scale is never the only way to read a value.
 */
export function HeatLegend({
  thresholds,
  format,
  note,
}: {
  thresholds: readonly number[];
  format: (v: number) => string;
  note?: React.ReactNode;
}) {
  const steps = Array.from({ length: HEAT_LEVELS + 1 }, (_, l) => l);
  const range = (l: number) => {
    if (l === 0) return "none";
    if (!thresholds.length) return "";
    if (l === 1) return `≤ ${format(thresholds[0])}`;
    if (l === HEAT_LEVELS) return `> ${format(thresholds[thresholds.length - 1])}`;
    return `${format(thresholds[l - 2])} – ${format(thresholds[l - 1])}`;
  };
  return (
    <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
      <span>{note}</span>
      <div className="flex items-center gap-1.5">
        <span>Less</span>
        {steps.map((l) => (
          <span key={l} title={range(l)} className="size-3 rounded-[2px]" style={{ background: heatColor(l) }} />
        ))}
        <span>More</span>
        {thresholds.length > 0 && (
          <span className="ml-2 hidden font-mono tabular sm:inline">
            steps: {thresholds.map(format).join(" · ")}
          </span>
        )}
      </div>
    </div>
  );
}
