"use client";

import { XCircleIcon } from "lucide-react";
import { useMemo } from "react";

import { HoverTip, useHoverTip } from "@/components/charts/hover-tip";
import { SectionCard } from "@/components/section-card";
import type { Schema } from "@/lib/api";
import { fmt } from "@/lib/format";

type Event = Schema<"ToolEvent">;

const MAX_LANES = 8;
/** Fixed tool → colour slots (identity follows the tool, never its rank). */
const TOOL_COLORS: Record<string, string> = {
  Read: "var(--chart-input)",
  Edit: "var(--chart-output)",
  Write: "var(--chart-cache-write)",
  Bash: "var(--chart-cache-read)",
  PowerShell: "var(--chart-cache-read)",
};
const OTHER_COLOR = "var(--muted-foreground)";
const OTHER = "Other";

interface Lane {
  name: string;
  color: string;
  events: (Event & { t: number })[];
  errors: number;
}

function sameDay(a: Date, b: Date) {
  return a.toDateString() === b.toDateString();
}

function eventTip(e: Event) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="flex items-center gap-1.5 font-medium">
        {e.tool_name}
        {e.is_error && (
          <span className="inline-flex items-center gap-0.5 text-destructive">
            <XCircleIcon className="size-3" /> error
          </span>
        )}
      </span>
      {e.target && <span className="blur-sensitive max-w-64 truncate font-mono text-[11px]">{e.target}</span>}
      <span className="font-mono tabular text-muted-foreground">{fmt.ts(e.ts)}</span>
    </div>
  );
}

/**
 * A swimlane per tool (the busiest 7, the rest in "Other"), each call a tick
 * at its time, coloured by tool; failed calls are red and taller. Hover a lane
 * for the nearest call; click to find its turn in the table.
 */
export function ToolTimeline({
  events,
  linked,
  onTurn,
}: {
  events: readonly Event[];
  /** Calls with a tool_use_id: only these can show an error. */
  linked: number;
  onTurn: (uuid: string) => void;
}) {
  const { ref: tipRef, tip, showAt: showTipAt, hide: hideTip } = useHoverTip();

  const { lanes, t0, t1 } = useMemo(() => {
    const timed = events.map((e) => ({ ...e, t: new Date(e.ts).getTime() }));
    const counts = new Map<string, number>();
    for (const e of timed) counts.set(e.tool_name, (counts.get(e.tool_name) ?? 0) + 1);
    const ranked = [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).map(([n]) => n);
    const named = ranked.length > MAX_LANES ? ranked.slice(0, MAX_LANES - 1) : ranked;
    const byName = new Map<string, Lane>(named.map((n) => [n, { name: n, color: TOOL_COLORS[n] ?? OTHER_COLOR, events: [], errors: 0 }]));
    const other: Lane = { name: OTHER, color: OTHER_COLOR, events: [], errors: 0 };
    for (const e of timed) {
      const lane = byName.get(e.tool_name) ?? other;
      lane.events.push(e);
      if (e.is_error) lane.errors++;
    }
    const lanes = [...byName.values()];
    if (other.events.length) lanes.push(other);
    const ts = timed.map((e) => e.t);
    return { lanes, t0: Math.min(...ts), t1: Math.max(...ts) };
  }, [events]);

  const span = Math.max(1, t1 - t0);
  const pos = (t: number) => ((t - t0) / span) * 100;
  const errors = lanes.reduce((s, l) => s + l.errors, 0);

  const nearest = (lane: Lane, e: React.MouseEvent<HTMLDivElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const t = t0 + ((e.clientX - r.left) / r.width) * span;
    let best: Lane["events"][number] | null = null;
    for (const ev of lane.events) if (!best || Math.abs(ev.t - t) < Math.abs(best.t - t)) best = ev;
    // within ~8px of the pointer
    return best && (Math.abs(best.t - t) / span) * r.width <= 8 ? best : null;
  };

  const axis = useMemo(() => {
    if (!Number.isFinite(t0)) return [];
    const multiDay = !sameDay(new Date(t0), new Date(t1));
    return [0, 0.25, 0.5, 0.75, 1].map((f) => {
      const d = new Date(t0 + f * span);
      return { f, label: multiDay ? fmt.ts(d.toISOString()).slice(5) : fmt.tsTime(d.toISOString()).slice(0, 5) };
    });
  }, [t0, t1, span]);

  return (
    <SectionCard
      title="Tool timeline"
      description={
        <>
          {fmt.int(events.length)} tool calls over time, one lane per tool.{" "}
          {linked < events.length
            ? `Errors are known for ${fmt.int(linked)} of ${fmt.int(events.length)} calls (older rows have no tool_use_id).`
            : `${fmt.int(errors)} failed.`}
        </>
      }
    >
      {!events.length ? (
        <p className="py-8 text-center text-sm text-muted-foreground">No tool calls in this session.</p>
      ) : (
        <div className="flex flex-col gap-3">
          <div ref={tipRef} className="relative flex flex-col gap-1.5" onMouseLeave={hideTip}>
            {lanes.map((lane) => (
              <div key={lane.name} className="grid grid-cols-[6.5rem_minmax(0,1fr)_3rem] items-center gap-2">
                <span className="flex items-center gap-1.5 truncate text-xs" title={lane.name}>
                  <span className="size-2 shrink-0 rounded-[2px]" style={{ background: lane.color }} aria-hidden />
                  <span className="truncate">{lane.name}</span>
                </span>
                <div
                  className="relative h-6 cursor-pointer rounded-sm bg-muted/50"
                  role="img"
                  aria-label={`${lane.name}: ${lane.events.length} calls${lane.errors ? `, ${lane.errors} failed` : ""}`}
                  onMouseMove={(e) => {
                    const ev = nearest(lane, e);
                    if (ev) showTipAt(e.clientX, e.currentTarget.getBoundingClientRect().top, eventTip(ev));
                    else hideTip();
                  }}
                  onClick={(e) => {
                    const ev = nearest(lane, e);
                    if (ev) onTurn(ev.message_uuid);
                  }}
                >
                  {lane.events.map((ev, k) =>
                    ev.is_error ? null : (
                      <span
                        key={k}
                        className="absolute top-1 bottom-1 w-0.5 -translate-x-1/2 rounded-full"
                        style={{ left: `${pos(ev.t)}%`, background: lane.color }}
                      />
                    ),
                  )}
                  {lane.events.map((ev, k) =>
                    ev.is_error ? (
                      <span
                        key={`e${k}`}
                        className="absolute inset-y-0 w-[3px] -translate-x-1/2 rounded-full bg-destructive ring-1 ring-card"
                        style={{ left: `${pos(ev.t)}%` }}
                      />
                    ) : null,
                  )}
                </div>
                <span className="text-right font-mono text-xs text-muted-foreground tabular">{fmt.int(lane.events.length)}</span>
              </div>
            ))}
            <div className="grid grid-cols-[6.5rem_minmax(0,1fr)_3rem] gap-2">
              <span />
              <div className="relative h-4">
                {axis.map((a) => (
                  <span
                    key={a.f}
                    className="absolute font-mono text-[10px] whitespace-nowrap text-muted-foreground tabular"
                    style={{ left: `${a.f * 100}%`, transform: a.f === 0 ? "none" : a.f === 1 ? "translateX(-100%)" : "translateX(-50%)" }}
                  >
                    {a.label}
                  </span>
                ))}
              </div>
            </div>
            <HoverTip tip={tip} />
          </div>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
            <span className="inline-flex items-center gap-1.5">
              <span className="h-3 w-[3px] rounded-full bg-destructive" aria-hidden />
              Failed call ({fmt.int(errors)})
            </span>
            <span>Hover a lane for details; click to find the turn.</span>
          </div>
        </div>
      )}
    </SectionCard>
  );
}
