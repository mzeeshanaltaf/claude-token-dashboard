import { Suspense } from "react";

import { PageSkeleton } from "@/components/loading";
import { AppSidebar } from "@/components/shell/app-sidebar";
import { PlanPicker } from "@/components/shell/client-only";
import { PrivacyShortcut } from "@/components/shell/privacy";
import { TopBar } from "@/components/shell/top-bar";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";

/**
 * The signed-in app shell. Pages under (dashboard)/ fetch their data in the
 * browser through TanStack Query, so the server renders the frame plus
 * skeletons; proxy.ts has already checked the session cookie.
 */
export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset className="lens-glow min-w-0">
        <TopBar />
        <main className="flex flex-1 flex-col gap-6 p-4 md:p-6">
          <Suspense fallback={<PageSkeleton />}>{children}</Suspense>
        </main>
      </SidebarInset>
      <PrivacyShortcut />
      <PlanPicker />
    </SidebarProvider>
  );
}
