"use client";

import { AlertTriangleIcon, RotateCwIcon } from "lucide-react";

import { Alert, AlertAction, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";

function describe(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 502) return "The backend isn't reachable. Is it running?";
    return `${error.detail} (HTTP ${error.status})`;
  }
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}

export function ErrorState({
  title = "Couldn't load this data",
  error,
  onRetry,
  className,
}: {
  title?: string;
  error?: unknown;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <Alert variant="destructive" className={className}>
      <AlertTriangleIcon />
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription>{describe(error)}</AlertDescription>
      {onRetry && (
        <AlertAction>
          <Button variant="outline" size="sm" onClick={onRetry}>
            <RotateCwIcon data-icon="inline-start" />
            Retry
          </Button>
        </AlertAction>
      )}
    </Alert>
  );
}
