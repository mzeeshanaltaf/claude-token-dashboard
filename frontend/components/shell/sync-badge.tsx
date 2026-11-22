"use client";

import { RefreshCwIcon } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { fmt } from "@/lib/format";
import { useApiQuery } from "@/lib/queries";
import { cn } from "@/lib/utils";

const STALE_AFTER_MS = 36 * 60 * 60 * 1000;

/** Re-render every minute so "5m ago" stays current. */
function useNow(intervalMs = 60_000) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), intervalMs);
    return () => window.clearInterval(id);
  }, [intervalMs]);
  return now;
}

/**
 * "Synced 5h ago" from /api/sync-status: amber after 36h, red when the latest
 * run on any machine failed. Client-only (relative time uses the clock).
 */
export function SyncBadge() {
  const now = useNow();
  const { data, isPending, isError } = useApiQuery("/api/sync-status", { refetchInterval: 10 * 60 * 1000 });

  if (isPending) {
    return (
      <Badge variant="outline" className="text-muted-foreground">
        <RefreshCwIcon data-icon="inline-start" className="animate-spin" />
        Sync…
      </Badge>
    );
  }

  const last = data?.last_synced_at ?? null;
  const failed = isError || (data?.machines ?? []).some((m) => m.last_run?.status === "error");
  const stale = !last || now - new Date(last).getTime() > STALE_AFTER_MS;
  const tone = failed ? "error" : stale ? "stale" : "ok";
  const label = isError ? "Sync status unavailable" : last ? `Synced ${fmt.relative(last, now)}` : "Never synced";

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Badge
          variant="outline"
          data-tone={tone}
          className={cn(
            "cursor-default gap-1.5 font-normal tabular",
            tone === "ok" && "text-muted-foreground",
            tone === "stale" && "border-warning/40 text-warning",
            tone === "error" && "border-destructive/40 text-destructive",
          )}
        >
          <span
            aria-hidden
            className={cn(
              "size-1.5 rounded-full",
              tone === "ok" && "bg-success",
              tone === "stale" && "bg-warning",
              tone === "error" && "bg-destructive",
            )}
          />
          {label}
        </Badge>
      </TooltipTrigger>
      <TooltipContent align="end" className="max-w-xs">
        {data && data.machines.length > 0 ? (
          <div className="flex flex-col gap-1">
            {data.machines.map((m) => (
              <div key={m.machine} className="flex flex-col">
                <span className="font-medium">{m.machine}</span>
                <span className="opacity-80">
                  last run {fmt.ts(m.last_run.started_at)} · {m.last_run.status}
                  {m.last_run.status === "error" && m.last_run.error ? ` (${fmt.short(m.last_run.error, 80)})` : ""}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <span>No sync runs recorded yet. Run `claude-lens scan` on your PC.</span>
        )}
      </TooltipContent>
    </Tooltip>
  );
}
