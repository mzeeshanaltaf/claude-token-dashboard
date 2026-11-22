"use client";

import { DownloadIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useRange } from "@/hooks/use-range";
import { rangeToApi } from "@/lib/range";

type Table = "sessions" | "prompts" | "projects";

/**
 * Downloads every row matching the page's current filters and range as CSV
 * (`/api/export/<table>.csv`, streamed through the API proxy). The URL is
 * built on click: `rangeToApi` reads the clock, which must not run in render.
 *
 * Uses useSearchParams (via useRange): render under <Suspense>.
 */
export function ExportButton({ table, query }: { table: Table; query: Record<string, string | number | null | undefined> }) {
  const { range } = useRange();
  const onClick = () => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries({ ...query, ...rangeToApi(range) })) {
      if (v !== null && v !== undefined && v !== "") qs.set(k, String(v));
    }
    const s = qs.toString();
    // A download link, not a navigation: the response is an attachment, so the
    // page stays put and the browser streams the file to disk.
    const a = document.createElement("a");
    a.href = `/api/export/${table}.csv${s ? `?${s}` : ""}`;
    a.download = "";
    document.body.appendChild(a);
    a.click();
    a.remove();
  };
  return (
    <Button variant="outline" size="sm" onClick={onClick} className="sm:ml-auto">
      <DownloadIcon data-icon="inline-start" />
      Export CSV
    </Button>
  );
}
