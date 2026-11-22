import type { Metadata } from "next";

import { ProjectsPlaceholder } from "@/components/placeholders";

export const metadata: Metadata = { title: "Projects" };

export default function ProjectsPage() {
  return <ProjectsPlaceholder />;
}
