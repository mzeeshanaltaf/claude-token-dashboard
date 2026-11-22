"use client";

import { AlertCircleIcon } from "lucide-react";
import { useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { ApiError, api } from "@/lib/api";
import { loginErrorMessage } from "@/lib/login-messages";
import { safeNext } from "@/lib/safe-next";

interface Props {
  next: string;
  /** Error from the no-JS fallback's redirect (`/login?error=…`). */
  initialError?: string | null;
}

/**
 * Progressive enhancement: without React, the form posts natively to
 * /login/submit (which answers with a 303). Once hydrated, onSubmit takes
 * over and signs in with fetch through the API proxy.
 */
export function LoginForm({ next, initialError = null }: Props) {
  const [error, setError] = useState<string | null>(initialError);
  const [pending, setPending] = useState(false);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const username = String(form.get("username") ?? "").trim();
    const password = String(form.get("password") ?? "");
    if (!username || !password) {
      setError(loginErrorMessage("missing"));
      return;
    }
    setPending(true);
    setError(null);
    try {
      await api.post("/api/auth/login", { username, password }, { redirectOn401: false });
      // A full load, so proxy.ts sees the new cookie and nothing cached from
      // the signed-out state survives.
      window.location.replace(safeNext(next));
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 422)) {
        setError(loginErrorMessage("invalid"));
      } else if (err instanceof ApiError && err.status === 429) {
        setError(loginErrorMessage("locked", err.retryAfter));
      } else {
        setError(loginErrorMessage("server"));
      }
      setPending(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Sign in</CardTitle>
        <CardDescription>Use the admin account for this dashboard.</CardDescription>
      </CardHeader>
      <CardContent>
        <form action="/login/submit" method="post" onSubmit={handleSubmit} noValidate>
          <input type="hidden" name="next" value={next} />
          <FieldGroup>
            {error && (
              <Alert variant="destructive" aria-live="polite">
                <AlertCircleIcon />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            <Field data-invalid={error ? true : undefined}>
              <FieldLabel htmlFor="username">Username</FieldLabel>
              <Input
                id="username"
                name="username"
                autoComplete="username"
                autoCapitalize="none"
                spellCheck={false}
                required
                autoFocus
                aria-invalid={error ? true : undefined}
              />
            </Field>
            <Field data-invalid={error ? true : undefined}>
              <FieldLabel htmlFor="password">Password</FieldLabel>
              <Input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
                aria-invalid={error ? true : undefined}
              />
            </Field>
            <Button type="submit" disabled={pending} className="w-full">
              {pending && <Spinner data-icon="inline-start" />}
              {pending ? "Signing in…" : "Sign in"}
            </Button>
          </FieldGroup>
        </form>
      </CardContent>
    </Card>
  );
}
