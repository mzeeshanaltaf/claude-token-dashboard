import type { Metadata } from "next";

import { ProjectDetail } from "@/components/projects/project-detail";

export const metadata: Metadata = { title: "Project" };

/** The slug is read on the client (useParams) under the layout's <Suspense>. */
export default function Page() {
  return <ProjectDetail />;
}
