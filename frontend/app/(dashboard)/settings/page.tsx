import type { Metadata } from "next";

import { SettingsClient } from "@/components/settings/settings-client";

export const metadata: Metadata = { title: "Settings" };

export default function Page() {
  return <SettingsClient />;
}
