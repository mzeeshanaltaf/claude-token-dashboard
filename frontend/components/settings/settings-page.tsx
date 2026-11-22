"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { EyeOffIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { ErrorState } from "@/components/error-state";
import { TableSkeleton } from "@/components/loading";
import { SectionCard } from "@/components/section-card";
import { Kbd } from "@/components/shell/kbd";
import { togglePrivacy, usePrivacy } from "@/components/shell/privacy";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, ApiError } from "@/lib/api";
import { useApiQuery } from "@/lib/queries";

import { PasswordForm } from "./password-form";
import { SyncStatusCard } from "./sync-status";
import { browserZone, TimezonePicker } from "./timezone-picker";

interface PlanInfo {
  label?: string;
  monthly?: number | null;
}
interface Rates {
  tier?: string;
  input: number;
  output: number;
  cache_read: number;
  cache_create_5m: number;
  cache_create_1h: number;
}

const rate = (v: number) => `$${v.toFixed(2)}`;

/**
 * Settings. Mounted client-only (it reads the browser's timezone), see
 * app/(dashboard)/settings/page.tsx.
 */
export function SettingsPage() {
  const settings = useApiQuery("/api/settings");
  const plan = useApiQuery("/api/plan");

  // The user menu links to /settings#password; scroll there once the form exists.
  useEffect(() => {
    if (window.location.hash === "#password") document.getElementById("password")?.scrollIntoView({ block: "start" });
  }, [settings.data]);

  if (settings.isError) return <ErrorState error={settings.error} onRetry={() => settings.refetch()} />;

  return (
    <div className="flex max-w-5xl flex-col gap-6">
      {settings.data ? <PlanAndZone plan={settings.data.plan} timezone={settings.data.timezone} plans={plan.data?.pricing?.plans as Record<string, PlanInfo> | undefined} /> : <TableSkeleton rows={3} />}
      <PricingTable models={plan.data?.pricing?.models as Record<string, Rates> | undefined} />
      <SyncStatusCard />
      <div id="password" className="scroll-mt-20">
        <PasswordForm />
      </div>
      <PrivacyCard />
    </div>
  );
}

function PlanAndZone({ plan, timezone, plans }: { plan: string | null; timezone: string; plans?: Record<string, PlanInfo> }) {
  const qc = useQueryClient();
  const [zone] = useState(browserZone);
  const save = useMutation({
    mutationFn: (body: { plan?: string; timezone?: string }) => api.post("/api/settings", body),
    onSuccess: (_d, body) => {
      if (body.timezone) {
        // Daily buckets move with the timezone: refetch everything.
        void qc.invalidateQueries();
        toast.success(`Timezone set to ${body.timezone}`);
      } else {
        void qc.invalidateQueries({ queryKey: ["/api/settings"] });
        void qc.invalidateQueries({ queryKey: ["/api/plan"] });
        toast.success("Plan saved");
      }
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.detail : "Couldn't save the setting."),
  });

  return (
    <SectionCard title="Plan & timezone" description="Saved on the server, so they apply on every device.">
      <FieldGroup className="grid gap-6 md:grid-cols-2">
        <Field>
          <FieldLabel htmlFor="plan">Plan</FieldLabel>
          <Select value={plan ?? ""} onValueChange={(v) => save.mutate({ plan: v })} disabled={!plans || save.isPending}>
            <SelectTrigger id="plan" className="w-full sm:w-72">
              <SelectValue placeholder="Choose a plan" />
            </SelectTrigger>
            <SelectContent>
              {Object.entries(plans ?? {}).map(([key, info]) => (
                <SelectItem key={key} value={key}>
                  {info.label ?? key}
                  {info.monthly ? ` · $${info.monthly}/mo` : ""}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <FieldDescription>
            Sets how cost is shown. API mode shows pay-per-token rates; a subscription adds what you actually pay each month next to the API-equivalent cost.
          </FieldDescription>
        </Field>
        <Field>
          <FieldLabel htmlFor="timezone">Timezone</FieldLabel>
          <TimezonePicker id="timezone" value={timezone} onChange={(z) => save.mutate({ timezone: z })} disabled={save.isPending} />
          <FieldDescription>
            Days in the charts start at midnight in this zone.
            {zone !== timezone && (
              <>
                {" "}
                <Button variant="link" size="xs" className="h-auto p-0 align-baseline" onClick={() => save.mutate({ timezone: zone })}>
                  Use this browser&apos;s zone ({zone})
                </Button>
              </>
            )}
          </FieldDescription>
        </Field>
      </FieldGroup>
    </SectionCard>
  );
}

function PricingTable({ models }: { models?: Record<string, Rates> }) {
  return (
    <SectionCard
      title="Pricing"
      description={
        <>
          USD per million tokens, from <code className="font-mono">backend/pricing.json</code> (read-only here; the backend picks up edits to the file without a restart).
        </>
      }
    >
      {!models ? (
        <TableSkeleton rows={6} />
      ) : (
        <div className="overflow-hidden rounded-lg border">
          <Table>
            <TableHeader className="bg-muted/40">
              <TableRow className="hover:bg-transparent">
                <TableHead className="text-xs">Model</TableHead>
                <TableHead className="text-right text-xs">Input</TableHead>
                <TableHead className="text-right text-xs">Output</TableHead>
                <TableHead className="text-right text-xs">Cache read</TableHead>
                <TableHead className="text-right text-xs">Cache 5m</TableHead>
                <TableHead className="text-right text-xs">Cache 1h</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {Object.entries(models).map(([id, r]) => (
                <TableRow key={id} className="font-mono text-xs tabular">
                  <TableCell>
                    <span className="flex items-center gap-2">
                      {id}
                      {r.tier && (
                        <Badge variant="outline" className="font-sans font-normal">
                          {r.tier}
                        </Badge>
                      )}
                    </span>
                  </TableCell>
                  <TableCell className="text-right">{rate(r.input)}</TableCell>
                  <TableCell className="text-right">{rate(r.output)}</TableCell>
                  <TableCell className="text-right">{rate(r.cache_read)}</TableCell>
                  <TableCell className="text-right">{rate(r.cache_create_5m)}</TableCell>
                  <TableCell className="text-right">{rate(r.cache_create_1h)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </SectionCard>
  );
}

function PrivacyCard() {
  const on = usePrivacy();
  return (
    <SectionCard title="Privacy blur" description="For screenshots and screen sharing.">
      <div className="flex flex-col gap-3 text-sm text-muted-foreground">
        <p>
          Press <Kbd keys={["mod", "B"]} /> anywhere (or the eye button in the top bar) to blur prompt text, project names, session titles and
          file paths. Numbers stay readable. The blur is per tab and isn&apos;t saved: it&apos;s off again after a reload.
        </p>
        <p className="flex flex-wrap items-center gap-3">
          <span className="blur-sensitive rounded-md border bg-muted/40 px-2 py-1 font-mono text-xs text-foreground">e:\Projects\secret-client\notes.md</span>
          <Button variant={on ? "secondary" : "outline"} size="sm" onClick={togglePrivacy} aria-pressed={on}>
            <EyeOffIcon data-icon="inline-start" />
            {on ? "Turn blur off" : "Try it"}
          </Button>
        </p>
      </div>
    </SectionCard>
  );
}
