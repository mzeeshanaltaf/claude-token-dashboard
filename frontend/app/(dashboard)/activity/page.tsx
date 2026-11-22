import type { Metadata } from "next";

import { ActivityPlaceholder } from "@/components/placeholders";

export const metadata: Metadata = { title: "Activity" };

export default function ActivityPage() {
  return <ActivityPlaceholder />;
}
