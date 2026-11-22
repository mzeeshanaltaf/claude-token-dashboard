import type { Metadata } from "next";

import { SessionsPlaceholder } from "@/components/placeholders";

export const metadata: Metadata = { title: "Sessions" };

export default function SessionsPage() {
  return <SessionsPlaceholder />;
}
