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

export function TopBar() {
  const pathname = usePathname();
  const item = navItemFor(pathname);

  return (
    <header className="sticky top-0 z-10 flex flex-wrap items-center gap-x-3 gap-y-2 border-b bg-background/80 px-4 py-2.5 backdrop-blur supports-backdrop-filter:bg-background/65 md:rounded-t-xl">
      <div className="flex min-w-0 items-center gap-2">
        <SidebarTrigger className="-ml-1" />
        <Separator orientation="vertical" className="data-[orientation=vertical]:h-4" />
        <h1 className="truncate text-base font-semibold tracking-tight">{item?.title ?? "Claude Lens"}</h1>
      </div>
      <div className="ml-auto flex flex-wrap items-center justify-end gap-2">
        {item?.ranged !== false && (
          <Suspense fallback={<Skeleton className="h-8 w-56" />}>
            <RangePicker />
          </Suspense>
        )}
        <SyncBadge />
        <CommandMenu />
        <PrivacyToggle />
        <UserMenu />
      </div>
    </header>
  );
}
