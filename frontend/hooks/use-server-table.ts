"use client";

import { useEffect } from "react";

import type { ServerTableState } from "@/components/data-table";
import { PAGE_SIZES } from "@/components/data-table";

import { enumParam, intParam, useUrlState } from "./use-url-state";

/**
 * Sort / order / page / page size for a server-paginated table, read from the
 * URL (`?sort=cost&order=desc&page=2&size=50`). `apiQuery` is what the
 * endpoint takes; `table(total)` is the DataTable `server` prop.
 *
 * Uses useSearchParams: render under <Suspense>.
 */
export function useServerTable<S extends string>(sorts: readonly S[], defaultSort: S, defaultPageSize = 50) {
  const { get, set } = useUrlState();
  const sort = enumParam(get("sort"), sorts, defaultSort);
  const order = enumParam(get("order"), ["asc", "desc"] as const, "desc");
  const page = intParam(get("page"), 1);
  const pageSize = intParam(get("size"), defaultPageSize, PAGE_SIZES);

  const apiQuery = { sort, order, page, page_size: pageSize } as const;

  const table = (total: number): ServerTableState => ({
    sort,
    desc: order === "desc",
    page,
    pageSize,
    total,
    onSort: (id, desc) => set({ sort: id, order: desc ? "desc" : "asc", page: null }),
    onPage: (p) => set({ page: p > 1 ? p : null }),
    onPageSize: (n) => set({ size: n === defaultPageSize ? null : n, page: null }),
  });

  return { sort, order, page, pageSize, apiQuery, table, set } as const;
}

/** When a filter or range change leaves the current page past the end, go back to page 1. */
export function useClampPage(page: number, total: number | undefined, itemsOnPage: number | undefined, set: (p: Record<string, null>) => void) {
  useEffect(() => {
    if (page > 1 && total !== undefined && itemsOnPage === 0) set({ page: null });
  }, [page, total, itemsOnPage, set]);
}
