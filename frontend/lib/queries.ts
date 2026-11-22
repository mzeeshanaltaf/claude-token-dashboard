"use client";

import { useQuery } from "@tanstack/react-query";

import { useRange } from "@/hooks/use-range";
import { api, type ApiQuery, type ApiResponse, type GetPath } from "@/lib/api";
import { rangeToApi } from "@/lib/range";

/** Endpoints that accept `since`/`until`. */
export type RangedPath =
  | "/api/overview"
  | "/api/daily"
  | "/api/by-model"
  | "/api/tools"
  | "/api/skills"
  | "/api/projects"
  | "/api/projects/daily"
  | "/api/projects/{slug}/sessions"
  | "/api/sessions"
  | "/api/prompts";

/**
 * Query keys: `[path, rangeKey, extraQuery]` for ranged data, `[path]`
 * otherwise. Invalidate by path prefix: `queryClient.invalidateQueries({ queryKey: ["/api/settings"] })`.
 */
export const queryKeys = {
  ranged: (path: RangedPath, rangeKey: string, query?: object, params?: object) =>
    (params ? [path, rangeKey, query ?? {}, params] : [path, rangeKey, query ?? {}]) as readonly unknown[],
  plain: (path: GetPath, params?: object) => (params ? [path, params] : [path]) as readonly unknown[],
};

/**
 * Fetches a ranged endpoint for the active date range. The range key is part
 * of the query key, so changing the range refetches. `since`/`until` are
 * computed when the request runs (local day boundaries).
 *
 * Uses useSearchParams via useRange: render under <Suspense>.
 */
export function useRangedQuery<P extends RangedPath>(
  path: P,
  query?: Omit<NonNullable<ApiQuery<P>>, "since" | "until">,
  opts?: { params?: Record<string, string>; enabled?: boolean },
) {
  const { range, key } = useRange();
  return useQuery({
    queryKey: queryKeys.ranged(path, key, query, opts?.params),
    queryFn: ({ signal }) =>
      // The spread can't be checked against the per-path union; P constrains it.
      api.get(path, {
        query: { ...query, ...rangeToApi(range) } as never,
        params: opts?.params,
        signal,
      }) as Promise<ApiResponse<P>>,
    placeholderData: (prev) => prev,
    enabled: opts?.enabled,
  });
}

/** A range-independent GET. */
export function useApiQuery<P extends GetPath>(
  path: P,
  opts?: { refetchInterval?: number; enabled?: boolean; params?: Record<string, string> },
) {
  const { params, ...rest } = opts ?? {};
  return useQuery({
    queryKey: queryKeys.plain(path, params),
    queryFn: ({ signal }) => api.get(path, { signal, params }) as Promise<ApiResponse<P>>,
    ...rest,
  });
}
