"use client";

import { useQuery } from "@tanstack/react-query";
import { FolderIcon, MessageSquareTextIcon, MessagesSquareIcon, SearchIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { Fragment, useEffect, useState } from "react";

import { Kbd } from "@/components/shell/kbd";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Spinner } from "@/components/ui/spinner";
import { api } from "@/lib/api";
import { fmt } from "@/lib/format";
import { ALL_NAV } from "@/lib/nav";

const DEBOUNCE_MS = 200;
const MIN_CHARS = 2;
// The backend marks matches with private-use characters (never HTML).
const HL_START = "";
const HL_STOP = "";

/** A snippet with its matches wrapped in <mark>; text only, so nothing is injected. */
function Snippet({ text }: { text: string }) {
  const parts = text.replace(/\s+/g, " ").split(HL_START);
  return (
    <span className="blur-sensitive line-clamp-2 text-xs text-muted-foreground">
      {parts.map((part, i) => {
        if (i === 0) return <Fragment key={i}>{part}</Fragment>;
        const [hit, rest = ""] = part.split(HL_STOP);
        return (
          <Fragment key={i}>
            <mark className="rounded-[2px] bg-primary/20 px-0.5 text-foreground">{hit}</mark>
            {rest}
          </Fragment>
        );
      })}
    </span>
  );
}

function useDebounced(value: string, ms: number) {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

/**
 * Cmd/Ctrl+K palette: jump to a page, or search prompts (full text), session
 * titles and projects. Arrow keys move, Enter opens; a prompt opens its
 * session scrolled to that turn.
 */
export function CommandMenu() {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const router = useRouter();
  const term = useDebounced(input.trim(), DEBOUNCE_MS);
  const searching = term.length >= MIN_CHARS;

  const results = useQuery({
    queryKey: ["/api/search", term],
    queryFn: ({ signal }) => api.get("/api/search", { query: { q: term, limit: 8 }, signal }),
    enabled: open && searching,
    staleTime: 60_000,
    placeholderData: (prev) => prev,
  });

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const onOpenChange = (o: boolean) => {
    setOpen(o);
    if (!o) setInput("");
  };
  const go = (href: string) => {
    onOpenChange(false);
    router.push(href);
  };

  const needle = input.trim().toLowerCase();
  const pages = needle ? ALL_NAV.filter((p) => p.title.toLowerCase().includes(needle)) : ALL_NAV;
  // While a new term loads, the previous results stay (placeholderData).
  const data = searching ? results.data : undefined;
  const pending = searching && (results.isFetching || term !== input.trim());

  return (
    <>
      <Button
        variant="outline"
        size="sm"
        onClick={() => setOpen(true)}
        className="text-muted-foreground"
        aria-label="Open command menu"
      >
        <SearchIcon data-icon="inline-start" />
        <span className="hidden lg:inline">Search</span>
        <Kbd keys={["mod", "K"]} className="hidden lg:inline-flex" />
      </Button>
      <CommandDialog open={open} onOpenChange={onOpenChange} title="Search" description="Search prompts, sessions and projects, or jump to a page">
        {/* This shadcn version's CommandDialog doesn't add the cmdk root itself. */}
        {/* The server ranks results, so cmdk's own filtering is off. */}
        <Command shouldFilter={false}>
          <div className="relative">
            <CommandInput value={input} onValueChange={setInput} placeholder="Search prompts, sessions, projects…" />
            {pending && <Spinner className="absolute top-1/2 right-3 size-4 -translate-y-1/2 text-muted-foreground" />}
          </div>
          <CommandList className="max-h-[min(70vh,32rem)]">
            <CommandEmpty>
              {!searching
                ? "Type at least 2 characters to search."
                : pending
                  ? "Searching…"
                  : results.isError
                    ? `Search failed: ${results.error.message}`
                    : "No prompts, sessions or projects match."}
            </CommandEmpty>
            {pages.length > 0 && (
              <CommandGroup heading="Pages">
                {pages.map((item) => (
                  <CommandItem key={item.href} value={`page:${item.href}`} onSelect={() => go(item.href)}>
                    <item.icon />
                    {item.title}
                  </CommandItem>
                ))}
              </CommandGroup>
            )}
            {data && data.prompts.length > 0 && (
              <CommandGroup heading="Prompts">
                {data.prompts.map((p) => (
                  <CommandItem
                    key={p.user_uuid}
                    value={`prompt:${p.user_uuid}`}
                    onSelect={() => go(`/sessions/${encodeURIComponent(p.session_id)}?turn=${encodeURIComponent(p.user_uuid)}`)}
                    className="items-start"
                  >
                    <MessageSquareTextIcon className="mt-0.5" />
                    <span className="flex min-w-0 flex-col gap-0.5">
                      <Snippet text={p.snippet} />
                      <span className="truncate text-[11px] text-muted-foreground/80">
                        <span className="blur-sensitive">{p.title ?? p.session_id.slice(0, 8)}</span> · {fmt.ts(p.timestamp)}
                      </span>
                    </span>
                  </CommandItem>
                ))}
              </CommandGroup>
            )}
            {data && data.sessions.length > 0 && (
              <CommandGroup heading="Sessions">
                {data.sessions.map((s) => (
                  <CommandItem key={s.session_id} value={`session:${s.session_id}`} onSelect={() => go(`/sessions/${encodeURIComponent(s.session_id)}`)}>
                    <MessagesSquareIcon />
                    <span className="blur-sensitive min-w-0 flex-1 truncate">{s.title}</span>
                    <span className="shrink-0 font-mono text-[11px] text-muted-foreground">{fmt.relative(s.ended)}</span>
                  </CommandItem>
                ))}
              </CommandGroup>
            )}
            {data && data.projects.length > 0 && (
              <CommandGroup heading="Projects">
                {data.projects.map((p) => (
                  <CommandItem key={p.project_slug} value={`project:${p.project_slug}`} onSelect={() => go(`/projects/${encodeURIComponent(p.project_slug)}`)}>
                    <FolderIcon />
                    <span className="blur-sensitive min-w-0 flex-1 truncate">{p.project_name}</span>
                    <span className="shrink-0 text-[11px] text-muted-foreground">{fmt.int(p.sessions)} sessions</span>
                  </CommandItem>
                ))}
              </CommandGroup>
            )}
          </CommandList>
        </Command>
      </CommandDialog>
    </>
  );
}
