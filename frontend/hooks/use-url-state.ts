"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { RANGE_PARAM_NAMES } from "@/lib/range";

type Patch = Record<string, string | number | null | undefined>;

/**
 * Page state kept in the URL (sort, page, filters), next to the date range,
 * so a link or the back button restores the exact view. `set` merges a patch
 * (null/"" removes a key) with router.replace, keeping every other param.
 *
 * Uses useSearchParams: render under <Suspense>.
 */
export function useUrlState() {
  const params = useSearchParams();
  const pathname = usePathname();
  const router = useRouter();

  const get = useCallback((name: string) => params.get(name), [params]);

  const set = useCallback(
    (patch: Patch) => {
      const next = new URLSearchParams(params.toString());
      for (const [k, v] of Object.entries(patch)) {
        if (v === null || v === undefined || v === "") next.delete(k);
        else next.set(k, String(v));
      }
      const qs = next.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [params, pathname, router],
  );

  return { get, set, params } as const;
}

/** An int URL param, clamped to the allowed values (or >= 1 when none given). */
export function intParam(raw: string | null, fallback: number, allowed?: readonly number[]): number {
  const n = Number(raw);
  if (!Number.isInteger(n) || n < 1) return fallback;
  if (allowed && !allowed.includes(n)) return fallback;
  return n;
}

/** A value from a whitelist, or the fallback. */
export function enumParam<T extends string>(raw: string | null, allowed: readonly T[], fallback: T): T {
  return raw !== null && (allowed as readonly string[]).includes(raw) ? (raw as T) : fallback;
}

/**
 * The current range params as a query string ("range=7d"), for links that
 * should keep the range (Overview → a project, a session → its project…).
 */
export function useRangedHref() {
  const params = useSearchParams();
  return useCallback(
    (path: string) => {
      const keep = new URLSearchParams();
      for (const n of RANGE_PARAM_NAMES) {
        const v = params.get(n);
        if (v) keep.set(n, v);
      }
      const qs = keep.toString();
      return qs ? `${path}?${qs}` : path;
    },
    [params],
  );
}

/**
 * A search box bound to a URL param: typing updates local state at once and
 * the URL (and so the query) after `delay` ms of quiet. Resets `page`.
 */
export function useDebouncedUrlParam(name: string, delay = 300) {
  const { get, set } = useUrlState();
  const urlValue = get(name) ?? "";
  const [value, setValue] = useState(urlValue);
  const [typing, setTyping] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Follow outside changes (back button, a cleared filter) unless mid-typing.
  const [seen, setSeen] = useState(urlValue);
  if (seen !== urlValue) {
    setSeen(urlValue);
    if (!typing) setValue(urlValue);
  }

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  const onChange = useCallback(
    (v: string) => {
      setValue(v);
      setTyping(true);
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => {
        timer.current = null;
        setTyping(false);
        set({ [name]: v.trim() || null, page: null });
      }, delay);
    },
    [delay, name, set],
  );

  return [value, onChange] as const;
}
