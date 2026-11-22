"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { api } from "@/lib/api";
import { useApiQuery } from "@/lib/queries";

interface PlanInfo {
  label?: string;
  monthly?: number;
}

/**
 * First-run plan picker (replaces the old `firstRun` in web/app.js). Shown
 * while `GET /api/settings` returns `plan: null`; saving sets the plan
 * server-side, so it never shows again on any device.
 */
export function PlanPicker() {
  const settings = useApiQuery("/api/settings");
  const needsPlan = settings.data?.plan === null;
  const plan = useApiQuery("/api/plan", { enabled: needsPlan });
  const plans = Object.entries((plan.data?.pricing?.plans ?? {}) as Record<string, PlanInfo>);
  const [choice, setChoice] = useState<string>("");
  const queryClient = useQueryClient();

  const save = useMutation({
    mutationFn: (value: string) => api.post("/api/settings", { plan: value }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/settings"] });
      queryClient.invalidateQueries({ queryKey: ["/api/plan"] });
      toast.success("Plan saved. You can change it in Settings.");
    },
    onError: () => toast.error("Couldn't save the plan. Try again."),
  });

  const selected = choice || plans[0]?.[0] || "";

  return (
    <Dialog open={needsPlan && !save.isSuccess}>
      <DialogContent
        showCloseButton={false}
        onEscapeKeyDown={(e) => e.preventDefault()}
        onInteractOutside={(e) => e.preventDefault()}
      >
        <DialogHeader>
          <DialogTitle>Welcome to Claude Lens</DialogTitle>
          <DialogDescription>
            Pick your Claude plan. It sets how costs are shown; you can change it later in Settings.
          </DialogDescription>
        </DialogHeader>
        <FieldGroup>
          <Field>
            <FieldLabel htmlFor="first-run-plan">Plan</FieldLabel>
            <Select value={selected} onValueChange={setChoice} disabled={plans.length === 0}>
              <SelectTrigger id="first-run-plan" className="w-full">
                <SelectValue placeholder={plan.isPending ? "Loading plans…" : "Choose a plan"} />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  {plans.map(([key, info]) => (
                    <SelectItem key={key} value={key}>
                      {info.label ?? key}
                      {info.monthly ? ` · $${info.monthly}/mo` : ""}
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
          </Field>
        </FieldGroup>
        <DialogFooter>
          <Button onClick={() => save.mutate(selected)} disabled={!selected || save.isPending}>
            {save.isPending && <Spinner data-icon="inline-start" />}
            Continue
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
