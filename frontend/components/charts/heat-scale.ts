/**
 * The heatmaps' sequential scale: one hue (the input blue), light→dark on the
 * light theme and dark→bright on the dark one, in 4 quantised steps plus an
 * "inactive" step. Steps are mixes of the hue into the card surface, so the
 * lightness order holds in both themes by construction (dataviz: sequential =
 * one hue, monotonic lightness; never a rainbow).
 */
export const HEAT_LEVELS = 4;

const MIX = [0, 28, 52, 76, 100];

export function heatColor(level: number): string {
  if (level <= 0) return "var(--heat-0)";
  return `color-mix(in oklab, var(--chart-input) ${MIX[Math.min(level, HEAT_LEVELS)]}%, var(--card))`;
}

/**
 * Quantile thresholds over the non-zero values (GitHub-style): a value of 0
 * is level 0, the rest split into HEAT_LEVELS buckets of roughly equal count,
 * so one huge day doesn't wash every other day out to the lightest step.
 */
export function quantizer(values: readonly number[]): { level: (v: number) => number; thresholds: number[] } {
  const nz = values.filter((v) => v > 0).sort((a, b) => a - b);
  if (!nz.length) return { level: () => 0, thresholds: [] };
  const thresholds: number[] = [];
  for (let i = 1; i < HEAT_LEVELS; i++) thresholds.push(nz[Math.min(nz.length - 1, Math.floor((i * nz.length) / HEAT_LEVELS))]);
  return {
    thresholds,
    level: (v: number) => {
      if (!(v > 0)) return 0;
      let l = 1;
      for (const t of thresholds) if (v > t) l++;
      return Math.min(l, HEAT_LEVELS);
    },
  };
}
