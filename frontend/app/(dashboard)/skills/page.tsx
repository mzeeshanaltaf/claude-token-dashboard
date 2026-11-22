import type { Metadata } from "next";

import { SkillsPage } from "@/components/skills/skills-page";

export const metadata: Metadata = { title: "Skills" };

export default function Page() {
  return <SkillsPage />;
}
