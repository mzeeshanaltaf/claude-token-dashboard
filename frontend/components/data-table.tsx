"use client";

import {
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type PaginationState,
  type Row,
  type SortingState,
  type Updater,
} from "@tanstack/react-table";
import { ArrowDownIcon, ArrowUpIcon, ChevronLeftIcon, ChevronRightIcon, ChevronsUpDownIcon } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { InfoTip } from "@/components/info-tip";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { fmt } from "@/lib/format";
import { cn } from "@/lib/utils";

declare module "@tanstack/react-table" {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  interface ColumnMeta<TData, TValue> {
    /** Right-align (numbers). */
    numeric?: boolean;
    /** Extra classes for the header and cells. */
    className?: string;
    /** A definition shown as an (i) next to the header. */
    info?: React.ReactNode;
  }
}

export const PAGE_SIZES = [25, 50, 100, 200] as const;

export interface ServerTableState {
  sort: string;
  desc: boolean;
  page: number;
  pageSize: number;
  total: number;
  onSort: (id: string, desc: boolean) => void;
  onPage: (page: number) => void;
  onPageSize: (size: number) => void;
}

/**
 * A TanStack table with shadcn styling.
 *
 * - `server`: sorting and paging are controlled by the caller (URL state); a
 *   header click asks for that column, first in its `sortDescFirst` direction.
 *   Column ids must be the API's sort keys.
 * - otherwise sorting runs in the browser, with optional client paging
 *   (`clientPageSize`).
 */
export function DataTable<T>({
  columns,
  data,
  server,
  clientPageSize,
  initialSort,
  onRowClick,
  getRowId,
  loading,
  dim,
  empty = "Nothing in this range.",
  className,
  rowClassName,
  focusRow,
}: {
  /**
   * Bring a row into view (client tables): switch to the page that holds it,
   * scroll to it and flash it. A new `nonce` repeats the jump for the same id.
   * Needs `getRowId`.
   */
  focusRow?: { id: string; nonce: number } | null;
  columns: ColumnDef<T, unknown>[];
  data: readonly T[] | undefined;
  server?: ServerTableState;
  clientPageSize?: number;
  initialSort?: SortingState;
  onRowClick?: (row: T) => void;
  getRowId?: (row: T, index: number) => string;
  loading?: boolean;
  dim?: boolean;
  empty?: React.ReactNode;
  className?: string;
  rowClassName?: (row: Row<T>) => string | undefined;
}) {
  const [clientSorting, setClientSorting] = useState<SortingState>(initialSort ?? []);
  const [pagination, setPagination] = useState<PaginationState>({ pageIndex: 0, pageSize: clientPageSize ?? 1_000_000 });

  const sorting: SortingState = server ? [{ id: server.sort, desc: server.desc }] : clientSorting;

  // TanStack only sorts columns that have an accessor. Server-sorted columns
  // are often display-only (`id` + `cell`), so give them a no-op accessor.
  const isServer = !!server;
  const cols = useMemo(
    () =>
      isServer
        ? columns.map((c) =>
            c.enableSorting !== false && !("accessorFn" in c) && !("accessorKey" in c)
              ? ({ ...c, accessorFn: () => null } as ColumnDef<T, unknown>)
              : c,
          )
        : columns,
    [columns, isServer],
  );

  const onSortingChange = (updater: Updater<SortingState>) => {
    const next = typeof updater === "function" ? updater(sorting) : updater;
    if (server) {
      if (next[0]) server.onSort(next[0].id, next[0].desc);
    } else {
      setClientSorting(next);
      setPagination((p) => ({ ...p, pageIndex: 0 }));
    }
  };

  // TanStack Table's instance is stable while its row models change, which
  // the React Compiler can't track. The compiler isn't enabled (next.config);
  // if it ever is, add "use no memo" to this component or rows go stale.
  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({
    data: (data ?? []) as T[],
    columns: cols,
    getRowId,
    state: { sorting, ...(clientPageSize ? { pagination } : {}) },
    onSortingChange,
    onPaginationChange: setPagination,
    enableSortingRemoval: false,
    manualSorting: !!server,
    manualPagination: !!server,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: server ? undefined : getSortedRowModel(),
    getPaginationRowModel: clientPageSize && !server ? getPaginationRowModel() : undefined,
  });

  const rows = table.getRowModel().rows;
  const colCount = table.getVisibleLeafColumns().length;

  // Jump to `focusRow`: pick its page while rendering (no effect → no extra
  // paint on the wrong page), then scroll and flash once it's in the DOM.
  const focusToken = focusRow ? `${focusRow.id}\u0000${focusRow.nonce}` : null;
  const [pagedFor, setPagedFor] = useState<string | null>(null);
  if (focusToken && focusToken !== pagedFor) {
    setPagedFor(focusToken);
    if (clientPageSize && !server) {
      const idx = table.getPrePaginationRowModel().rows.findIndex((r) => r.id === focusRow!.id);
      if (idx >= 0) setPagination((p) => ({ ...p, pageIndex: Math.floor(idx / p.pageSize) }));
    }
  }
  const tableRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!focusRow) return;
    const el = tableRef.current?.querySelector<HTMLElement>(`[data-row-id="${CSS.escape(focusRow.id)}"]`);
    if (!el) return;
    el.scrollIntoView({ block: "center", behavior: "smooth" });
    el.focus({ preventScroll: true });
    el.animate?.(
      [{ backgroundColor: "color-mix(in oklab, var(--primary) 22%, transparent)" }, { backgroundColor: "transparent" }],
      { duration: 1800, easing: "ease-out" },
    );
  }, [focusRow, pagination.pageIndex]);

  return (
    <div ref={tableRef} className={cn("flex min-w-0 flex-col gap-3", className)}>
      <div className={cn("overflow-hidden rounded-lg border transition-opacity", dim && "opacity-60")}>
        <Table>
          <TableHeader className="bg-muted/40">
            {table.getHeaderGroups().map((hg) => (
              <TableRow key={hg.id} className="hover:bg-transparent">
                {hg.headers.map((header) => {
                  const meta = header.column.columnDef.meta;
                  const canSort = header.column.getCanSort();
                  const dir = header.column.getIsSorted();
                  const label = header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext());
                  return (
                    <TableHead
                      key={header.id}
                      className={cn("h-9 text-xs font-medium text-muted-foreground", meta?.numeric && "text-right", meta?.className)}
                      aria-sort={dir === "asc" ? "ascending" : dir === "desc" ? "descending" : undefined}
                    >
                      <span className={cn("inline-flex items-center gap-1", meta?.numeric && "flex-row-reverse")}>
                        {canSort ? (
                          <button
                            type="button"
                            onClick={header.column.getToggleSortingHandler()}
                            className={cn(
                              "inline-flex items-center gap-1 rounded-sm hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
                              dir && "text-foreground",
                              meta?.numeric && "flex-row-reverse",
                            )}
                          >
                            {label}
                            {dir === "asc" ? (
                              <ArrowUpIcon className="size-3" />
                            ) : dir === "desc" ? (
                              <ArrowDownIcon className="size-3" />
                            ) : (
                              <ChevronsUpDownIcon className="size-3 opacity-40" />
                            )}
                          </button>
                        ) : (
                          label
                        )}
                        {meta?.info && <InfoTip label={`About ${String(header.column.id)}`}>{meta.info}</InfoTip>}
                      </span>
                    </TableHead>
                  );
                })}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {loading && !rows.length ? (
              Array.from({ length: 8 }, (_, i) => (
                <TableRow key={i} className="hover:bg-transparent">
                  <TableCell colSpan={colCount}>
                    <Skeleton className="h-5 w-full opacity-70" />
                  </TableCell>
                </TableRow>
              ))
            ) : rows.length ? (
              rows.map((row) => (
                <TableRow
                  key={row.id}
                  data-row-id={row.id}
                  onClick={onRowClick ? () => onRowClick(row.original) : undefined}
                  onKeyDown={
                    onRowClick
                      ? (e) => {
                          if (e.key === "Enter" && e.target === e.currentTarget) onRowClick(row.original);
                        }
                      : undefined
                  }
                  tabIndex={onRowClick ? 0 : undefined}
                  className={cn(onRowClick && "cursor-pointer focus-visible:bg-muted/60 focus-visible:outline-none", rowClassName?.(row))}
                >
                  {row.getVisibleCells().map((cell) => {
                    const meta = cell.column.columnDef.meta;
                    return (
                      <TableCell
                        key={cell.id}
                        className={cn(meta?.numeric && "text-right font-mono text-xs tabular", meta?.className)}
                      >
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </TableCell>
                    );
                  })}
                </TableRow>
              ))
            ) : (
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={colCount} className="h-24 text-center text-muted-foreground">
                  {empty}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
      {server ? (
        <Pager
          page={server.page}
          pageSize={server.pageSize}
          total={server.total}
          onPage={server.onPage}
          onPageSize={server.onPageSize}
        />
      ) : clientPageSize && (data?.length ?? 0) > clientPageSize ? (
        <Pager
          page={pagination.pageIndex + 1}
          pageSize={pagination.pageSize}
          total={data?.length ?? 0}
          onPage={(p) => setPagination((s) => ({ ...s, pageIndex: p - 1 }))}
        />
      ) : null}
    </div>
  );
}

export function Pager({
  page,
  pageSize,
  total,
  onPage,
  onPageSize,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPage: (page: number) => void;
  onPageSize?: (size: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const start = total ? (page - 1) * pageSize + 1 : 0;
  const end = Math.min(page * pageSize, total);
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-muted-foreground">
      <span className="tabular">{total ? `Showing ${fmt.int(start)}–${fmt.int(end)} of ${fmt.int(total)}` : "No rows"}</span>
      <span className="flex-1" />
      {onPageSize && (
        <label className="flex items-center gap-2">
          Rows
          <Select value={String(pageSize)} onValueChange={(v) => onPageSize(Number(v))}>
            <SelectTrigger size="sm" className="w-20" aria-label="Rows per page">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PAGE_SIZES.map((n) => (
                <SelectItem key={n} value={String(n)}>
                  {n}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </label>
      )}
      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" onClick={() => onPage(page - 1)} disabled={page <= 1} aria-label="Previous page">
          <ChevronLeftIcon />
        </Button>
        <span className="tabular">
          Page {fmt.int(Math.min(page, pages))} / {fmt.int(pages)}
        </span>
        <Button variant="outline" size="sm" onClick={() => onPage(page + 1)} disabled={page >= pages} aria-label="Next page">
          <ChevronRightIcon />
        </Button>
      </div>
    </div>
  );
}
