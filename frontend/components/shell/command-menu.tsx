"use client";

import { SearchIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

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
import { ALL_NAV } from "@/lib/nav";

/**
 * Cmd/Ctrl+K palette. Phase 04 ships navigation only; phase 06 adds search
 * over prompts and sessions.
 */
export function CommandMenu() {
  const [open, setOpen] = useState(false);
  const router = useRouter();

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
      <CommandDialog open={open} onOpenChange={setOpen} title="Command menu" description="Jump to a page">
        {/* This shadcn version's CommandDialog doesn't add the cmdk root itself. */}
        <Command>
          <CommandInput placeholder="Go to…" />
          <CommandList>
            <CommandEmpty>Nothing matches. Prompt and session search arrive in a later update.</CommandEmpty>
            <CommandGroup heading="Pages">
              {ALL_NAV.map((item) => (
                <CommandItem
                  key={item.href}
                  value={item.title}
                  onSelect={() => {
                    setOpen(false);
                    router.push(item.href);
                  }}
                >
                  <item.icon />
                  {item.title}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </CommandDialog>
    </>
  );
}
