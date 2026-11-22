import { Badge } from "@/components/ui/badge";
import { familyColor } from "@/lib/chart-colors";
import { fmt } from "@/lib/format";
import { cn } from "@/lib/utils";

/**
 * "● Opus 4.7". The dot carries the family colour; the text stays in text
 * ink (dataviz rule: text never wears the series colour). The raw id is in
 * the title.
 */
export function ModelBadge({ model, className }: { model: string | null | undefined; className?: string }) {
  if (!model) return <span className="text-muted-foreground">—</span>;
  return (
    <Badge variant="outline" className={cn("gap-1.5 font-normal", className)} title={model}>
      <span aria-hidden className="size-2 shrink-0 rounded-full" style={{ background: familyColor(fmt.modelFamily(model)) }} />
      {fmt.modelLabel(model)}
    </Badge>
  );
}
