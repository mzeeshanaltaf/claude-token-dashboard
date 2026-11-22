"use client";

import { ArrowLeftIcon, CheckIcon, CopyIcon } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

/** Back link, a (sensitive) title and a meta line, for the detail pages. */
export function DetailHeader({
  backHref,
  backLabel,
  title,
  meta,
  actions,
}: {
  backHref: string;
  backLabel: string;
  title: React.ReactNode;
  meta?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-2">
      <Button asChild variant="ghost" size="xs" className="-ml-2 w-fit text-muted-foreground">
        <Link href={backHref}>
          <ArrowLeftIcon data-icon="inline-start" />
          {backLabel}
        </Link>
      </Button>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-1">
          <h2 className="blur-sensitive text-xl font-semibold tracking-tight text-balance">{title}</h2>
          {meta && <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">{meta}</div>}
        </div>
        {actions}
      </div>
    </div>
  );
}

/** A monospace id with a copy button: "a1b2c3d4…". */
export function CopyId({ id, chars = 8, label = "id" }: { id: string; chars?: number; label?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <span className="inline-flex items-center gap-1 font-mono">
      <span title={id}>{id.length > chars ? `${id.slice(0, chars)}…` : id}</span>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            className="rounded-sm p-0.5 hover:text-foreground"
            aria-label={`Copy ${label}`}
            onClick={() => {
              void navigator.clipboard?.writeText(id).then(() => {
                setCopied(true);
                setTimeout(() => setCopied(false), 1500);
              });
            }}
          >
            {copied ? <CheckIcon className="size-3" /> : <CopyIcon className="size-3" />}
          </button>
        </TooltipTrigger>
        <TooltipContent>{copied ? "Copied" : `Copy ${label}`}</TooltipContent>
      </Tooltip>
    </span>
  );
}
