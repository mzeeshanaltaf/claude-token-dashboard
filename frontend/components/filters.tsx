"use client";

import { SearchIcon, XIcon } from "lucide-react";

import { InputGroup, InputGroupAddon, InputGroupButton, InputGroupInput } from "@/components/ui/input-group";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useDebouncedUrlParam, useUrlState } from "@/hooks/use-url-state";
import { fmt } from "@/lib/format";
import { useRangedQuery } from "@/lib/queries";
import { cn } from "@/lib/utils";

const ALL = "__all";

/** The one filter row above a table: wraps on narrow screens. */
export function FilterBar({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn("flex flex-wrap items-center gap-2", className)}>{children}</div>;
}

/** A text search bound to `?q=` (debounced; resets the page). */
export function SearchBox({ placeholder, param = "q", className }: { placeholder: string; param?: string; className?: string }) {
  const [value, setValue] = useDebouncedUrlParam(param);
  return (
    <InputGroup className={cn("w-full sm:w-72", className)}>
      <InputGroupAddon>
        <SearchIcon />
      </InputGroupAddon>
      <InputGroupInput
        type="search"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={placeholder}
        aria-label={placeholder}
      />
      {value && (
        <InputGroupAddon align="inline-end">
          <InputGroupButton size="icon-xs" aria-label="Clear search" onClick={() => setValue("")}>
            <XIcon />
          </InputGroupButton>
        </InputGroupAddon>
      )}
    </InputGroup>
  );
}

/** `?project=<slug>`, listing the projects active in the range. */
export function ProjectSelect({ className }: { className?: string }) {
  const { get, set } = useUrlState();
  const projects = useRangedQuery("/api/projects");
  const value = get("project") ?? ALL;
  const list = [...(projects.data ?? [])].sort((a, b) => a.project_name.localeCompare(b.project_name));
  // Keep a selected slug visible even when the range no longer includes it.
  const missing = value !== ALL && !list.some((p) => p.project_slug === value);
  return (
    <Select value={value} onValueChange={(v) => set({ project: v === ALL ? null : v, page: null })}>
      <SelectTrigger className={cn("w-full sm:w-56", className)} aria-label="Project">
        <SelectValue placeholder="All projects" />
      </SelectTrigger>
      <SelectContent className="max-h-80">
        <SelectItem value={ALL}>All projects</SelectItem>
        {missing && (
          <SelectItem value={value}>
            <span className="blur-sensitive">{value}</span>
          </SelectItem>
        )}
        {list.map((p) => (
          <SelectItem key={p.project_slug} value={p.project_slug}>
            <span className="blur-sensitive truncate">{p.project_name}</span>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

/** `?model=<id>`, listing the models used in the range. */
export function ModelSelect({ className }: { className?: string }) {
  const { get, set } = useUrlState();
  const models = useRangedQuery("/api/by-model");
  const value = get("model") ?? ALL;
  const list = (models.data ?? []).map((m) => m.model).filter((m) => m !== "unknown");
  const missing = value !== ALL && !list.includes(value);
  return (
    <Select value={value} onValueChange={(v) => set({ model: v === ALL ? null : v, page: null })}>
      <SelectTrigger className={cn("w-full sm:w-48", className)} aria-label="Model">
        <SelectValue placeholder="All models" />
      </SelectTrigger>
      <SelectContent className="max-h-80">
        <SelectItem value={ALL}>All models</SelectItem>
        {missing && <SelectItem value={value}>{fmt.modelLabel(value)}</SelectItem>}
        {list.map((m) => (
          <SelectItem key={m} value={m}>
            {fmt.modelLabel(m)}
            {fmt.modelLabel(m) !== m && <span className="text-xs text-muted-foreground">{fmt.modelShort(m)}</span>}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
