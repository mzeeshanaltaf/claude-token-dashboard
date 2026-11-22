"use client";

import { EyeIcon, EyeOffIcon } from "lucide-react";
import { useEffect, useSyncExternalStore } from "react";

import { Button } from "@/components/ui/button";
import { Kbd } from "@/components/shell/kbd";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

/**
 * Privacy blur: `privacy-on` on <body> blurs every `.blur-sensitive` element
 * (see globals.css). The class is the single source of truth; components
 * read it through useSyncExternalStore (server snapshot: off).
 */
const CLASS = "privacy-on";
const EVENT = "lens:privacy";

function subscribe(onChange: () => void) {
  window.addEventListener(EVENT, onChange);
  return () => window.removeEventListener(EVENT, onChange);
}

const isOn = () => document.body.classList.contains(CLASS);

export function togglePrivacy() {
  document.body.classList.toggle(CLASS);
  window.dispatchEvent(new Event(EVENT));
}

export function usePrivacy(): boolean {
  return useSyncExternalStore(subscribe, isOn, () => false);
}

/** Ctrl/Cmd+B anywhere toggles the blur. */
export function PrivacyShortcut() {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && !e.altKey && !e.shiftKey && e.key.toLowerCase() === "b") {
        e.preventDefault();
        togglePrivacy();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  return null;
}

export function PrivacyToggle() {
  const on = usePrivacy();
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant={on ? "secondary" : "ghost"}
          size="icon-sm"
          onClick={togglePrivacy}
          aria-pressed={on}
          aria-label={on ? "Show sensitive text" : "Blur sensitive text"}
        >
          {on ? <EyeOffIcon /> : <EyeIcon />}
        </Button>
      </TooltipTrigger>
      <TooltipContent>
        {on ? "Privacy blur on" : "Blur sensitive text"} <Kbd keys={["mod", "B"]} />
      </TooltipContent>
    </Tooltip>
  );
}
