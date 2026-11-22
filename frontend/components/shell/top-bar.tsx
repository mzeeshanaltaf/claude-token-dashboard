"use client";

import { usePathname } from "next/navigation";
import { Suspense } from "react";

import { CommandMenu } from "@/components/shell/command-menu";
import { RangePicker, SyncBadge } from "@/components/shell/client-only";
import { PrivacyToggle } from "@/components/shell/privacy";
import { UserMenu } from "@/components/shell/user-menu";
import { Separator } from "@/components/ui/separator";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { Skeleton } from "@/components/ui/skeleton";
import { navItemFor } from "@/lib/nav";

/*
 * On dynamic routes (/sessions/[id], /projects/[slug]) the pathname is URL
 * data: only components inside <Suspense> may read it, so the title and the
 * range slot each sit in their own boundary (phase 05).
 */

function PageTitle() {
  const item = navItemFor(usePathname());
  return <>{item?.title ?? "Claude Lens"}</>;
}

function RangeSlot() {
  const item = navItemFor(usePathname());
  return item?.ranged !== false ? <RangePicker /> : null;
}

export function TopBar() {
  return (
    <header className="sticky top-0 z-10 flex flex-wrap items-center gap-x-3 gap-y-2 border-b bg-background/80 px-4 py-2.5 backdrop-blur supports-backdrop-filter:bg-background/65 md:rounded-t-xl">
      <div className="flex min-w-0 items-center gap-2">
        <SidebarTrigger className="-ml-1" />
        <Separator orientation="vertical" className="data-[orientation=vertical]:h-4" />
        <h1 className="truncate text-base font-semibold tracking-tight">
          <Suspense fallback={<Skeleton className="h-5 w-24" />}>
            <PageTitle />
          </Suspense>
        </h1>
      </div>
      <div className="ml-auto flex flex-wrap items-center justify-end gap-2">
        <Suspense fallback={<Skeleton className="h-8 w-56" />}>
          <RangeSlot />
        </Suspense>
        <SyncBadge />
        <CommandMenu />
        <PrivacyToggle />
        <UserMenu />
      </div>
    </header>
  );
}
