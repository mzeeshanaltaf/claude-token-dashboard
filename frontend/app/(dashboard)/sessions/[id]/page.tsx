import type { Metadata } from "next";

import { SessionDetail } from "@/components/sessions/session-detail";

export const metadata: Metadata = { title: "Session" };

/**
 * The id is read on the client (useParams) under the dashboard layout's
 * <Suspense>, so the route keeps a static shell; data loads in the browser.
 */
export default function Page() {
  return <SessionDetail />;
}
