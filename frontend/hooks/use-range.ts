"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo, useSyncExternalStore } from "react";

import {
  DEFAULT_RANGE,
  parseRange,
  rangeFromKey,
  rangeKey,
  withRange,
  type RangeSpec,
} from "@/lib/range";

const STORAGE_KEY = "lens.range";
const CHANGE_EVENT = "lens:range-stored";

function subscribe(onChange: () => void) {
  window.addEventListener("storage", onChange);
  window.addEventListener(CHANGE_EVENT, onChange);
  return () => {
    window.removeEventListener("storage", onChange);
    window.removeEventListener(CHANGE_EVENT, onChange);
  };
}

function readStored(): string | null {
  try {
    return window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function writeStored(spec: RangeSpec) {
  try {
    window.localStorage.setItem(STORAGE_KEY, rangeKey(spec));
  } catch {
    /* private mode */
  }
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

/**
 * The active range: the URL's when present, else the last choice remembered
 * in localStorage, else the default.
 *
 * localStorage is read through useSyncExternalStore with a `null` server
 * snapshot, so the server render and the hydration pass agree (no mismatch);
 * the stored value applies right after hydration.
 *
 * Uses useSearchParams: render it under a <Suspense> boundary.
 */
export function useRange() {
  const params = useSearchParams();
  const pathname = usePathname();
  const router = useRouter();
  const storedKey = useSyncExternalStore(subscribe, readStored, () => null);

  const spec = useMemo<RangeSpec>(
    () => parseRange(params) ?? rangeFromKey(storedKey) ?? DEFAULT_RANGE,
    [params, storedKey],
  );

  const setRange = useCallback(
    (next: RangeSpec) => {
      writeStored(next);
      const qs = withRange(new URLSearchParams(params.toString()), next).toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [params, pathname, router],
  );

  return { range: spec, key: rangeKey(spec), setRange } as const;
}
