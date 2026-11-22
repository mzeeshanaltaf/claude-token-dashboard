"use client";

import { ModelBadge } from "@/components/model-badge";
import { TurnBreakdown } from "@/components/turn-breakdown";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import type { Schema } from "@/lib/api";
import { fmt } from "@/lib/format";

type Turn = Schema<"TurnRow">;

export interface ToolCall {
  name: string;
  [k: string]: unknown;
}

/** `tool_calls_json` is parsed JSON (a list of `{name, …}`); tolerate anything else. */
export function toolCallsOf(t: Turn): ToolCall[] {
  const v = t.tool_calls_json as unknown;
  if (!Array.isArray(v)) return [];
  return v.filter((x): x is ToolCall => !!x && typeof x === "object" && typeof (x as ToolCall).name === "string");
}

function toolText(calls: ToolCall[]): string {
  return calls
    .map(({ name, ...rest }) => {
      const input = "input" in rest ? rest.input : rest;
      return `${name}(\n${JSON.stringify(input ?? {}, null, 2)}\n)`;
    })
    .join("\n\n");
}

/** The full prompt or tool calls of one record (the old modal), plus its cost when it's an assistant turn. */
export function TurnDialog({ turn, onOpenChange }: { turn: Turn | null; onOpenChange: (open: boolean) => void }) {
  const calls = turn ? toolCallsOf(turn) : [];
  const content = turn?.prompt_text || toolText(calls);
  return (
    <Dialog open={!!turn} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] w-[calc(100vw-2rem)] max-w-3xl grid-rows-[auto_minmax(0,1fr)] sm:max-w-3xl">
        {turn && (
          <>
            <DialogHeader>
              <DialogTitle className="flex flex-wrap items-center gap-2">
                {turn.prompt_text ? "Prompt" : `Tool calls (${calls.length})`}
                {turn.model && <ModelBadge model={turn.model} />}
              </DialogTitle>
              <DialogDescription className="font-mono text-xs tabular">
                {fmt.ts(turn.timestamp)} · {turn.type}
                {turn.is_sidechain ? " · sidechain" : ""}
                {turn.agent_id ? ` · agent ${turn.agent_id}` : ""}
              </DialogDescription>
            </DialogHeader>
            <div className="flex min-h-0 flex-col gap-4 overflow-auto">
              <pre className="blur-sensitive rounded-lg border bg-muted/40 p-3 font-mono text-xs leading-relaxed wrap-break-word whitespace-pre-wrap">
                {content || "(empty)"}
              </pre>
              {turn.type === "assistant" && turn.estimated_cost_usd != null && <TurnBreakdown t={turn} />}
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
