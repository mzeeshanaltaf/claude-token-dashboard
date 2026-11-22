import type { Metadata } from "next";

import { PromptsPage } from "@/components/prompts/prompts-page";

export const metadata: Metadata = { title: "Prompts" };

export default function Page() {
  return <PromptsPage />;
}
