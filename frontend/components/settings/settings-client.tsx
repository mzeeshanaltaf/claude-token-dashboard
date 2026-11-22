"use client";

/**
 * Settings reads the browser's timezone (Intl) while rendering, so per the
 * hydration rule it never renders on the server.
 */
import dynamic from "next/dynamic";

import { PageSkeleton } from "@/components/loading";

export const SettingsClient = dynamic(() => import("./settings-page").then((m) => m.SettingsPage), {
  ssr: false,
  loading: () => <PageSkeleton />,
});
