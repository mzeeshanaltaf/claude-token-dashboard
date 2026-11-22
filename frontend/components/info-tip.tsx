"use client";

import { InfoIcon } from "lucide-react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { GLOSSARY, type GlossaryTerm } from "@/lib/glossary";
import { cn } from "@/lib/utils";

/** An (i) button with a definition: a glossary term or any text. */
export function InfoTip({
  term,
  children,
  label,
  className,
}: {
  term?: GlossaryTerm;
  children?: React.ReactNode;
  /** Accessible name: "About cache read". */
  label?: string;
  className?: string;
}) {
  const content = children ?? (term ? GLOSSARY[term] : null);
  if (!content) return null;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          className={cn("inline-flex shrink-0 text-muted-foreground hover:text-foreground", className)}
          aria-label={label ?? `About ${term ?? "this"}`}
        >
          <InfoIcon className="size-3.5" />
        </button>
      </TooltipTrigger>
      <TooltipContent className="max-w-72 text-pretty">{content}</TooltipContent>
    </Tooltip>
  );
}
