"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  BotIcon,
  DatabaseZapIcon,
  FileStackIcon,
  LightbulbIcon,
  PackageOpenIcon,
  ScaleIcon,
  SparklesIcon,
  SquareTerminalIcon,
  XIcon,
  type LucideIcon,
} from "lucide-react";
import { toast } from "sonner";

import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { TableSkeleton } from "@/components/loading";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { api, type Schema } from "@/lib/api";
import { queryKeys, useApiQuery } from "@/lib/queries";

type Tip = Schema<"Tip">;

const CATEGORIES: Record<string, { icon: LucideIcon; label: string }> = {
  cache: { icon: DatabaseZapIcon, label: "Cache" },
  "repeat-file": { icon: FileStackIcon, label: "Repeated reads" },
  "repeat-bash": { icon: SquareTerminalIcon, label: "Repeated commands" },
  "right-size": { icon: ScaleIcon, label: "Right-size model" },
  "tool-bloat": { icon: PackageOpenIcon, label: "Tool bloat" },
  "subagent-outlier": { icon: BotIcon, label: "Subagent outlier" },
};

const KEY = queryKeys.plain("/api/tips");

/** Tip text uses `backticks` for commands and paths: render them as code. */
function withCode(text: string) {
  return text.split(/(`[^`]+`)/g).map((part, i) =>
    part.startsWith("`") && part.endsWith("`") && part.length > 2 ? (
      <code key={i} className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]">
        {part.slice(1, -1)}
      </code>
    ) : (
      part
    ),
  );
}

export function TipsPage() {
  const qc = useQueryClient();
  const tips = useApiQuery("/api/tips");

  const restore = useMutation({
    mutationFn: (key: string) => api.post("/api/tips/restore", { key }),
    onSettled: () => qc.invalidateQueries({ queryKey: KEY }),
    onError: () => toast.error("Couldn't restore the tip."),
  });

  const dismiss = useMutation({
    mutationFn: (tip: Tip) => api.post("/api/tips/dismiss", { key: tip.key }),
    // Optimistic: the card goes at once; it comes back if the request fails.
    onMutate: async (tip) => {
      await qc.cancelQueries({ queryKey: KEY });
      const before = qc.getQueryData<Tip[]>(KEY);
      qc.setQueryData<Tip[]>(KEY, (cur) => cur?.filter((t) => t.key !== tip.key));
      return { before };
    },
    onError: (_e, _tip, ctx) => {
      if (ctx?.before) qc.setQueryData(KEY, ctx.before);
      toast.error("Couldn't dismiss the tip.");
    },
    onSuccess: (_d, tip) => {
      toast("Tip dismissed", {
        description: "It stays hidden for 14 days.",
        action: {
          label: "Undo",
          onClick: () => {
            qc.setQueryData<Tip[]>(KEY, (cur) => (cur ? [tip, ...cur.filter((t) => t.key !== tip.key)] : [tip]));
            restore.mutate(tip.key);
          },
        },
      });
    },
  });

  if (tips.isError) return <ErrorState error={tips.error} onRetry={() => tips.refetch()} />;
  if (!tips.data) return <TableSkeleton rows={4} />;

  return (
    <div className="flex max-w-4xl flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        Rule-based pattern detection over the last 7 days. Dismissed tips re-appear after 14 days.
      </p>
      {tips.data.length === 0 ? (
        <EmptyState
          icon={SparklesIcon}
          title="No suggestions right now"
          description="Claude Lens looks for costly patterns in the last 7 days of activity. Check back after more sessions."
        />
      ) : (
        tips.data.map((tip) => {
          const cat = CATEGORIES[tip.category] ?? { icon: LightbulbIcon, label: tip.category };
          const Icon = cat.icon;
          return (
            <Card key={tip.key} size="sm">
              <CardContent className="flex items-start gap-3">
                <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary" aria-hidden>
                  <Icon className="size-4.5" />
                </span>
                <div className="flex min-w-0 flex-1 flex-col gap-1.5">
                  <Badge variant="outline" className="font-normal">
                    {cat.label}
                  </Badge>
                  <h3 className="blur-sensitive text-sm leading-snug font-semibold wrap-break-word">{withCode(tip.title)}</h3>
                  <p className="blur-sensitive text-sm text-pretty wrap-break-word text-muted-foreground">{withCode(tip.body)}</p>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  className="shrink-0"
                  onClick={() => dismiss.mutate(tip)}
                  aria-label={`Dismiss: ${tip.title}`}
                >
                  <XIcon data-icon="inline-start" />
                  <span className="hidden sm:inline">Dismiss</span>
                </Button>
              </CardContent>
            </Card>
          );
        })
      )}
    </div>
  );
}
