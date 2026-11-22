import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

/** A titled card for a chart or table: title, optional description and actions. */
export function SectionCard({
  title,
  description,
  action,
  children,
  className,
  contentClassName,
  dim,
}: {
  title: React.ReactNode;
  description?: React.ReactNode;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  contentClassName?: string;
  /** Holds the previous render at reduced opacity while a refetch runs. */
  dim?: boolean;
}) {
  return (
    <Card className={cn("min-w-0", className)}>
      <CardHeader>
        <CardTitle className="flex items-center gap-1.5 text-sm font-semibold">{title}</CardTitle>
        {description && <CardDescription className="text-xs text-pretty">{description}</CardDescription>}
        {action && <CardAction>{action}</CardAction>}
      </CardHeader>
      <CardContent className={cn("min-w-0 transition-opacity", dim && "opacity-60", contentClassName)}>
        {children}
      </CardContent>
    </Card>
  );
}
