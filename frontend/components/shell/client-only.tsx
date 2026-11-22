"use client";

/**
 * Shell pieces that depend on the browser (localStorage, the clock, the
 * platform), mounted with next/dynamic({ ssr: false }) per the hydration rule
 * in the global CLAUDE.md: they never render on the server, so they can't
 * mismatch.
 */
import dynamic from "next/dynamic";

import { Skeleton } from "@/components/ui/skeleton";

export const RangePicker = dynamic(() => import("./range-picker").then((m) => m.RangePicker), {
  ssr: false,
  loading: () => <Skeleton className="h-8 w-56" />,
});

export const SyncBadge = dynamic(() => import("./sync-badge").then((m) => m.SyncBadge), {
  ssr: false,
  loading: () => <Skeleton className="h-5 w-28 rounded-full" />,
});

export const PlanPicker = dynamic(() => import("./plan-picker").then((m) => m.PlanPicker), { ssr: false });
