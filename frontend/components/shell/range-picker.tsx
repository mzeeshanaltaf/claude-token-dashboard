"use client";

import { CalendarIcon } from "lucide-react";
import { useState } from "react";
import type { DateRange } from "react-day-picker";

import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { useRange } from "@/hooks/use-range";
import { formatDay, parseDay, PRESET_LABELS, RANGE_PRESETS, rangeLabel, type RangePreset } from "@/lib/range";

/**
 * 7d · 30d · 90d · All, plus a custom from/to calendar. Client-only (mounted
 * via next/dynamic ssr:false): it shows the remembered choice and "today".
 */
export function RangePicker() {
  const { range, setRange } = useRange();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<DateRange | undefined>(undefined);

  function openCustom(next: boolean) {
    if (next) {
      setDraft(
        range.kind === "custom"
          ? { from: parseDay(range.since) ?? undefined, to: parseDay(range.until) ?? undefined }
          : undefined,
      );
    }
    setOpen(next);
  }

  function apply() {
    if (!draft?.from) return;
    const to = draft.to ?? draft.from;
    setRange({ kind: "custom", since: formatDay(draft.from), until: formatDay(to) });
    setOpen(false);
  }

  return (
    <div className="flex items-center gap-2">
      <ToggleGroup
        type="single"
        variant="outline"
        size="sm"
        value={range.kind === "preset" ? range.preset : ""}
        onValueChange={(v) => v && setRange({ kind: "preset", preset: v as RangePreset })}
        aria-label="Date range"
      >
        {RANGE_PRESETS.map((p) => (
          <ToggleGroupItem key={p} value={p} className="px-2.5 font-mono text-xs">
            {PRESET_LABELS[p]}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
      <Popover open={open} onOpenChange={openCustom}>
        <PopoverTrigger asChild>
          <Button variant={range.kind === "custom" ? "secondary" : "outline"} size="sm" aria-label="Custom date range">
            <CalendarIcon data-icon="inline-start" />
            <span className="hidden sm:inline">{range.kind === "custom" ? rangeLabel(range) : "Custom"}</span>
          </Button>
        </PopoverTrigger>
        <PopoverContent align="end" className="w-auto p-0">
          <Calendar
            mode="range"
            numberOfMonths={2}
            selected={draft}
            onSelect={setDraft}
            defaultMonth={draft?.from}
            disabled={{ after: new Date() }}
          />
          <div className="flex items-center justify-between gap-3 border-t p-3">
            <span className="text-xs text-muted-foreground tabular">
              {draft?.from
                ? rangeLabel({ kind: "custom", since: formatDay(draft.from), until: formatDay(draft.to ?? draft.from) })
                : "Pick a start and end day"}
            </span>
            <Button size="sm" onClick={apply} disabled={!draft?.from}>
              Apply
            </Button>
          </div>
        </PopoverContent>
      </Popover>
    </div>
  );
}
