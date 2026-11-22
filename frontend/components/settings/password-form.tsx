"use client";

import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { SectionCard } from "@/components/section-card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { api, ApiError, loginUrl } from "@/lib/api";

const MIN = 8;

function message(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 400) return "The current password is wrong.";
    if (e.status === 429) {
      const mins = e.retryAfter ? Math.max(1, Math.ceil(e.retryAfter / 60)) : null;
      return `Too many failed attempts. Try again in ${mins ? `${mins} minute${mins === 1 ? "" : "s"}` : "a few minutes"}.`;
    }
    if (e.status === 422) return e.detail;
  }
  return "Couldn't change the password. Try again.";
}

/**
 * Current / new / confirm. On success the backend revokes every session of
 * the user (this one too), so we sign out and go to the login page.
 */
export function PasswordForm() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [touched, setTouched] = useState(false);

  const change = useMutation({
    mutationFn: () => api.post("/api/auth/password", { current, new: next }, { redirectOn401: false }),
    onSuccess: async () => {
      await new Promise((r) => setTimeout(r, 1500));
      await fetch("/api/auth/logout", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: "{}",
        credentials: "same-origin",
      }).catch(() => undefined);
      // A full page load on purpose: drop every cached query with the session.
      window.location.assign(loginUrl());
    },
  });

  const tooShort = next.length > 0 && next.length < MIN;
  const mismatch = confirm.length > 0 && next !== confirm;
  const invalid = !current || next.length < MIN || next !== confirm;

  return (
    <SectionCard title="Change password" description="You'll be signed out everywhere, including here, and asked to sign in again.">
      <form
        id="password-form"
        className="flex max-w-md flex-col gap-4"
        onSubmit={(e) => {
          e.preventDefault();
          setTouched(true);
          if (!invalid) change.mutate();
        }}
      >
        <FieldGroup>
          <Field>
            <FieldLabel htmlFor="pw-current">Current password</FieldLabel>
            <Input id="pw-current" type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} />
            {touched && !current && <FieldError>Enter your current password.</FieldError>}
          </Field>
          <Field data-invalid={tooShort || undefined}>
            <FieldLabel htmlFor="pw-new">New password</FieldLabel>
            <Input
              id="pw-new"
              type="password"
              autoComplete="new-password"
              value={next}
              onChange={(e) => setNext(e.target.value)}
              aria-invalid={tooShort || undefined}
            />
            {tooShort ? <FieldError>At least {MIN} characters.</FieldError> : <FieldDescription>At least {MIN} characters.</FieldDescription>}
          </Field>
          <Field data-invalid={mismatch || undefined}>
            <FieldLabel htmlFor="pw-confirm">Confirm new password</FieldLabel>
            <Input
              id="pw-confirm"
              type="password"
              autoComplete="new-password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              aria-invalid={mismatch || undefined}
            />
            {mismatch && <FieldError>The passwords don&apos;t match.</FieldError>}
          </Field>
        </FieldGroup>
        {change.isError && (
          <Alert variant="destructive">
            <AlertDescription>{message(change.error)}</AlertDescription>
          </Alert>
        )}
        {change.isSuccess && (
          <Alert>
            <AlertDescription>Password changed. Signing you out…</AlertDescription>
          </Alert>
        )}
        <Button type="submit" className="w-fit" disabled={change.isPending || change.isSuccess}>
          {change.isPending && <Spinner data-icon="inline-start" />}
          Change password
        </Button>
      </form>
    </SectionCard>
  );
}
