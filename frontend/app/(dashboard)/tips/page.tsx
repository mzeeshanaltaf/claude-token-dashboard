import type { Metadata } from "next";

import { TipsPage } from "@/components/tips/tips-page";

export const metadata: Metadata = { title: "Tips" };

export default function Page() {
  return <TipsPage />;
}
