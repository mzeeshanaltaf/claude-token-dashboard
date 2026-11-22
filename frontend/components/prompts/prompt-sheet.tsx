"use client";

import { ArrowRightIcon } from "lucide-react";
import Link from "next/link";

import { ModelBadge } from "@/components/model-badge";
import { TurnBreakdown } from "@/components/turn-breakdown";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { useRangedHref } from "@/hooks/use-url-state";
import type { Schema } from "@/lib/api";
import { fmt } from "@/lib/format";

/** The full prompt, its token / cost breakdown and a link to its session. */
export function PromptSheet({
  prompt,
  projectName,
  onOpenChange,
}: {
  prompt: Schema<"PromptRow"> | null;
  projectName: string;
  onOpenChange: (open: boolean) => void;
}) {
  const href = useRangedHref();
  return (
    <Sheet open={!!prompt} onOpenChange={onOpenChange}>
      <SheetContent className="w-full gap-0 sm:max-w-xl">
        {prompt && (
          <>
            <SheetHeader className="border-b">
              <SheetTitle className="flex flex-wrap items-center gap-2">
                Prompt
                <ModelBadge model={prompt.model} />
              </SheetTitle>
              <SheetDescription className="flex flex-wrap gap-x-3 gap-y-1 font-mono text-xs tabular">
                <span>{fmt.ts(prompt.timestamp)}</span>
                <span className="blur-sensitive">{projectName}</span>
                <span>{fmt.int(prompt.prompt_chars)} chars</span>
              </SheetDescription>
            </SheetHeader>
            <ScrollArea className="min-h-0 flex-1">
              <div className="flex flex-col gap-5 p-4">
                <pre className="blur-sensitive max-h-[45vh] overflow-auto rounded-lg border bg-muted/40 p-3 font-mono text-xs leading-relaxed wrap-break-word whitespace-pre-wrap">
                  {prompt.prompt_text || "(empty)"}
                </pre>
                <section>
                  <h3 className="mb-1 text-sm font-semibold">Answering turn</h3>
                  <TurnBreakdown t={prompt} />
                </section>
                <section className="flex flex-col gap-1">
                  <h3 className="text-sm font-semibold">Session</h3>
                  <p className="blur-sensitive text-sm">{prompt.title || <span className="text-muted-foreground">Untitled session</span>}</p>
                  <p className="font-mono text-xs text-muted-foreground">{prompt.session_id}</p>
                </section>
              </div>
            </ScrollArea>
            <SheetFooter className="border-t">
              <Button asChild>
                <Link href={href(`/sessions/${encodeURIComponent(prompt.session_id)}`)}>
                  Open session
                  <ArrowRightIcon data-icon="inline-end" />
                </Link>
              </Button>
            </SheetFooter>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
