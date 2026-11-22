import type { Metadata } from "next";

import { SessionsPage } from "@/components/sessions/sessions-page";

export const metadata: Metadata = { title: "Sessions" };

export default function Page() {
  return <SessionsPage />;
}
