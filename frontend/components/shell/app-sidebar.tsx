"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { LogoMark, Wordmark } from "@/components/logo";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from "@/components/ui/sidebar";
import { MAIN_NAV, SETTINGS_NAV, type NavItem } from "@/lib/nav";
import { RANGE_PARAM_NAMES } from "@/lib/range";

function NavLinks({ items, rangeQuery }: { items: NavItem[]; rangeQuery: string }) {
  const pathname = usePathname();
  return (
    <SidebarMenu>
      {items.map((item) => {
        const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
        const href = item.ranged && rangeQuery ? `${item.href}?${rangeQuery}` : item.href;
        return (
          <SidebarMenuItem key={item.href}>
            <SidebarMenuButton asChild isActive={active} tooltip={item.title}>
              <Link href={href}>
                <item.icon />
                <span>{item.title}</span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        );
      })}
    </SidebarMenu>
  );
}

/** Carries the URL's range across pages, so a shared link keeps its range. */
function RangedNavLinks({ items }: { items: NavItem[] }) {
  const params = useSearchParams();
  const keep = new URLSearchParams();
  for (const name of RANGE_PARAM_NAMES) {
    const v = params.get(name);
    if (v) keep.set(name, v);
  }
  return <NavLinks items={items} rangeQuery={keep.toString()} />;
}

export function AppSidebar() {
  return (
    <Sidebar collapsible="icon" variant="inset">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild>
              <Link href="/overview">
                <LogoMark className="size-8" />
                <div className="flex flex-col gap-0.5 leading-none">
                  <Wordmark className="text-sm" />
                  <span className="text-xs text-sidebar-foreground/60">Claude Code analytics</span>
                </div>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <Suspense fallback={<NavLinks items={MAIN_NAV} rangeQuery="" />}>
              <RangedNavLinks items={MAIN_NAV} />
            </Suspense>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter>
        <NavLinks items={[SETTINGS_NAV]} rangeQuery="" />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
