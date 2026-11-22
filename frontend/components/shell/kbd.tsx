"use client";

import { useSyncExternalStore } from "react";

import { cn } from "@/lib/utils";

const noop = () => () => {};

function detectMac(): boolean {
  const nav = navigator as Navigator & { userAgentData?: { platform?: string } };
  const p = nav.userAgentData?.platform || nav.platform || nav.userAgent || "";
  return /mac|iphone|ipad|ipod/i.test(p);
}

/** True on Apple platforms; false on the server and during hydration. */
export function useIsMac(): boolean {
  return useSyncExternalStore(noop, detectMac, () => false);
}

/** A keyboard shortcut hint. `mod` renders as ⌘ on Apple platforms, Ctrl elsewhere. */
export function Kbd({ keys, className }: { keys: string[]; className?: string }) {
  const mac = useIsMac();
  return (
    <kbd
      className={cn(
        "ml-1 inline-flex items-center gap-0.5 rounded border border-current/20 px-1 font-mono text-[10px] leading-4 opacity-80",
        className,
      )}
    >
      {keys.map((k) => (k === "mod" ? (mac ? "⌘" : "Ctrl+") : k)).join("")}
    </kbd>
  );
}
